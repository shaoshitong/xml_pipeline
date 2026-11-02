"""One finite source audit -> independent B/C -> fixed gated mass handoff."""
import argparse,json,os,sqlite3,subprocess,sys,time,traceback,uuid
from pathlib import Path
import compiler_source_core_attempts_v3 as history
import html_paragraph_source_contract_v9 as contract

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
RUN_ID='html_paragraph_unseen100_20261101_v9'
ROOT=R/'release/compiler_iterations/chains'/RUN_ID
CONTROLS=R/'release/compiler_iterations/controls/html_paragraph_runtime_controls_20261101_v9'
CONTROL_RUN='html_paragraph_runtime_preflight_20261101_v9'
CONSUMED='0bc37fc196e3f7ea12094ff9fe36f687bf2ff2c17308c27c7435ba5677ed4d20'
POSITIVE='002937254103449d702e89c8cf7f773e01110de0e74c96e66c6fab75ff18166a'


def own_pins():
    import compiler_types_program_v1 as common
    names=['html_paragraph_iteration_'+name+'_v9.py'for name in('batch','program','pool','chain','case')]+['html_paragraph_source_contract_v9.py','compiler_html_source_family_v1.py','compiler_html_paragraph_controls_v9.py','compiler_html_source_paragraph_quality_ro_v9.py','compiler_source_core_attempts_v3.py','compiler_plantuml_engine_canonical_claim_v1.py','compiler_typed_runtime_failure_v1.py','compiler_mermaid_alpha_iteration_overlap_v2.py','compiler_mermaid_alpha_qualifications_v2.py']
    return {**{str(W/'scripts'/name):common.sha((W/'scripts'/name).read_bytes())for name in names},str(R/contract.CATALOG):common.sha((R/contract.CATALOG).read_bytes())}


def positive_metadata(bundle,identifier):
    import compiler_types_program_v1 as common
    _,payload=common.checked(bundle['qualified_manifest']);rows=[json.loads(line)for line in payload.splitlines()if line];matched=[row for row in rows if row['id']==identifier]
    if len(matched)!=1:raise ValueError('HTML_existing_positive_manifest_not_unique')
    row=matched[0];path,body=common.checked(dict(file=row['metadata_file'],sha256=row['metadata_sha256']),clean=True);record=json.loads(body)
    if(record['id'],record['source_code_sha256'],record['source_image_sha256'])!=(identifier,row['source_code_sha256'],row['source_image_sha256']):raise ValueError('HTML_existing_positive_original_identity_changed')
    return str(path)


def canonical_rows(ids=(CONSUMED,POSITIVE)):
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:return[db.execute('select*from jobs where id=?',(identifier,)).fetchone()for identifier in ids]


