"""Preregistered finite seen controls for the remaining-format fixed program."""
import argparse
import concurrent.futures
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

import compiler_types_batch_v1 as controller
import compiler_types_case_v1 as case
from fixed_batch_case_v1 import R,W,raw,save,sha

FORMATS=('drawio','mermaid','html')
FIRST=R/'release/fixed_batch_v1/initial_screen_20261031_1717'
AUDIT=R/'release/compiler_types_audit_v1/source_only_20261101_v1'


def asset(path,role=None):
    p=Path(path).resolve(strict=True)
    if not p.is_relative_to(R.resolve()):raise ValueError('control_asset_outside_HKUST')
    x=dict(file=str(p),sha256=sha(p.read_bytes()))
    if role:x['role']=role
    return x


def paths(run_id):
    if not run_id or not all(c.isalnum() or c in '-_' for c in run_id):raise ValueError('invalid_control_run_id')
    return R/'release/compiler_types_v1'/('controls_'+run_id),W/'compiler_types_v1'/('controls_'+run_id)


def create(run_id):
    import compiler_types_program_v1 as program
    seal,workroot=paths(run_id);seal.mkdir(parents=True,exist_ok=False);workroot.mkdir(parents=True,exist_ok=False)
    freeze=program.implementation_template();save(seal/'freeze.json',raw(freeze))
    dev={json.loads(line)['id'] for line in (AUDIT/'compiler_types_development_audit.jsonl').read_bytes().splitlines() if line}
    accepted=[json.loads(line) for line in (FIRST/'qualified.jsonl').read_bytes().splitlines() if line]
    records=[json.loads(line) for line in (AUDIT/'compiler_types_development_audit.jsonl').read_bytes().splitlines() if line]
    db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
    manifest=[];expected=[];tasks=[];required={}
    try:
        for fmt in FORMATS:
            unit=case.unit(fmt)
            positives=sorted((r for r in accepted if r.get('source_format')==fmt and r['id'] in dev),
                             key=lambda r:sha(raw(['typed-controls-positive-v1',fmt,r['id']])))
            positive=None;job=None
            for r in positives:
                j=db.execute('select * from jobs where id=?',(r['id'],)).fetchone()
                if j and case.static_support(j)['supported']:positive,job=r,j;break
            if positive is None:raise ValueError('missing_seen_prior_qualified_control:'+fmt)
            record=json.loads((R/positive['metadata_file']).read_bytes())
            if sha((R/positive['metadata_file']).read_bytes())!=positive['metadata_sha256']:raise ValueError('old_accepted_metadata_changed')
            required[unit]=[positive['id']]
            chosen=[('positive',job,record)]
            candidates=sorted((r for r in records if r['format']==fmt and r['id']!=positive['id']),
                              key=lambda r:sha(raw(['typed-controls-development-v1',fmt,r['id']])))
            for r in candidates:
                j=db.execute('select * from jobs where id=?',(r['id'],)).fetchone()
                if j and case.static_support(j)['supported']:
                    chosen.append(('development',j,None))
                if sum(kind=='development' for kind,_,_ in chosen)==2:break
            # Well-formed XML with an invalid parent must fail the actual frozen
            # structure gate before any producer-specific proof is consulted.
            tree=ET.fromstring((R/record['code_file']).read_text());model=tree.find('.//mxGraphModel/root')
            if model is None:raise ValueError('positive_control_has_no_model_root')
            used={c.get('id') for c in tree.iter('mxCell')};bad_id='typed_negative_unbound_parent'
            if bad_id in used:raise ValueError('negative_control_id_collision')
            c=ET.SubElement(model,'mxCell',id=bad_id,parent=bad_id+'_missing',vertex='1',value='negative control',style='shape=rectangle;')
            ET.SubElement(c,'mxGeometry',x='10',y='10',width='20',height='20',attrib={'as':'geometry'})
            bad=ET.tostring(tree,encoding='unicode');dest=R/'clean/compiler_types_controls_v1'/run_id/fmt;dest.mkdir(parents=True,exist_ok=False)
            code=dest/'invalid_parent.drawio';save(code,bad.encode())
            negative={**record,'code_file':str(code.relative_to(R)),'code_sha256':sha(bad.encode())}
            chosen.append(('negative',job,negative))
            for kind,j,r in chosen:
                identifier=j[0];control_id=fmt+'_'+kind+'_'+identifier;work=workroot/control_id;work.mkdir()
                source=json.loads(j[4]);source_record=work/'source_record.json';save(source_record,(j[9] or '').encode())
                request=dict(id=identifier,seq=len(tasks)+1,compiler_unit=unit,source=source,first_result={},
                             mode='development',work=str(work),source_record_sha256=sha((j[9] or '').encode()),pins=freeze['pins'])
                inputs=[asset(source_record,'source_record')]
                if r is not None:
                    proposal=dest/(kind+'_'+identifier+'_record.json');save(proposal,raw(r));request['development_candidate']=str(proposal)
                    for field in ('code_file','image_file','original_source_code','original_reference'):
                        inputs.append(asset(R/r[field],'candidate_'+field))
                    inputs.append(asset(proposal,'development_candidate'))
                if kind=='positive':
                    request.update(evaluation_phase='baseline',baseline_code_sha256=r['code_sha256'],baseline_image_sha256=r['image_sha256'])
                if kind=='negative':request['negative_control']=True
                req=work/'request.json';save(req,raw(request));inputs.insert(0,asset(req,'request'))
                manifest.append(dict(control_id=control_id,id=identifier,kind=kind,compiler_unit=unit,input_assets=inputs))
                expected.append(dict(control_id=control_id,kind=kind,compiler_unit=unit,
                                     expected_status='qualified' if kind=='positive' else 'abandoned' if kind=='negative' else 'terminal',
                                     expected_failure_stage='structure' if kind=='negative' else None,
                                     expected_failure_reason='dangling_parent' if kind=='negative' else None))
                tasks.append(dict(control_id=control_id,kind=kind,compiler_unit=unit,request=str(req),work=str(work)))
    finally:db.close()
    save(seal/'manifest.jsonl',b''.join(raw(r) for r in manifest));save(seal/'expectations.jsonl',b''.join(raw(r) for r in expected))
    plan=dict(schema='compiler_types_controls_plan_v1',at=controller.base.now(),implementation_identity_sha256=freeze['implementation_identity_sha256'],
              controls_manifest=asset(seal/'manifest.jsonl'),expectations=asset(seal/'expectations.jsonl'),tasks=tasks,
              required_positive_ids=required,unseen_cases=0,model_calls=0,prior_to_execution=True)
    save(seal/'plan.json',raw(plan));return dict(seal=str(seal),controls=len(tasks),identity=freeze['implementation_identity_sha256'])


