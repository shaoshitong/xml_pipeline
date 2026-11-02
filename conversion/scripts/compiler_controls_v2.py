"""Finite, preregistered positive and corrupted-source controls on seen IDs."""
import argparse
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import compiler_batch_v2 as controller
import compiler_prepare_validation_v2 as prepare
import compiler_quality_v2 as quality
from compiler_capture_snapshot_v1 import seal_snapshot
from fixed_batch_case_v1 import R,W,raw,save,sha

UNIT='python_graphviz_cached_source_v1'
POSITIVE='18b42bc74a7f5b426ded51e0f676c5d48c849c33c67b08d66ba59e7b8fe28611'
NEGATIVE='90c1277f020e3ff508bff77392141301df548dfc1bc9b3c5064cc1d8a6fbbc4e'
SEEN_NEGATIVE_RECORD='clean/round2_source_repair_v1/90/'+NEGATIVE+'/b544e32c2ec04109835afb0fe4a3bd29/compiler_candidate_record.json'
V1_REGRESSIONS={
 'e6409913a83b92611e5cc6354f48873ed809d4c0366a87206f582f078cc5d0e8':(4,'44ccabae84c2ce94d73f535a865e3728e1b26f32ee3f267c278643a84b459456'),
 'c367e5d71ab193cd842a3dc9e3570d04984d013061c50e4c60f74d978b6e0e56':(6,'66946645d9f9172eb29ae03170f3fc0c0ef96dec7960b588e5e0534a50df899e'),
 '9603f6dffd98a2687647decbaa7dce24e53c68ac764014a2124cdd6fd102c865':(13,'8ee8520f2918c5d5bf84b89454c82bd8bccc84564b4690dfc8bf06a98ebd7930'),
 'ca5009341f873e4c7b972da89ccaa0fbd3c7994d485390f56b451a9818cd09ca':(18,'5949004938bf71f57a97034d179c8a5ed583c8c6bfe5d8bbc4dfd7370328ecdf')}


def asset(path,role=None):
    path=Path(path).resolve(strict=True)
    if not path.is_relative_to(R.resolve()):raise ValueError('control_asset_outside_HKUST_root')
    item=dict(file=str(path),sha256=sha(path.read_bytes()))
    if role:item['role']=role
    return item


def paths(run_id):
    if not run_id or not all(c.isalnum() or c in '-_' for c in run_id):raise ValueError('invalid_control_run_id')
    return R/'release/compiler_v2'/('controls_'+run_id), W/'compiler_v2'/('controls_'+run_id)


