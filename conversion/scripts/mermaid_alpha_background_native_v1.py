"""One editable rectangle per real CSS background layer, with source alpha/order."""
import math
import xml.etree.ElementTree as ET

from mermaid_native_v3 import build as previous
from mermaid_native_v2 import MOVE_SCRIPT
from svg_convert_v2 import color, num
from svg_convert_v3 import unpack


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def check_layers(xml, layers):
    cells = {c.get('id'): c for c in ET.fromstring(xml).iter('mxCell')}
    seen = set()
    orders = set()
    parents = {}
    for layer in layers:
        identifier = layer['background']
        require(identifier not in seen, 'duplicate_source_background_layer')
        seen.add(identifier)
        cell = cells.get(identifier)
        require(cell is not None and cell.get('vertex') == '1', 'source_background_layer_missing')
        st = unpack(cell.get('style'))
        alpha = float(layer['source_alpha'])
        require(math.isfinite(alpha) and 0 <= alpha <= 1, 'source_background_alpha_invalid')
        require(st.get('fillColor') == layer['source_css_color'] and
                abs(float(st.get('fillOpacity', 100)) - alpha * 100) < 1e-8 and
                float(st.get('opacity', 100)) == 100 and st.get('strokeColor') == 'none',
                'source_background_alpha_or_color_changed')
        require(cell.get('visible', '1') != '0' and cell.get('sourceCssBackground') == layer['source_css'] and
                abs(float(cell.get('sourceCssBackgroundAlpha', '-1')) - alpha) < 1e-8 and
                cell.get('sourceCssBackgroundOrder') == str(layer['source_order']),
                'source_background_identity_or_order_changed')
        require(cell.get('parent') == layer['native_parent'], 'source_background_native_owner_changed')
        ordinal = layer['source_order']
        require(isinstance(ordinal, int) and ordinal > 0 and ordinal not in orders,
                'source_background_source_order_not_unique')
        orders.add(ordinal)
        parents.setdefault(cell.get('parent'), []).append((ordinal, identifier))
    document_order = {identifier: index for index, identifier in enumerate(cells)}
    for members in parents.values():
        expected = [identifier for _, identifier in sorted(members)]
        require(expected == sorted(expected, key=document_order.get), 'source_background_paint_order_changed')
    return {'ok': True, 'source_background_layers': len(layers), 'alpha_layers_preserved': True}


def build(dom, w, h, metadata):
    xml, stats, processed = previous(dom, w, h, metadata)
    root = ET.fromstring(xml)
    cells = {c.get('id'): c for c in root.iter('mxCell')}
    layers = []
    by_layer = {}
    for obj in processed['objects']:
        if not obj.get('sourceHtmlBackgroundOwner'):
            continue
        require(obj.get('sourceHtmlBackgroundCss') is not None and
                obj.get('sourceHtmlBackgroundAlpha') is not None and
                obj.get('sourceHtmlBackgroundOrder') is not None, 'source_background_alpha_identity_missing')
        cell = cells[obj['id']]
        alpha = float(obj['sourceHtmlBackgroundAlpha'])
        require(abs(obj['style']['fillOpacity'] - alpha) < 1e-8, 'source_background_extractor_alpha_changed')
        layer = {'background': obj['id'], 'source_owner': obj['sourceHtmlBackgroundOwner'],
                 'source_css': obj['sourceHtmlBackgroundCss'], 'source_css_color': color(obj['style']['fill']),
                 'source_alpha': alpha, 'source_order': obj['sourceHtmlBackgroundOrder'],
                 'source_bbox': obj['bbox'], 'native_parent': cell.get('parent')}
        cell.set('sourceCssBackground', layer['source_css'])
        cell.set('sourceCssBackgroundAlpha', num(alpha))
        cell.set('sourceCssBackgroundOrder', str(layer['source_order']))
        layers.append(layer)
        by_layer[obj['id']] = layer
    for binding in stats['native_html_label_backgrounds']:
        layer = by_layer[binding['background']]
        binding.update(source_alpha=layer['source_alpha'], source_css=layer['source_css'],
                       source_order=layer['source_order'], native_parent=layer['native_parent'])
    stats['source_html_background_layers'] = layers
    stats['converter_version'] = 'mermaid_individual_css_alpha_background_layers_v1'
    xml = ET.tostring(root, encoding='unicode')
    check_layers(xml, layers)
    check_backgrounds(xml, stats['native_html_label_backgrounds'])
    return xml, stats, processed


def check_backgrounds(xml, bindings):
    check_layers(xml, bindings)
    cells = {c.get('id'): c for c in ET.fromstring(xml).iter('mxCell')}
    for binding in bindings:
        bg, label, edge = (cells.get(binding[k]) for k in ('background', 'label', 'edge'))
        require(bg is not None and label is not None and edge is not None and edge.get('edge') == '1',
                'source_background_edge_or_label_missing')
        require(bg.get('parent') == label.get('parent') == edge.get('id') and
                bg.find('mxGeometry').get('relative') == '1', 'source_background_edge_binding_changed')
    return {'ok': True, 'source_backgrounds': len(bindings), 'native_edge_owned_backgrounds': len(bindings)}


def repair_paint_order(browser, xml, bindings):
    from native_label_paint_order import inspect_order, reorder
    check_backgrounds(xml, bindings)
    order = inspect_order(browser, xml, bindings)
    candidate = reorder(xml, order)
    check_backgrounds(candidate, bindings)
    return candidate, order