def preflight():
    import compiler_types_program_v1 as common
    import html_paragraph_source_contract_v9 as frontend
    import html_paragraph_iteration_case_v9 as case
    import html_paragraph_iteration_batch_v9 as controller
    import html_paragraph_iteration_program_v9 as program
    import html_paragraph_iteration_pool_v9 as pool
    bundle=program.control_bundle(frontend);program.check_controls(bundle);config=frontend.configuration();before=canonical_rows();normal_before=history.collect(config,root=R,catalog=contract.CATALOG);history.validate(normal_before,config,root=R)
    if len(normal_before)!=3:raise ValueError('HTML_runtime_expected_three_consumed_normals')
    historical=next(row for row in normal_before if row['id']==CONSUMED)
    CONTROLS.mkdir(parents=True,exist_ok=False);own=own_pins();pins={**controller.base.pins(),**config['pins'],**own}
    freeze=dict(pins=pins,qa_policy_sha256=common.sha(common.raw(dict(source=config['policy'],case=own[str(W/'scripts/html_paragraph_iteration_case_v9.py')]))),predicate_hashes={frontend.UNIT:common.sha(common.raw(dict(consumed_controls_only=True,source_policy=config['policy'])))})
    freeze['implementation_identity']=controller.implementation_identity(freeze);freeze['implementation_identity_sha256']=controller.implementation_digest(freeze)
    common.immutable(CONTROLS/'normal_history_before.jsonl',b''.join(common.raw(row)for row in normal_before));common.immutable(CONTROLS/'historical_manual_normal_event.json',common.raw(historical))
    requests=[]
    for seq,job in enumerate(before,1):
        source=json.loads(job[4]);support=pool.static_support_from_job(frontend,job)
        if support.get('supported')is not True:raise ValueError('HTML_consumed_control_outside_static_profile')
        row=pool.request_from_job(job,source,frontend.UNIT,support['source_capture_snapshot']);row.update(seq=seq,cluster='known_consumed_runtime_control',evaluation_phase='candidate');requests.append(row)
    requests[1].update(evaluation_phase='control_positive',existing_development_candidate=positive_metadata(bundle,POSITIVE))
    program.validate_source_requests(requests)
    candidates=list(dict.fromkeys([CONSUMED,POSITIVE]+sorted(row['id']for row in pool.supplementary_development_rows())));ids=[];contract_rows=[];contract_before=[];observed=[]
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        for identifier in candidates:
            job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
            if job is None:raise ValueError('HTML_known_source_contract_job_missing')
            if job[2]!='html'or job[1]!='poster':continue
            support=pool.static_support_from_job(frontend,job)
            if support.get('supported')is not True:continue
            source=json.loads(job[4]);contract_rows.append(pool.request_from_job(job,source,frontend.UNIT,support['source_capture_snapshot']));contract_before.append(job);ids.append(identifier);observed.append(dict(id=identifier,supported=True,canonical_job_columns=len(pool.canonical_job(job)),complete_source_fields=len(source)))
            if len(ids)==5:break
    if len(ids)!=5:raise ValueError('HTML_five_consumed_source_contracts_unavailable')
    program.validate_source_requests(contract_rows);contract_after=canonical_rows(ids)
    if contract_after!=contract_before:raise ValueError('HTML_known_canonical_baseline_or_capture_changed')
    common.immutable(CONTROLS/'source_contract_metadata.json',common.raw(dict(cases=observed,actual_pool_constructor_and_program_validator=True,canonical_baseline_and_capture_unchanged=True,canonical_sha256_before=common.sha(common.raw(contract_before)),canonical_sha256_after=common.sha(common.raw(contract_after)),normal_conversions=0,new_heldout_consumed=0)))
    payload=b''.join(common.raw(row)for row in requests);freeze['input_sha256']=common.sha(payload);common.immutable(CONTROLS/'input.jsonl',payload);common.immutable(CONTROLS/'freeze.json',common.raw(freeze));run=controller.FLOOR/CONTROL_RUN;controller.create(run,CONTROLS/'input.jsonl',CONTROLS/'freeze.json','development')
    with(CONTROLS/'controller.log').open('xb')as log:
        result=subprocess.run([sys.executable,'-B',str(Path(controller.__file__)),'run','--run-id',CONTROL_RUN,'--workers','1','--case-timeout','900'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:raise RuntimeError('HTML_real_controller_preflight_failed')
    state=controller.snapshot(run)
    if state['infrastructure_stop']or not state['metadata'].get('finished'):raise ValueError('HTML_precall_guard_stopped_next_dispatch')
    with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as db:rows=db.execute('select seq,id,status,attempts,result from samples order by seq').fetchall()
    cases=[];qualified={}
    for seq,identifier,status,attempts,body in rows:
        value=json.loads(body);directory=R/value['evidence_directory'];front=directory/'frontend_result.json'
        if attempts!=1 or front.exists():raise ValueError('HTML_runtime_control_reexecuted_normal')
        common.immutable(CONTROLS/(str(seq)+'_result.json'),common.raw(value));row=dict(id=identifier,seq=seq,status=status,attempts=attempts,result=common.asset(CONTROLS/(str(seq)+'_result.json')),frontend=None)
        if seq==1:
            if status!='abandoned'or value.get('phase')!='input'or value.get('infrastructure_failure')is not False or value.get('detail')not in('same_source_core_already_attempted_preserved','already_qualified_complete_original_preserved'):raise ValueError('HTML_manual_consumed_normal_not_proved_prevented')
        else:
            if status!='qualified':raise ValueError('HTML_existing_positive_not_full_qualified')
            manifest=value['manifest'];_,blob=common.checked(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True);qa=R/value['quality_report'];case.full_quality(json.loads(qa.read_bytes()),json.loads(blob));row.update(existing_positive_no_normal_reexecution=True,manifest=manifest,quality=common.asset(qa));qualified[identifier]=manifest
        cases.append(row)
    if canonical_rows()!=before:raise ValueError('HTML_runtime_preflight_changed_original_jobs')
    _,blob=common.checked(bundle['qualified_manifest'])
    for line in blob.splitlines():
        if line:item=json.loads(line);qualified.setdefault(item['id'],item)
    common.immutable(CONTROLS/'qualified.jsonl',b''.join(common.raw(qualified[identifier])for identifier in sorted(qualified)))
    normal_after=history.collect(config,root=R,catalog=contract.CATALOG);history.validate(normal_after,config,root=R)
    if normal_after!=normal_before:raise ValueError('HTML_runtime_reexecuted_normal_source_core')
    common.immutable(CONTROLS/'normal_history_after.jsonl',b''.join(common.raw(row)for row in normal_after))
    proof=dict(schema='real_once_safe_HTML_paragraph_runtime_dispatch_controls_v9',producer=common.asset(Path(__file__)),orchestration_pins=own,source_configuration=config,source_core=history.core_identity(config),freeze=common.asset(CONTROLS/'freeze.json'),input=common.asset(CONTROLS/'input.jsonl'),run=str(run),historical_manual_normal_event=common.asset(CONTROLS/'historical_manual_normal_event.json'),normal_history_before=common.asset(CONTROLS/'normal_history_before.jsonl'),normal_history_after=common.asset(CONTROLS/'normal_history_after.jsonl'),source_contract_metadata=common.asset(CONTROLS/'source_contract_metadata.json'),cases=cases,consumed_normal_prevented_then_next_full_positive=True,same_core_normal_history_unchanged=True,normal_source_conversion_calls=0,no_infrastructure_stop=True,each_attempted_once=True,canonical_original_jobs_unchanged=True,canonical_sha256_before=common.sha(common.raw(before)),canonical_sha256_after=common.sha(common.raw(canonical_rows())),qualified_manifest=common.asset(CONTROLS/'qualified.jsonl'),new_heldout_consumed=0,model_calls=0,goal_complete=False)
    common.immutable(CONTROLS/'proof.json',common.raw(proof));program.runtime_controls();return common.asset(CONTROLS/'proof.json')


def execute(nonce):
    import compiler_types_program_v1 as common
    import html_paragraph_iteration_batch_v9 as controller
    import html_paragraph_iteration_program_v9 as program
    import html_paragraph_iteration_pool_v9 as pool
    freeze=json.loads((ROOT/'freeze.json').read_bytes());controller.check_pins(freeze['pins']);owner={**controller.process_identity(),'nonce':nonce,'argv':sys.argv,'finite':True,'watch':False};common.atomic(ROOT/'owner.json',owner);common.wait_ack(ROOT/('ack_'+nonce+'.json'),owner,nonce)
    try:
        common.atomic(ROOT/'state.json',dict(stage='verified_finite_preflight',goal_complete=False));controls=program.runtime_controls();common.immutable(ROOT/'preflight_ready.json',common.raw(controls));pointer=json.loads((R/'release/compiler_iterations/current.json').read_bytes());summary=R/pointer['inventory']
        if common.sha(summary.read_bytes())!=pointer['inventory_sha256']:raise ValueError('audited_inventory_pointer_changed')
        common.immutable(ROOT/'inventory_start.json',common.raw(dict(summary=common.asset(summary))));source_pool=R/'release/compiler_iterations/source_pools'/RUN_ID;common.atomic(ROOT/'state.json',dict(stage='source_only_full_scope_audit',goal_complete=False));audit=pool.prepare(source_pool,summary.parent)
        if not audit['selected']:
            value=dict(stage='source_family_repair_required_no_remaining_independent_observed_family',goal_complete=False,source_pool=str(source_pool),next_action='Improve generic source family accounting using the source audit; retain every applicable pending original and all thresholds. This is not format completion.');common.atomic(ROOT/'next_repair.json',value);common.atomic(ROOT/'state.json',value);return value
        common.atomic(ROOT/'state.json',dict(stage='prepare_frozen_B_C',goal_complete=False));ready=program.prepare(source_pool,RUN_ID);common.immutable(ROOT/'prepared.json',common.raw(ready));controller.check_pins(freeze['pins']);started=program.launch(Path(ready['program_dir']),4,900);handoff=dict(stage='fixed_validation_then_gated_mass_launched',program=started,prepared=ready,source_pool=str(source_pool),validation_samples_each=audit['selected'],runtime_controls=controls,workers=4,case_timeout_seconds=900,goal_complete=False,watch=False,model_calls=0);common.immutable(ROOT/'handoff.json',common.raw(handoff));common.atomic(ROOT/'state.json',dict(stage=handoff['stage'],goal_complete=False));return handoff
    except BaseException as error:
        common.atomic(ROOT/'failure.json',dict(stage='finite_chain_requires_generic_repair',reason=str(error),error_type=type(error).__name__,traceback=traceback.format_exc(),goal_complete=False,model_calls=0));common.atomic(ROOT/'state.json',dict(stage='finite_chain_requires_generic_repair',goal_complete=False));raise


def launch():
    import compiler_types_program_v1 as common
    import html_paragraph_iteration_batch_v9 as controller
    import html_paragraph_iteration_program_v9 as program
    program.check_controls(program.control_bundle(contract));program.runtime_controls();pins={**controller.base.pins(),**contract.configuration()['pins'],**own_pins()};controller.check_pins(pins);ROOT.mkdir(parents=True,exist_ok=False);common.immutable(ROOT/'freeze.json',common.raw(dict(pins=pins,workers=4,case_timeout_seconds=900,source_scope=24739,global_identity_provenance_scope=131904,run_id=RUN_ID,gate=dict(minimum_fraction=.2,minimum_incremental=5,maximum_regressions=0,maximum_false_acceptances=0,maximum_infrastructure_failures=0),watch=False)))
    nonce=uuid.uuid4().hex;argv=[sys.executable,'-B',str(Path(__file__).resolve()),'execute','--nonce',nonce]
    with(ROOT/'chain.log').open('xb')as log:child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    from initial_conversion_process_v1 import identity
    birth=identity(child.pid);deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if child.poll()is not None:raise RuntimeError('HTML_chain_exited_before_handshake')
        try:
            owner=json.loads((ROOT/'owner.json').read_bytes());current=identity(child.pid)
            if birth and current and owner['pid']==child.pid and owner['start_ticks']==birth['start_ticks']==current['start_ticks']and owner['nonce']==nonce:
                common.immutable(ROOT/('ack_'+nonce+'.json'),common.raw(owner));value=dict(pid=child.pid,start_ticks=birth['start_ticks'],argv=argv,chain_dir=str(ROOT),finite=True,watch=False,goal_complete=False);common.immutable(ROOT/'launch.json',common.raw(value));return value
        except(OSError,ValueError,KeyError):pass
        time.sleep(.05)
    raise RuntimeError('HTML_chain_handshake_timeout_no_restart')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('preflight','launch','execute'));parser.add_argument('--nonce');args=parser.parse_args();value=preflight()if args.action=='preflight'else launch()if args.action=='launch'else execute(args.nonce);print(json.dumps(value),flush=True)