def create(run_id):
    seal,workroot=paths(run_id);seal.mkdir(parents=True,exist_ok=False);workroot.mkdir(parents=True,exist_ok=False)
    config=quality.configuration()
    scene_source=(W/'scripts/compiler_scene_v1.py').read_text()
    import ast
    function=next(node for node in ast.parse(scene_source).body if isinstance(node,ast.FunctionDef) and node.name=='static_support')
    freeze=dict(pins=prepare.implementation_pins(),qa_policy_sha256=config['policy_sha256'],
                predicate_hashes={UNIT:sha(ast.dump(function,include_attributes=False).encode())})
    freeze['implementation_identity']=controller.implementation_identity(freeze)
    freeze['implementation_identity_sha256']=controller.implementation_digest(freeze)
    manifest=[];expectations=[];tasks=[]
    d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
    try:
        controls=[(identifier,'positive') for identifier in prepare.REQUIRED_POSITIVE_CONTROL_IDS]+[(NEGATIVE,'negative')]
        for seq,(identifier,kind) in enumerate(controls,1):
            job=d.execute('select input_record,output_record from jobs where id=?',(identifier,)).fetchone()
            source=json.loads(job[0]);original=json.loads(job[1]);snapshot=seal_snapshot(original)
            control_id=kind+'_'+identifier
            work=workroot/control_id;work.mkdir()
            task=dict(id=identifier,seq=seq,compiler_unit=UNIT,source=source,mode='development',
                      source_record_sha256=sha(job[1].encode()),source_capture_snapshot=snapshot,
                      pins=freeze['pins'],work=str(work))
            inputs=[]
            if identifier in V1_REGRESSIONS:
                previous_seq,previous_sha=V1_REGRESSIONS[identifier]
                previous=W/'compiler_v1/graphviz_unseen_20261101_v1_C'/(str(previous_seq).zfill(6)+'_'+identifier)/'result.json'
                if sha(previous.read_bytes())!=previous_sha:raise ValueError('v1_regression_qualification_evidence_changed')
                old=json.loads(previous.read_bytes())
                if old.get('status')!='qualified' or old.get('id')!=identifier:raise ValueError('v1_regression_was_not_qualified')
                inputs.append(asset(previous,'prior_qualified_v1_result'))
                for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256')]:
                    prior=asset(R/old['manifest'][field],'prior_qualified_v1_'+field)
                    if prior['sha256']!=old['manifest'][digest]:raise ValueError('v1_regression_payload_changed')
                    inputs.append(prior)
            if kind=='negative':
                record=json.loads((R/SEEN_NEGATIVE_RECORD).read_bytes())
                xml=(R/record['code_file']).read_text();root=ET.fromstring(xml)
                parents={child:parent for parent in root.iter() for child in parent}
                cells=list(root.iter('mxCell'));edge=next(cell for cell in cells if cell.get('edge')=='1')
                remove={edge.get('id')};changed=True
                while changed:
                    changed=False
                    for cell in cells:
                        if cell.get('parent') in remove and cell.get('id') not in remove:
                            remove.add(cell.get('id'));changed=True
                for cell in cells:
                    if cell.get('id') in remove:parents[cell].remove(cell)
                bad=ET.tostring(root,encoding='unicode')
                from auto_quality_common import structure_checks
                structure_checks(bad)  # Corruption remains structurally valid: semantic coverage must reject it.
                dest=R/'clean/compiler_controls_v2'/run_id/identifier;dest.mkdir(parents=True,exist_ok=False)
                code=dest/'missing_edge.drawio';save(code,bad.encode())
                record={**record,'code_file':str(code.relative_to(R)),'code_sha256':sha(bad.encode())}
                recordfile=dest/'candidate_record.json';save(recordfile,raw(record))
                task['development_candidate']=str(recordfile)
                inputs.extend((asset(code,'corrupted_target_code'),asset(recordfile,'corrupted_candidate_record')))
                for field in ('image_file','original_source_code','original_reference'):
                    inputs.append(asset(R/record[field],'candidate_'+field))
            baseline=work/'original_output_record.json';save(baseline,job[1].encode())
            inputs.append(asset(baseline,'source_record'))
            for field in ('code_file','image_file'):
                inputs.append(asset(R/original[field],'baseline_candidate_'+field))
            request=work/'request.json';save(request,raw(task))
            inputs.insert(0,asset(request,'request'))
            for field,digest in [('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
                item=asset(R/original[field],field)
                if item['sha256']!=original[digest]:raise ValueError('control_original_payload_hash_changed')
                inputs.append(item)
            for field in ('source_dot','source_svg','execution_audit','returned_png'):
                inputs.append(asset(R/snapshot[field],field))
            manifest.append(dict(control_id=control_id,id=identifier,kind=kind,compiler_unit=UNIT,input_assets=inputs))
            expectations.append(dict(control_id=control_id,kind=kind,expected_status='qualified' if kind=='positive' else 'abandoned',
                                     expected_failure_stage=None if kind=='positive' else 'source'))
            tasks.append(dict(control_id=control_id,request=str(request),work=str(work)))
    finally:d.close()
    save(seal/'manifest.jsonl',b''.join(raw(row) for row in manifest))
    save(seal/'expectations.jsonl',b''.join(raw(row) for row in expectations))
    save(seal/'freeze.json',raw(freeze))
    plan=dict(schema='compiler_controls_plan_v1',compiler_version='compiler_v2',at=controller.base.now(),implementation_identity_sha256=freeze['implementation_identity_sha256'],
              controls_manifest=asset(seal/'manifest.jsonl'),expectations=asset(seal/'expectations.jsonl'),tasks=tasks,
              prior_to_execution=True,unseen_cases=0,model_calls=0)
    save(seal/'plan.json',raw(plan))
    return dict(seal=str(seal),controls=len(tasks),implementation_identity_sha256=freeze['implementation_identity_sha256'])


def run(run_id):
    seal,_=paths(run_id);plan=json.loads((seal/'plan.json').read_bytes());freeze=json.loads((seal/'freeze.json').read_bytes())
    controller.check_pins(freeze['pins']);controller.check_implementation_identity(freeze)
    for key in ('controls_manifest','expectations'):
        if asset(plan[key]['file'])['sha256']!=plan[key]['sha256']:raise ValueError('control_preregistration_changed')
    from initial_conversion_process_v1 import run as isolated
    env={key:os.environ[key] for key in ('PATH','HOME','LANG','LC_ALL','TMPDIR','XDG_CACHE_HOME') if key in os.environ}
    env.update(PYTHONPATH=str(R/'env')+':'+str(W/'scripts'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    for task in plan['tasks']:
        work=Path(task['work'])
        if (work/'isolation.json').exists() or (work/'result.json').exists():raise ValueError('control_attempt_already_exists')
        evidence=isolated([sys.executable,'-B',str(controller.CASE),task['request']],work,600,env)
        save(work/'isolation.json',raw(evidence))
        if not evidence.get('ok') or not evidence.get('cleanup_complete'):raise RuntimeError('control_process_or_cleanup_failed')
        result=json.loads((work/'result.json').read_bytes())
        print(json.dumps(dict(control_id=task['control_id'],status=result.get('status'),reason=result.get('reason'),
                              quality_report=result.get('quality_report'),cleanup_complete=True,seconds=evidence['seconds'])),flush=True)
    return proof(run_id)


def proof(run_id):
    seal,_=paths(run_id);plan=json.loads((seal/'plan.json').read_bytes());freeze=json.loads((seal/'freeze.json').read_bytes())
    outcomes=[]
    for task in plan['tasks']:
        work=Path(task['work']);result=json.loads((work/'result.json').read_bytes())
        evidence=json.loads((work/'isolation.json').read_bytes())
        if not evidence.get('ok') or not evidence.get('cleanup_complete'):raise RuntimeError('controls_lack_complete_process_cleanup')
        outcomes.append(dict(control_id=task['control_id'],result=asset(work/'result.json'),
                             quality_audit=asset(R/result['quality_report']),isolation=asset(work/'isolation.json')))
    save(seal/'outcomes.jsonl',b''.join(raw(row) for row in outcomes))
    result=dict(schema='compiler_controls_proof_v1',implementation_identity=freeze['implementation_identity'],
                implementation_identity_sha256=freeze['implementation_identity_sha256'],
                controls_manifest=plan['controls_manifest'],expectations=plan['expectations'],outcomes=asset(seal/'outcomes.jsonl'))
    save(seal/'proof.json',raw(result))
    return dict(proof=str(seal/'proof.json'),controls=len(outcomes),unseen_cases=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('create','run','proof'));parser.add_argument('--run-id',required=True)
    args=parser.parse_args();print(json.dumps(globals()[args.action](args.run_id)),flush=True)
