"""Finite frozen iterative compiler execution (new version, prior runs unchanged). Only this run's ledger is writable.

The caller freezes a manifest and implementation before validation or release.
A batch release additionally requires a hash-bound, passing validation gate.
"""
import argparse
import concurrent.futures
import contextlib
import fcntl
import json
import multiprocessing
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import fixed_batch_pipeline_v1 as base

R=base.R
W=base.W
FLOOR=R/'release/compiler_iterations/runs'
WORK=W/'compiler_iterations'
CASE=W/'scripts/compiler_native_source_repair_iteration_case_v1.py'
EXECUTION_PROTOCOL='generation_flock_v1'


def owned(run):
    run=Path(run).resolve()
    if not run.is_relative_to(FLOOR.resolve()) or run==FLOOR.resolve():
        raise ValueError('compiler_run_outside_release_owner')
    return run


def check_pins(pins):
    import initial_conversion_process_v1 as process
    required=[CASE,Path(__file__),Path(base.__file__),Path(process.__file__),Path(__file__).with_name('compiler_typed_runtime_failure_v1.py'),Path(__file__).with_name('compiler_native_source_repair_iteration_overlap_v1.py')]
    canonical={str(Path(path).resolve()) for path in pins or {}}
    if not all(str(path.resolve()) in canonical for path in required):
        raise ValueError('compiler_control_module_missing_from_freeze')
    base.ensure_pins(pins)


def _digest(value,field):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('invalid_compiler_identity_digest:'+field)
    return value


def implementation_identity(freeze):
    """Identity of everything approved, independent of input set/run name."""
    pins={};aliases={}
    for path,digest in freeze.get('pins',{}).items():
        canonical=str(Path(path).resolve())
        digest=_digest(digest,'pins:'+canonical)
        if canonical in pins and pins[canonical]!=digest:
            raise ValueError('conflicting_canonical_compiler_pin:'+canonical)
        pins[canonical]=digest
        aliases[str(Path(path).absolute())]=canonical
    predicates=freeze.get('predicate_hashes')
    if not pins or not isinstance(predicates,dict) or not predicates:
        raise ValueError('missing_compiler_implementation_identity')
    return dict(schema='compiler_implementation_identity_alias_bound_v2',pins=dict(sorted(pins.items())),
                raw_path_resolutions=dict(sorted(aliases.items())),
                qa_policy_sha256=_digest(freeze.get('qa_policy_sha256'),'qa_policy_sha256'),
                predicate_hashes={unit:_digest(value,'predicate:'+unit)
                                  for unit,value in sorted(predicates.items())})


def implementation_digest(freeze):
    return base.sha(base.raw(implementation_identity(freeze)))


def check_implementation_identity(freeze):
    identity=implementation_identity(freeze)
    if (freeze.get('implementation_identity',identity)!=identity or
            freeze.get('implementation_identity_sha256')!=base.sha(base.raw(identity))):
        raise ValueError('compiler_freeze_implementation_identity_changed')
    return identity


def release_gate(freeze, units):
    identity=check_implementation_identity(freeze)
    proof=freeze.get('release_gate') or {}
    path=Path(proof.get('file',''))
    if not path.is_file() or base.sha(path.read_bytes())!=proof.get('sha256'):
        raise ValueError('missing_or_changed_iteration_validation_gate')
    gate=json.loads(path.read_bytes())
    if gate.get('implementation_identity')!=identity or gate.get('implementation_identity_sha256')!=implementation_digest(freeze):
        raise ValueError('validation_gate_implementation_identity_mismatch')
    if not units or not units<=set(gate.get('approved_units',[])) or not gate.get('controls_passed') or gate.get('infrastructure_errors')!=0:
        raise ValueError('unvalidated_iteration_release_unit_or_controls')
    from compiler_native_source_repair_iteration_program_v1 import verify_release_gate
    verify_release_gate(path,freeze,units)
    return gate


