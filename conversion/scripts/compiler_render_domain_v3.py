"""Independent, symmetric source/target renderer-domain quality checks.

No candidate-only conversion proof is required. Fresh DOT PNG retains the old
source-reference gates. Fresh DOT SVG is replayed with independently resolved
physical font bytes in the same pinned browser domain as drawio; every source
object, grapheme and portable physical face is checked independently. The old
reference/native local-text SSIM is retained as a cross-domain diagnostic only.
Other reference/native gates and ALL same-domain gates are unchanged.
"""
from __future__ import annotations
import base64
import copy
import io
import json
import math
import re
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from compiler_scene_v1 import R, W, _read, _save, _source_scene, raw, sha

POLICY = 'independent_fresh_source_same_browser_render_domain_v3'
POSITION_TOLERANCE_PX = .03
CROSS_DOMAIN_DIAGNOSTIC_ONLY = 'local_text_line_ssim_below_0.55'


def _unique(rows, key, reason):
    result = {}
    for row in rows:
        value = row.get(key)
        if value is None or value in result:
            raise ValueError(reason)
        result[value] = row
    return result


def _xml_cells(xml):
    root = ET.fromstring(xml)
    cells = _unique(list(root.iter('mxCell')), 'id', 'duplicate_or_missing_native_cell_id')
    models = list(root.iter('mxGraphModel'))
    if len(models) != 1:
        raise ValueError('exactly_one_native_page_required')
    return root, cells, models[0]


def _style(cell):
    fields = [part for part in cell.get('style', '').split(';') if '=' in part]
    keys = [part.split('=', 1)[0] for part in fields]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate_native_style_key')
    return dict(part.split('=', 1) for part in fields)


def _font_signature(fonts, custom=None):
    result = []
    for font in fonts:
        count = font.get('glyphCount')
        if type(count) is not int or count < 0:
            raise ValueError('invalid_fresh_physical_font_glyph_count')
        if count:
            if not font.get('postScriptName') or custom is not None and font.get('isCustomFont') is not custom:
                raise ValueError('fresh_native_font_not_custom')
            result.append((font['postScriptName'], count))
    if not result:
        raise ValueError('missing_fresh_physical_font_usage')
    return sorted(result)


def _graphemes(info):
    if 'actual_text_positions' not in info or 'actual_platform_font_usage' not in info:
        raise RuntimeError('infrastructure_fresh_native_text_observers_missing')
    rows = _unique(info['actual_text_positions'], 'cell', 'duplicate_native_text_observation')
    fonts = _unique(info['actual_platform_font_usage'], 'cell', 'duplicate_native_font_observation')
    chars = {key: [char for run in row.get('runs', []) for char in run.get('chars', [])]
             for key, row in rows.items()}
    if not chars or not any(char.get('text', '').strip() for row in chars.values() for char in row):
        raise ValueError('empty_fresh_native_text_scope')
    return chars, {key: row['fonts'] for key, row in fonts.items()}


def glyph_check(source, native_info, offset=(0., 0.)):
    """Exact complete strings and actual individual browser range rectangles."""
    actual, fonts = _graphemes(native_info)
    failures = []
    if not source:
        raise ValueError('empty_fresh_source_text_scope')
    if set(source) != set(actual):
        failures.append({'reason': 'fresh_native_text_coverage_changed',
                         'missing': sorted(set(source)-set(actual)), 'extra': sorted(set(actual)-set(source))})
    if set(source) != set(fonts):
        failures.append({'reason': 'fresh_native_font_coverage_changed'})
    maximum = 0.
    for identifier, expected in source.items():
        wanted, got = expected['chars'], actual.get(identifier, [])
        if not wanted or [c['text'] for c in wanted] != [c.get('text') for c in got]:
            failures.append({'reason': 'fresh_native_graphemes_changed', 'cell': identifier})
            continue
        try:
            if _font_signature(expected['actual_fonts'], True) != _font_signature(fonts.get(identifier, []), True):
                failures.append({'reason': 'fresh_native_physical_font_usage_changed', 'cell': identifier})
        except ValueError as error:
            failures.append({'reason': str(error), 'cell': identifier})
        for index, (want, observed) in enumerate(zip(wanted, got)):
            errors = [abs(float(observed[key])-float(want[key])-(offset[0] if key == 'x' else offset[1] if key == 'y' else 0.))
                      for key in ('x', 'y', 'width', 'height')]
            maximum = max(maximum, *errors)
            if any(not math.isfinite(value) or value > POSITION_TOLERANCE_PX for value in errors):
                failures.append({'reason': 'fresh_native_source_grapheme_geometry_changed', 'cell': identifier,
                                 'grapheme': index, 'maximum_error_px': max(errors)})
    return {'ok': not failures, 'failures': failures,
            'source_text_objects': len(source), 'source_graphemes': sum(len(row['chars']) for row in source.values()),
            'maximum_geometry_error_px': maximum, 'tolerance_px': POSITION_TOLERANCE_PX,
            'matching': 'exact source object id, complete one-to-one; ID remapping unsupported'}


