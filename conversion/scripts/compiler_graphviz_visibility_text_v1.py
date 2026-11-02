"""Restore source SVG text anchors lost to native HTML integer-pixel rounding.

Only one whole-run relative translation is allowed.  Characters, font/style,
glyph shaping, cell geometry and graph topology are preserved.  Offsets are
derived from fresh source/native DOM ranges; reference pixels are never read
for alignment.  Full independent target QA is still mandatory.
"""
from __future__ import annotations

import copy
import html
import io
import json
import math
import statistics
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import compiler_graphviz_visibility_scene_v1 as scene_v1
from compiler_graphviz_visibility_scene_v1 import R, W, _read, _save, raw, sha

POLICY = 'source_svg_fractional_text_anchor_native_html_visibility_v1'
POSITION_TOLERANCE_PX = .03
MAX_TRANSLATION_PX = 2.


def source_positions(record):
    """Fresh actual source SVG grapheme ranges and physical fonts, not reports."""
    from PIL import Image
    from playwright.sync_api import sync_playwright
    from fixed_batch_conversion_adapters_v1 import CHROME
    width, height = Image.open(io.BytesIO(_read(record['original_reference'], record['source_image_sha256']))).size
    svg = _read(record['source_render_svg'], record['source_render_svg_sha256'])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, args=['--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=False, service_workers='block')
        blocked = []
        try:
            context.route('**/*', lambda request: (blocked.append(request.request.url), request.abort()))
            page = context.new_page()
            page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode())
            page.evaluate('''([w,h])=>{const s=document.querySelector('svg');s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''', [width, height])
            page.evaluate('document.fonts.ready')
            dom = page.evaluate((W/'scripts/svg_dom_v6.js').read_text())
            rows = page.evaluate('''()=>{const rows=[];for(const [index,e] of [...document.querySelectorAll('svg text')].entries()){e.dataset.compilerTextV2=String(index);const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim())continue;const all=document.createRange();all.selectNodeContents(n);const whole=all.getBoundingClientRect();if(!whole.width||!whole.height)continue;const chars=[];for(const {segment,index:i} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const range=document.createRange();range.setStart(n,i);range.setEnd(n,i+segment.length);const b=range.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}rows.push({source_element_index:index,text:n.textContent,chars});}}return rows;}''')
            objects = [obj for obj in dom['objects'] if obj['type'] == 'text']
            if len(objects) != len(rows):
                raise ValueError('source_text_run_count_mismatch')
            session = context.new_cdp_session(page)
            try:
                session.send('DOM.enable'); session.send('CSS.enable')
                document = session.send('DOM.getDocument', {'depth': 1})['root']['nodeId']
                positions = {}
                for obj, row in zip(objects, rows):
                    if obj['text'] != row['text']:
                        raise ValueError('source_text_order_mismatch')
                    node = session.send('DOM.querySelector', {'nodeId': document, 'selector': '[data-compiler-text-v2="'+str(row['source_element_index'])+'"]'})['nodeId']
                    fonts = session.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
                    positions[obj['id']] = {**row, 'bbox': obj['bbox'], 'fontSize': obj['fontSize'],
                                           'fontFamily': obj['fontFamily'], 'actual_fonts': fonts}
            finally:
                session.detach()
            if blocked:
                raise ValueError('blocked_source_resource_request')
            return positions, dom
        finally:
            context.close(); browser.close()


def _chars(info):
    rows = {}
    for row in info.get('actual_text_positions', []):
        identifier = row['cell']
        if identifier in rows:
            raise ValueError('duplicate_native_text_observation')
        rows[identifier] = [char for run in row['runs'] for char in run['chars']]
    return rows


def _fonts(info):
    return {row['cell']: row['fonts'] for row in info.get('actual_platform_font_usage', [])}


def _font_signature(fonts):
    return sorted((font['postScriptName'], font['glyphCount']) for font in fonts if font.get('glyphCount'))