def create(run,manifest,freeze_file,mode):
    run=owned(run)
    if run.exists():
        raise ValueError('compiler_run_exists_use_resume')
    manifest=Path(manifest);freeze_file=Path(freeze_file)
    payload=manifest.read_bytes();freeze=json.loads(freeze_file.read_bytes())
    check_pins(freeze['pins'])
    check_implementation_identity(freeze)
    if base.sha(payload)!=freeze['input_sha256']:
        raise ValueError('compiler_input_not_frozen')
    rows=[json.loads(line) for line in payload.splitlines() if line]
    ids=set();units=set()
    for seq,row in enumerate(rows,1):
        source=row['source'];identifier=row['id']
        if row['seq']!=seq or identifier in ids or identifier!=source['pair_sha256']:
            raise ValueError('compiler_input_id_or_order_mismatch')
        if source['category'] not in ('scientific_diagram','poster'):
            raise ValueError('compiler_input_outside_categories')
        ids.add(identifier);units.add(row['compiler_unit'])
    if not rows:
        raise ValueError('empty_compiler_manifest')
    if not units<=set(freeze['predicate_hashes']):
        raise ValueError('compiler_unit_missing_frozen_predicate')
    if mode=='batch':
        release_gate(freeze,units)
    elif mode not in ('development','validation'):
        raise ValueError('unknown_compiler_run_mode')
    run.mkdir(parents=True)
    base.atomic(run/'targets.jsonl',payload)
    base.atomic(run/'freeze.json',base.raw(freeze))
    d=sqlite3.connect(run/'status.sqlite')
    d.execute('pragma journal_mode=WAL');d.execute('pragma synchronous=FULL')
    base.create_schema(d)
    for row in rows:
        d.execute('insert into samples(seq,id,source) values(?,?,?)',
                  (row['seq'],row['id'],json.dumps(row,ensure_ascii=False)))
    for key,value in dict(total=len(rows),full_scope=False,scope_total=131904,
                          mode=mode,policy='compiler_types_single_pass_v1',compiler_version='native_source_font_runs_iteration_v1',
                          input_sha256=base.sha(payload),freeze_sha256=base.sha(base.raw(freeze)),
                          units=sorted(units),created_at=base.now(),finished=False,model_calls=0).items():
        base.meta(d,key,value)
    base.meta(d,'execution_protocol',EXECUTION_PROTOCOL)
    durable(run/'generation.json',dict(protocol=EXECUTION_PROTOCOL,token=uuid.uuid4().hex,
                                      created_at=base.now()))
    d.commit();d.close()
    return snapshot(run)


def snapshot(run):
    run=owned(run)
    d=sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)
    meta=base.metadata(d)
    counts=dict(d.execute('select status,count(*) from samples group by status'))
    attempts=dict(d.execute('select attempts,count(*) from samples group by attempts'))
    d.close();owner={};live=False
    try:
        owner=json.loads((run/'owner.json').read_bytes())
        from initial_conversion_process_v1 import identity
        current=identity(owner['pid'])
        command=Path('/proc',str(owner['pid']),'cmdline').read_bytes().split(b'\0')
        live=bool(current and current['state']!='Z' and current['start_ticks']==owner['start_ticks']
                  and str(Path(__file__).resolve()).encode() in command)
    except (OSError,ValueError,KeyError):
        pass
    return dict(at=base.now(),run=str(run),metadata=meta,counts=counts,
                dispatch_attempt_counts=attempts,supervisor_live=live,owner=owner,
                infrastructure_stop=(run/'infrastructure_stop.json').exists())


def process_identity():
    from initial_conversion_process_v1 import identity
    return identity(os.getpid()) or dict(pid=os.getpid(),start_ticks=None,state='unavailable')


def durable(path,value):
    """Persist the directory entry as well as atomic()'s fsynced file bytes."""
    path=Path(path);base.atomic(path,base.raw(value))
    directory=path.parent
    while directory.is_relative_to(R):
        fd=os.open(directory,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(fd)
        finally:os.close(fd)
        if directory==R:break
        directory=directory.parent


def task_identity(task):
    source=task['source']
    return dict(id=task['id'],seq=task['seq'],compiler_unit=task['compiler_unit'],
                source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])


def failure(task,reason,**details):
    return dict(**task_identity(task),status='abandoned',reason=reason,
                cluster=task.get('cluster'),compiler_version='native_source_font_runs_iteration_v1',model_calls=0,**details)


