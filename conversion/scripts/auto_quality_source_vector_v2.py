"""Fresh, revision-bound source coverage profiles for automatic batch quality checks.

This module proves source object/text/terminal/asset coverage, not original-image
fidelity. The caller must additionally perform fresh native rendering, font,
canvas, local image and editability gates before accepting a record.
"""
import base64
import collections
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import math
import mimetypes
import re
import statistics
from pathlib import Path
import urllib.parse
import xml.etree.ElementTree as E

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
CHROME = '/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
sha = lambda b: hashlib.sha256(b).hexdigest()


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')


def _plain(value):
    if any(t in (value or '').lower() for t in ('<span', '<div', '<font', '<b>', '<i>', '<br')):
        parser = _Text()
        parser.feed(value)
        return ''.join(parser.parts)
    return html.unescape(value or '')


def _style(cell):
    return dict(x.split('=', 1) for x in cell.get('style', '').split(';') if '=' in x)


def _read_clean(relative, digest=None):
    path = (R / relative).resolve()
    assert path.is_relative_to((R / 'clean').resolve()), 'source resource outside clean: ' + str(relative)
    blob = path.read_bytes()
    if digest is not None:
        assert sha(blob) == digest, 'source resource hash mismatch: ' + str(relative)
    return blob


def _identity(record, xml):
    assert sha(xml.encode()) == record['code_sha256'], 'candidate XML revision mismatch'
    assert record.get('original_source_code'), 'missing preserved source code'
    code = _read_clean(record['original_source_code'], record['source_code_sha256'])
    if record.get('original_reference'):
        _read_clean(record['original_reference'], record['source_image_sha256'])
    source = record.get('source_record') or {}
    for a, b in [('code_sha256', 'source_code_sha256'), ('image_sha256', 'source_image_sha256')]:
        if a in source:
            assert source[a] == record[b], 'source record identity mismatch: ' + a
    return code