def execute_control(t,env):
    from initial_conversion_process_v1 import run as isolated
    work=Path(t['work'])
    if (work/'isolation.json').exists() or (work/'result.json').exists():raise ValueError('control_must_not_repeat')
    evidence=isolated([sys.executable,'-B',str(controller.CASE),t['request']],work,600,env)
    save(work/'isolation.json',raw(evidence))
    if not evidence.get('ok') or not evidence.get('cleanup_complete'):raise RuntimeError('control_process_infrastructure_failure')
    result=json.loads((work/'result.json').read_bytes())
    print(json.dumps(dict(control_id=t['control_id'],status=result['status'],reason=result['reason'],seconds=evidence['seconds'])),flush=True)
    return dict(control_id=t['control_id'],kind=t['kind'],compiler_unit=t['compiler_unit'],result=asset(work/'result.json'),
                quality_audit=asset(R/result['quality_report']) if result.get('quality_report') else None,isolation=asset(work/'isolation.json'))


def run(run_id,workers=4):
    seal,_=paths(run_id);plan=json.loads((seal/'plan.json').read_bytes());freeze=json.loads((seal/'freeze.json').read_bytes())
    controller.check_pins(freeze['pins']);controller.check_implementation_identity(freeze)
    for key in ('controls_manifest','expectations'):
        if asset(plan[key]['file'])['sha256']!=plan[key]['sha256']:raise ValueError('control_plan_changed')
    env=os.environ.copy();env.update(PYTHONPATH=str(R/'env')+':'+str(W/'scripts'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    context=multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=context) as pool:
        outcomes=list(pool.map(execute_control,plan['tasks'],[env]*len(plan['tasks'])))
    save(seal/'outcomes.jsonl',b''.join(raw(r) for r in outcomes))
    proof=dict(schema='compiler_types_controls_proof_v1',implementation_identity=freeze['implementation_identity'],
               implementation_identity_sha256=freeze['implementation_identity_sha256'],controls_manifest=plan['controls_manifest'],
               expectations=plan['expectations'],outcomes=asset(seal/'outcomes.jsonl'),required_positive_ids=plan['required_positive_ids'])
    save(seal/'proof.json',raw(proof));return dict(proof=str(seal/'proof.json'),controls=len(outcomes),unseen_cases=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('create','run'));p.add_argument('--run-id',required=True);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();print(json.dumps(create(a.run_id) if a.action=='create' else run(a.run_id,a.workers)),flush=True)