def offsets(source, native_info):
    """Single whole-run translation only; reject shaping or physical-font loss."""
    observed = _chars(native_info)
    fonts = _fonts(native_info)
    if set(source) != set(observed):
        raise ValueError('source_native_text_object_identity_mismatch')
    result = {}
    for identifier, expected in source.items():
        actual = observed[identifier]
        wanted = expected['chars']
        if not actual or len(actual) != len(wanted) or [row['text'] for row in actual] != [row['text'] for row in wanted]:
            raise ValueError('source_native_graphemes_changed')
        if _font_signature(expected['actual_fonts']) != _font_signature(fonts.get(identifier, [])):
            raise ValueError('source_native_physical_font_mismatch')
        if not all(font.get('isCustomFont') for font in fonts.get(identifier, []) if font.get('glyphCount')):
            raise ValueError('native_fonts_must_be_embedded_before_text_calibration')
        dx = statistics.median(want['x']-got['x'] for want, got in zip(wanted, actual))
        dy = statistics.median(want['y']-got['y'] for want, got in zip(wanted, actual))
        if not all(math.isfinite(value) for value in (dx, dy)) or max(abs(dx), abs(dy)) > MAX_TRANSLATION_PX:
            raise ValueError('source_native_anchor_delta_exceeds_supported_rounding')
        for want, got in zip(wanted, actual):
            if any(not math.isfinite(got[key]) or abs(got[key]-want[key]) > POSITION_TOLERANCE_PX for key in ('width', 'height')):
                raise ValueError('source_native_text_shaping_differs_not_translation')
            if abs(got['x']+dx-want['x']) > POSITION_TOLERANCE_PX or abs(got['y']+dy-want['y']) > POSITION_TOLERANCE_PX:
                raise ValueError('source_native_text_spacing_differs_not_translation')
        result[identifier] = {'dx': dx, 'dy': dy,
                              'applied': max(abs(dx), abs(dy)) > POSITION_TOLERANCE_PX,
                              'graphemes': len(wanted)}
    return result


def _plain(value):
    from auto_quality_source_vector_v2 import _plain as plain
    return plain(value)


def wrap(text, identifier, offset):
    # Relative inline positioning preserves the original line box and shaping.
    # It introduces no line breaks, per-character spans, scaling or kerning.
    return '<span data-compiler-anchor-v2="'+html.escape(identifier, quote=True)+'" style="position:relative;left:'+format(offset['dx'], '.6f')+'px;top:'+format(offset['dy'], '.6f')+'px;">'+html.escape(text)+'</span>'


def apply_offsets(xml, source, corrections):
    root = ET.fromstring(xml)
    cells = {cell.get('id'): cell for cell in root.iter('mxCell')}
    if set(corrections) != set(source):
        raise ValueError('text_correction_mapping_incomplete')
    for identifier, correction in corrections.items():
        cell = cells.get(identifier)
        if cell is None or _plain(cell.get('value')) != source[identifier]['text']:
            raise ValueError('baseline_source_text_changed')
        if correction['applied']:
            # Rewrapping rich font runs could remove per-run style semantics.
            # The input unit is unchanged; unsupported inputs count as failures.
            if '<span' in cell.get('value', '').lower() or '<font' in cell.get('value', '').lower():
                raise ValueError('rich_native_font_runs_require_separate_layout_compiler')
            cell.set('value', wrap(source[identifier]['text'], identifier, correction))
    return ET.tostring(root, encoding='unicode')


def _fingerprint(xml, ignore_registered_geometry=False):
    root = ET.fromstring(xml)
    if ignore_registered_geometry:
        model = root.find('.//mxGraphModel')
        model.attrib.pop('pageWidth', None); model.attrib.pop('pageHeight', None)
        for cell in root.iter('mxCell'):
            geometry = cell.find('mxGeometry')
            if geometry is not None:
                cell.remove(geometry)
    return ET.canonicalize(ET.tostring(root, encoding='unicode'))


def _load_setup(record, xml):
    if sha(xml.encode()) != record['code_sha256']:
        raise ValueError('text_candidate_xml_hash_mismatch')
    descriptor = record.get('compiler_graphviz_visibility_text_v1')
    if not descriptor or descriptor.get('policy') != POLICY:
        raise ValueError('missing_compiler_graphviz_visibility_text_v1_proof')
    proof = json.loads(_read(descriptor['proof_file'], descriptor['proof_sha256']))
    for field in ('id', 'source_code_sha256', 'source_image_sha256', 'source_render_svg_sha256'):
        if proof[field] != record[field]:
            raise ValueError('text_proof_source_identity_changed')
    source = json.loads(_read(proof['source_positions']['file'], proof['source_positions']['sha256']))
    baseline = _read(proof['baseline_xml']['file'], proof['baseline_xml']['sha256']).decode()
    expected = apply_offsets(baseline, source, proof['offsets'])
    registration = record.get('_verified_reference_registration')
    if _fingerprint(expected, bool(registration)) != _fingerprint(xml, bool(registration)):
        raise ValueError('text_calibration_changed_graph_geometry_style_or_content')
    if not registration and sha(expected.encode()) != proof['output_code_sha256']:
        raise ValueError('text_proof_output_revision_changed')
    return proof, source


