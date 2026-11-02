"""Finite, explicitly evidenced recovery after exact original bytes are restored.

No implementation/freeze or accepted payload changes. Existing generation
fences recover orphan outcomes without repeating conversion. Stop evidence is
archived only after all original pins and release gates verify again.
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
from initial_conversion_process_v1 import identity
from compiler_types_program_v1 import atomic,raw,wait_ack

DEFINITIONS={
 'python':('compiler_batch_v2',None,R/'release/compiler_v2/graphviz_batch_20261101_v2_renderdomain',8,600),
 'svg':('compiler_iteration_batch_v1','compiler_iteration_program_v1',R/'release/compiler_iterations/runs/svg_v6_20261101_round3_mass',4,600),
 'mermaid':('compiler_mermaid_iteration_batch_v1','compiler_mermaid_iteration_program_v1',R/'release/compiler_iterations/runs/mermaid_cli_export_v3_unseen100_20261101_v1_mass',4,600),
 'native':('compiler_iteration_batch_v2','compiler_iteration_program_v2',R/'release/compiler_iterations/runs/native_complete_export_20261101_round4_mass',4,900),
}
EXPECTED='d1dd882a7e603d5b9b6596369a4930e7b8afb77a077f7c378934f50e03e92969'
FILE=W/'scripts/plantuml_native_v4.py'
INCIDENT=W/'incident_recovery_20261101_v1'


def read(p):return json.loads(p.read_bytes()) if p.exists() else {}


def alive(owner):
    current=identity(owner.get('pid',-1)) if owner.get('pid') else None
    return bool(current and current['start_ticks']==owner.get('start_ticks') and current.get('state')!='Z')


def run(name,nonce):
    controller_name,program_name,run_dir,workers,timeout=DEFINITIONS[name]
    operation=INCIDENT/('resume_'+name);operation.mkdir(parents=True,exist_ok=True)
    controller=importlib.import_module(controller_name)
    program=importlib.import_module(program_name) if program_name else None
    program_dir=R/'release/compiler_iterations/programs'/run_dir.name.removesuffix('_mass') if program else None
    with (operation/'execution.lock').open('a+') as operation_lock:
        fcntl.flock(operation_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (run_dir/'run.lock').open('a+') as run_lock:
            fcntl.flock(run_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if alive(read(run_dir/'owner.json')) or (program_dir and alive(read(program_dir/'owner.json'))):
                raise RuntimeError('prior_owner_still_alive_no_duplicate_recovery')
            freeze=read(run_dir/'freeze.json')
            if freeze['pins'].get(str(FILE))!=EXPECTED or hashlib.sha256(FILE.read_bytes()).hexdigest()!=EXPECTED:
                raise RuntimeError('exact_original_shared_bytes_not_restored')
            controller.check_pins(freeze['pins']);controller.check_implementation_identity(freeze)
            with contextlib.closing(sqlite3.connect(run_dir/'status.sqlite')) as database:
                import fixed_batch_pipeline_v1 as base
                metadata=base.metadata(database)
                if hashlib.sha256((run_dir/'targets.jsonl').read_bytes()).hexdigest()!=metadata['input_sha256']:
                    raise RuntimeError('recovery_target_bytes_changed')
                if base.sha(base.raw(freeze))!=metadata['freeze_sha256']:
                    raise RuntimeError('recovery_freeze_bytes_changed')
                if metadata['mode']=='batch':controller.release_gate(freeze,set(metadata['units']))
                stop=read(run_dir/'infrastructure_stop.json')
                if stop and not (stop.get('reason')=='compiler_parent_error' and 'implementation_changed:'+str(FILE) in stop.get('detail','')):
                    raise RuntimeError('unrelated_stop_requires_separate_diagnosis:'+json.dumps(stop))
                # Existing tested fencing requires exclusive execution generation
                # and complete old process-tree cleanup; no requeue is performed.
                recovered=controller.resume_interrupted(run_dir,database)
                controller.check_pins(freeze['pins'])
                proof={'original_freeze_unchanged':True,'original_targets_unchanged':True,
                       'original_release_gate_verified':True,'all_original_pins_verified':len(freeze['pins']),
                       'original_shared_sha256':EXPECTED,'prior_owner_dead':True,
                       'generation_recovery':recovered,'prior_stop':stop,
                       'normal_conversion_reexecutions_requested':0,'model_calls':0}
                atomic(operation/'exact_restoration_acknowledgement.json',proof)
                if stop:os.replace(run_dir/'infrastructure_stop.json',operation/'prior_run_infrastructure_stop.json')
                if program_dir and (program_dir/'infrastructure_stop.json').exists():
                    os.replace(program_dir/'infrastructure_stop.json',operation/'prior_program_infrastructure_stop.json')
        owner={**identity(os.getpid()),'nonce':nonce,'run':str(run_dir),'argv':sys.argv,
               'watch':False,'exact_pin_recovery':True,'workers':workers}
        atomic(operation/'owner.json',owner)
        wait_ack(operation/('ack_'+nonce+'.json'),owner,nonce)
        if program_dir:
            atomic(program_dir/'recovery_owner.json',owner)
            atomic(program_dir/'state.json',{'stage':'mass_exact_pin_recovery','recovery_operation':str(operation),
                                           'goal_complete':False,'original_freeze_preserved':True})
        try:
            if program:
                program.run_phase(run_dir,workers,timeout,operation)
            else:
                command=[sys.executable,'-B',str(Path(controller.__file__).resolve()),'run','--run-id',run_dir.name,
                         '--workers',str(workers),'--case-timeout',str(timeout)]
                with (operation/'controller.log').open('ab') as log:
                    child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
                           env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
                atomic(operation/'controller_child.json',identity(child.pid))
                if child.wait()!=0:raise RuntimeError('recovered_python_controller_failed')
            inventory=R/'release/compiler_iterations'/('exact_pin_recovery_'+name+'_final_inventory_20261101_v1')
            with (operation/'inventory.log').open('ab') as log:
                result=subprocess.run([sys.executable,'-B',str(W/'scripts/compiler_iteration_inventory_v1.py'),
                                       '--output',str(inventory)],stdout=log,stderr=log)
            if result.returncode:raise RuntimeError('recovery_final_inventory_failed')
            completion={'stage':'round_complete_next_repair_required','goal_complete':False,'inventory':str(inventory)}
            atomic(operation/'completion.json',completion)
            if program_dir:atomic(program_dir/'state.json',completion)
        except BaseException as exc:
            atomic(operation/'infrastructure_stop.json',{'reason':str(exc),'goal_complete':False})
            raise


def launch(name):
    operation=INCIDENT/('resume_'+name);operation.mkdir(parents=True,exist_ok=True)
    if (operation/'launch.json').exists() or (operation/'owner.json').exists():
        raise ValueError('already_launched_inspect_same_process_no_duplicate')
    nonce=uuid.uuid4().hex
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'run','--name',name,'--nonce',nonce]
    with (operation/'supervisor.log').open('ab') as log:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
                                 env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
    birth=identity(process.pid);deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('recovery_child_exited_read_supervisor_log')
        owner=read(operation/'owner.json')
        if owner and alive(owner) and owner['pid']==process.pid and owner['start_ticks']==birth['start_ticks'] and owner['nonce']==nonce:
            atomic(operation/('ack_'+nonce+'.json'),owner)
            result={'name':name,'pid':process.pid,'start_ticks':birth['start_ticks'],'operation':str(operation),
                    'finite':True,'watch':False,'original_freeze_preserved':True,'goal_complete':False}
            atomic(operation/'launch.json',result);return result
        time.sleep(.05)
    raise RuntimeError('recovery_launch_observation_timeout_inspect_same_pid')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('launch','run'))
    parser.add_argument('--name',choices=tuple(DEFINITIONS),required=True);parser.add_argument('--nonce')
    arguments=parser.parse_args()
    result=launch(arguments.name) if arguments.action=='launch' else run(arguments.name,arguments.nonce)
    print(json.dumps(result))