def _physical_faces(postscript_names):
    """Resolve source's actually used system faces; reject same-name ambiguity."""
    from portable_native_fonts import catalog
    from native_source_font_profile_v4 import _sfnt
    from fontTools.ttLib import TTFont
    catalog_rows = catalog()
    result = {}
    for name in sorted(set(postscript_names)):
        unique = {}
        for file, index in catalog_rows.get(name, []):
            blob = Path(file).read_bytes()
            unique[(sha(blob), index)] = (file, index, blob)
        if len(unique) != 1:
            raise ValueError('source_physical_font_missing_or_ambiguous:'+name)
        file, index, blob = next(iter(unique.values()))
        ft = TTFont(io.BytesIO(blob), fontNumber=index)
        try:
            fs_type = ft['OS/2'].fsType if 'OS/2' in ft else 0
            if fs_type & (0x2 | 0x200) or 'fvar' in ft:
                raise ValueError('source_physical_font_not_portable')
            if blob[:4] == b'ttcf':
                stream = io.BytesIO(); ft.save(stream); embedded = stream.getvalue()
            else:
                embedded = blob
        finally:
            ft.close()
        face = _sfnt(blob, index)
        if face['postscript'] != name or _sfnt(embedded) != face:
            raise ValueError('source_physical_font_face_identity_changed')
        result[name] = {'file': file, 'collection_index': index, 'original_sha256': sha(blob),
                        'embedded_sha256': sha(embedded), 'embedded': embedded, 'face': face,
                        'family': 'CompilerSource_'+sha(embedded)[:20]}
    return result


_TEXT_JS = r'''()=>{const rows=[];for(const [index,e] of [...document.querySelectorAll('svg text')].entries()){e.dataset.compilerDomainV3=String(index);const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim())continue;const all=document.createRange();all.selectNodeContents(n);const whole=all.getBoundingClientRect();if(!whole.width||!whole.height)continue;const chars=[];for(const {segment,index:i} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const range=document.createRange();range.setStart(n,i);range.setEnd(n,i+segment.length);const b=range.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}rows.push({source_element_index:index,text:n.textContent,chars});}}return rows;}'''


def _observe(page, context):
    dom = page.evaluate((W/'scripts/svg_dom_v6.js').read_text())
    rows = page.evaluate(_TEXT_JS)
    objects = [obj for obj in dom['objects'] if obj['type'] == 'text']
    if len(objects) != len(rows) or not objects:
        raise ValueError('fresh_source_text_run_scope_invalid')
    _unique(dom['objects'], 'id', 'duplicate_or_missing_source_object_id')
    session = context.new_cdp_session(page)
    try:
        session.send('DOM.enable'); session.send('CSS.enable')
        document = session.send('DOM.getDocument', {'depth': 1})['root']['nodeId']
        positions = {}
        for obj, row in zip(objects, rows):
            if obj['text'] != row['text']:
                raise ValueError('fresh_source_text_order_changed')
            node = session.send('DOM.querySelector', {'nodeId': document,
                'selector': '[data-compiler-domain-v3="'+str(row['source_element_index'])+'"]'})['nodeId']
            fonts = session.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
            positions[obj['id']] = {**row, 'bbox': obj['bbox'], 'actual_fonts': fonts}
        return positions, dom
    finally:
        session.detach()