def validate_case_result(value,expected):
    if not isinstance(value,dict):
        raise RuntimeError('compiler_case_result_not_object')
    for key in ('id','seq','compiler_unit','source_code_sha256','source_image_sha256'):
        if value.get(key)!=expected[key]:
            raise RuntimeError('compiler_case_result_identity_mismatch:'+key)
    if value.get('status') not in base.TERMINAL:
        raise RuntimeError('compiler_case_did_not_return_terminal_status')
    if 'infrastructure_failure'in value and type(value['infrastructure_failure'])is not bool:
        raise RuntimeError('compiler_case_infrastructure_flag_not_boolean')
    if value['status']=='qualified':
        manifest=value.get('manifest')
        if not isinstance(manifest,dict):
            raise RuntimeError('compiler_qualified_result_missing_manifest')
        for key in ('id','source_code_sha256','source_image_sha256'):
            if manifest.get(key)!=expected[key]:
                raise RuntimeError('compiler_qualified_manifest_identity_mismatch:'+key)
        for key in ('code_file','code_sha256','image_file','image_sha256','original_source_code',
                    'original_reference','metadata_file','metadata_sha256'):
            if not isinstance(manifest.get(key),str) or not manifest[key]:
                raise RuntimeError('compiler_qualified_manifest_missing_field:'+key)
    return value


@contextlib.contextmanager
def execution_lock(run,exclusive=False):
    """Worker holds SH across its entire child tree; recovery requires EX."""
    with (Path(run)/'execution.lock').open('a+') as lock:
        flags=fcntl.LOCK_EX|fcntl.LOCK_NB if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(lock,flags)
        except BlockingIOError as error:
            raise RuntimeError('resume_execution_workers_still_locked') from error
        try:
            yield
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)


def phase(task,name,**details):
    durable(Path(task['work'])/'execution.json',dict(
        protocol=EXECUTION_PROTOCOL,generation=task['generation'],phase=name,
        owner=process_identity(),at=base.now(),**task_identity(task),**details))


def prepare_dispatch(run,row,claimed,pins,timeout,mode,generation):
    task={**row,**claimed,'work':str(WORK/run.name/(str(claimed['seq']).zfill(6)+'_'+claimed['id'])),
          'run':str(run),'generation':generation,'pins':pins,
          'case_timeout_seconds':timeout,'mode':mode}
    work=Path(task['work']);work.mkdir(parents=True,exist_ok=False)
    durable(work/'request.json',task)
    phase(task,'claimed')
    return task