def _capture(record, code, width, height, kind):
    """Extract actual current source DOM offline. Never reads stored candidate DOM flags."""
    from playwright.sync_api import sync_playwright
    blocked, served = [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=['--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=False, service_workers='block')
        try:
            page = context.new_page()
            page.set_default_timeout(45000)
            if kind == 'html':
                asset_root = record.get('original_asset_root')
                assets = (R / asset_root).resolve() if asset_root else None
                if assets is not None:
                    assert assets.is_relative_to((R / 'clean').resolve()), 'HTML assets outside clean'
                def route(req):
                    url = urllib.parse.urlparse(req.request.url)
                    if url.hostname != 'source.invalid':
                        blocked.append(req.request.url); req.abort(); return
                    name = urllib.parse.unquote(url.path.lstrip('/'))
                    if name == 'index.html':
                        req.fulfill(body=code, content_type='text/html'); return
                    target = (assets / name).resolve() if assets else None
                    if target is None or not target.is_relative_to(assets) or not target.is_file():
                        blocked.append(req.request.url); req.abort(); return
                    blob = target.read_bytes(); served[req.request.url] = blob
                    req.fulfill(body=blob, content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
                context.route('**/*', route)
                page.goto('http://source.invalid/index.html', wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                from html_range_extractor_v2 import source_js as range_source_js
                source_js = range_source_js(W / 'scripts/html_dom_clip.js')
                dom = page.evaluate(source_js)
                cdp = context.new_cdp_session(page)
                try:
                    snapshot = cdp.send('DOMSnapshot.captureSnapshot', {'computedStyles':[], 'includePaintOrder':True})
                    dom['_source_paint_order'] = _snapshot_paint_orders(dom, snapshot)
                finally:
                    cdp.detach()
            else:
                # SVG assets must already be inline in these supported direct-source profiles.
                # Unresolved external images/styles/fonts are an explicit failure, not silently omitted.
                context.route('**/*', lambda r: (blocked.append(r.request.url), r.abort()))
                page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>' + code.decode())
                if kind == 'plantuml':
                    variant = record.get('variant_selection', {}).get('chosen')
                    assert variant in ('scaled', 'natural'), 'missing pinned source layout variant'
                    page.evaluate('''({w,h,variant})=>{const s=document.querySelector('svg');if(!s)throw Error('missing source SVG');if(variant==='scaled'){s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}else{const bg=s.querySelector(':scope > g > rect');if(bg&&+bg.getAttribute('x')===0&&+bg.getAttribute('y')===0){bg.setAttribute('width',w);bg.setAttribute('height',h);}}}''', {'w':width,'h':height,'variant':variant})
                    from plantuml_fonts import resolve as resolve_fonts
                    from plantuml_runtime import JAR, JAR_SHA
                    assert sha(JAR.read_bytes()) == JAR_SHA, 'pinned PlantUML runtime modified'
                    assert record.get('plantuml_runtime',{}).get('jar_sha256') == JAR_SHA, 'source PlantUML runtime identity differs'
                    work = W / 'auto_quality_source_vector' / record['id'] / record['code_sha256']
                    work.mkdir(parents=True, exist_ok=True)
                    fonts = resolve_fonts(page, work)
                    (work/'source_font_resolution.json').write_text(json.dumps(fonts,indent=2)+'\n')
                    page.evaluate('document.fonts.ready')
                    metadata = page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text())
                    dom = page.evaluate((W/'scripts/svg_dom_plantuml_v4.js').read_text())
                    dom['_plantuml_metadata'] = metadata
                    dom['_plantuml_fonts'] = fonts
                else:
                    page.evaluate('''([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('missing source SVG');if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''', [width, height])
                    page.evaluate('document.fonts.ready')
                    dom = page.evaluate((W / 'scripts/svg_dom_v6.js').read_text())
            assert not blocked, 'blocked source resources: ' + repr(blocked[:8])
            return dom, served
        finally:
            context.close(); browser.close()


def _snapshot_paint_orders(dom, snapshot):
    """Map Chrome's actual stacking-context paint order to fresh source objects."""
    doc = snapshot['documents'][0]
    nodes, layout, strings = doc['nodes'], doc['layout'], snapshot['strings']
    pseudo = set(nodes.get('pseudoType', {}).get('index', []))
    element_nodes = [i for i, t in enumerate(nodes['nodeType']) if t == 1 and i not in pseudo]
    assert len(element_nodes) == dom['qaElementCount'], 'source DOM snapshot element mapping is incomplete'
    order_map = collections.defaultdict(list)
    for node, order in zip(layout['nodeIndex'], layout['paintOrders']):
        order_map[node].append(order)
    result = {}
    for obj in dom['objects']:
        index = obj['qaOwner']
        assert 0 <= index < len(element_nodes), 'source DOM object owner is missing'
        node = element_nodes[index]
        assert strings[nodes['nodeName'][node]].upper() == obj['qaOwnerTag'].upper(), 'source DOM paint owner identity changed'
        orders = order_map.get(node, [])
        if obj['type'] == 'text':
            text_orders = []
            for item, values in order_map.items():
                if nodes['nodeType'][item] == 3 and nodes['parentIndex'][item] == node:
                    text_orders.extend(values)
            if text_orders:
                orders = text_orders
        assert orders and len(set(orders)) == 1, 'source paint order is missing/ambiguous for object ' + str(obj['id'])
        result[str(obj['id'])] = orders[0]
    return result


def _html_paint_order(dom, xml):
    """Nonzero CSS z-index is safe only if overlapping objects keep real paint order."""
    orders = dom.get('_source_paint_order')
    if orders is None:
        return {'ok':False,'errors':[{'reason':'source_browser_paint_order_not_captured'}]}
    native_order = {c.get('id'):i for i,c in enumerate(E.fromstring(xml).iter('mxCell'))}
    errors = []
    checked = 0
    def painted_rects(obj):
        x,y,w,h=[obj[k] for k in ('x','y','w','h')]
        if obj['type']=='rect' and not obj['fill']['opacity']:
            border=obj['bw']
            return [(x,y,w,border),(x,y+h-border,w,border),(x,y,border,h),(x+w-border,y,border,h)] if border else []
        return [(x,y,w,h)]
    def overlap(a,b):
        return any(min(x+w,xx+ww)>max(x,xx)+.01 and min(y+h,yy+hh)>max(y,yy)+.01 for x,y,w,h in painted_rects(a) for xx,yy,ww,hh in painted_rects(b))
    objects=dom['objects']
    source_order={obj['id']:(obj.get('qaPaintEvent',i),obj.get('qaTextStart',0)) for i,obj in enumerate(objects)}
    active=[]
    for a in sorted(objects,key=lambda obj:obj['y']):
        active=[b for b in active if b['y']+b['h']>a['y']+.01]
        for b in active:
            if not overlap(a,b):
                continue
            ao,bo=orders[str(a['id'])],orders[str(b['id'])]
            # Inside a shared actual painting context, source DOM object order
            # still matters (background before text, earlier siblings below later).
            expected=(ao-bo) if ao!=bo else (1 if source_order[a['id']]>source_order[b['id']] else -1 if source_order[a['id']]<source_order[b['id']] else 0)
            ac,bc=str(a['id']+1),str(b['id']+1)
            if ac not in native_order or bc not in native_order:
                continue  # The independent object coverage gate reports this.
            checked+=1
            if expected*(native_order[ac]-native_order[bc])<0:
                errors.append({'reason':'overlapping_source_css_paint_order_changed','cells':[ac,bc]})
        active.append(a)
    return {'ok':not errors,'errors':errors,'overlapping_different_context_pairs_checked':checked,'method':'actual_Chromium_DOMSnapshot_layout_paintOrders'}


def _world_box(cell, cells, seen=None):
    seen = set(seen or ())
    key = cell.get('id')
    assert key not in seen, 'native parent cycle'
    seen.add(key)
    geo = cell.find('mxGeometry')
    assert geo is not None, 'missing native geometry: ' + str(key)
    x, y, width, height = [float(geo.get(k, 0)) for k in ('x', 'y', 'width', 'height')]
    parent = cells.get(cell.get('parent'))
    if parent is not None and parent.get('edge') == '1':
        assert geo.get('relative') == '1', 'edge child uses unsupported absolute label geometry'
        points = _edge_points(parent, cells, seen)
        segments = [math.dist(a, b) for a, b in zip(points, points[1:])]
        along = max(0, min(1, (x+1)/2))*sum(segments)
        point = points[-1]
        for a, b, length in zip(points, points[1:], segments):
            if along <= length and length:
                fraction = along/length
                # mxGraph's relative y is perpendicular distance along the edge.
                point = (a[0]+fraction*(b[0]-a[0])+y*(b[1]-a[1])/length,
                         a[1]+fraction*(b[1]-a[1])-y*(b[0]-a[0])/length)
                break
            along -= length
        offset = geo.find("mxPoint[@as='offset']")
        return (point[0] + (float(offset.get('x', 0)) if offset is not None else 0),
                point[1] + (float(offset.get('y', 0)) if offset is not None else 0), width, height)
    if parent is not None and parent.get('vertex') == '1':
        assert geo.get('relative') != '1', 'relative vertex requires a separate source geometry profile'
        px, py, _, _ = _world_box(parent, cells, seen)
        x += px; y += py
    return x, y, width, height


def _edge_points(edge, cells, seen=None):
    style = _style(edge)
    points = []
    for key, prefix in [('source', 'exit'), ('target', 'entry')]:
        terminal = cells.get(edge.get(key))
        assert terminal is not None, 'missing bound terminal'
        x, y, width, height = _world_box(terminal, cells, seen)
        assert prefix+'X' in style and prefix+'Y' in style, 'source geometry requires explicit fixed connection constraints'
        points.append((x+float(style[prefix+'X'])*width, y+float(style[prefix+'Y'])*height))
    geo = edge.find('mxGeometry')
    assert geo is not None, 'missing native edge geometry'
    bends = [(float(p.get('x')), float(p.get('y'))) for p in geo.findall("Array[@as='points']/mxPoint")]
    return [points[0], *bends, points[1]]


def _near(actual, expected, tolerance=.03):
    return abs(float(actual)-float(expected)) <= tolerance


def _paint_coverage(dom, xml, kind='svg'):
    """Verify native shape payloads, paint, and source geometry, not merely IDs.

    A single shared translation is allowed: it preserves relative layout and is
    separately constrained by original-reference image checks in the caller.
    """
    from svg_convert_v2 import stencil, style as svg_style, color
    cells = {c.get('id'): c for c in E.fromstring(xml).iter('mxCell')}
    errors, shapes, pending_text, translations, connectors = [], [], [], [], []
    for obj in dom['objects']:
        key = str(obj['id']+1) if kind == 'html' else obj['id']
        cell = cells.get(key)
        if cell is None:
            # Native source-proven arrow markers replace these precise polygons.
            if kind != 'html' and obj.get('edge') and obj.get('tag') == 'polygon':
                continue
            errors.append({'reason': 'source_paint_object_missing', 'cell': key}); continue
        native_style = _style(cell)
        try:
            actual_box = _world_box(cell, cells)
            if kind == 'html':
                expected_box = tuple(float(obj[k]) for k in ('x', 'y', 'w', 'h'))
                if obj['type'] == 'rect':
                    expected_style = {'fillColor': obj['fill']['color'] if obj['fill']['opacity'] else 'none',
                        'fillOpacity': obj['fill']['opacity']*100,
                        'strokeColor': obj['stroke']['color'] if obj['bw'] else 'none', 'strokeWidth': obj['bw'],
                        'opacity': obj['opacity']*100}
                    if native_style.get('shape', 'rectangle') != 'rectangle':
                        errors.append({'reason':'poster_rectangle_shape_changed','cell':key})
                    if obj['radius']:
                        expected_style.update(rounded='1', absoluteArcSize='1', arcSize=obj['radius']*2)
                    elif native_style.get('rounded', '0') != '0':
                        errors.append({'reason':'poster_rectangle_rounding_changed','cell':key})
                elif obj['type'] == 'image':
                    expected_style = {'shape':'image','opacity':obj['opacity']*100}
                elif obj['type'] == 'text':
                    expected_style = {'shape':'text','fontSize':obj['fontSize'],'fontColor':obj['color']['color'],'opacity':obj['opacity']*obj['color'].get('opacity',1)*100}
                else:
                    raise AssertionError('unsupported source paint object')
            elif obj['type'] == 'shape' and cell.get('edge') == '1':
                expected_style = svg_style(obj)
                # Connector source geometry is fully represented as native points.
                source_points = obj.get('sampledPoints')
                native_points = _edge_points(cell, cells)
                assert source_points and len(source_points)>=2, 'source connector geometry missing'
                if len(native_points)==len(source_points) and len(native_points)>2:
                    pairs=[(a[0]-b[0],a[1]-b[1]) for a,b in zip(native_points[1:-1],source_points[1:-1])]
                    translations.append((statistics.median(p[0] for p in pairs),statistics.median(p[1] for p in pairs)))
                connectors.append((obj,native_points,source_points))
                # Source arrow attachment can move the endpoint by its original marker length.
                # Correct terminals/marker side are checked independently by graph coverage.
                shapes.append({'cell':key,'connector_waypoints':len(native_points)})
                actual_box = expected_box = None
            elif obj['type'] == 'shape':
                expected_style = svg_style(obj)
                if obj.get('filterDefinition'):
                    from plantuml_native_v4 import shadow_filter
                    shadow = shadow_filter(obj['filterDefinition'], obj['matrix'])
                    assert shadow, 'source filter lacks a verified native paint mapping'
                    expected_style.update(shadow='1',shadowColor='#000000',shadowOpacity=shadow['opacity']*100,shadowOffsetX=shadow['dx'],shadowOffsetY=shadow['dy'],shadowBlur=shadow['blur'])
                shape, expected_box = stencil(obj)
                if native_style.get('shape') != shape:
                    errors.append({'reason':'source_stencil_payload_changed','cell':key})
                shapes.append({'cell':key,'stencil_sha256':sha(shape.encode())})
            else:
                expected_box = tuple(obj['bbox'][k] for k in ('x','y','w','h'))
                if obj['type'] == 'text':
                    expected_style = {'shape':'text','fontSize':obj['fontSize'],'fontColor':color(obj['color']),'opacity':obj['opacity']*100}
                    if obj.get('rotationHandled'):
                        expected_style['rotation'] = obj['nativeRotation']
                    elif not _near(native_style.get('rotation', 0), 0):
                        errors.append({'reason':'source_text_rotation_changed','cell':key})
                elif obj['type'] == 'image':
                    expected_style = {'shape':'image','opacity':obj['style']['opacity']*100}
                    assert obj['href'].startswith('data:image/'), 'source raster asset must be resolved inline'
                    a = base64.b64decode(native_style.get('image','').split(',',1)[1])
                    b = base64.b64decode(obj['href'].split(',',1)[1])
                    assert sha(a) == sha(b), 'source raster asset bytes changed'
                else:
                    raise AssertionError('unsupported source object type')
            # Visual properties only: html/layout implementation flags may legitimately differ.
            ignored = {'html'}
            if not obj.get('filterDefinition'):
                ignored.add('shadow')
            for name, expected in expected_style.items():
                if name in ignored:
                    continue
                actual = native_style.get(name)
                if actual is None:
                    # Source converters omit these when their visible default applies.
                    defaults = {'opacity':'100','fillOpacity':'100','strokeOpacity':'100','strokeWidth':'1'}
                    actual = defaults.get(name)
                try:
                    matches = actual is not None and _near(actual, expected)
                except (TypeError,ValueError):
                    matches = str(actual) == str(expected)
                if not matches:
                    errors.append({'reason':'source_paint_style_changed','cell':key,'property':name})
            if actual_box is not None:
                tolerance = 2 if obj['type'] == 'text' else .03
                if not all(_near(a,b,tolerance) for a,b in zip(actual_box[2:], expected_box[2:])):
                    errors.append({'reason':'source_object_size_changed','cell':key})
                delta = (actual_box[0]-expected_box[0], actual_box[1]-expected_box[1])
                if obj['type'] == 'text':
                    pending_text.append((key,delta))
                else:
                    translations.append(delta)
        except Exception as exc:
            errors.append({'reason':'source_paint_validation_error','cell':key,'error':repr(exc)[:400]})
    # Shared translation cannot conceal a single missing, moved or reshaped source object.
    dx = statistics.median(p[0] for p in translations) if translations else 0
    dy = statistics.median(p[1] for p in translations) if translations else 0
    if any(abs(x-dx)>.03 or abs(y-dy)>.03 for x,y in translations):
        errors.append({'reason':'source_relative_shape_or_connector_geometry_changed'})
    for key,(x,y) in pending_text:
        if abs(x-dx)>2 or abs(y-dy)>2:
            errors.append({'reason':'source_text_position_changed','cell':key})
    def distance_to_polyline(point, points):
        best=float('inf')
        for a,b in zip(points,points[1:]):
            vx,vy=b[0]-a[0],b[1]-a[1];length=vx*vx+vy*vy
            fraction=max(0,min(1,((point[0]-a[0])*vx+(point[1]-a[1])*vy)/length)) if length else 0
            best=min(best,math.dist(point,(a[0]+fraction*vx,a[1]+fraction*vy)))
        return best
    for obj,native_points,source_points in connectors:
        source_points=[(x+dx,y+dy) for x,y in source_points]
        if len(native_points)==len(source_points):
            path_ok=all(math.dist(a,b)<=.05 for a,b in zip(native_points[1:-1],source_points[1:-1]))
        else:
            # Fewer collinear waypoints are the same editable geometry, not a
            # semantic failure. Validate the entire source polyline both ways.
            path_ok=all(distance_to_polyline(p,native_points)<=.1 for p in source_points)
            path_ok=path_ok and all(distance_to_polyline(p,source_points)<=.1 for p in native_points[1:-1])
        allowances=[.1,.1]
        for arrow in dom['objects']:
            if arrow.get('tag')!='polygon' or not arrow.get('edge') or arrow['edge']['id']!=obj['edge']['id']:
                continue
            b=arrow['bbox'];center=(b['x']+b['w']/2+dx,b['y']+b['h']/2+dy)
            side=0 if math.dist(center,source_points[0])<math.dist(center,source_points[-1]) else 1
            allowances[side]=max(allowances[side],math.hypot(b['w'],b['h'])+2)
        path_ok=path_ok and all(math.dist(native_points[i],source_points[i])<=allowances[side] for side,i in enumerate((0,-1)))
        if not path_ok:
            errors.append({'reason':'source_native_connector_path_changed','cell':obj['id']})
    return {'ok':not errors,'errors':errors,'verified_native_shapes':len(shapes),'source_layout_translation':{'dx':dx,'dy':dy},'text_geometry_tolerance_px':2}


def _decorative_profile(dom):
    # Rectangles/ellipses/circles cannot carry an undeclared arrow marker or open
    # connector path. Arbitrary closed paths/polygons can encode arrows and need
    # a source graph profile rather than being silently called decoration.
    uncertain=[]
    for obj in dom['objects']:
        if obj.get('edge') or obj.get('markerOwner') or any(obj.get(k,'none')!='none' for k in ('markerStart','markerEnd')):
            uncertain.append(obj['id'])
        elif obj['type']=='shape' and obj['tag'] not in ('rect','circle','ellipse'):
            uncertain.append(obj['id'])
        elif obj['type']=='shape':
            b=obj['bbox']; ratio=max(b['w'],b['h'])/max(.01,min(b['w'],b['h']))
            if ratio>12 and min(b['w'],b['h'])<4:
                uncertain.append(obj['id'])
    return {'ok':not uncertain,'uncertain_connector_or_custom_path_objects':uncertain[:30]}


def _graphviz_coverage(dom, xml, stats):
    from svg_source_coverage_v2 import audit
    root = E.fromstring(xml)
    # Embedded physical-font spans keep the same editable logical characters.
    # Flatten only markup; do not normalize words, punctuation, case or counts.
    for cell in root.iter('mxCell'):
        if cell.get('value'):
            cell.set('value', html.escape(_plain(cell.get('value'))))
    normalized = E.tostring(root, encoding='unicode')
    result = audit(dom, normalized, stats)
    cells = {c.get('id'): c for c in E.fromstring(xml).iter('mxCell')}
    errors = list(result['errors'])
    objects = dom['objects']
    expected_ids = {o['id'] for o in objects} | {'node_'+key for key in dom['nodes']} | {'0','1'}
    for key,cell in cells.items():
        if key in expected_ids or not (cell.get('vertex')=='1' or cell.get('edge')=='1'):
            continue
        style = _style(cell)
        transparent_group = cell.get('vertex')=='1' and style.get('group')=='1' and style.get('fillColor')=='none' and style.get('strokeColor')=='none' and not cell.get('value')
        if not transparent_group:
            errors.append({'reason':'extra_native_paint_object_not_in_source','cell':key})
    paths = [o for o in objects if o.get('edge') and o.get('tag') == 'path' and o['style']['fill'] == 'none']
    native_edges = [c for c in cells.values() if c.get('edge') == '1']
    if len(paths) != len(native_edges):
        errors.append({'reason': 'extra_or_missing_native_edges', 'expected': len(paths), 'actual': len(native_edges)})
    arrows = [o for o in objects if o.get('edge') and o.get('tag') == 'polygon']
    marker_requirements = []
    for arrow in arrows:
        matches = [o for o in paths if o['edge']['id'] == arrow['edge']['id']]
        if len(matches) != 1 or not matches[0].get('sampledPoints'):
            errors.append({'reason': 'source_arrow_path_ambiguous', 'arrow': arrow['id']}); continue
        path = matches[0]; box = arrow['bbox']; center = [box['x'] + box['w']/2, box['y'] + box['h']/2]
        distances = [math.dist(center, path['sampledPoints'][i]) for i in (0, -1)]
        if abs(distances[0]-distances[1]) < 1:
            errors.append({'reason': 'source_arrow_side_ambiguous', 'arrow': arrow['id']}); continue
        side = 'start' if distances[0] < distances[1] else 'end'
        edge = cells.get(path['id']); style = _style(edge) if edge is not None else {}
        requirement = {'arrow': arrow['id'], 'edge': path['id'], 'side': side}
        marker_requirements.append(requirement)
        if edge is None or edge.get('edge') != '1' or style.get(side+'Arrow', 'none') in ('none', ''):
            errors.append({**requirement, 'reason': 'source_arrow_missing_attached_native_marker'})
        if arrow['id'] in cells:
            errors.append({**requirement, 'reason': 'source_arrow_remains_standalone_object'})
    # All source node-owned visible objects remain within the same logical node.
    for obj in objects:
        if not obj.get('node') or obj['id'] not in cells:
            continue
        parent = cells[obj['id']].get('parent'); seen = set(); expected = 'node_' + obj['node']
        while parent in cells and parent not in seen and parent != expected:
            seen.add(parent); parent = cells[parent].get('parent')
        if parent != expected:
            errors.append({'reason': 'source_node_membership_changed', 'object': obj['id'], 'expected': expected})
    result.update(ok=not errors, errors=errors, source_arrow_requirements=marker_requirements)
    return result


def _image_blob(src, served):
    from PIL import Image
    if src.startswith('data:'):
        header, data = src.split(',', 1)
        blob = base64.b64decode(data) if ';base64' in header else urllib.parse.unquote_to_bytes(data)
    else:
        assert src in served, 'source image not actually served: ' + src
        blob = served[src]
    image = Image.open(io.BytesIO(blob))
    if image.format in ('JPEG', 'PNG'):
        return blob
    output = io.BytesIO(); image.save(output, format='PNG'); return output.getvalue()


def _html_coverage(dom, xml, served):
    cells = {c.get('id'): c for c in E.fromstring(xml).iter('mxCell')}
    vertices = {k for k, c in cells.items() if c.get('vertex') == '1'}
    expected = {str(o['id']+1) for o in dom['objects']}
    errors, images = [], []
    if vertices != expected:
        errors.append({'reason': 'poster_object_coverage_mismatch', 'missing': sorted(expected-vertices)[:20], 'extra': sorted(vertices-expected)[:20]})
    text_count = 0
    for obj in dom['objects']:
        key = str(obj['id']+1); cell = cells.get(key)
        if cell is None:
            continue
        style = _style(cell)
        if obj['type'] == 'text':
            text_count += 1
            if _plain(cell.get('value', '')) != obj['text']:
                errors.append({'reason': 'poster_text_changed', 'cell': key})
            if style.get('shape') != 'text':
                errors.append({'reason': 'poster_text_not_editable_text_object', 'cell': key})
        elif obj['type'] == 'image':
            if not obj.get('loaded'):
                errors.append({'reason': 'poster_source_image_not_loaded', 'cell': key}); continue
            expected_blob = _image_blob(obj['src'], served)
            value = style.get('image', '')
            try:
                assert value.startswith('data:image/')
                # drawio data URIs omit the ;base64 marker but remain base64 encoded.
                actual = base64.b64decode(value.split(',', 1)[1], validate=True)
                assert sha(actual) == sha(expected_blob)
                images.append({'cell': key, 'sha256': sha(actual)})
            except Exception:
                errors.append({'reason': 'poster_original_asset_bytes_changed_or_missing', 'cell': key})
        elif obj['type'] != 'rect':
            errors.append({'reason': 'unsupported_poster_source_object', 'cell': key, 'type': obj['type']})
    if not text_count:
        errors.append({'reason': 'poster_has_no_editable_source_text'})
    paint = _paint_coverage(dom, xml, 'html')
    errors.extend(paint['errors'])
    return {'ok': not errors, 'errors': errors, 'source_objects': len(expected), 'source_text_runs': text_count, 'verified_original_images': images, 'native_source_paint': paint}


def check_vector_profile(record, xml):
    fmt = record.get('source_format')
    profile = {'svg': 'fresh_svg_graphviz_source_coverage_v1', 'python': 'fresh_python_svg_graphviz_source_coverage_v1', 'html': 'fresh_html_wrapped_words_and_browser_paint_order_v2', 'plantuml': 'fresh_pinned_plantuml_source_geometry_v1'}.get(fmt)
    unsupported = {'supported': False, 'ok': False, 'profile': profile or 'unsupported_vector_source_profile', 'failures': [], 'evidence': {}}
    if fmt not in ('svg', 'python', 'html', 'plantuml'):
        unsupported['failures'] = ['format_requires_separate_source_semantics_profile']
        return unsupported
    if fmt == 'html' and record.get('category') != 'poster':
        unsupported['failures'] = ['html_diagram_semantic_connectors_require_source_graph_profile']
        return unsupported
    result = {'supported': True, 'ok': False, 'profile': profile, 'failures': [], 'evidence': {}}
    try:
        code = _identity(record, xml)
        from PIL import Image
        width, height = Image.open(io.BytesIO(_read_clean(record['original_reference'], record['source_image_sha256']))).size
        if fmt in ('python', 'plantuml'):
            code = _read_clean(record['source_render_svg'], record['source_render_svg_sha256'])
            if record.get('original_source_data'):
                _read_clean(record['original_source_data'], record['source_data_sha256'])
        dom, served = _capture(record, code, width, height, 'html' if fmt == 'html' else 'plantuml' if fmt == 'plantuml' else 'svg')
        issues = dom.get('unsupported', []) if fmt == 'html' else dom.get('issues', [])
        css_paint = _html_paint_order(dom, xml) if fmt == 'html' else None
        if css_paint and not css_paint['ok']:
            result['failures'].extend(css_paint['errors'])
        unresolved_features = []
        for issue in issues:
            if issue.get('reason') == 'css_stacking_order' and css_paint and css_paint['ok']:
                continue
            source_objects = [o for o in dom['objects'] if o.get('sourceId') == issue.get('id') and (not issue.get('tag') or o.get('tag')==issue['tag'])]
            if issue.get('reason') == 'fill_paint_server':
                source_objects = [o for o in source_objects if o.get('style',{}).get('fill') == issue.get('value')]
                from svg_convert_v2 import style as svg_style
                for obj in source_objects:
                    svg_style(obj)
                if source_objects and all(o.get('gradientHandled') for o in source_objects):
                    continue
            if fmt == 'plantuml' and issue.get('reason') == 'filter':
                from plantuml_native_v4 import shadow_filter
                match = re.search(r'#([^\"\')]+)', issue.get('value',''))
                source_objects = [o for o in source_objects if o.get('filterDefinition') and match and o['filterDefinition']['id']==match.group(1)]
                if source_objects and all(o.get('filterDefinition') and shadow_filter(o['filterDefinition'],o['matrix']) for o in source_objects):
                    continue
            unresolved_features.append(issue)
        if unresolved_features:
            result['failures'].append({'reason': 'unsupported_fresh_source_features', 'issues': unresolved_features[:20]})
        if fmt == 'plantuml':
            metadata = dom['_plantuml_metadata']
            if not metadata['groups'] or metadata['expectedLinkCount'] != len(metadata['links']):
                result['failures'].append({'reason':'pinned_source_engine_semantic_graph_incomplete'})
            cells = {c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
            for parent in metadata['parents']:
                cell = cells.get('node_'+parent['child'])
                if cell is None or cell.get('parent') != 'node_'+parent['parent']:
                    result['failures'].append({'reason':'source_cluster_membership_changed','child':parent['child']})
            # These two adapter notes describe independently checked deterministic
            # source grouping, not missing geometry or a manual-review requirement.
            known = {'plantuml_unwrapped_state_container_requires_source_review','plantuml_initial_final_circle_binding_requires_source_review'}
            bad = [i for i in metadata['issues'] if i.get('reason') not in known]
            if bad:
                result['failures'].append({'reason':'pinned_source_engine_unresolved_metadata','issues':bad[:20]})
            if dom['_plantuml_fonts']['needs_glyph_fallback_review']:
                result['failures'].append({'reason':'pinned_source_java_glyph_coverage_unresolved'})
        if fmt == 'html':
            proof = _html_coverage(dom, xml, served)
            proof['wrapped_word_range_proofs'] = dom.get('qaWrappedWords', [])
            if css_paint:
                proof['source_css_paint_order'] = css_paint
        else:
            if not dom.get('nodes'):
                decoration = _decorative_profile(dom)
                if not decoration['ok']:
                    result['supported'] = False
                    result['failures'].append({'reason':'unidentified_svg_connectors_require_semantic_profile', **decoration})
                    return result
                result['profile'] = 'fresh_primitive_vector_source_paint_v1'
                proof = _graphviz_coverage(dom, xml, record.get('svg_conversion', {}))
                proof['primitive_only_no_source_connectors'] = decoration
            else:
                proof = _graphviz_coverage(dom, xml, record.get('svg_conversion', {}))
            paint = _paint_coverage(dom, xml)
            proof['native_source_paint'] = paint
            proof['errors'].extend(paint['errors'])
            proof['ok'] = not proof['errors']
        result['evidence'] = {'code_sha256': sha(xml.encode()), 'source_code_sha256': record['source_code_sha256'], 'fresh_source_dom_sha256': sha(json.dumps(dom, sort_keys=True).encode()), 'source_coverage': proof, 'fresh_offline_source_dom': True, 'scope': 'Current source text/object/terminal/asset coverage; caller additionally verifies actual native render, fonts, editability and original-reference image fidelity.'}
        result['failures'].extend(proof['errors'])
        result['ok'] = not result['failures']
    except Exception as exc:
        result['failures'].append({'reason': 'source_profile_validation_error', 'error': repr(exc)[:1200]})
    return result
