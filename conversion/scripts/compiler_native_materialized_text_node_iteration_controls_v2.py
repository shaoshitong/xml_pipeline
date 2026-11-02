"""Publish hash-bound real controls for materialized native Text font capture."""
import datetime
import json
from pathlib import Path
import sqlite3

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
ADAPTER = R / 'release/compiler_native_materialized_text_node_v2/controls/actual_20261101_v1/receipt.json'
DEVELOPMENT = W / 'compiler_native_materialized_text_node_dev_v2/3a15781311874a68ad6406b521b8ff07/summary.json'
OUTPUT = R / 'release/compiler_iterations/controls/native_materialized_text_node_controls_20261101_v2'


def run():
    import compiler_native_source_repair_frontend_v2 as frontend
    import compiler_native_source_repair_iteration_case_v1 as quality_contract
    import compiler_native_source_repair_iteration_program_v1 as control_contract
    import compiler_types_program_v1 as common
    import compiler_iteration_inventory_v1 as inventory
    from qualified_index_v4 import manifest_row, require_source

    adapter = json.loads(ADAPTER.read_bytes())
    config = frontend.configuration()
    if adapter.get('ok') is not True or adapter['configuration'] != config:
        raise ValueError('materialized_text_control_configuration_changed')
    positives = list(adapter['positive'])
    negatives = list(adapter['negative'])
    for row in json.loads(DEVELOPMENT.read_bytes())['results']:
        if row.get('quality_ok') is not True:
            continue
        candidate = Path(row['candidate_file'])
        record = json.loads(candidate.read_bytes())
        positives.append(dict(id=row['id'], candidate=common.asset(candidate),
                              qa=common.asset(Path(row['quality_report'])),
                              code=common.asset(R / record['code_file']),
                              fresh_png=common.asset(R / record['image_file']),
                              source_code_sha256=record['source_code_sha256'],
                              source_image_sha256=record['source_image_sha256'],
                              actual_full_QA=True))
    if len(positives) != 3 or len({row['id'] for row in positives}) != 3 or len(negatives) != 2:
        raise ValueError('materialized_text_actual_controls_incomplete')
    for role, entries in (('positive', positives), ('negative', negatives)):
        for row in entries:
            control_contract.check_control_case(row, role, config)

    manifests = []
    hashes = {}
    for row in positives:
        record = json.loads(Path(row['candidate']['file']).read_bytes())
        qa = json.loads(Path(row['qa']['file']).read_bytes())
        quality_contract.full_quality(qa, record)
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as database:
            job = database.execute('select * from jobs where id=?', (row['id'],)).fetchone()
        source = json.loads(job[4])
        require_source(record, source)
        fresh = (Path(row['qa']['file']).parent / 'fresh.png').read_bytes()
        if common.sha(fresh) != record['image_sha256'] or fresh != (R / record['image_file']).read_bytes():
            raise ValueError('materialized_text_actual_fresh_image_changed')
        accepted = {**record,
                    'quality_state': 'accepted_complete_materialized_Text_backend_fonts_v2',
                    'automatic_quality_policy': qa['quality_policy'],
                    'automatic_quality_audit': str(Path(row['qa']['file']).relative_to(R)),
                    'accepted_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'model': None,
                    'model_configuration': {'external_model_calls': 0, 'deterministic_compiler': True}}
        manifest = manifest_row(accepted, R)[0]
        inventory.check_manifest(R, row['id'], source, manifest, hashes)
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as database:
            if database.execute('select * from jobs where id=?', (row['id'],)).fetchone() != job:
                raise RuntimeError('infrastructure_materialized_text_canonical_changed')
        manifests.append(manifest)
    OUTPUT.mkdir(parents=True, exist_ok=False)
    common.immutable(OUTPUT / 'qualified.jsonl', b''.join(common.raw(row) for row in sorted(manifests, key=lambda x: x['id'])))
    proof = dict(schema='compiler_native_materialized_text_node_controls_v2',
                 frozen_frontend=config, producer=common.asset(Path(__file__)),
                 adapter_receipt=common.asset(ADAPTER), development_receipt=common.asset(DEVELOPMENT),
                 positive_cases=positives, negative_cases=negatives,
                 actual_endpoint_editing_reports=[row['qa'] for row in positives],
                 qualified_manifest=common.asset(OUTPUT / 'qualified.jsonl'),
                 normal_conversions_in_this_publication=0, new_heldout_consumed=0,
                 canonical_mutations=0, model_calls=0, goal_complete=False)
    common.immutable(OUTPUT / 'proof.json', common.raw(proof))
    return dict(proof=common.asset(OUTPUT / 'proof.json'), positive_cases=len(positives),
                actual_rerendered_semantic_negatives=len(negatives),
                checked_clean_asset_hashes=len(hashes), new_unique_development_qualified=1,
                goal_complete=False)


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False))