def _wait_fonts(page, timeout=45.):
    # The source document forbids its own script callbacks. Playwright's
    # browser-side RAF/promise wait helpers can therefore wait indefinitely;
    # synchronous status observations have a client-side monotonic deadline.
    deadline=time.monotonic()+timeout
    while True:
        page.evaluate('document.documentElement.getBoundingClientRect()')
        if page.evaluate('document.fonts.status') == 'loaded':return
        if time.monotonic() >= deadline:
            raise RuntimeError('infrastructure_source_font_loading_timeout')
        time.sleep(.05)


def marker_check(dom, xml):
    """Re-derive every native marker's style/size from the fresh source contour.

    This produces the old coverage adapter's polygon replacement mapping from
    independent source geometry and actual native styles, never converter stats.
    """
    from svg_convert_v5 import marker
    from svg_convert_v2 import style as svg_style, color
    _, cells, _ = _xml_cells(xml)
    arrows = [obj for obj in dom['objects'] if obj.get('edge') and obj.get('tag') == 'polygon']
    paths = [obj for obj in dom['objects'] if obj.get('edge') and obj.get('tag') == 'path' and obj['style']['fill'] == 'none']
    mappings, failures = [], []
    occupied = set()
    for arrow in arrows:
        try:
            matches = [path for path in paths if path['edge']['id'] == arrow['edge']['id']]
            if len(matches) != 1:
                raise ValueError('source_arrow_path_not_unique')
            path = matches[0]
            choices = [(side, marker(arrow, path['sampledPoints'], side)) for side in ('start','end')]
            choices = [(side, geometry) for side, geometry in choices if geometry]
            if len(choices) != 1:
                raise ValueError('source_arrow_contour_not_uniquely_supported')
            side, geometry = choices[0]
            if (path['id'],side) in occupied:
                raise ValueError('duplicate_source_arrow_at_native_marker_side')
            occupied.add((path['id'],side))
            cell = cells.get(path['id'])
            if cell is None or cell.get('edge') != '1':
                raise ValueError('native_marker_edge_missing')
            actual = _style(cell)
            width = float(svg_style(path).get('strokeWidth',1))
            expected_size = geometry['length']-width
            if color(arrow['style']['fill']) != color(path['style']['stroke']) or expected_size <= 0:
                raise ValueError('source_marker_paint_or_size_unsupported')
            if actual.get(side+'Arrow') != geometry['arrow']:
                raise ValueError('native_marker_type_differs_from_source_contour')
            if abs(float(actual.get(side+'Size','nan'))-expected_size) > POSITION_TOLERANCE_PX or not math.isfinite(float(actual.get(side+'Size','nan'))):
                raise ValueError('native_marker_size_differs_from_source_contour')
            if actual.get(side+'Fill','1') != '1':
                raise ValueError('native_marker_fill_differs_from_source_contour')
            mappings.append({'source_arrow_object':arrow['id'],'native_edge':path['id'],'side':side,
                             'type':geometry['arrow'],'source_length':geometry['length'],
                             'verified_native_size':expected_size,'independently_reconstructed':True})
        except Exception as exc:
            failures.append({'reason':str(exc).split(':',1)[0], 'source_arrow':arrow['id'], 'detail':str(exc)[:1000]})
    # A native marker without an exact source contour is also additional paint.
    for path in paths:
        cell=cells.get(path['id'])
        if cell is None:continue
        actual=_style(cell)
        for side in ('start','end'):
            if actual.get(side+'Arrow','none') not in ('none','') and (path['id'],side) not in occupied:
                failures.append({'reason':'native_marker_has_no_source_contour','edge':path['id'],'side':side})
    return {'ok':not failures,'failures':failures,'source_arrows':len(arrows),
            'verified_arrows':len(mappings),'native_graphviz_arrowheads':mappings}


