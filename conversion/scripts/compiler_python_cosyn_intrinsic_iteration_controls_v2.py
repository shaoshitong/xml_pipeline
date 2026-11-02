"""Finite revalidation of two consumed positives and three actual negatives."""
import argparse
import datetime
import json
from pathlib import Path
import sqlite3
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
ADAPTER=R/'release/compiler_python_cosyn_intrinsic_adapter_controls_v2/frozen_spacing5a_fullQA_20261101_v2/receipt.json'
EXPECTED='69381cfbf24f3ffae3ce8b726ee8c9baebe06d0a58d2497abde3cd1334fba49a'
DEFAULT=R/'release/compiler_iterations/controls/python_cosyn_intrinsic_controls_20261101_v2'
IDS=('5a168a15ecd06ff195a1910509f228151d223045bbf38535da73141350c9e95b','a213c15534b068ae23a356f04358c364d1c112323692ed390e7709deffe8300b')


def main(output=DEFAULT):
    import compiler_python_cosyn_intrinsic_frontend_claims_v2 as frontend
    import compiler_python_cosyn_intrinsic_quality_ro_claims_v2 as quality
    import compiler_python_cosyn_intrinsic_case_v2 as case
    import compiler_python_cosyn_intrinsic_program_v2 as program
    import compiler_graphviz_visibility_text_v1 as renderer
    import compiler_types_program_v1 as common
    from qualified_index_v4 import manifest_row,require_source
    output=Path(output).resolve()
    if not output.is_relative_to((R/'release/compiler_iterations/controls').resolve()):raise ValueError('intrinsic_controls_outside_owner')
    payload=ADAPTER.read_bytes()
    if common.sha(payload)!=EXPECTED:raise ValueError('frozen_intrinsic_adapter_receipt_changed')
    adapter=json.loads(payload);config=frontend.configuration();output.mkdir(parents=True,exist_ok=False)
    positives=[];negatives=[];codec=[];accepted={};positive_images={}
    for identifier in IDS:
        original=W/'compiler_python_cosyn_intrinsic_diagnostic_v2/consumed3_fullQA_20261101_v1'/identifier/'compile/candidate_record.json'
        destination=R/'clean/compiler_python_cosyn_intrinsic_controls_v2'/identifier[:2]/identifier/uuid.uuid4().hex
        destination.mkdir(parents=True,exist_ok=False);candidate=destination/'positive.candidate.json';common.immutable(candidate,original.read_bytes());record=json.loads(candidate.read_bytes())
        work=W/'prototype/candidate_quality_ro_v1'/('intrinsic_claims_positive_'+identifier[:8]+'_'+uuid.uuid4().hex)
        report=quality.verify(identifier,candidate,R,frontend.__file__,work);case.full_quality(report,record)
        row=dict(name='intrinsic_complete_'+identifier[:8],id=identifier,candidate=common.asset(candidate),qa=common.asset(work/'report.json'),fresh_png=dict(file=record['image_file'],sha256=record['image_sha256']),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'])
        program.check_control_case(row,'positive',config);positives.append(row);positive_images[identifier]=record['image_sha256'];codec.append(common.asset(R/report['checks']['native_editing']['every_object_proof']))
        with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:source=json.loads(db.execute('select input_record from jobs where id=?',(identifier,)).fetchone()[0])
        require_source(record,source);published={**record,'quality_state':'accepted_fresh_intrinsic_integer_viewport_claim_control_v2','automatic_quality_policy':report['quality_policy'],'automatic_quality_audit':str((work/'report.json').relative_to(R)),'accepted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_configuration':dict(external_model_calls=0,deterministic_compiler=True)}
        accepted[identifier]=manifest_row(published,R)[0]
    for old in adapter['semantic_negatives']:
        candidate=Path(old['candidate_file']);record=json.loads(candidate.read_bytes());xml=(R/record['code_file']).read_text();width,height=record['render']['canvas'];png,_=renderer._render_observed(xml,width,height)
        if common.sha(png)!=record['image_sha256']or common.sha(xml.encode())!=record['code_sha256']or record['image_sha256']==positive_images[record['id']]:raise ValueError('semantic_negative_not_actual_distinct_rerendered_candidate')
        work=W/'prototype/candidate_quality_ro_v1'/('intrinsic_claims_negative_'+old['kind']+'_'+uuid.uuid4().hex);report=quality.verify(record['id'],candidate,R,frontend.__file__,work)
        row=dict(name=old['kind'],id=record['id'],candidate=common.asset(candidate),qa=common.asset(work/'report.json'),fresh_png=dict(file=record['image_file'],sha256=record['image_sha256']),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],actual_rerendered_pixels_changed=True,code_and_image_rehashed=True)
        program.check_control_case(row,'negative',config);negatives.append(row)
    common.immutable(output/'qualified.jsonl',b''.join(common.raw(accepted[i])for i in sorted(accepted)))
    proof=dict(schema='compiler_python_cosyn_intrinsic_iteration_controls_v2',frozen_frontend=config,adapter_receipt=common.asset(ADAPTER),producer=common.asset(Path(__file__)),positive_cases=positives,negative_cases=negatives,target_codec_edit_save=codec,qualified_manifest=common.asset(output/'qualified.jsonl'),all_actual_controls_rechecked=True,normal_source_conversion_calls=0,new_heldout_consumed=0,model_calls=0,canonical_mutations=0)
    common.immutable(output/'proof.json',common.raw(proof));program.check_controls({**proof,'definition':common.asset(output/'proof.json')})
    return dict(proof=common.asset(output/'proof.json'),qualified=2,positive=2,semantic_negatives=3)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT);print(json.dumps(main(parser.parse_args().output)))
