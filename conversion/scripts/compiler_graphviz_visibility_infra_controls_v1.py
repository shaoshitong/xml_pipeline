"""Two consumed real cases: ordinary failure must dispatch the next positive.

Optionally continues into one exhaustive source-only audit and prepare-only
operation. Never dispatches an unseen validation or a production mass pass.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
ROOT=R/'release/compiler_iterations/controls/python_graphviz_infra_dispatch_20261101_v1'
RUN='python_graphviz_infra_dispatch_controls_20261101_v1'
OLD=R/'release/compiler_iterations/runs/python_graphviz_nonpainting_20261101_v2_C/status.sqlite'
FAILED='67112188dbb2ded9141bd3ef9b1d63f202680a3d12acfa3afb1a6d8c9baf2a92'
POSITIVE='a46d1e8c5ed503c92b38d7fe328e649bc0f38ff93563c3dc3a1f296dc5e21019'


def old_digest():
    import compiler_types_program_v1 as common
    with sqlite3.connect('file:'+str(OLD)+'?mode=ro',uri=True,timeout=30)as database:
        rows=database.execute('select seq,id,status,attempts,source,result from samples order by seq').fetchall()
    return common.sha(common.raw(rows))


def main(args):
    import compiler_types_program_v1 as common
    import compiler_graphviz_visibility_frontend_v1 as frontend
    import compiler_graphviz_visibility_iteration_case_v2 as case
    import compiler_graphviz_visibility_iteration_batch_v3 as controller
    import compiler_graphviz_visibility_iteration_program_v3 as program
    ROOT.mkdir(parents=True,exist_ok=False);before=old_digest();config=frontend.configuration()
    program.check_controls(program.control_bundle(frontend))
    own=('compiler_graphviz_visibility_iteration_case_v2.py','compiler_graphviz_visibility_iteration_batch_v3.py',
         'compiler_graphviz_visibility_iteration_program_v3.py','compiler_graphviz_visibility_iteration_pool_v2.py',
         'compiler_graphviz_visibility_infra_controls_v1.py','compiler_typed_runtime_failure_v1.py')
    ownpins={str(W/'scripts'/name):common.sha((W/'scripts'/name).read_bytes())for name in own}
    pins={**config['pins'],**ownpins}
    freeze=dict(pins=pins,qa_policy_sha256=common.sha(common.raw(dict(source=config['policy'],case=ownpins[str(W/'scripts'/own[0])]))),
                predicate_hashes={frontend.UNIT:common.sha(common.raw(dict(consumed_controls_only=True,source_policy=config['policy'])))})
    freeze['implementation_identity']=controller.implementation_identity(freeze);freeze['implementation_identity_sha256']=controller.implementation_digest(freeze)
    with sqlite3.connect('file:'+str(OLD)+'?mode=ro',uri=True,timeout=30)as old:
        row=json.loads(old.execute('select source from samples where id=?',(FAILED,)).fetchone()[0])
    row.update(seq=1,evaluation_phase='candidate')
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
        job=database.execute('select*from jobs where id=?',(POSITIVE,)).fetchone()
    source=json.loads(job[4]);baseline=json.loads(job[9]);support=frontend.static_support(job)
    assert support['supported']
    positive=dict(seq=2,id=POSITIVE,source=source,compiler_unit=frontend.UNIT,cluster='existing_consumed_positive',evaluation_phase='candidate',
                  source_capture_snapshot=support['source_capture_snapshot'],source_record_sha256=common.sha(job[9].encode()),
                  baseline_code_sha256=baseline.get('code_sha256'),baseline_image_sha256=baseline.get('image_sha256'))
    manifest=b''.join(common.raw(x)for x in (row,positive));freeze['input_sha256']=common.sha(manifest)
    common.immutable(ROOT/'input.jsonl',manifest);common.immutable(ROOT/'freeze.json',common.raw(freeze))
    run=controller.FLOOR/RUN;controller.create(run,ROOT/'input.jsonl',ROOT/'freeze.json','development')
    with(ROOT/'controller.log').open('xb')as log:
        result=subprocess.run([sys.executable,'-B',str(Path(controller.__file__)), 'run','--run-id',RUN,'--workers','1','--case-timeout','900'],
                              stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:raise RuntimeError('real_runtime_control_program_failed')
    snapshot=controller.snapshot(run)
    if not snapshot['metadata'].get('finished')or snapshot['infrastructure_stop']:raise ValueError('ordinary_failure_still_stops_real_dispatch')
    cases=[]
    with sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)as database:
        rows=database.execute('select seq,id,status,attempts,result from samples order by seq').fetchall()
    for seq,identifier,status,attempts,body in rows:
        value=json.loads(body);directory=R/value['evidence_directory']
        common.immutable(ROOT/(str(seq)+'_result.json'),common.raw(value))
        item=dict(id=identifier,seq=seq,status=status,attempts=attempts,result=common.asset(ROOT/(str(seq)+'_result.json')),
                  frontend=common.asset(directory/'frontend_result.json'))
        if seq==1:
            actual=json.loads((directory/'frontend_result.json').read_bytes())
            assert status=='abandoned'and value.get('infrastructure_failure')is False and actual.get('infrastructure_failure')is False
        else:
            assert status=='qualified';manifest=value['manifest'];record=json.loads(common.checked(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True)[1])
            qa=R/value['quality_report'];case.full_quality(json.loads(qa.read_bytes()),record)
            item.update(manifest=manifest,quality=common.asset(qa))
        assert attempts==1;cases.append(item)
    assert len(cases)==2 and old_digest()==before
    proof=dict(schema='real_typed_runtime_dispatch_controls_v1',producer=common.asset(Path(__file__)),orchestration_pins=ownpins,
               source_configuration=config,freeze=common.asset(ROOT/'freeze.json'),input=common.asset(ROOT/'input.jsonl'),run=str(run),cases=cases,
               ordinary_failure_then_next_full_positive=True,no_infrastructure_stop=True,each_attempted_once=True,
               old_production_rows_sha256_before=before,old_production_rows_sha256_after=old_digest(),old_production_rows_unchanged=True,
               new_heldout_consumed=0,production_dispatch=False,model_calls=0)
    common.immutable(ROOT/'proof.json',common.raw(proof));print(json.dumps(dict(proof=common.asset(ROOT/'proof.json'),ordinary_failure_then_next_full_positive=True)),flush=True)
    if args.prepare_after:
        from compiler_graphviz_visibility_iteration_pool_v2 import prepare as audit
        audit(args.pool,args.inventory)
        ready=program.prepare(args.pool,args.run_id);common.immutable(ROOT/'prepare_handoff.json',common.raw(ready));print(json.dumps(ready),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-after',action='store_true');parser.add_argument('--pool',type=Path);parser.add_argument('--inventory',type=Path);parser.add_argument('--run-id');main(parser.parse_args())
