"""Close existing actual QA controls; no conversion, layout or QA rerun."""
from pathlib import Path
import hashlib
import json
import sys

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
S = W / 'scripts'
sys.path.insert(0, str(S))
import compiler_svg_general_guard_v4 as compiler
import compiler_source_core_attempts_v3 as history
import svg_analytic_iteration_controls_v3 as controls
from compiler_svg_general_iteration_case_v2 import publish


def raw(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def asset(path):
    return {'file': str(path.relative_to(R)), 'sha256': sha(path.read_bytes())}


def immutable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == body, 'immutable_closure_collision:' + str(path)
    else:
        path.write_bytes(body)
        path.chmod(0o444)


def main():
    normal_work = W / 'compiler_svg_scene_frontend_v8/normal_development_v1/8a1226994ed24fa08ee94a53d3b87fd8/2a6f2b074d5050fc30f67a12a516aca7ab0ec7764a747b07a0846c020ded0251'
    control_run = W / 'svg_nested_groups_controls_v1/ae4e99f7d98b4596a47f2ae3e578e94d'
    normal = json.loads((normal_work / 'summary.json').read_bytes())
    cfg = compiler.configuration()
    assert normal['quality_ok'] and normal['canonical_unchanged']
    assert normal['source_core'] == history.core_identity(cfg)
    root = R / 'release/compiler_iterations/controls/svg_source_nested_groups_20261102_v1'
    root.mkdir(parents=True, exist_ok=True)
    candidate = Path(normal['candidate_file'])
    qa = Path(normal['quality_report'])
    record = json.loads(candidate.read_bytes())
    positive = [{'id': record['id'], 'name': 'new_normal_nested_groups',
        'source_code_sha256': record['source_code_sha256'], 'source_image_sha256': record['source_image_sha256'],
        'candidate': asset(candidate), 'qa': asset(qa), 'native_render': asset(qa.parent / 'native_render.json'),
        'fresh_png': asset(R / record['image_file']), 'normal_conversion_calls': 1}]
    second_candidate = R / 'clean/svg_nested_groups_controls_v1/positive/c9923bb0b4f24a2489a6c3bb74557833/record.json'
    second_qa = W / 'prototype/candidate_quality_ro_v1/SVG_nested_groups_positive_a67597a84db04bb8a31bdec69b686973/report.json'
    second = json.loads(second_candidate.read_bytes())
    positive.append({'id': second['id'], 'name': 'preserved_existing_complex_pair',
        'source_code_sha256': second['source_code_sha256'], 'source_image_sha256': second['source_image_sha256'],
        'candidate': asset(second_candidate), 'qa': asset(second_qa),
        'native_render': asset(second_qa.parent / 'native_render.json'),
        'fresh_png': asset(R / second['image_file']), 'normal_conversion_calls': 0})
    negative = [json.loads((control_run / role / 'case/summary.json').read_bytes())['control']
                for role in ('negative_text', 'negative_geometry')]
    for row in positive:
        controls.check_control_case(row, 'positive', cfg)
    for row in negative:
        controls.check_control_case(row, 'negative', cfg)
    second_report = json.loads(second_qa.read_bytes())
    second_source = second.get('source_record')
    if not second_source:
        import sqlite3
        with sqlite3.connect((W / 'jobs.sqlite').as_uri() + '?mode=ro', uri=True) as db:
            second_source = json.loads(db.execute('select input_record from jobs where id=?', (second['id'],)).fetchone()[0])
    qualified = [normal['qualified_manifest'], publish(second, second_source, second_report, second_qa.parent)]
    manifest = root / 'qualified.jsonl'
    immutable(manifest, b''.join(raw(row).replace(b'\n', b'') + b'\n' for row in qualified))
    receipt = root / 'normal_history_receipt.json'
    immutable(receipt, raw({'rows': [normal]}))
    base_path = R / history.CATALOG
    catalog = json.loads(base_path.read_bytes())
    declaration = {'source_core_key': history.core_identity(cfg)['key'], 'id': normal['id'],
        'source': normal['source'], 'receipt': asset(receipt), 'rows_key': 'rows', 'row_index': 0,
        'normal_count_key': 'normal_frontend_calls', 'requires_unchanged_canonical': True,
        'frontend': asset(normal_work / 'frontend_result.json')}
    assert not any(item['source_core_key'] == declaration['source_core_key'] and item['id'] == declaration['id'] for item in catalog['entries'])
    catalog = {**catalog, 'entries': catalog['entries'] + [declaration],
               'preserved_parent_catalog': asset(base_path)}
    catalog_path = R / 'release/compiler_iterations/source_core_attempts/manual_catalog_svg_nested_groups_20261102_v4.json'
    immutable(catalog_path, raw(catalog))
    methods = [Path(__file__), S / 'svg_analytic_iteration_controls_v3.py', S / 'strict_native_canvas_evidence_v1.py']
    bundle = {'schema': 'actual_SVG_nested_groups_controls_v1', 'frozen_frontend': cfg,
        'source_core': history.core_identity(cfg), 'positive_cases': positive, 'negative_cases': negative,
        'qualified_manifest': asset(manifest), 'producer': asset(Path(__file__)),
        'method_pins': {str(path): sha(path.read_bytes()) for path in methods},
        'strict_canvas_evidence': 'Existing exact native padded-pixel and DOM-bound artifacts, bound by hashes; clip fallback is optional when the strict renderer ran directly.',
        'original_QA_reports_modified': False, 'new_normal_calls': 0, 'new_QA_calls': 0,
        'new_model_calls': 0, 'goal_complete': False}
    proof = root / 'proof.json'
    immutable(proof, raw(bundle))
    print(json.dumps({'proof': asset(proof), 'catalog': asset(catalog_path),
                      'source_core': history.core_identity(cfg), 'positive_cases': len(positive),
                      'negative_cases': len(negative), 'new_normal_calls': 0, 'new_QA_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
