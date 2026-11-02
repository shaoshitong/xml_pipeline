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
import compiler_source_core_attempts_v3 as history

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
RUN_ID='native_materialized_text_node_unseen100_20261101_v4'
ROOT=R/'release/compiler_iterations/chains'/RUN_ID
CONTROLS=R/'release/compiler_iterations/controls/native_materialized_text_node_runtime_controls_20261101_v4'
CONTROL_RUN='native_materialized_text_node_runtime_preflight_20261101_v4'
FAILED='eba2f26d00ab20976a97ed684ee07fd94192c9789b0265fd0cfa546416f867c7'
POSITIVE='59c543653635f629f0b52859a97d042e13c280f1fdb7bf7f00abd74c788b9b1f'
MODULES=('case','batch','program','controls','pool','finite_chain','overlap')


def own_pins():
    import compiler_types_program_v1 as common
    names=['compiler_native_materialized_text_node_iteration_'+name+'_v4.py'for name in ('batch','program','pool','chain')]+['compiler_native_materialized_text_node_iteration_case_v3.py','compiler_native_materialized_text_node_iteration_controls_v2.py','compiler_native_source_repair_iteration_family_v1.py','compiler_source_core_attempts_v3.py','compiler_typed_runtime_failure_v1.py','compiler_mermaid_alpha_iteration_overlap_v2.py','compiler_mermaid_alpha_qualifications_v2.py']
    return {**{str(W/'scripts'/name):common.sha((W/'scripts'/name).read_bytes())for name in names},str(R/history.CATALOG):common.sha((R/history.CATALOG).read_bytes())}


def positive_metadata(bundle,identifier):
    """Reuse the immutable accepted clean record, never a scratch candidate."""
    import compiler_types_program_v1 as common
    _,payload=common.checked(bundle['qualified_manifest'])
    matches=[row for line in payload.splitlines()if line for row in [json.loads(line)]if row['id']==identifier]
    if len(matches)!=1:raise ValueError('existing_clean_positive_manifest_missing_or_duplicate')
    row=matches[0];path,payload=common.checked(dict(file=row['metadata_file'],sha256=row['metadata_sha256']),clean=True);record=json.loads(payload)
    if(record['id'],record['source_code_sha256'],record['source_image_sha256'])!=(identifier,row['source_code_sha256'],row['source_image_sha256']):raise ValueError('existing_clean_positive_original_identity_changed')
    return str(path)


def canonical_rows():
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:return [db.execute('select*from jobs where id=?',(i,)).fetchone()for i in (FAILED,POSITIVE)]


