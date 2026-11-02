"""Independent candidate QA, with no canonical claims or publication API.

New source profiles run in a separate process with explicit data roots. All
existing structure, original-source, portable-font, strict-canvas and local
image gates remain mandatory. A successful report is evidence, not acceptance.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import time
import uuid
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
VERSION = 'independent_svg_source_analytic_bezier_nested_groups_candidate_quality_readonly_session_owner_source_owned_edge_layers_untouched_UA_use_leaf_alpha_interleaving_background_rotation_local_anchor_painter_frame_rotated_visual_scope_v23'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()


def identity(record, job):
    original = json.loads(job['input_record'])
    require(job['category'] in ('scientific_diagram', 'poster'), 'outside_requested_scope')
    require(job['id'] == record['id'] == original['pair_sha256'] == record['source_pair_sha256'], 'original_pair_identity_changed')
    require(job['source'] == original['source'] == record['source'], 'original_dataset_changed')
    require(job['category'] == original['category'] == record['category'], 'original_category_changed')
    require(job['format'] == original['format'] == record['source_format'], 'original_format_changed')
    for key in ('code', 'image'):
        require(record['source_' + key + '_sha256'] == original[key + '_sha256'], 'original_' + key + '_hash_changed')
    require(record.get('format') == 'drawio', 'candidate_is_not_editable_drawio')
    return original


def source_gate(result):
    require(isinstance(result, dict), 'source_hook_did_not_return_evidence')
    require(result.get('supported') is True, 'source_profile_unsupported')
    require(result.get('ok') is True and not result.get('failures'), 'source_profile_failed')
    require(bool(result.get('profile')) and isinstance(result.get('evidence'), dict), 'source_profile_missing_named_evidence')
    evidence = result['evidence']
    require(evidence.get('complete_source_coverage') is True, 'source_profile_only_proves_partial_coverage')
    text_ids = evidence.get('required_text_cell_ids')
    require(isinstance(text_ids, list) and all(isinstance(item, str) and item for item in text_ids)
            and len(set(text_ids)) == len(text_ids), 'source_profile_has_no_complete_unique_text_inventory')


def actual_fonts(render):
    usage = [font for row in render.get('actual_platform_font_usage', [])
             for font in row.get('fonts', []) if font.get('glyphCount', 0) > 0]
    require(not render.get('actual_text_positions') or usage, 'rendered_text_has_no_physical_font_evidence')
    require(all(font.get('isCustomFont') is True for font in usage), 'actual_font_portability_requires_embedding')
    return {'all_rendered_fonts_embedded': True, 'actual_custom_font_glyphs': sum(font['glyphCount'] for font in usage)}


def pins_unchanged(pins):
    require(bool(pins), 'empty_profile_implementation_pins')
    for name, digest in pins.items():
        require(Path(name).is_absolute() and re.fullmatch('[0-9a-f]{64}', digest) is not None, 'invalid_profile_pin')
        require(sha(Path(name).read_bytes()) == digest, 'implementation_changed:' + name)


def source_profile(plugin, record, xml, source, data_root, native_info=None):
    try:
        return plugin.check_source(record, xml, source, data_root, native_info=native_info)
    finally:
        # A source browser may not remain active while the independent native
        # renderer or editing runtime starts another Playwright Sync context.
        if hasattr(plugin, 'close_worker_runtime'):
            plugin.close_worker_runtime()


def load_plugin(path):
    path = Path(path).resolve(strict=True)
    require(path.is_relative_to(W.resolve()), 'source_hook_outside_owned_remote_conversion')
    spec = importlib.util.spec_from_file_location('candidate_quality_profile_' + sha(str(path).encode())[:16], path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, path


def job_snapshot(db, identifier):
    columns = [row[1] for row in db.execute('pragma table_info(jobs)')]
    row = db.execute('select * from jobs where id=?', (identifier,)).fetchone()
    require(row is not None, 'missing_authoritative_original_job')
    return dict(zip(columns, row))


def verify(identifier, record_file, data_root, plugin_file, work, database=W / 'jobs.sqlite'):
    import compiler_svg_general_guard_v14 as generation
    from compiler_source_core_attempts_v3 import core_identity
    require(Path(plugin_file).resolve()==Path(generation.__file__).resolve(),'wrong_frozen_SVG_generation_plugin')
    generation_configuration=generation.configuration(data_root)
    plugin_file=Path(__file__).with_name('compiler_svg_general_quality_adapter_v19.py')
    from PIL import Image
    from auto_quality_common_v4 import checked, structure_checks, resource_checks, image_quality, require_rendered_text
    from clip_canvas_render_v4b import render
    from strict_canvas_gate import require_declared_page

    started = time.monotonic()
    data_root = Path(data_root).resolve(strict=True)
    require(data_root.is_relative_to(R.resolve()), 'candidate_data_must_remain_on_remote_registered_root')
    work = Path(work).resolve()
    require(work.is_relative_to(W / 'prototype/candidate_quality_ro_v1'), 'unowned_quality_evidence_directory')
    require(not work.exists(), 'quality_evidence_directory_must_be_new')
    work.mkdir(parents=True)
    db = sqlite3.connect('file:' + str(Path(database).resolve()) + '?mode=ro', uri=True, timeout=60, isolation_level=None)
    report = {'version': VERSION, 'id': identifier, 'checks': {}, 'failures': [], 'ok': False,
              'accepted': False, 'canonical_mutations': 0, 'model_calls': 0, 'data_root': str(data_root)}
    record_raw = Path(record_file).read_bytes()
    record = json.loads(record_raw)
    try:
        db.execute('BEGIN')
        original_job = job_snapshot(db, identifier)
        require(original_job['worker_pid'] is None, 'authoritative_job_currently_owned')
        original = identity(record, original_job)
        db.rollback()
        plugin, plugin_path = load_plugin(plugin_file)
        config = plugin.configuration(data_root)
        pins = dict(config['pins'])
        require(pins.get(str(plugin_path)) == sha(plugin_path.read_bytes()), 'source_hook_not_self_pinned')
        pins[str(Path(__file__).resolve())] = sha(Path(__file__).read_bytes())
        import auto_quality_batch_v4b as qa
        for name, digest in qa.IMPLEMENTATION.items():
            full = Path(name) if Path(name).is_absolute() else Path(qa.__file__).parent / name
            require(str(full) not in pins or pins[str(full)] == digest, 'conflicting_quality_dependency_pin')
            pins[str(full)] = digest
        pins_unchanged(pins)
        report.update(generation_source_core=core_identity(generation_configuration),generation_configuration=generation_configuration,profile_policy=config['policy'], implementation_pins=pins, input_record_sha256=sha(record_raw),
                      quality_policy=VERSION + ':' + sha(canonical(pins))[:20])
        xml = checked(data_root, record['code_file'], record['code_sha256']).decode()
        checked(data_root, record['image_file'], record['image_sha256'])
        reference = checked(data_root, record['original_reference'], record['source_image_sha256'])
        source = checked(data_root, record['original_source_code'], record['source_code_sha256']).decode()
        report['checks']['structure'] = plugin.structure_checks(xml,record=record) if hasattr(plugin,'structure_checks') else structure_checks(xml)
        if hasattr(plugin, 'registration_record'):
            public_before = {key: value for key, value in record.items() if not key.startswith('_verified_')}
            record, contract = plugin.registration_record(record, reference, xml, data_root)
            require({key: value for key, value in record.items() if not key.startswith('_verified_')} == public_before,
                    'registration_hook_changed_public_candidate_metadata')
            if contract:
                report['checks']['reference_registration'] = contract
        report['checks']['resources'] = resource_checks(data_root, record, xml, reference)
        model = ET.fromstring(xml).find('.//mxGraphModel')
        dimensions = [float(model.get(name, 0)) for name in ('pageWidth', 'pageHeight')]
        require(all(math.isfinite(value) and value == round(value) and 0 < value <= 8192 for value in dimensions), 'unsupported_native_canvas')
        width, height = map(int, dimensions)
        if not config.get('source_requires_native_info', False):
            preliminary = source_profile(plugin, record, xml, source, data_root)
            report['checks']['source_preliminary'] = preliminary
            source_gate(preliminary)
        renderer = W / 'rendering_paintbounds_strict/remote_render.py'
        result = render(xml, width, height, 180, renderer, 8192,
                        R / 'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
        require(result.get('ok') is True, 'fresh_native_render_failed')
        png = result['png']
        info = result['native_render']
        require_declared_page(info, width, height)
        require(Image.open(io.BytesIO(png)).size == (width, height), 'native_png_canvas_changed')
        report['checks']['render'] = {'code_sha256': sha(xml.encode()), 'image_sha256': sha(png),
                                      'canvas': [width, height], 'strict_outside_page_pixels': 0,
                                      'strict_clip_canvas_proof': info.get('clip_canvas_strict_proof_v4b')}
        # Preserve already completed stages even when a later whole-source gate
        # rejects a partial producer. These are remote diagnostic artifacts.
        (work / 'fresh_native.png').write_bytes(png)
        (work / 'native_render.json').write_bytes(canonical(info))
        profile = source_profile(plugin, record, xml, source, data_root, native_info=info)
        report['checks']['source'] = profile
        source_gate(profile)
        report['checks']['text_paint'] = require_rendered_text(xml, info)
        actual_text = {row['cell'] for row in info.get('actual_text_positions', [])
                       if any(char.get('text', '').strip() and char.get('width', 0) > 0 and char.get('height', 0) > 0
                              for run in row.get('runs', []) for char in run.get('chars', []))}
        require(set(profile['evidence']['required_text_cell_ids']) <= actual_text, 'original_source_text_missing_from_actual_native_render')
        report['checks']['fonts'] = actual_fonts(info)
        require(hasattr(plugin, 'quality_visual'), 'source_profile_has_no_staged_visual_verifier')
        visual = plugin.quality_visual(record, xml, info, png, reference, profile, data_root)
        report['checks']['visual'] = visual
        require(visual.get('ok') is True, 'raster_anomaly:' + ','.join(visual['failures']))
        require(hasattr(plugin, 'audit_editing'), 'source_profile_has_no_actual_native_editing_verifier')
        editing = plugin.audit_editing(record, xml, profile, data_root)
        report['checks']['native_editing'] = editing
        require(editing.get('ok') is True, 'actual_native_editing_failed')
        # The producer's proposed stored PNG must be the actual declared-page
        # renderer result; an observational padded image is never substituted.
        proposed = checked(data_root, record['image_file'], record['image_sha256'])
        require(Image.open(io.BytesIO(proposed)).convert('RGBA').tobytes() == Image.open(io.BytesIO(png)).convert('RGBA').tobytes()
                and Image.open(io.BytesIO(proposed)).size == (width, height), 'proposed_png_differs_from_fresh_declared_native_page')
        pins_unchanged(pins)
        require(Path(record_file).read_bytes() == record_raw, 'proposal_metadata_changed_during_quality_work')
        checked(data_root, record['code_file'], record['code_sha256'])
        db.execute('BEGIN')
        require(job_snapshot(db, identifier) == original_job, 'authoritative_job_changed_during_quality_work')
        db.rollback()
        (work / 'fresh.png').write_bytes(png)
        report['ok'] = True
        report['original_source'] = original
    except Exception as error:
        if db.in_transaction:
            db.rollback()
        report['failures'].append({'type': type(error).__name__, 'reason': str(error)[:4000]})
    finally:
        db.close()
    report['seconds'] = round(time.monotonic() - started, 3)
    report['evidence_file'] = str(work / 'report.json')
    (work / 'report.json').write_bytes(canonical(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--work', type=Path, default=W / 'prototype/candidate_quality_ro_v1' / uuid.uuid4().hex)
    args = parser.parse_args()
    print(json.dumps(verify(args.id, args.record, args.data_root, args.plugin, args.work)))