def replay_source(record, scene, reference_size, page_size, offset, work):
    """Same source SVG/physical faces, exact reference viewport, fixed page shift."""
    from playwright.sync_api import sync_playwright
    from fixed_batch_conversion_adapters_v1 import CHROME
    work.mkdir(parents=True, exist_ok=True)
    def progress(stage):
        (work/'progress.json').write_bytes(raw({'stage':stage,'id':record['id']}))
    progress('source_browser_start')
    svg = _read(record['source_render_svg'], scene['source']['svg_sha256'])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, args=['--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': reference_size[0], 'height': reference_size[1]},
                                      java_script_enabled=False, service_workers='block', device_scale_factor=1)
        blocked = []
        try:
            context.route('**/*', lambda request: (blocked.append(request.request.url), request.abort()))
            page = context.new_page(); page.set_default_timeout(45000)
            page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+svg.decode())
            page.evaluate('''([w,h])=>{const s=document.querySelector('svg');s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''', list(reference_size))
            progress('source_system_fonts')
            _wait_fonts(page)
            before, dom = _observe(page, context)
            if dom.get('issues'):
                raise ValueError('unsupported_fresh_source_dom:'+json.dumps(dom['issues'])[:1000])
            names = [font['postScriptName'] for row in before.values() for font in row['actual_fonts'] if font.get('glyphCount')]
            faces = _physical_faces(names)
            progress('source_physical_faces_resolved')
            css = []
            for face in faces.values():
                css.append('@font-face{font-family:"'+face['family']+'";src:url(data:font/ttf;base64,'+
                           base64.b64encode(face['embedded']).decode()+');font-weight:normal;font-style:normal;}')
            # add_style_tag waits on injected inline load/error callbacks. Those
            # callbacks are disabled by this deliberately script-disabled source
            # context. A synchronous DOM insertion has no such event dependency.
            page.evaluate("css=>{const style=document.createElement('style');style.textContent=css;document.head.appendChild(style);}", '\n'.join(css))
            progress('source_font_css_added')
            replacements = []
            for row in before.values():
                signature = _font_signature(row['actual_fonts'])
                if len(signature) != 1:
                    raise ValueError('mixed_source_physical_fonts_per_text_run_unsupported')
                replacements.append([row['source_element_index'], faces[signature[0][0]]['family']])
            page.evaluate('''rows=>{for(const [i,family] of rows){const e=document.querySelector('[data-compiler-domain-v3="'+i+'"]');e.style.fontFamily=family;e.style.fontWeight='normal';e.style.fontStyle='normal';}}''', replacements)
            page.evaluate('document.documentElement.getBoundingClientRect()')
            progress('source_custom_fonts')
            _wait_fonts(page)
            positions, _ = _observe(page, context)
            progress('source_custom_fonts_observed')
            # Bundling source faces must retain the system-resolved source layout.
            for key in before:
                if [c['text'] for c in before[key]['chars']] != [c['text'] for c in positions[key]['chars']]:
                    raise ValueError('source_font_embedding_changed_characters')
                if _font_signature(before[key]['actual_fonts']) != _font_signature(positions[key]['actual_fonts'], True):
                    raise ValueError('source_font_embedding_changed_physical_usage')
                if any(abs(a[k]-b[k]) > POSITION_TOLERANCE_PX for a,b in zip(before[key]['chars'], positions[key]['chars']) for k in ('x','y','width','height')):
                    raise ValueError('source_font_embedding_changed_geometry')
            page.set_viewport_size({'width': page_size[0], 'height': page_size[1]})
            page.evaluate('''([x,y])=>{const s=document.querySelector('svg');s.style.position='absolute';s.style.left=x+'px';s.style.top=y+'px';}''', list(offset))
            progress('source_screenshot')
            png = page.screenshot(type='png', full_page=False, timeout=45000)
            if blocked:
                raise ValueError('source_replay_blocked_external_resource')
            _save(work/'source_browser.png', png)
            _save(work/'fresh_source_positions.json', raw(positions)); _save(work/'fresh_source_dom.json', raw(dom))
            progress('source_replay_complete')
            face_evidence = {}
            for name, face in faces.items():
                font_file = work/'fonts'/(face['embedded_sha256']+'.ttf'); _save(font_file, face['embedded'])
                face_evidence[name] = {key: value for key, value in face.items() if key != 'embedded'}
            return {'png': png, 'positions': positions, 'dom': dom, 'faces': face_evidence,
                    'evidence': {'reference_canvas': list(reference_size), 'page_canvas': list(page_size),
                                 'page_offset': list(offset), 'device_scale_factor': 1,
                                 'svg_sha256': scene['source']['svg_sha256'], 'chromium_sha256': sha(Path(CHROME).read_bytes()),
                                 'source_fonts': face_evidence, 'source_browser_png_sha256': sha(png),
                                 'source_positions_sha256': sha(raw(positions)), 'reference_pixels_used_for_alignment': False}}
        finally:
            context.close(); browser.close()


