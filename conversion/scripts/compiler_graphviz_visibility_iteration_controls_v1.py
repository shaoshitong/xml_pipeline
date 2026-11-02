"""Bind existing actual adapter controls to finite program publication/QA."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
ADAPTER=R/'release/compiler_graphviz_visibility_adapter_controls_v1/9fbcad69d5c44b518e0b87db65f18fb8/receipt.json'
EXPECTED='489b04edb3cedfd077942b4920c2f4cf5f0e7e2fa6d6aee10ab761af1acc972a'
DEFAULT=R/'release/compiler_iterations/controls/python_graphviz_nonpainting_v1_20261101_v1'


def main(output=DEFAULT):
    import compiler_graphviz_visibility_frontend_v1 as frontend
    import compiler_graphviz_visibility_iteration_case_v1 as case
    import compiler_types_program_v1 as common
    from fixed_batch_case_v1 import sha
    output=Path(output).resolve()
    if not output.is_relative_to((R/'release/compiler_iterations/controls').resolve()):raise ValueError('Graphviz_controls_outside_owner')
    blob=ADAPTER.read_bytes()
    if sha(blob)!=EXPECTED:raise ValueError('frozen_adapter_control_receipt_changed')
    adapter=json.loads(blob)
    if adapter['configuration']!=frontend.configuration()or not adapter['all_actual_controls_passed']:raise ValueError('adapter_controls_or_pins_changed')
    positive=[];negative=[];manifests=[]
    for role,key in [('positive','positive'),('negative','negative')]:
        for actual in adapter[key]:
            _,payload=common.checked(actual['record_file']);record=json.loads(payload)
            _,payload=common.checked(actual['quality_report']);quality=json.loads(payload)
            item=dict(name=actual['kind'],id=actual['id'],candidate=actual['record_file'],qa=actual['quality_report'],fresh_png=actual['fresh_png'],
                      source_code_sha256=actual['source_code_sha256'],source_image_sha256=actual['source_image_sha256'])
            if role=='positive':
                case.full_quality(quality,record)
                with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
                    source=json.loads(database.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0])
                directory=Path(actual['quality_report']['file']).parent
                manifests.append(case.publish(record,source,quality,directory));positive.append(item)
            else:
                if not actual['all_font_and_text_proofs_regenerated']:raise ValueError('missing_actual_negative_regenerated_proofs')
                text=record['compiler_graphviz_visibility_text_v1']
                _,payload=common.checked(dict(file=text['proof_file'],sha256=text['proof_sha256']),clean=True);proof=json.loads(payload)
                _,payload=common.checked(proof['baseline_record'],clean=True);baseline=json.loads(payload)
                font=baseline['round2_font_repair']
                if font['output_code_sha256']!=baseline['code_sha256']or not all(font.get(k)is True for k in ('native_pixels_unchanged','physical_postscript_and_glyph_counts_unchanged','all_actual_fonts_custom','source_graph_text_and_nonfont_styles_unchanged')):
                    raise ValueError('negative_actual_font_rebuild_not_bound_to_text_baseline')
                if proof['output_code_sha256']!=record['code_sha256']:raise ValueError('negative_text_proof_not_rebuilt_for_actual_candidate')
                item.update(expected_semantic_rejection=actual['expected_semantic_rejection'],regenerated_font_and_text_proofs=True,
                            font_proof=common.asset(R/font['audit']),text_proof=common.asset(R/text['proof_file']),
                            font_result=common.asset(Path(actual['record_file']['file']).parent/'font_result.json'),
                            text_result=common.asset(Path(actual['record_file']['file']).parent/'text_result.json'))
                negative.append(item)
    output.mkdir(parents=True,exist_ok=False)
    common.immutable(output/'qualified.jsonl',b''.join(common.raw(x)for x in manifests))
    proof=dict(schema='compiler_graphviz_visibility_iteration_controls_v1',frozen_frontend=frontend.configuration(),
               adapter_receipt=common.asset(ADAPTER),producer=common.asset(Path(__file__)),
               positives=[x['qa']for x in positive],negatives=[x['qa']for x in negative],positive_cases=positive,negative_cases=negative,
               target_codec_edit_save=[x['artifact']for x in adapter['actual_target_codec_edit_save']],
               qualified_manifest=common.asset(output/'qualified.jsonl'),
               existing_qualified_preservation='Pool carries full five-asset-hash-verified prior qualifications; fresh B/C gate requires zero positive regressions; ordinary Graphviz-v2 queue remains untouched.',
               source_normal_conversions=0,new_heldout_consumed=0,new_model_calls=0)
    common.immutable(output/'proof.json',common.raw(proof))
    print(json.dumps(dict(proof=common.asset(output/'proof.json'),qualified=len(manifests),positive=len(positive),negative=len(negative),codec=len(proof['target_codec_edit_save']))),flush=True)
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT);args=parser.parse_args();main(args.output)