def preflight():
    import compiler_types_program_v1 as common
    import compiler_native_source_repair_frontend_v2 as frontend
    import compiler_native_materialized_text_node_iteration_case_v3 as case
    import compiler_native_materialized_text_node_iteration_batch_v4 as controller
    import compiler_native_materialized_text_node_iteration_program_v4 as program
    import compiler_native_materialized_text_node_iteration_pool_v4 as pool
    program.check_controls(program.control_bundle(frontend))
    CONTROLS.mkdir(parents=True,exist_ok=False);before=canonical_rows();config=frontend.configuration();own=own_pins();pins={**config['pins'],**own}
    freeze=dict(pins=pins,qa_policy_sha256=common.sha(common.raw(dict(source=config['policy'],case=own[str(W/'scripts/compiler_native_materialized_text_node_iteration_case_v3.py')]))),predicate_hashes={frontend.UNIT:common.sha(common.raw(dict(consumed_controls_only=True,source_policy=config['policy'])))})
    freeze['implementation_identity']=controller.implementation_identity(freeze);freeze['implementation_identity_sha256']=controller.implementation_digest(freeze)
    normal_before=history.collect(config,root=R);history.validate(normal_before,config,root=R)
    if len(normal_before)!=4:raise ValueError('native_once_preflight_expected_four_consumed_normals')
    common.immutable(CONTROLS/'normal_history_before.jsonl',b''.join(common.raw(row)for row in normal_before))
    failures=[row for row in normal_before if row['id']==FAILED and row['evidence_kind']=='manual_development']
    if len(failures)!=1 or failures[0]['frontend']['sha256']!='935edd752fb5406043357109c07796277589867696d377b2607ef8cf188b6eff':raise ValueError('historical_same_core_manual_failure_changed')
    historical=failures[0];_,payload=common.checked(historical['frontend']);original=json.loads(payload)
    if original.get('ok')is not False or case.is_infrastructure(original):raise ValueError('historical_manual_event_not_ordinary_failure')
    common.immutable(CONTROLS/'historical_manual_failure_event.json',common.raw(historical))
    requests=[]
    for seq,job in enumerate(before,1):
        source=json.loads(job[4]);baseline=json.loads(job[9]);support=pool.static_support_from_job(frontend,job)
        if not support['supported']:raise ValueError('finite_consumed_control_outside_frozen_profile:'+json.dumps(support['reasons']))
        requests.append(dict(seq=seq,id=source['pair_sha256'],source=source,compiler_unit=frontend.UNIT,cluster='existing_consumed_real_preflight',evaluation_phase='candidate',source_capture_snapshot=support['source_capture_snapshot'],source_record_sha256=common.sha(job[9].encode()),baseline_code_sha256=baseline.get('code_sha256'),baseline_image_sha256=baseline.get('image_sha256')))
    positive=positive_metadata(program.control_bundle(frontend),POSITIVE)
    requests[0].update(evaluation_phase='control_failure_replay',existing_development_failure=historical['frontend'])
    requests[1].update(evaluation_phase='control_positive',existing_development_candidate=positive)
    program.validate_source_requests(requests)
    # Real consumed sources exercise this very pool dictionary/static-support
    # constructor and the actual complete-source validator before any dispatch.
    observed=[];contract_rows=[];contract_before=[]
    ids=[FAILED,POSITIVE,'04e7525044d8bc4417177303924cf8df108333af303376a297c36055d2a174b5','0133a0d0b8a43ed69b38b18150c948107bf1d59575f71e92a9d689cfa1e91a69','3b3bdbab801b84422e16a9539cae5d510348f1ba0656af8de1ae90fca32d6f5a']
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:
        for identifier in ids:
            job=database.execute('select*from jobs where id=?',(identifier,)).fetchone()
            if job is None:raise ValueError('consumed_source_contract_job_missing:'+identifier)
            contract_before.append(job);source=json.loads(job[4]);support=pool.static_support_from_job(frontend,job)
            if support['supported']is not True:raise ValueError('consumed_real_source_dictionary_contract_not_supported:'+identifier+':'+json.dumps(support['reasons']))
            row=pool.request_from_job(job,source,frontend.UNIT,support['source_capture_snapshot']);contract_rows.append(row);observed.append(dict(id=identifier,supported=True,canonical_job_columns=len(pool.canonical_job(job)),complete_source_fields=len(source)))
    program.validate_source_requests(contract_rows)
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:
        contract_after=[database.execute('select*from jobs where id=?',(identifier,)).fetchone()for identifier in ids]
    if contract_before!=contract_after:raise ValueError('consumed_source_contract_canonical_or_baseline_changed')
    common.immutable(CONTROLS/'source_contract_metadata.json',common.raw(dict(cases=observed,actual_pool_constructor_and_program_validator=True,canonical_baseline_and_capture_unchanged=True,canonical_sha256_before=common.sha(common.raw(contract_before)),canonical_sha256_after=common.sha(common.raw(contract_after)),new_heldout_consumed=0,normal_conversions=0)))
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
        value=json.loads(body);directory=R/value['evidence_directory'];front=directory/'frontend_result.json';actual=json.loads(front.read_bytes())if front.exists()else None;common.immutable(CONTROLS/(str(seq)+'_result.json'),common.raw(value))
        row=dict(id=identifier,seq=seq,status=status,attempts=attempts,result=common.asset(CONTROLS/(str(seq)+'_result.json')),frontend=common.asset(front)if front.exists()else None)
        if seq==1:
            if actual is None or status!='abandoned'or value.get('infrastructure_failure')is not False or actual.get('normal_source_conversion_called')is not False or actual.get('replayed_prior_normal_attempt')!=historical['frontend']:raise ValueError('normal_source_failure_incorrectly_infrastructure')
        else:
            if status!='qualified'or front.exists():raise ValueError('real_NativeSource_next_positive_not_qualified_without_reexecution')
            row['existing_positive_no_normal_reexecution']=True
            manifest=value['manifest'];_,blob=common.checked(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True);qa=R/value['quality_report'];case.full_quality(json.loads(qa.read_bytes()),json.loads(blob));row.update(manifest=manifest,quality=common.asset(qa));qualified[identifier]=manifest
        if attempts!=1:raise ValueError('preflight_case_attempt_not_once')
        cases.append(row)
    if len(cases)!=2 or canonical_rows()!=before:raise ValueError('canonical_original_jobs_changed_by_preflight')
    for item in program.readrows(Path(program.control_bundle(frontend)['qualified_manifest']['file'])):qualified.setdefault(item['id'],item)
    common.immutable(CONTROLS/'qualified.jsonl',b''.join(common.raw(qualified[i])for i in sorted(qualified)))
    normal_after=history.collect(config,root=R);history.validate(normal_after,config,root=R)
    if normal_after!=normal_before:raise ValueError('replay_controls_reexecuted_source_core')
    common.immutable(CONTROLS/'normal_history_after.jsonl',b''.join(common.raw(row)for row in normal_after))
    proof=dict(schema='real_typed_NativeSource_once_safe_runtime_dispatch_controls_v4',source_core=history.core_identity(config),normal_source_conversion_calls=0,ordinary_failure_replay_then_next_full_positive=True,same_core_normal_history_unchanged=True,historical_manual_failure_event=common.asset(CONTROLS/'historical_manual_failure_event.json'),source_contract_metadata=common.asset(CONTROLS/'source_contract_metadata.json'),normal_history_before=common.asset(CONTROLS/'normal_history_before.jsonl'),normal_history_after=common.asset(CONTROLS/'normal_history_after.jsonl'),producer=common.asset(Path(__file__)),orchestration_pins=own,source_configuration=config,freeze=common.asset(CONTROLS/'freeze.json'),input=common.asset(CONTROLS/'input.jsonl'),run=str(run),cases=cases,ordinary_failure_then_next_full_positive=True,no_infrastructure_stop=True,each_attempted_once=True,canonical_original_jobs_sha256_before=common.sha(common.raw(before)),canonical_original_jobs_sha256_after=common.sha(common.raw(canonical_rows())),canonical_original_jobs_unchanged=True,qualified_manifest=common.asset(CONTROLS/'qualified.jsonl'),new_heldout_consumed=0,model_calls=0,canonical_mutations=0)
    common.immutable(CONTROLS/'proof.json',common.raw(proof));program.runtime_controls();return common.asset(CONTROLS/'proof.json')


def execute(nonce):
    import compiler_types_program_v1 as common
    import compiler_native_materialized_text_node_iteration_batch_v4 as controller
    import compiler_native_materialized_text_node_iteration_program_v4 as program
    import compiler_native_materialized_text_node_iteration_pool_v4 as pool
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
    import compiler_native_source_repair_frontend_v2 as frontend
    import compiler_native_materialized_text_node_iteration_batch_v4 as controller
    import compiler_types_program_v1 as common
    import compiler_native_materialized_text_node_iteration_program_v4 as program
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