def validate_registration_setup(record, xml):
    """Only span-delta proof. The caller must validate old canvas/font lineage.

    For an already registered pre-text candidate this returns the hash-bound
    before-text record/XML, rather than claiming current pixels are unchanged.
    """
    result = {'supported': False, 'ok': False, 'profile': POLICY+':registration_setup',
              'failures': [], 'evidence': {}}
    try:
        proof, _ = _load_setup(record, xml)
        baseline = json.loads(_read(proof['baseline_record']['file'], proof['baseline_record']['sha256']))
        baseline_xml = _read(proof['baseline_xml']['file'], proof['baseline_xml']['sha256']).decode()
        for key in ('id', 'source_pair_sha256', 'source_code_sha256', 'source_image_sha256'):
            if baseline.get(key) != record.get(key):
                raise ValueError('before_text_record_source_identity_changed')
        if baseline['code_sha256'] != proof['baseline_xml']['sha256'] or _read(baseline['code_file'], baseline['code_sha256']).decode() != baseline_xml:
            raise ValueError('before_text_record_xml_revision_changed')
        _read(baseline['image_file'], baseline['image_sha256'])
        result.update(supported=True, ok=True, baseline_record=baseline, baseline_xml=baseline_xml,
                      evidence={'span_delta_only': True, 'before_text_record_sha256': proof['baseline_record']['sha256'],
                                'before_text_code_sha256': proof['baseline_xml']['sha256'],
                                'same_native_pixels_claimed': False,
                                'old_canvas_and_font_lineage_must_be_independently_validated': True})
    except Exception as exc:
        result['failures'].append({'reason': str(exc).split(':', 1)[0], 'detail': str(exc)[:2000]})
        result['exception_type'] = type(exc).__name__
        result['infrastructure_failure'] = isinstance(exc, (ImportError, ModuleNotFoundError)) or str(exc).startswith('infrastructure_')
    return result


def validate(record, xml, frontend_report=None):
    report = {'supported': False, 'ok': False, 'profile': POLICY, 'failures': [], 'evidence': {}}
    try:
        proof, source = _load_setup(record, xml)
        baseline_report = scene_v1.validate(record, xml)
        report['evidence']['source_scene_v1'] = baseline_report
        if not baseline_report['supported'] or not baseline_report['ok']:
            report['failures'] = baseline_report['failures']
            report['infrastructure_failure'] = baseline_report.get('infrastructure_failure', False)
            return report
        fresh, _ = source_positions(record)
        if raw(fresh) != raw(source):
            raise ValueError('fresh_source_text_positions_changed')
        report.update(supported=True, ok=True)
        report['evidence'].update(source_positions_sha256=sha(raw(fresh)),
                                 calibrated_text_objects=len(proof['offsets']),
                                 reference_pixels_used_for_alignment=False,
                                 actual_target_glyph_verification_required_after_fresh_render=True)
    except Exception as exc:
        report['failures'].append({'reason': str(exc).split(':', 1)[0], 'detail': str(exc)[:2000]})
        report['exception_type'] = type(exc).__name__
        report['infrastructure_failure'] = isinstance(exc, (ImportError, ModuleNotFoundError)) or str(exc).startswith('infrastructure_')
    return report


