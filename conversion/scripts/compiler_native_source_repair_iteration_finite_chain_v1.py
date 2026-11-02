"""One unattended finite chain: controls, source audit, fresh100, gated mass.

No repeated polling, automatic threshold changes, or automatic compiler repair.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
RUN_ID='native_source_font_runs_unseen100_20261101_v1'
ROOT=R/'release/compiler_iterations/chains'/RUN_ID
CONTROLS=R/'release/compiler_iterations/controls/native_source_font_runs_runtime_controls_20261101_v1'
CONTROL_RUN='native_source_font_runs_runtime_preflight_20261101_v1'
FAILED='01277e4a226a6c9bfb45e7b437b43fa0c35f649f1e8919b24790732b01359a74'
POSITIVE='0133a0d0b8a43ed69b38b18150c948107bf1d59575f71e92a9d689cfa1e91a69'
MODULES=('case','batch','program','controls','pool','finite_chain','overlap','family')


def own_pins():
    import compiler_types_program_v1 as common
    names=['compiler_native_source_repair_iteration_'+name+'_v1.py'for name in MODULES]+['compiler_typed_runtime_failure_v1.py','compiler_native_source_repair_controls_v1.py']
    return {str(W/'scripts'/name):common.sha((W/'scripts'/name).read_bytes())for name in names}


def canonical_rows():
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:return [db.execute('select*from jobs where id=?',(i,)).fetchone()for i in (FAILED,POSITIVE)]


def preflight():
    import compiler_types_program_v1 as common
    import compiler_native_source_repair_frontend_v1 as frontend
    import compiler_native_source_repair_iteration_case_v1 as case
    import compiler_native_source_repair_iteration_batch_v1 as controller
    import compiler_native_source_repair_iteration_program_v1 as program
    import compiler_native_source_repair_iteration_controls_v1 as normalize
    normalized=normalize.main();program.check_controls(program.control_bundle(frontend))
    CONTROLS.mkdir(parents=True,exist_ok=False);before=canonical_rows();config=frontend.configuration();own=own_pins();pins={**config['pins'],**own}
    freeze=dict(pins=pins,qa_policy_sha256=common.sha(common.raw(dict(source=config['policy'],case=own[str(W/'scripts/compiler_native_source_repair_iteration_case_v1.py')]))),predicate_hashes={frontend.UNIT:common.sha(common.raw(dict(consumed_controls_only=True,source_policy=config['policy'])))})
    freeze['implementation_identity']=controller.implementation_identity(freeze);freeze['implementation_identity_sha256']=controller.implementation_digest(freeze)
    requests=[]
    for seq,job in enumerate(before,1):
        source=json.loads(job[4]);baseline=json.loads(job[9]);support=frontend.static_support(job)
        if not support['supported']:raise ValueError('finite_consumed_control_outside_frozen_profile:'+json.dumps(support['reasons']))
        requests.append(dict(seq=seq,id=source['pair_sha256'],source=source,compiler_unit=frontend.UNIT,cluster='existing_consumed_real_preflight',evaluation_phase='candidate',source_capture_snapshot=support['source_capture_snapshot'],source_record_sha256=common.sha(job[9].encode()),baseline_code_sha256=baseline.get('code_sha256'),baseline_image_sha256=baseline.get('image_sha256')))
    payload=b''.join(common.raw(row)for row in requests);freeze['input_sha256']=common.sha(payload)
    common.immutable(CONTROLS/'input.jsonl',payload);common.immutable(CONTROLS/'freeze.json',common.raw(freeze))
    run=controller.FLOOR/CONTROL_RUN;controller.create(run,CONTROLS/'input.jsonl',CONTROLS/'freeze.json','development')
    with(CONTROLS/'controller.log').open('xb')as log:
        result=subprocess.run([sys.executable,'-B',str(Path(controller.__file__)), 'run','--run-id',CONTROL_RUN,'--workers','1','--case-timeout','900'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:raise RuntimeError('real_NativeSource_preflight_controller_failed')
    state=controller.snapshot(run)
    if not state['metadata'].get('finished')or state['infrastructure_stop']:raise ValueError('ordinary_failure_stopped_real_NativeSource_dispatch')
    with sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)as db:rows=db.execute('select seq,id,status,attempts,result from samples order by seq').fetchall()
    cases=[];qualified={}
    for seq,identifier,status,attempts,body in rows:
        value=json.loads(body);directory=R/value['evidence_directory'];actual=json.loads((directory/'frontend_result.json').read_bytes());common.immutable(CONTROLS/(str(seq)+'_result.json'),common.raw(value))
        row=dict(id=identifier,seq=seq,status=status,attempts=attempts,result=common.asset(CONTROLS/(str(seq)+'_result.json')),frontend=common.asset(directory/'frontend_result.json'))
        if seq==1:
            if status!='abandoned'or value.get('infrastructure_failure')is not False or actual.get('infrastructure_failure')is not False:raise ValueError('normal_source_failure_incorrectly_infrastructure')
        else:
            if status!='qualified':raise ValueError('real_NativeSource_next_positive_not_qualified')
            manifest=value['manifest'];_,blob=common.checked(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True);qa=R/value['quality_report'];case.full_quality(json.loads(qa.read_bytes()),json.loads(blob));row.update(manifest=manifest,quality=common.asset(qa));qualified[identifier]=manifest
        if attempts!=1:raise ValueError('preflight_case_attempt_not_once')
        cases.append(row)
    if len(cases)!=2 or canonical_rows()!=before:raise ValueError('canonical_original_jobs_changed_by_preflight')
    for item in program.readrows(Path(program.control_bundle(frontend)['qualified_manifest']['file'])):qualified.setdefault(item['id'],item)
    common.immutable(CONTROLS/'qualified.jsonl',b''.join(common.raw(qualified[i])for i in sorted(qualified)))
    proof=dict(schema='real_typed_NativeSource_runtime_dispatch_controls_v1',producer=common.asset(Path(__file__)),orchestration_pins=own,source_configuration=config,freeze=common.asset(CONTROLS/'freeze.json'),input=common.asset(CONTROLS/'input.jsonl'),run=str(run),cases=cases,ordinary_failure_then_next_full_positive=True,no_infrastructure_stop=True,each_attempted_once=True,canonical_original_jobs_sha256_before=common.sha(common.raw(before)),canonical_original_jobs_sha256_after=common.sha(common.raw(canonical_rows())),canonical_original_jobs_unchanged=True,qualified_manifest=common.asset(CONTROLS/'qualified.jsonl'),new_heldout_consumed=0,model_calls=0,canonical_mutations=0)
    common.immutable(CONTROLS/'proof.json',common.raw(proof));program.runtime_controls();return common.asset(CONTROLS/'proof.json')


def execute(nonce):
    import compiler_types_program_v1 as common
    import compiler_native_source_repair_iteration_batch_v1 as controller
    import compiler_native_source_repair_iteration_program_v1 as program
    import compiler_native_source_repair_iteration_pool_v1 as pool
    freeze=json.loads((ROOT/'freeze.json').read_bytes());controller.check_pins(freeze['pins'])
    owner={**controller.process_identity(),'nonce':nonce,'argv':sys.argv,'finite':True,'watch':False};common.atomic(ROOT/'owner.json',owner);common.wait_ack(ROOT/('ack_'+nonce+'.json'),owner,nonce)
    try:
        common.atomic(ROOT/'state.json',dict(stage='verified_finite_preflight',goal_complete=False));controls=program.runtime_controls();common.immutable(ROOT/'preflight_ready.json',common.raw(controls))
        current=R/'release/compiler_iterations/current.json';pointer=json.loads(current.read_bytes());summary=R/pointer['inventory']
        if common.sha(summary.read_bytes())!=pointer['inventory_sha256']:raise ValueError('latest_fullyaudited_inventory_pointer_changed')
        inventory=summary.parent;common.immutable(ROOT/'inventory_start.json',common.raw(dict(pointer=common.asset(current),summary=common.asset(summary))))
        source_pool=R/'release/compiler_iterations/source_pools'/RUN_ID
        common.atomic(ROOT/'state.json',dict(stage='source_only_full_scope_audit',goal_complete=False));audit=pool.prepare(source_pool,inventory)
        if not audit['selected']:
            failure=dict(stage='no_remaining_source_independent_known_families',source_pool=str(source_pool),goal_complete=False,next_action='Use the exhaustive source audit to diagnose source-family shortage; unknown supported families remain pending in the population. No thresholds were changed.')
            common.atomic(ROOT/'next_repair.json',failure);common.atomic(ROOT/'state.json',failure);return failure
        common.atomic(ROOT/'state.json',dict(stage='prepare_frozen_B_C',goal_complete=False));ready=program.prepare(source_pool,RUN_ID);common.immutable(ROOT/'prepared.json',common.raw(ready))
        controller.check_pins(freeze['pins']);launch=program.launch(Path(ready['program_dir']),4,900)
        handoff=dict(stage='fixed_validation_then_gated_mass_launched',program=launch,source_pool=str(source_pool),prepared=ready,workers=4,case_timeout_seconds=900,validation_samples_each=audit['selected'],runtime_controls=controls,goal_complete=False,watch=False,model_calls=0)
        common.immutable(ROOT/'handoff.json',common.raw(handoff));common.atomic(ROOT/'state.json',dict(stage=handoff['stage'],goal_complete=False));return handoff
    except BaseException as error:
        common.atomic(ROOT/'failure.json',dict(stage='finite_chain_requires_repair',reason=str(error),error_type=type(error).__name__,goal_complete=False,traceback=traceback.format_exc(),model_calls=0));common.atomic(ROOT/'state.json',dict(stage='finite_chain_requires_repair',goal_complete=False));raise


def launch():
    import compiler_native_source_repair_frontend_v1 as frontend
    import compiler_native_source_repair_iteration_batch_v1 as controller
    import compiler_types_program_v1 as common
    import compiler_native_source_repair_iteration_program_v1 as program
    program.check_controls(program.control_bundle(frontend));program.runtime_controls()
    ROOT.mkdir(parents=True,exist_ok=False);pins={**frontend.configuration()['pins'],**own_pins()};controller.check_pins(pins);common.immutable(ROOT/'freeze.json',common.raw(dict(pins=pins,workers=4,case_timeout_seconds=900,source_scope=1539,run_id=RUN_ID,gate=dict(minimum_fraction=.2,minimum_incremental=5,maximum_regressions=0,maximum_false_acceptances=0,maximum_infrastructure_failures=0),watch=False)))
    nonce=uuid.uuid4().hex;argv=[sys.executable,'-B',str(Path(__file__).resolve()),'execute','--nonce',nonce]
    with(ROOT/'chain.log').open('xb')as log:child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    from initial_conversion_process_v1 import identity
    birth=identity(child.pid);deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if child.poll()is not None:raise RuntimeError('finite_chain_exited_before_handshake')
        try:
            owner=json.loads((ROOT/'owner.json').read_bytes());current=identity(child.pid)
            if birth and current and owner['pid']==child.pid and owner['start_ticks']==birth['start_ticks']==current['start_ticks']and owner['nonce']==nonce:
                common.immutable(ROOT/('ack_'+nonce+'.json'),common.raw(owner));result=dict(pid=child.pid,start_ticks=birth['start_ticks'],argv=argv,chain_dir=str(ROOT),finite=True,watch=False,goal_complete=False);common.immutable(ROOT/'launch.json',common.raw(result));return result
        except(OSError,KeyError,ValueError):pass
        time.sleep(.05)
    raise RuntimeError('finite_chain_handshake_timeout_no_automatic_restart')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('launch','execute','preflight'));parser.add_argument('--nonce');args=parser.parse_args()
    result=launch()if args.action=='launch'else preflight()if args.action=='preflight'else execute(args.nonce);print(json.dumps(result),flush=True)
