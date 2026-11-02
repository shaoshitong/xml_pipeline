"""Seal finite development/control evidence for root-owned fresh evaluation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
sha=lambda b:hashlib.sha256(b).hexdigest()


def ref(path):
    path=Path(path);blob=path.read_bytes()
    return dict(file=str(path),sha256=sha(blob),bytes=len(blob))


def checked(item):
    actual=ref(item['file'])
    if actual['sha256']!=item['sha256']:raise ValueError('evidence_changed:'+item['file'])
    return actual


def main():
    from compiler_graphviz_visibility_frontend_v1 import configuration,UNIT,MODULES
    folder=W/'compiler_graphviz_visibility_controls_v1/frozen_final_20261101_v1'
    control=json.loads((folder/'receipt.json').read_text())
    if not control['all_actual_controls_passed']:raise ValueError('actual_controls_failed')
    config=configuration();positive=[];negative=[]
    for item in control['controls']:
        for key in ('record_file','quality_report','code','image','original_code','original_image','fresh_png'):
            checked(item[key])
        quality=json.loads(Path(item['quality_report']['file']).read_text())
        if quality['implementation_pins']!=config['pins']:raise ValueError('quality_pin_configuration_changed')
        if quality['input_record_sha256']!=item['record_file']['sha256']:raise ValueError('quality_record_changed')
        if item['kind'].startswith('positive_'):
            if not quality['ok'] or quality['failures'] or not item['quality_ok']:raise ValueError('positive_not_fully_qualified')
            if item['fresh_png']['sha256']!=item['image']['sha256']:raise ValueError('final_png_not_actual_drawio_render')
            positive.append(item)
        else:
            if quality['ok'] or not item['all_font_and_text_proofs_regenerated']:raise ValueError('negative_proof_invalid')
            if item['expected_semantic_rejection']not in json.dumps(quality['failures']):raise ValueError('wrong_semantic_rejection')
            negative.append(item)
    if len(positive)!=2 or len(negative)!=3:raise ValueError('wrong_controls')
    codec=[]
    for name in ('actual_codec_roundtrip.json','actual_codec_roundtrip_padded.json'):
        path=folder/name;result=json.loads(path.read_text())
        if not result['ok']or not all(result[k]for k in ('after_actual_decode_exact','after_actual_move_exact','after_restore_exact','logical_model_restore_exact')):
            raise ValueError('target_codec_metadata_dropped')
        checked(result['record_file']);codec.append(dict(result=result,artifact=ref(path)))
    tests=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(W/'scripts'),'-p','test_compiler_graphviz_visibility_ir_v1.py'],capture_output=True,text=True)
    if tests.returncode or 'Ran 11 tests'not in tests.stderr:raise ValueError('meaningful_ir_tests_failed')
    own={str(W/'scripts'/('compiler_graphviz_visibility_'+name+'_v1.py')):config['pins'][str(W/'scripts'/('compiler_graphviz_visibility_'+name+'_v1.py'))]for name in MODULES}
    producer_names=('compiler_graphviz_visibility_controls_v3.py','compiler_graphviz_visibility_codec_roundtrip_v1.py','test_compiler_graphviz_visibility_ir_v1.py',Path(__file__).name)
    producers=[ref(W/'scripts'/name)for name in producer_names]
    result=dict(schema='compiler_graphviz_visibility_finite_adapter_delivery_v1',unit=UNIT,
                configuration=config,production_modules=own,producers=producers,
                api=dict(frontend='compiler_graphviz_visibility_frontend_v1',
                         configuration='configuration(data_root=R)',static_support='static_support(jobtuple_or_dict)',
                         convert='convert(record,job,work)',quality='compiler_graphviz_visibility_quality_ro_v1.verify(id,record_file,data_root,plugin_file,work,database)'),
                full_actual_controls=ref(folder/'receipt.json'),positive=positive,negative=negative,
                actual_target_codec_edit_save=codec,
                tests=dict(local=dict(tests=11,passed=True,command="python3 -m unittest discover -s work/drawio_conversion -p test_compiler_graphviz_visibility_ir_v1.py",test_sha256=ref(W/'scripts'/'test_compiler_graphviz_visibility_ir_v1.py')['sha256']),
                           hkust=dict(tests=11,passed=True,stdout=tests.stdout,stderr=tests.stderr)),
                supported_source_scope='Existing Python Graphviz14.1.2 captured DOT with explicit style=invis source constraints and supported source SVG grammar. Runtime proves all six draw channels empty; missing visible paths remain unsupported.',
                exact_nonpainting_conservation='Source IDs, endpoints, ports, attributes, drawing-channel emptiness and full source-edge payload hashes retained as typed layout constraints on native root mxCell id=0. All visible source edges keep named bindings and full source fidelity QA.',
                capture_handoff='Freeze static_support result source_capture_snapshot in every population/selected row and pass it as record.compiler_source_capture_snapshot. Frontend checks existing frozen snapshot without resealing. Source/capture changes after selection must fail.',
                deterministic_final_png='Actual unchanged strict drawio renderer creates the final dataset PNG. Immutable padding renderer output remains a geometry/page preservation witness; all original-source, glyph/font, paint and editing quality gates remain required.',
                finite_development=dict(registry=str(R/'release/compiler_iterations/development_seen_v1/python_visibility_ir_20261101_v1.jsonl'),
                                        consumed_ids=12,earlier_generation_full_quality_passed=7,
                                        final_carrier_full_pipeline_controls_passed=2,
                                        pending=dict(source_reference_canvas_mismatch=3,source_domain_visual=1,padding_proof=1),
                                        note='Seven of twelve is development evidence before codec-carrier correction; only the two final full controls attest current exact pins. Remaining failures remain pending, not asserted irrecoverable.'),
                all_actual_controls_passed=True,model_calls=0,heldout_consumed=0,bulk_launched=False,canonical_mutations=0)
    dest=R/'release/compiler_graphviz_visibility_adapter_controls_v1'/uuid.uuid4().hex
    dest.mkdir(parents=True,exist_ok=False);out=dest/'receipt.json'
    with out.open('x')as stream:stream.write(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(receipt=ref(out),policy=config['policy'],unit=UNIT,positive=len(positive),negative=len(negative),codec_edit_save_passed=len(codec),pins=len(config['pins']),production_modules=own,all_actual_controls_passed=True)))


if __name__=='__main__':main()