def execute(task):
    run=owned(task['run']);work=Path(task['work'])
    expected_work=WORK/run.name/(str(task['seq']).zfill(6)+'_'+task['id'])
    if work.resolve()!=expected_work.resolve():
        raise RuntimeError('compiler_worker_work_identity_mismatch')
    with execution_lock(run):
        current=json.loads((run/'generation.json').read_bytes())
        if current.get('protocol')!=EXECUTION_PROTOCOL or current.get('token')!=task['generation']:
            # Never touch the work marker: recovery may have already closed it.
            return failure(task,'compiler_stale_generation',case_cleanup_complete=True,
                           cleanup_basis='rejected_before_spawn')
        if base.sha((work/'request.json').read_bytes())!=base.sha(base.raw(task)):
            raise RuntimeError('compiler_worker_request_identity_mismatch')
        check_pins(task['pins'])
        frozen=json.loads((run/'freeze.json').read_bytes())
        if frozen['pins']!=task['pins']:raise RuntimeError('compiler_worker_pins_differ_from_frozen_run')
        check_implementation_identity(frozen)
        phase(task,'worker_locked')
        env={k:os.environ[k] for k in ('PATH','HOME','LANG','LC_ALL','TMPDIR','XDG_CACHE_HOME') if k in os.environ}
        env.update(PYTHONPATH=str(R/'env')+':'+str(W/'scripts'),PYTHONDONTWRITEBYTECODE='1',
                   OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        # This durable marker precedes every possible child spawn. An intent
        # without cleanup proof remains ambiguous even if the worker PID died.
        phase(task,'spawn_intent')
        from initial_conversion_process_v1 import run as isolated
        evidence=isolated([sys.executable,'-B',str(CASE),str(work/'request.json')],
                          work,task['case_timeout_seconds'],env)
        durable(work/'isolation.json',evidence)
        phase(task,'isolation_complete',cleanup_complete=evidence.get('cleanup_complete') is True)
        result=dict(**task_identity(task),cluster=task.get('cluster'),compiler_version='native_source_font_runs_iteration_v1',model_calls=0,
                    evidence_directory=str(work.relative_to(R)),
                    case_cleanup_complete=evidence.get('cleanup_complete') is True)
        if not result['case_cleanup_complete']:
            return dict(result,status='abandoned',reason='compiler_case_cleanup_failed',infrastructure_failure=True)
        if evidence.get('deadline_exceeded'):
            return dict(result,status='abandoned',phase='timeout',reason='compiler_case_timeout',
                        timeout_seconds=task['case_timeout_seconds'])
        target=work/'result.json'
        if not evidence.get('ok') or not target.is_file():
            return dict(result,status='abandoned',phase='runtime',reason='compiler_case_process_failed',
                        infrastructure_failure=True,process=evidence)
        value=validate_case_result(json.loads(target.read_bytes()),result)
        return {**value,**result}


def export(run,final=False):
    result=base.export(run,final)
    result['interpretation']='One frozen compiler attempt per target ID; failures and unsupported features are explicit. Every failed or unsupported sample remains pending for the next compiler repair. This round does not complete the overall goal.'
    result['scope_total']=131904
    base.atomic(Path(run)/('summary.json' if final else 'progress.json'),base.raw(result))
    return result


def final_asset_audit(d):
    audited=failed=0
    for seq,body,result_body in d.execute('select seq,source,result from samples where status="qualified"').fetchall():
        source=json.loads(body)['source'];result=json.loads(result_body);manifest=result['manifest']
        try:
            if (manifest['id'],manifest['source_code_sha256'],manifest['source_image_sha256'])!=(result['id'],source['code_sha256'],source['image_sha256']):
                raise ValueError('compiler_qualified_source_identity_changed')
            for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),
                                 ('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),
                                 ('metadata_file','metadata_sha256')]:
                path=(R/manifest[field]).resolve(strict=True)
                if not path.is_relative_to((R/'clean').resolve()) or base.sha(path.read_bytes())!=manifest[digest]:
                    raise ValueError('compiler_qualified_payload_not_complete_in_clean:'+field)
            audited+=1
        except Exception as error:
            failed+=1;result.update(status='abandoned',reason='compiler_final_asset_audit_failed',
                                    detail=repr(error),prior_qualified_manifest=result.pop('manifest'))
            d.execute('update samples set status="abandoned",result=?,finished_at=? where seq=?',
                      (json.dumps(result,ensure_ascii=False),base.now(),seq))
    d.commit()
    return dict(at=base.now(),qualified_payloads_verified=audited,late_asset_failures=failed)


