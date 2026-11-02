"""Add an actually reviewed, full-QA scientific pair without changing old views."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import os
import uuid

R = Path('/backup/shaoshitong/img2code_20261029')
C = R / 'clean/complexity_curation_20261102T054553Z_v1'
NORMAL = R / 'conversion/compiler_svg_scene_frontend_v8/normal_development_v1/8a1226994ed24fa08ee94a53d3b87fd8/2a6f2b074d5050fc30f67a12a516aca7ab0ec7764a747b07a0846c020ded0251/summary.json'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def raw(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def asset(path):
    return {'file': str(path.relative_to(R)), 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}


def main():
    before = (C / 'current.json').read_bytes()
    pointer = json.loads(before)
    locator = pointer['views']['paired_priority_complex']
    body = (R / locator['file']).read_bytes()
    assert sha(body) == locator['sha256']
    rows = [json.loads(line) for line in body.splitlines() if line]
    normal = json.loads(NORMAL.read_bytes())
    assert normal['quality_ok'] and normal['canonical_unchanged']
    pair = normal['qualified_manifest']
    assert pair['id'] not in {row['id'] for row in rows}, 'already_added_preserve_current'
    for field, digest in [('code_file', 'code_sha256'), ('image_file', 'image_sha256'),
                          ('metadata_file', 'metadata_sha256'), ('original_source_code', 'source_code_sha256'),
                          ('original_reference', 'source_image_sha256')]:
        path = (R / pair[field]).resolve(strict=True)
        assert path.is_relative_to((R / 'clean').resolve()) and sha(path.read_bytes()) == pair[digest]
    import sys
    sys.path.insert(0, str(R / 'conversion/scripts'))
    import compiler_svg_general_guard_v4 as compiler
    import svg_analytic_iteration_controls_v3 as quality
    report_path = Path(normal['quality_report'])
    report = json.loads(report_path.read_bytes())
    record = json.loads((R / pair['metadata_file']).read_bytes())
    quality.full_quality(report, record, compiler.configuration(), asset(report_path.parent / 'native_render.json'))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    review = {'id': pair['id'], 'recorded_at_utc': now, 'verdict': 'reviewed_complex_scientific_diagram',
        'review_method': 'Visual inspection of the actual native PNG plus existing independent full-eight source/editing QA.',
        'image_file': pair['image_file'], 'image_sha256': pair['image_sha256'],
        'source_code_sha256': pair['source_code_sha256'], 'source_image_sha256': pair['source_image_sha256'],
        'previous_automatic_source_screen': 'structure_review', 'previous_source_screen_preserved': True,
        'observed_content': 'Two-panel Multi-turn 3D-SPO versus GRPO comparison: policy/reference/reward models, grouped trajectories or rewards, grouped advantages and KL/refinement feedback edges.',
        'complexity_basis': 'Multiple algorithm panels, nested functional groups, many distinct research labels and feedback relationships; no webpage UI or incomplete source content.',
        'fidelity_and_editability': 'Existing full-eight QA and actual source primitive, text, font, marker and editing evidence; no raster wrapper acceptance.',
        'review_is_not_a_claim_of_scientific_correctness': True, 'external_model_calls': 0}
    output = C / ('published_current_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_review_v5')
    output.mkdir()
    review_path = output / 'value_review.json'
    review_path.write_bytes(raw(review))
    pair = {**pair, 'curation': {'selection': 'visually_reviewed_complex_scientific_comparison',
        'previous_source_status': 'structure_review', 'review': asset(review_path),
        'recorded_full_quality_reused': True, 'source_index_and_old_qualifications_modified': False}}
    rows.append(pair)
    mainfile = output / 'paired_priority_complex.jsonl'
    mainfile.write_bytes(b''.join((json.dumps(row, sort_keys=True) + '\n').encode() for row in sorted(rows, key=lambda row: row['id'])))
    main_asset = {**asset(mainfile), 'rows': len(rows)}
    parent_summary = json.loads((R / pointer['summary']['file']).read_bytes())
    summary = {**parent_summary, 'schema': 'reviewed_complex_curation_snapshot_v5', 'at_utc': now,
        'root': str(output), 'paired_priority_complex': len(rows),
        'paired_priority_by_source': dict(collections.Counter(row['source'] for row in rows)),
        'paired_priority_by_format': dict(collections.Counter(row['source_format'] for row in rows)),
        'reviewed_complex_additions': [pair['id']], 'value_review': asset(review_path),
        'refresh_scope': 'One full-QA pair added after direct scientific-content review; every other frozen view is inherited unchanged.',
        'inherited_view_snapshot_at_utc': pointer['at_utc'], 'new_conversions': 0, 'new_QA_calls': 0,
        'producer_sha256': sha(Path(__file__).read_bytes()), 'goal_complete': False}
    summary_path = output / 'summary.json'
    summary_path.write_bytes(raw(summary))
    previous = output / 'previous_current_snapshot.json'
    previous.write_bytes(before)
    inventory = output / 'hash_inventory.json'
    inventory.write_bytes(raw({'main': main_asset, 'summary': asset(summary_path), 'review': asset(review_path),
                               'parent_pointer': asset(previous), 'inherited_views': pointer['views']}))
    current = {**pointer, 'schema': 'curated_current_pointer_v5', 'at_utc': now,
        'snapshot': str(output.relative_to(R)), 'summary': asset(summary_path), 'hash_inventory': asset(inventory),
        'views': {**pointer['views'], 'paired_priority_complex': main_asset},
        'paired_priority_complex': len(rows), 'previous_current_snapshot': asset(previous)}
    assert (C / 'current.json').read_bytes() == before, 'concurrent_pointer_change_preserve_existing'
    temporary = C / ('current.' + uuid.uuid4().hex + '.tmp')
    temporary.write_bytes(raw(current))
    os.replace(temporary, C / 'current.json')
    for path in output.iterdir():
        path.chmod(0o444)
    print(json.dumps({'paired_priority_complex': len(rows), 'added_id': pair['id'],
        'main': main_asset, 'review': asset(review_path), 'current_pointer': asset(C / 'current.json'),
        'new_QA_calls': 0, 'new_conversions': 0}), flush=True)


if __name__ == '__main__':
    main()