def physical_font_check(record, xml, source, source_faces, native_info):
    """Actual per-cell custom font -> inline bytes -> source actual sfnt tables."""
    from native_source_font_profile_v4 import _ext, _font_blob, _sfnt
    _, cells, model = _xml_cells(xml)
    embedded = _ext(model)
    assets = _unique(record.get('native_embedded_fonts') or [], 'family', 'duplicate_native_font_asset_family')
    _, usage = _graphemes(native_info)
    checked = {}
    failures = []
    for identifier, row in source.items():
        try:
            cell = cells.get(identifier)
            if cell is None:
                raise ValueError('native_text_cell_missing_for_physical_font')
            # Relative span positioning is supported, but local font overrides
            # must be compiled into separate text runs; do not flatten them.
            value = cell.get('value', '')
            if re.search(r'(?:font-family|font-size|font-weight|font-style)\s*:|<font\b|<(?:b|i|strong|em)\b', value, re.I):
                raise ValueError('unaccounted_native_rich_font_override')
            family = _style(cell).get('fontFamily')
            if not family or ',' in family or family not in embedded or family not in assets:
                raise ValueError('native_physical_font_has_no_unique_portable_asset')
            asset = assets[family]
            blob = _read(asset['file'], asset['sha256'])
            original = _read(asset['original_file'], asset['original_sha256'])
            if _font_blob(embedded[family]) != blob:
                raise ValueError('native_inline_font_bytes_disagree_with_asset')
            font_source = _style(cell).get('fontSource')
            if font_source:
                import urllib.parse
                if _font_blob(urllib.parse.unquote(font_source)) != blob:
                    raise ValueError('native_font_source_bytes_disagree_with_ext_font')
            face = _sfnt(blob)
            if _sfnt(original, int(asset.get('collection_index', 0))) != face:
                raise ValueError('native_embedded_font_differs_from_its_original_face')
            expected = _font_signature(row['actual_fonts'], True)
            if len(expected) != 1 or face != source_faces[expected[0][0]]['face']:
                raise ValueError('native_physical_font_differs_from_source_actual_file')
            if _font_signature(usage.get(identifier, []), True) != expected:
                raise ValueError('native_actual_physical_font_usage_differs_from_source')
            checked[identifier] = {'family': family, 'asset_sha256': sha(blob), 'postscript': face['postscript'],
                                   'source_original_font_sha256': source_faces[expected[0][0]]['original_sha256'],
                                   'sfnt_table_identity_verified': True}
        except Exception as exc:
            failures.append({'reason': str(exc).split(':',1)[0], 'cell': identifier, 'detail': str(exc)[:1000]})
    if not source or len(checked) != len(source):
        failures.append({'reason': 'incomplete_independent_physical_font_scope'})
    return {'ok': not failures, 'failures': failures, 'checked_text_objects': len(checked), 'objects': checked}


def _registration(record, xml, reference, png_size, reference_size):
    # Strip injected trust flags. Reconstruct the original page proof each time.
    clean = {key: value for key, value in record.items() if not key.startswith('_verified_')}
    from compiler_quality_v2 import registration_record
    registered, contract = registration_record(clean, reference, xml)
    offset = list((contract or {}).get('original_page_offset', [0, 0]))
    if len(offset) != 2 or any(not math.isfinite(float(value)) or value < 0 for value in offset):
        raise ValueError('invalid_independently_verified_source_page_offset')
    if not contract and tuple(png_size) != tuple(reference_size):
        raise ValueError('unregistered_source_native_page_difference')
    _, _, model = _xml_cells(xml)
    declared = [float(model.get(key, 'nan')) for key in ('pageWidth','pageHeight')]
    if declared != list(map(float,png_size)):
        raise ValueError('native_page_canvas_disagrees_with_fresh_png')
    if contract and list(map(float,contract['output_page'])) != list(map(float,png_size)):
        raise ValueError('independent_page_contract_canvas_changed')
    if offset[0]+reference_size[0] > png_size[0] or offset[1]+reference_size[1] > png_size[1]:
        raise ValueError('source_reference_does_not_fit_independently_verified_page')
    return registered, contract, offset