def resume_interrupted(run,d):
    from initial_conversion_process_v1 import identity
    if base.metadata(d).get('execution_protocol')!=EXECUTION_PROTOCOL:
        raise RuntimeError('resume_requires_generation_lock_protocol')
    recovered=[]
    with execution_lock(run,exclusive=True):
        # No previous worker is inside its execution scope. Workers queued in
        # an orphan executor can only acquire SH after this fence, then reject
        # the old token before touching a marker or spawning anything.
        generation=uuid.uuid4().hex
        durable(run/'generation.json',dict(protocol=EXECUTION_PROTOCOL,token=generation,
                                          created_at=base.now(),owner=process_identity()))
        for seq,identifier,body in d.execute('select seq,id,source from samples where status="running"').fetchall():
            row=json.loads(body);task={**row,'id':identifier,'seq':seq}
            work=WORK/run.name/(str(seq).zfill(6)+'_'+identifier);proof=work/'isolation.json'
            failed_submission=(work/'submission_failure.json').is_file()
            failed_worker=(work/'worker_failure.json').is_file()
            failure_reason='compiler_submit_failed' if failed_submission else 'compiler_supervisor_error' if failed_worker else None
            if not proof.is_file():
                marker_path=work/'execution.json'
                marker=json.loads(marker_path.read_bytes()) if marker_path.is_file() else None
                if marker is None and work.is_dir() and any(
                        p.name not in ('request.json','submission_failure.json','worker_failure.json')
                        for p in work.iterdir()):
                    raise RuntimeError('resume_unmarked_work_requires_cleanup_proof:'+identifier)
                if marker is not None:
                    for key,value in task_identity(task).items():
                        if marker.get(key)!=value:
                            raise RuntimeError('resume_execution_marker_identity_mismatch:'+identifier+':'+key)
                    if marker.get('protocol')!=EXECUTION_PROTOCOL or marker.get('phase') not in ('claimed','worker_locked'):
                        raise RuntimeError('resume_needs_prior_tree_cleanup_proof:'+identifier)
                result=failure(task,failure_reason or 'compiler_dispatch_interrupted',
                               phase='dispatch',case_cleanup_complete=True,
                               cleanup_basis='exclusive_execution_lock_and_generation_fence_no_spawn_intent',
                               infrastructure_failure=bool(failure_reason),recovered_without_reexecution=True)
            else:
                iso=json.loads(proof.read_bytes())
                if iso.get('cleanup_complete') is not True:
                    raise RuntimeError('resume_prior_tree_not_clean:'+identifier)
                for prior in iso.get('tracked_processes',[]):
                    current=identity(prior['pid'])
                    if current and current.get('state')!='Z' and current.get('start_ticks')==prior.get('start_ticks'):
                        raise RuntimeError('resume_prior_process_still_live:'+identifier)
                p=work/'result.json'
                if failure_reason:
                    result=failure(task,failure_reason,phase='dispatch',infrastructure_failure=True,
                                   case_cleanup_complete=True,cleanup_basis='isolation_cleanup_proof',
                                   recovered_without_reexecution=True)
                elif p.is_file():
                    try:
                        out=json.loads(p.read_bytes())
                        validate_case_result(out,task_identity(task))
                        result={**out,'case_cleanup_complete':True,'recovered_without_reexecution':True}
                    except (RuntimeError,ValueError,TypeError) as error:
                        result=failure(task,'compiler_interrupted_result_invalid',detail=repr(error),
                                       infrastructure_failure=True,case_cleanup_complete=True,
                                       recovered_without_reexecution=True)
                else:
                    result=failure(task,'compiler_interrupted_attempt',case_cleanup_complete=True,
                                   recovered_without_reexecution=True)
            base.finish(d,seq,result);recovered.append(result)
    return dict(generation=generation,recovered=recovered,
                infrastructure_failures=[r for r in recovered if r.get('infrastructure_failure')])