def validate_text_render(record, xml, native_info):
    """Must receive this QA invocation's fresh render info, never record.render."""
    report = {'supported': False, 'ok': False, 'profile': POLICY+':fresh_glyphs', 'failures': [], 'evidence': {}}
    try:
        proof, _ = _load_setup(record, xml)
        source, dom = source_positions(record)
        from auto_quality_source_vector_v2 import _paint_coverage
        paint = _paint_coverage(dom, xml)
        if not paint['ok']:
            raise ValueError('text_calibration_source_paint_geometry_changed:'+json.dumps(paint['errors'])[:1200])
        translation = paint['source_layout_translation']
        dx, dy = translation['dx'], translation['dy']
        if max(abs(dx), abs(dy)) > POSITION_TOLERANCE_PX:
            registration = record.get('_verified_reference_registration') or {}
            allowed = registration.get('original_page_offset')
            if not allowed or len(allowed) != 2 or max(abs(dx-allowed[0]), abs(dy-allowed[1])) > POSITION_TOLERANCE_PX:
                raise ValueError('text_translation_lacks_verified_canvas_registration')
        actual = _chars(native_info); fonts = _fonts(native_info)
        if set(source) != set(actual):
            raise ValueError('fresh_native_text_coverage_changed')
        failures, maximum = [], 0.
        for identifier, expected in source.items():
            got = actual[identifier]; wanted = expected['chars']
            if len(got) != len(wanted) or [char['text'] for char in got] != [char['text'] for char in wanted]:
                failures.append({'reason': 'fresh_native_graphemes_changed', 'cell': identifier}); continue
            if _font_signature(expected['actual_fonts']) != _font_signature(fonts.get(identifier, [])):
                failures.append({'reason': 'fresh_native_source_physical_font_changed', 'cell': identifier})
            if not all(font.get('isCustomFont') for font in fonts.get(identifier, []) if font.get('glyphCount')):
                failures.append({'reason': 'fresh_native_font_not_embedded', 'cell': identifier})
            for index, (want, observed) in enumerate(zip(wanted, got)):
                errors = [abs(observed['x']-want['x']-dx), abs(observed['y']-want['y']-dy),
                          abs(observed['width']-want['width']), abs(observed['height']-want['height'])]
                maximum = max(maximum, *errors)
                if any(not math.isfinite(value) or value > POSITION_TOLERANCE_PX for value in errors):
                    failures.append({'reason': 'fresh_native_source_grapheme_position_changed', 'cell': identifier, 'grapheme': index, 'maximum_error_px': max(errors)})
        report.update(supported=True, ok=not failures, failures=failures,
                      evidence={'fresh_native_info_sha256': sha(raw(native_info)), 'fresh_source_positions_sha256': sha(raw(source)),
                                'source_layout_translation': translation, 'text_objects_checked': len(source),
                                'graphemes_checked': sum(len(row['chars']) for row in source.values()),
                                'maximum_position_or_size_error_px': maximum,
                                'tolerance_px': POSITION_TOLERANCE_PX, 'reference_pixels_used_for_alignment': False,
                                'source_paint_coverage': paint})
    except Exception as exc:
        report['failures'].append({'reason': str(exc).split(':', 1)[0], 'detail': str(exc)[:2000]})
        report['exception_type'] = type(exc).__name__
        report['infrastructure_failure'] = isinstance(exc, (ImportError, ModuleNotFoundError)) or str(exc).startswith('infrastructure_')
    return report


def _asset(path):
    blob = Path(path).read_bytes()
    return {'file': str(Path(path).relative_to(R)), 'sha256': sha(blob), 'bytes': len(blob)}


