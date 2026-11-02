"""Normalize the frozen actual CoSyn controls for fixed-program validation."""
import argparse
import datetime
import json
from pathlib import Path
import sqlite3

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
ADAPTER=R/'release/compiler_python_cosyn_adapter_controls_v1/a213_official_frame_20261101_v1/receipt.json'
EXPECTED='3dcadbce5edff2250e5a76e977a9e67817144ec64410592c7876681aff7d1cec'
DEFAULT=R/'release/compiler_iterations/controls/python_cosyn_forward_controls_20261101_v1'


def main(output=DEFAULT):
    import compiler_python_cosyn_frontend_v1 as frontend
    import compiler_python_cosyn_iteration_case_v1 as case
    import compiler_python_cosyn_iteration_program_v1 as program
    import compiler_graphviz_visibility_text_v1 as renderer
    import compiler_types_program_v1 as common
    from qualified_index_v4 import manifest_row,require_source
    output=Path(output).resolve()
    if not output.is_relative_to((R/'release/compiler_iterations/controls').resolve()):raise ValueError('CoSyn_controls_outside_owner')
    blob=ADAPTER.read_bytes()
    if common.sha(blob)!=EXPECTED:raise ValueError('frozen_CoSyn_adapter_receipt_changed')
    adapter=json.loads(blob);config=frontend.configuration()
    if not adapter['ok']or adapter['source_frontend_policy']!=config['policy']or adapter['source_frontend_pins']!=config['pins']:raise ValueError('CoSyn_frozen_controls_or_frontend_changed')
    actual=adapter['positive'];record_path=Path(actual['record_file']);record=json.loads(record_path.read_bytes());qa_path=Path(actual['report_file']);qa=json.loads(qa_path.read_bytes())
    if common.sha(record_path.read_bytes())!=actual['record_sha256']or common.sha(qa_path.read_bytes())!=actual['report_sha256']:raise ValueError('CoSyn_positive_control_changed')
    positive=dict(name='a213_full_official_forward_native',id=record['id'],candidate=common.asset(record_path),qa=common.asset(qa_path),fresh_png=dict(file=record['image_file'],sha256=record['image_sha256']),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'])
    program.check_control_case(positive,'positive',config)
    negatives=[]
    for old in adapter['semantic_negatives']:
        candidate_path=Path(old['candidate_file']);candidate=json.loads(candidate_path.read_bytes());report_path=Path(old['report']);report=json.loads(report_path.read_bytes())
        actual_xml=(R/candidate['code_file']).read_text();width,height=candidate['render']['canvas'];png,info=renderer._render_observed(actual_xml,width,height)
        if common.sha(png)!=candidate['image_sha256']or candidate['image_sha256']==record['image_sha256']or candidate['code_sha256']==record['code_sha256']:raise ValueError('CoSyn_semantic_negative_not_actual_rerendered_intervention')
        row=dict(name=old['kind'],id=candidate['id'],candidate=common.asset(candidate_path),qa=common.asset(report_path),fresh_png=dict(file=candidate['image_file'],sha256=candidate['image_sha256']),source_code_sha256=candidate['source_code_sha256'],source_image_sha256=candidate['source_image_sha256'],actual_rerendered_pixels_changed=True,code_and_image_rehashed=True)
        program.check_control_case(row,'negative',config);negatives.append(row)
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:source=json.loads(db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0])
    require_source(record,source);accepted={**record,'quality_state':'accepted_fresh_official_CoSyn_forward_control_v1','automatic_quality_policy':qa['quality_policy'],'automatic_quality_audit':str(qa_path.relative_to(R)),'accepted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_configuration':dict(external_model_calls=0,deterministic_compiler=True)}
    manifest=manifest_row(accepted,R)[0]
    output.mkdir(parents=True,exist_ok=False);common.immutable(output/'qualified.jsonl',common.raw(manifest))
    proof=dict(schema='compiler_python_cosyn_iteration_controls_v1',frozen_frontend=config,adapter_receipt=common.asset(ADAPTER),producer=common.asset(Path(__file__)),positive_cases=[positive],negative_cases=negatives,target_codec_edit_save=[common.asset(R/qa['checks']['native_editing']['every_object_proof'])],qualified_manifest=common.asset(output/'qualified.jsonl'),all_actual_controls_rechecked=True,model_calls=0,new_heldout_consumed=0,canonical_mutations=0)
    common.immutable(output/'proof.json',common.raw(proof));program.check_controls({**proof,'definition':common.asset(output/'proof.json')})
    return dict(proof=common.asset(output/'proof.json'),qualified=1,positive=1,semantic_negatives=2)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT);args=parser.parse_args();print(json.dumps(main(args.output)))