def run_batch(run,workers,timeout):
    run=owned(run)
    with (run/'run.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with contextlib.closing(sqlite3.connect(run/'status.sqlite')) as d:
            return _run_batch_locked(run,workers,timeout,d)


def _run_batch_locked(run,workers,timeout,d):
    freeze=json.loads((run/'freeze.json').read_bytes());check_pins(freeze['pins']);check_implementation_identity(freeze)
    d.execute('pragma synchronous=FULL');meta=base.metadata(d)
    if base.sha(base.raw(freeze))!=meta['freeze_sha256']:
        raise ValueError('compiler_freeze_changed_after_create')
    if base.sha((run/'targets.jsonl').read_bytes())!=meta['input_sha256']:
        raise ValueError('compiler_targets_changed_after_create')
    if meta['mode']=='batch':release_gate(freeze,set(meta['units']))
    if (run/'infrastructure_stop.json').exists():raise RuntimeError('existing_infrastructure_stop_requires_new_freeze')
    if meta.get('finished'):return export(run,True)
    recovery=resume_interrupted(run,d)
    if recovery['infrastructure_failures']:
        durable(run/'infrastructure_stop.json',dict(at=base.now(),reason='compiler_resume_infrastructure_failure',
                                                  failures=recovery['infrastructure_failures']))
        return export(run)
    generation=recovery['generation']
    owner=dict(pid=os.getpid(),start_ticks=process_identity()['start_ticks'],
               at=base.now(),workers=workers,case_timeout_seconds=timeout,mode=meta['mode'],
               freeze_sha256=meta['freeze_sha256'],generation=generation,
               execution_protocol=EXECUTION_PROTOCOL,watch=False,model_calls=0)
    base.atomic(run/'owner.json',base.raw(owner))
    control=run/'control.json'
    if not control.exists():base.atomic(control,base.raw({'stop_dispatch':False}))
    todo=iter(d.execute('select seq from samples where status="queued" order by seq').fetchall())
    active={};exhausted=False;fatal=None;deferred=False;completed_count=0;last_export=time.monotonic()
    try:
        context=multiprocessing.get_context('spawn')
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=context) as pool:
            while active or not exhausted:
                check_pins(freeze['pins'])
                check_implementation_identity(freeze)
                stopped=json.loads(control.read_bytes()).get('stop_dispatch') is True
                while not exhausted and not fatal and not stopped and len(active)<workers:
                    entry=next(todo,None)
                    if entry is None:exhausted=True;break
                    seq=entry[0];claimed=base.claim(d,seq);row=claimed.pop('source')
                    task=prepare_dispatch(run,row,claimed,freeze['pins'],timeout,meta['mode'],generation)
                    try:
                        active[pool.submit(execute,task)]=task
                    except Exception as error:
                        fatal=failure(task,'compiler_submit_failed',detail=repr(error),infrastructure_failure=True)
                        durable(Path(task['work'])/'submission_failure.json',fatal)
                        # submit may fail after queuing a call. Drain the pool,
                        # then fence/recover under EX before declaring no spawn.
                        deferred=True;break
                if not active:break
                done,_=concurrent.futures.wait(active,timeout=5,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    task=active.pop(future)
                    try:result=future.result()
                    except Exception as error:
                        result=failure(task,'compiler_supervisor_error',detail=repr(error),infrastructure_failure=True)
                    if result.get('infrastructure_failure') and result.get('case_cleanup_complete') is not True:
                        durable(Path(task['work'])/'worker_failure.json',result)
                        deferred=True
                    else:
                        base.finish(d,task['seq'],result);completed_count+=1
                    if result.get('infrastructure_failure'):fatal=result
                    print(json.dumps(dict(at=base.now(),completed_this_start=completed_count,
                                          seq=task['seq'],status='running' if result.get('case_cleanup_complete') is not True
                                          and result.get('infrastructure_failure') else result['status'],
                                          reported_case_status=result['status'],reason=result.get('reason'))),flush=True)
                if time.monotonic()-last_export>30:
                    export(run);last_export=time.monotonic()
            if fatal:base.atomic(run/'infrastructure_stop.json',base.raw(fatal))
        if deferred:
            recovery=resume_interrupted(run,d)
            completed_count+=len(recovery['recovered'])
            if recovery['infrastructure_failures']:
                durable(run/'infrastructure_stop.json',dict(at=base.now(),reason='compiler_dispatch_infrastructure_failure',
                                                          failures=recovery['infrastructure_failures']))
        remaining=d.execute('select count(*) from samples where status not in ("qualified","abandoned")').fetchone()[0]
        if remaining==0:
            audit=final_asset_audit(d);base.atomic(run/'final_asset_audit.json',base.raw(audit))
            result=export(run,True)
            base.meta(d,'finished',True);base.meta(d,'finished_at',base.now());d.commit()
            return result
        return export(run)
    except BaseException as error:
        base.atomic(run/'infrastructure_stop.json',base.raw(dict(at=base.now(),reason='compiler_parent_error',detail=repr(error))))
        raise


def cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('create','run','status','export'))
    p.add_argument('--run-id',required=True);p.add_argument('--manifest');p.add_argument('--freeze')
    p.add_argument('--mode',choices=('development','validation','batch'),default='validation')
    p.add_argument('--workers',type=int,default=4);p.add_argument('--case-timeout',type=float,default=900)
    p.add_argument('--program-start');p.add_argument('--program-ack');p.add_argument('--program-nonce')
    a=p.parse_args()
    if not a.run_id or not all(c.isalnum() or c in '-_' for c in a.run_id):p.error('invalid run ID')
    if not 1<=a.workers<=24 or not 1<=a.case_timeout<=1800:p.error('invalid resource limits')
    run=FLOOR/a.run_id
    if a.action=='create':result=create(run,a.manifest,a.freeze,a.mode)
    elif a.action=='run':
        if a.program_start or a.program_ack or a.program_nonce:
            if not all((a.program_start,a.program_ack,a.program_nonce)):raise ValueError('incomplete_program_handshake')
            start=Path(a.program_start).resolve();ack=Path(a.program_ack).resolve()
            if start.parent!=run.resolve() or ack.parent!=run.resolve():raise ValueError('program_handshake_outside_run')
            own={**process_identity(),'nonce':a.program_nonce,'argv':sys.argv,'run':str(run)};durable(start,own)
            from compiler_types_program_v1 import wait_ack
            wait_ack(ack,own,a.program_nonce)
        result=run_batch(run,a.workers,a.case_timeout)
    elif a.action=='status':result=snapshot(run)
    else:result=export(run)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':cli()