def _positions(source, offset):
    return [{'cell': identifier, 'runs': [{'chars': [{**char, 'x': char['x']+offset[0], 'y': char['y']+offset[1]} for char in row['chars']]}]}
            for identifier, row in source.items()]


def _primitive_positions(dom, offset):
    result=[]
    for obj in dom['objects']:
        if obj['type'] != 'shape':continue
        box=obj['bbox'];stroke=float(obj['style'].get('strokeWidth',1))
        half=max(.5,stroke/2)
        result.append({'cell':'source_primitive:'+obj['id'],'runs':[{'chars':[{
            'text':'source_primitive','x':box['x']+offset[0]-half,'y':box['y']+offset[1]-half,
            'width':max(.01,box['w']+2*half),'height':max(.01,box['h']+2*half)}]}]})
    if not result:raise ValueError('empty_source_primitive_pixel_scope')
    return result


def _reference_visual_record(record, contract):
    result={key:value for key,value in record.items() if key not in ('native_canvas_contract','native_page_padding') and not key.startswith('_verified_')}
    if contract:
        result['native_canvas_contract']={**contract,'offset':contract['original_page_offset']}
    return result


def check(record, xml, native_info, png, reference, work):
    """One independent B/C checker. Caller supplies this invocation's fresh native render."""
    started = time.monotonic()
    report = {'policy': POLICY, 'supported': False, 'ok': False, 'failures': [], 'evidence': {},
              'infrastructure_failure': False, 'reference_visual': None, 'source_replay_visual': None}
    try:
        work = Path(work).resolve()
        if not work.is_relative_to((W/'compiler_render_domain_v3').resolve()):
            raise ValueError('render_domain_work_outside_owner')
        work.mkdir(parents=True, exist_ok=True)
        if sha(xml.encode()) != record['code_sha256']:
            raise ValueError('candidate_xml_revision_mismatch')
        if sha(reference) != record['source_image_sha256'] or _read(record['original_reference'], record['source_image_sha256']) != reference:
            raise ValueError('reference_identity_mismatch')
        _xml_cells(xml); _graphemes(native_info)
        from compiler_capture_snapshot_v1 import check_snapshot
        snapshot = check_snapshot(record, record.get('compiler_source_capture_snapshot'))
        scene = _source_scene(record, work/'fresh_dot')
        if scene['source']['svg_sha256'] != snapshot['source_svg_sha256'] or scene['source']['dot_sha256'] != snapshot['source_dot_sha256']:
            raise RuntimeError('infrastructure_fresh_source_snapshot_drift')
        from PIL import Image
        size = Image.open(io.BytesIO(png)).size
        ref_size = Image.open(io.BytesIO(reference)).size
        registered, contract, offset = _registration(record, xml, reference, size, ref_size)
        replay = replay_source(record, scene, ref_size, size, offset, work/'source_replay')
        source, dom = replay['positions'], replay['dom']
        if not source or not any(obj['type'] == 'shape' for obj in dom['objects']):
            raise ValueError('empty_source_text_or_primitive_scope')
        report['supported'] = True
        report['evidence'].update(capture_snapshot=snapshot, fresh_source_scene_sha256=sha(raw(scene)),
            source_replay=replay['evidence'], independent_registration=contract,
            candidate_xml_sha256=sha(xml.encode()), fresh_native_png_sha256=sha(png),
            fresh_native_info_sha256=sha(raw(native_info)), independent_of_candidate_textproof=True,
            source_objects=len(dom['objects']), source_text_objects=len(source),
            source_primitives=sum(obj['type']=='shape' for obj in dom['objects']))
        from auto_quality_source_vector_v2 import _graphviz_coverage, _paint_coverage
        from compiler_scene_v1 import _json_endpoint_validation
        markers = marker_check(dom, xml)
        coverage = _graphviz_coverage(dom, xml, {'native_graphviz_arrowheads':markers['native_graphviz_arrowheads']})
        paint = _paint_coverage(dom, xml)
        semantic_failures = coverage['errors'] + paint['errors'] + markers['failures']
        try:
            endpoints = _json_endpoint_validation(scene, dom, xml)
        except Exception as error:
            endpoints = {'ok': False, 'reason': str(error).split(':',1)[0]}
            semantic_failures.append({'reason': 'source_json_endpoint_changed', 'detail': str(error)[:1000]})
        translation = paint['source_layout_translation']
        if any(abs(translation[key]-wanted) > POSITION_TOLERANCE_PX for key,wanted in zip(('dx','dy'),offset)):
            semantic_failures.append({'reason':'source_layout_translation_lacks_independent_registration', 'observed':translation, 'verified_offset':offset})
        semantics = {'ok':not semantic_failures,'failures':semantic_failures,'source_coverage':coverage,
                     'source_paint':paint,'source_json_endpoints':endpoints,'source_markers':markers}
        glyphs = glyph_check(source, native_info, offset)
        fonts = physical_font_check(record, xml, source, replay['faces'], native_info)
        from auto_quality_common import image_quality
        positions = _positions(source, offset)
        same = image_quality(replay['png'], png, {}, positions)
        primitive_positions = _primitive_positions(dom,offset)
        primitive_pixels = image_quality(replay['png'],png,{},primitive_positions)
        if primitive_pixels['text_regions_checked'] != len(primitive_positions):
            raise ValueError('incomplete_source_primitive_local_pixel_scope')
        cross = image_quality(reference, png, _reference_visual_record(registered,contract), positions)
        if same['text_regions_checked'] <= 0 or cross['text_regions_checked'] <= 0:
            raise ValueError('empty_source_expected_local_pixel_checks')
        from compiler_source_reproduction_v1 import check as reproduce
        reproduced = reproduce(record, work/'source_reference')
        if reproduced.get('infrastructure_failure'):
            raise RuntimeError('infrastructure_source_reproduction:'+str(reproduced.get('detail')))
        cross_failures = [failure for failure in cross['failures'] if failure != CROSS_DOMAIN_DIAGNOSTIC_ONLY]
        checks = {'source_reference': {'ok': reproduced.get('ok') is True, 'reason': reproduced.get('reason'), 'evidence': reproduced.get('evidence'), 'visual': reproduced.get('source_reference_visual')},
                  'source_semantics': semantics, 'fresh_graphemes': glyphs, 'physical_fonts': fonts,
                  'same_domain_pixels': same,
                  'source_primitive_pixels':primitive_pixels,
                  'reference_nonlocal_pixels': {'ok':not cross_failures, 'failures':cross_failures}}
        for gate, result in checks.items():
            if not result.get('ok'):
                report['failures'].append({'gate':gate, 'reason':result.get('reason', gate+'_failed'), 'failures':result.get('failures',[])})
        report.update(ok=not report['failures'], reference_visual=cross, source_replay_visual=same)
        report['evidence'].update(checks=checks, source_expected_local_text_regions=same['text_regions_checked'],
             cross_domain_local_text_ssim_is_diagnostic_only=True, thresholds_unchanged=same['thresholds'],
             source_scope='All fresh source objects, arrow requirements, JSON endpoints and source grapheme regions; candidate cannot reduce the expected scope.')
    except Exception as exc:
        report['failures'].append({'gate':'setup_or_registration', 'reason':str(exc).split(':',1)[0], 'detail':str(exc)[:3000]})
        report['exception_type'] = type(exc).__name__
        report['infrastructure_failure'] = isinstance(exc,(ImportError,ModuleNotFoundError)) or str(exc).startswith('infrastructure_')
    report['seconds'] = time.monotonic()-started
    if 'work' in locals() and isinstance(work,Path) and work.is_relative_to((W/'compiler_render_domain_v3').resolve()) and work.exists():
        _save(work/'render_domain_report.json', raw(report))
        report['evidence_file'] = str((work/'render_domain_report.json').relative_to(R))
        report['evidence_sha256'] = sha((work/'render_domain_report.json').read_bytes())
    return report
