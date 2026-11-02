"""Reuse a sealed full-source audit; exhaust all remaining independent families.

The child hands off B/C and approved mass to a fixed program, without a watcher.
"""
import argparse,fcntl,importlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
from compiler_types_program_v1 import R,W,raw,sha,asset,checked,immutable,atomic,wait_ack
from initial_conversion_process_v1 import identity
import compiler_svg_source_viewport_iteration_program_v2 as program
import compiler_svg_source_viewport_iteration_launch_chain_v1 as legacy

RUN_ID='svg_source_surface_exhaustive_20261101_v2'
ROOT=R/'release/compiler_iterations/preparation'/RUN_ID
POOL=R/'release/compiler_iterations/source_pools/svg_source_surface_unseen100_20261101_v1_sourceonly_v1'
NAMES=('compiler_svg_source_viewport_iteration_case_v2','compiler_svg_source_viewport_iteration_batch_v2',
       'compiler_svg_source_viewport_iteration_program_v2','compiler_svg_source_viewport_exhaustive_chain_v2',
       'compiler_svg_source_viewport_controller_preflight_v2','compiler_source_core_attempts_v3',
       'compiler_source_cohort_exhaustive_v1','compiler_svg_source_viewport_iteration_launch_chain_v1')


def module_pins():
    pins=legacy.module_pins()
    for name in NAMES:
        path=Path(importlib.import_module(name).__file__).absolute();pins[str(path)]=sha(path.read_bytes())
    return pins


def preconditions():
    original=legacy.preconditions()
    current=program.runtime_controls()
    info=json.loads((POOL/'summary.json').read_bytes())
    from compiler_source_cohort_exhaustive_v1 import validate
    cohort=validate(info,program.readrows(POOL/'selected.jsonl'))
    old=legacy.ROOT
    status=json.loads((old/'failure.json').read_bytes())
    if status.get('reason')!='source_only_exhaustive_audit_has_fewer_than100_fresh_independent_families':
        raise ValueError('old_source_preparation_boundary_not_proven')
    if (program.PROGRAMS/legacy.RUN_ID).exists():
        raise ValueError('previous_program_exists_do_not_relaunch_same_source_core')
    return dict(original_controls=original,current_controller_controls=current,
                source_audit=asset(POOL/'summary.json'),exhaustive_cohort=cohort)


def supervise(nonce):
    with (ROOT/'chain.lock').open('a+')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        owner={**identity(os.getpid()),'pid':os.getpid(),'nonce':nonce,'argv':sys.argv,'watch':False}
        atomic(ROOT/'owner.json',owner);wait_ack(ROOT/('ack_'+nonce+'.json'),owner,nonce)
        pins=json.loads((ROOT/'pins.json').read_bytes())
        try:
            legacy.ensure(pins);pre=preconditions()
            atomic(ROOT/'state.json',dict(stage='prepare_all_remaining_independent_families',preconditions=pre,goal_complete=False))
            prepared=program.prepare(POOL,RUN_ID);legacy.ensure(pins)
            launch=program.launch(Path(prepared['program_dir']),4,900)
            handoff=dict(stage='exhaustive_validation_then_gated_mass_launched',program=launch,
                         prepared=prepared,preconditions=pre,workers=4,case_timeout_seconds=900,
                         fixed_minimum_qualified_fraction=.20,fixed_minimum_new_qualified=5,
                         automatic_mass_after_gate=True,agent_watch=False,model_calls=0,goal_complete=False)
            immutable(ROOT/'handoff.json',raw(handoff));atomic(ROOT/'state.json',handoff)
        except BaseException as error:
            from compiler_typed_runtime_failure_v1 import diagnose
            value=dict(stage='preparation_failed_next_repair_required',reason=str(error),error_type=type(error).__name__,
                       runtime_diagnosis=diagnose(exception=error),goal_complete=False,format_stopped=False)
            atomic(ROOT/'failure.json',value);atomic(ROOT/'state.json',value);raise


def launch():
    preconditions();pins=module_pins();legacy.ensure(pins)
    ROOT.mkdir(parents=True,exist_ok=False);immutable(ROOT/'pins.json',raw(pins));nonce=uuid.uuid4().hex
    argv=[sys.executable,'-B',str(Path(__file__).absolute()),'execute','--nonce',nonce]
    with(ROOT/'chain.log').open('ab')as log:
        child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
          env={**os.environ,'PYTHONPATH':str(R/'env')+':'+str(W/'scripts'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    birth=identity(child.pid);deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if child.poll()is not None:raise RuntimeError('chain_exited_before_identity_handshake')
        try:
            owner=json.loads((ROOT/'owner.json').read_bytes());now=identity(child.pid)
            if birth and now and owner['pid']==child.pid and owner['nonce']==nonce and owner['start_ticks']==birth['start_ticks']==now['start_ticks']:
                immutable(ROOT/('ack_'+nonce+'.json'),raw(owner))
                value=dict(pid=child.pid,start_ticks=birth['start_ticks'],argv=argv,chain_dir=str(ROOT),
                           finite=True,watch=False,goal_complete=False)
                immutable(ROOT/'launch.json',raw(value));return value
        except(OSError,KeyError,ValueError):pass
        time.sleep(.05)
    raise RuntimeError('chain_launch_observation_timeout_inspect_same_pid_no_restart')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('launch','execute'));parser.add_argument('--nonce')
    args=parser.parse_args();result=launch()if args.action=='launch'else supervise(args.nonce)
    print(json.dumps(result),flush=True)
