"""Finite real XML/PNG/portable-font controls; no heldout or canonical writes."""
import argparse
import copy
import concurrent.futures
import hashlib
import io
import json
import multiprocessing
from pathlib import Path
import sqlite3
import sys
import uuid
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def asset(path):
    p=Path(path).resolve(strict=True);return dict(file=str(p),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)


def run(task):
    kind,record_path,root=task
    import compiler_graphviz_visibility_frontend_v1 as frontend
    import compiler_graphviz_visibility_quality_ro_v1 as quality
    from compiler_graphviz_visibility_scene_v1 import LAYOUT_ATTRIBUTE
    from compiler_graphviz_visibility_text_v1 import calibrate,_render_observed
    from round2_font_repair_v1 import repair as fonts
    from svg_convert_v3 import unpack,pack
    positive=json.loads(Path(record_path).read_bytes());identifier=positive['id'];work=Path(root)/kind
    work.mkdir(parents=True,exist_ok=False);job=frontend.job_tuple({'id':identifier})
    if kind=='positive_final_frontend':
        attempt=frontend.convert(None,job,work/'compile')
        (work/'frontend_result.json').write_text(json.dumps(attempt,ensure_ascii=False)+'\n')
        if not attempt.get('ok'):return dict(kind=kind,ok=False,stage='frontend',reason=attempt.get('reason'),detail=attempt.get('detail'))
        record=attempt['record'];candidate=Path(attempt['record_file'])
    else:
        # Rebuild every font/text proof around the mutated pre-font source IR,
        # so independent source rejection cannot be an obsolete-hash failure.
        text=positive['compiler_graphviz_visibility_text_v1']
        proof=json.loads((R/text['proof_file']).read_bytes())
        embedded=json.loads((R/proof['baseline_record']['file']).read_bytes())
        font_folder=(R/embedded['round2_font_repair']['audit']).parent
        base=json.loads((font_folder/'before_record.json').read_bytes())
        xml=(R/base['code_file']).read_text();tree=ET.fromstring(xml);model=tree.find('.//mxGraphModel')
        cells={c.get('id'):c for c in tree.iter('mxCell')};edges=[c for c in cells.values() if c.get('edge')=='1']
        if kind=='visible_endpoint_changed':
            edge=next(c for c in edges if c.get('source')!=c.get('target'));edge.set('target',edge.get('source'))
        elif kind=='source_arrow_removed':
            edge=next(c for c in edges if unpack(c.get('style','')).get('endArrow','none')!='none')
            style=unpack(edge.get('style',''));style['endArrow']='none';edge.set('style',pack(style))
        elif kind=='nonpainting_relation_changed':
            constraints=json.loads(model.get(LAYOUT_ATTRIBUTE));row=constraints[0]
            row['target_node']=row['source_node'];row['target_name']=row['source_name']
            row['source_attributes']['head']=row['source_node']
            row['source_payload_sha256']=sha(json.dumps(row['source_attributes'],sort_keys=True).encode())
            model.set(LAYOUT_ATTRIBUTE,json.dumps(constraints,sort_keys=True))
        else:raise ValueError('unknown_control_kind')
        changed=ET.tostring(tree,encoding='unicode')
        width,height=[int(round(float(model.get(k)))) for k in ('pageWidth','pageHeight')]
        png,info=_render_observed(changed,width,height)
        destination=R/'clean/compiler_graphviz_visibility_controls_v1'/identifier[:2]/identifier/uuid.uuid4().hex
        destination.mkdir(parents=True,exist_ok=False)
        (destination/'pre_font.drawio').write_text(changed);(destination/'pre_font.png').write_bytes(png)
        record={**copy.deepcopy(base),'code_file':str((destination/'pre_font.drawio').relative_to(R)),
                'code_sha256':sha(changed.encode()),'image_file':str((destination/'pre_font.png').relative_to(R)),
                'image_sha256':sha(png),'render':info,'quality_state':'negative_source_semantics_control'}
        for stale in ('round2_font_repair','compiler_graphviz_visibility_text_v1','auto_quality_canvas_repair'):
            record.pop(stale,None)
        (work/'mutated_pre_font_record.json').write_text(json.dumps(record,ensure_ascii=False)+'\n')
        embedded=fonts(record,job,work/'new_font_proof')
        (work/'font_result.json').write_text(json.dumps(embedded,ensure_ascii=False)+'\n')
        if not embedded.get('ok'):return dict(kind=kind,ok=False,stage='font',reason=embedded.get('reason'),detail=embedded.get('detail') or embedded.get('error'))
        calibrated=calibrate(embedded['record'],job,work/'new_text_proof')
        (work/'text_result.json').write_text(json.dumps(calibrated,ensure_ascii=False)+'\n')
        if calibrated.get('record'):
            record=calibrated['record']
        elif calibrated.get('candidate_record_file'):
            record=json.loads((R/calibrated['candidate_record_file']).read_bytes())
        else:return dict(kind=kind,ok=False,stage='text',reason=calibrated.get('reason'),detail=calibrated.get('detail'))
        record['compiler_source_reproduction']=positive['compiler_source_reproduction']
        record['compiler_quality_phase_visibility_v1']='candidate'
        candidate=work/'candidate_record.json';candidate.write_text(json.dumps(record,ensure_ascii=False)+'\n')
    directory=W/'prototype/candidate_quality_ro_v1'/('graphviz_visibility_control_'+kind+'_'+uuid.uuid4().hex)
    checked=quality.verify(identifier,candidate,R,Path(frontend.__file__),directory)
    row=dict(kind=kind,id=identifier,record_file=asset(candidate),quality_report=asset(directory/'report.json'),
             code=asset(R/record['code_file']),image=asset(R/record['image_file']),
             original_code=asset(R/record['original_source_code']),original_image=asset(R/record['original_reference']),
             source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],
             failures=checked.get('failures',[]),quality_ok=checked.get('ok') is True,
             all_font_and_text_proofs_regenerated=kind!='positive_final_frontend',
             original_python_or_capture_payloads_modified=False,model_calls=0)
    if kind=='positive_final_frontend':row.update(ok=checked.get('ok') is True,fresh_png=asset(directory/'fresh.png') if (directory/'fresh.png').exists() else None)
    else:
        expected={'visible_endpoint_changed':'native_graphviz_json_endpoint_changed',
                  'source_arrow_removed':'source_arrow_missing_attached_native_marker',
                  'nonpainting_relation_changed':'native_nonpainting_layout_constraints_changed'}[kind]
        row.update(ok=not checked.get('ok') and expected in json.dumps(checked.get('failures',[])),expected_semantic_rejection=expected,
                   fresh_png=asset(R/record['image_file']))
    (work/'receipt.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
    return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--positive-record',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((W/'compiler_graphviz_visibility_controls_v1').resolve());output.mkdir(parents=True,exist_ok=False)
    kinds=['positive_final_frontend','visible_endpoint_changed','source_arrow_removed','nonpainting_relation_changed']
    results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),max_tasks_per_child=1) as pool:
        tasks={pool.submit(run,(kind,str(args.positive_record),str(output))):kind for kind in kinds}
        for future in concurrent.futures.as_completed(tasks):
            kind=tasks[future]
            try:result=future.result()
            except Exception as exc:result=dict(kind=kind,ok=False,error=repr(exc))
            results.append(result);print(json.dumps({'kind':kind,'ok':result.get('ok'),'error':result.get('error'),'stage':result.get('stage'),'failures':result.get('failures')}),flush=True)
    report=dict(schema='compiler_graphviz_visibility_real_controls_v1',controls=results,
                all_actual_controls_passed=all(row['ok'] for row in results),model_calls=0,heldout_consumed=0,bulk_launched=False)
    (output/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'receipt':str(output/'receipt.json'),'all_actual_controls_passed':report['all_actual_controls_passed']}),flush=True)


if __name__=='__main__':main()