def _render_observed(xml, width, height):
    from native_worker import native
    result = native.native_job(xml, width, height, 150, W/'rendering_paintbounds_strict/remote_render.py',
                               8192, R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not result.get('ok'):
        raise ValueError('text_calibration_native_render_failed:'+json.dumps({key: value for key, value in result.items() if key != 'png'})[:2000])
    info = result['native_render']
    if not all(field in info for field in ('actual_text_positions', 'actual_platform_font_usage')):
        raise RuntimeError('infrastructure_native_text_observer_missing')
    return result['png'], info


def calibrate(record, job, work):
    """Apply one deterministic correction to an already embedded v1 candidate."""
    started = time.monotonic()
    try:
        work = Path(work).resolve()
        if not work.is_relative_to(W.resolve()):
            raise ValueError('text_calibration_work_outside_conversion')
        work.mkdir(parents=True, exist_ok=True)
        xml = _read(record['code_file'], record['code_sha256']).decode()
        from PIL import Image
        width, height = Image.open(io.BytesIO(_read(record['image_file'], record['image_sha256']))).size
        baseline_png, baseline_info = _render_observed(xml, width, height)
        for chars in _chars(baseline_info).values():
            for char in chars:
                if char['text'].strip() and (char['x'] < -POSITION_TOLERANCE_PX or char['y'] < -POSITION_TOLERANCE_PX or char['x']+char['width'] > width+POSITION_TOLERANCE_PX or char['y']+char['height'] > height+POSITION_TOLERANCE_PX):
                    raise ValueError('text_calibration_requires_prior_proven_paint_padding')
        source, _ = source_positions(record)
        # A proven pre-existing canvas offset belongs to the graph/page, not to
        # text. Never subtract that offset as if it were HTML anchor rounding.
        from round2_font_canvas_registration_v1 import registration_record
        reference = _read(record['original_reference'], record['source_image_sha256'])
        _, baseline_contract = registration_record(record, reference, xml)
        alignment_offset = (baseline_contract or {}).get('original_page_offset', [0, 0])
        aligned_source = copy.deepcopy(source)
        for row in aligned_source.values():
            for char in row['chars']:
                char['x'] += alignment_offset[0]; char['y'] += alignment_offset[1]
        corrections = offsets(aligned_source, baseline_info)
        new = apply_offsets(xml, source, corrections)
        png, info = _render_observed(new, width, height)
        dest = R/'clean/compiler_graphviz_visibility_text_v1'/record['id'][:2]/record['id']/uuid.uuid4().hex
        dest.mkdir(parents=True, exist_ok=False)
        for name, blob in [('baseline.drawio', xml.encode()), ('baseline.png', baseline_png),
                           ('baseline_record.json', raw(record)),
                           ('baseline_native_info.json', raw(baseline_info)), ('source_positions.json', raw(source)),
                           ('diagram.drawio', new.encode()), ('image.png', png)]:
            _save(dest/name, blob)
        proof = {'policy': POLICY, 'id': record['id'], 'source_code_sha256': record['source_code_sha256'],
                 'source_image_sha256': record['source_image_sha256'], 'source_render_svg_sha256': record['source_render_svg_sha256'],
                 'baseline_xml': _asset(dest/'baseline.drawio'), 'baseline_native_info': _asset(dest/'baseline_native_info.json'),
                 'baseline_record': _asset(dest/'baseline_record.json'),
                 'source_positions': _asset(dest/'source_positions.json'), 'offsets': corrections,
                 'source_alignment_offset': alignment_offset,
                 'before_text_canvas_contract': baseline_contract,
                 'output_code_sha256': sha(new.encode()), 'reference_pixels_used_for_alignment': False,
                 'method': 'single whole-run inline relative left/top from source minus actual native grapheme range',
                 'cell_geometry_styles_text_topology_unchanged': True,
                 'maximum_translation_px': MAX_TRANSLATION_PX, 'glyph_position_tolerance_px': POSITION_TOLERANCE_PX,
                 'requires_independent_fresh_render_and_full_quality': True, 'model_calls': 0}
        _save(dest/'text_calibration_proof.json', raw(proof))
        out = {**copy.deepcopy(record), 'code_file': str((dest/'diagram.drawio').relative_to(R)), 'code_sha256': sha(new.encode()),
               'image_file': str((dest/'image.png').relative_to(R)), 'image_sha256': sha(png), 'render': info,
               'compiler_graphviz_visibility_text_v1': {'policy': POLICY, 'proof_file': str((dest/'text_calibration_proof.json').relative_to(R)),
                                          'proof_sha256': sha(raw(proof)), 'requires_fresh_native_glyph_check': True},
               'quality_state': 'pending_compiler_text_v2_full_quality'}
        for stale in ('automatic_quality_policy', 'automatic_quality_audit', 'accepted_at_utc', 'native_font_validation'):
            out.pop(stale, None)
        for stale in list(out):
            if stale.startswith('_verified_'):
                out.pop(stale)
        setup = validate(out, new)
        observed_record = out
        if baseline_contract:
            # Only this local freshly validated composition is used for the
            # conversion check; the exported record carries no trusted flag.
            # QA must independently revalidate before-text registration.
            observed_record = {**out, '_verified_reference_registration': {**baseline_contract, 'same_source_text_delta_verified': True}}
        observed = validate_text_render(observed_record, new, info)
        _save(dest/'source_setup_check.json', raw(setup)); _save(dest/'actual_text_render_check.json', raw(observed))
        _save(dest/'candidate_record.json', raw(out))
        if not setup['ok'] or not observed['ok']:
            return {'ok': False, 'reason': 'text_calibration_independent_verification_failed',
                    'source_profile': setup, 'text_render_profile': observed,
                    'candidate_record_file': str((dest/'candidate_record.json').relative_to(R)), 'model_calls': 0}
        return {'ok': True, 'record': out, 'source_profile': setup, 'text_render_profile': observed,
                'model_calls': 0, 'seconds': time.monotonic()-started}
    except Exception as exc:
        return {'ok': False, 'reason': str(exc).split(':', 1)[0], 'detail': str(exc)[:4000],
                'error_type': type(exc).__name__, 'infrastructure_failure': isinstance(exc, (ImportError, ModuleNotFoundError)) or str(exc).startswith('infrastructure_'),
                'model_calls': 0, 'seconds': time.monotonic()-started}


def convert(record, job, work):
    work = Path(work)
    first = scene_v1.convert(record, job, work/'scene_v1')
    if not first.get('ok'):
        return first
    from round2_font_repair_v1 import repair as embed_fonts
    fonts = embed_fonts(first['record'], job, work/'embedded_fonts')
    if not fonts.get('ok'):
        return fonts
    return calibrate(fonts['record'], job, work/'fractional_anchor')


repair = convert
