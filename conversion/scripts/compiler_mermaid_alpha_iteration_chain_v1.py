"""Finite source audit -> frozen unseen validation -> automatically gated mass.

The preparation parent exits after the program's real PID/birth handshake.
Neither parent is an agent watcher, a model loop or an overall goal completion.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import compiler_mermaid_alpha_iteration_program_v1 as program
import compiler_mermaid_alpha_iteration_pool_v1 as pool

R,W,raw,sha=program.R,program.W,program.raw,program.sha
RUN='mermaid_alpha_unseen100_20261101_v1'
DIRECTORY=R/'release/compiler_iterations/chains'/RUN
POOL=R/'release/compiler_iterations/source_pools'/RUN
INVENTORY=R/'release/compiler_iterations/round8_alpha_repair_inventory_20261101_v1'
RUNTIME=R/'release/compiler_iterations/controls/mermaid_alpha_runtime_controls_20261101_v1/proof.json'
RUNTIME_SHA='bf9e537b5ece84ca61da9bc8eca65ce846652c1e4f09134f39d1070e96d99670'


def verify_runtime():
    if sha(RUNTIME.read_bytes())!=RUNTIME_SHA:raise ValueError('runtime_control_receipt_changed')
    proof=json.loads(RUNTIME.read_bytes())
    compiler,_=program.case.bindings('mermaid')
    if proof.get('ok')is not True or proof.get('frozen_frontend')!=compiler.configuration():raise ValueError('runtime_frontend_control_changed')
    program.checked(proof['producer'])
    cases=proof['cases']
    if len(cases)!=2 or cases[0]['status']!='abandoned'or cases[0]['infrastructure_failure']or cases[1]['status']!='qualified'or any(row['attempts']!=1 for row in cases):raise ValueError('runtime_continue_control_incomplete')
    if not (proof.get('canonical_jobs_unchanged')is True and proof.get('typed_failure_continues_to_next_sample')is True and proof.get('positive_normal_reconversions')==0):raise ValueError('runtime_control_scope_changed')
    freeze=json.loads((Path(proof['run'])/'freeze.json').read_bytes())
    program.controller.check_pins(freeze['pins']);program.controller.check_implementation_identity(freeze)
    controls=program.control_bundle(compiler);program.check_controls(controls)
    return compiler.configuration()


def module_pins():
    names=('compiler_mermaid_alpha_iteration_case_v1.py','compiler_mermaid_alpha_iteration_batch_v1.py',
           'compiler_mermaid_alpha_iteration_program_v1.py','compiler_mermaid_alpha_iteration_pool_v1.py',
           'compiler_mermaid_alpha_iteration_overlap_v1.py','compiler_mermaid_alpha_iteration_preflight_v1.py',
           'compiler_mermaid_alpha_iteration_chain_v1.py','compiler_typed_runtime_failure_v1.py')
    return {str(W/'scripts'/name):sha((W/'scripts'/name).read_bytes())for name in names}


def execute(nonce):
    freeze=json.loads((DIRECTORY/'freeze.json').read_bytes())
    if freeze['nonce']!=nonce:raise ValueError('preparation_nonce_changed')
    owner={**program.controller.process_identity(),'nonce':nonce,'argv':sys.argv,'watch':False}
    program.atomic(DIRECTORY/'owner.json',owner)
    program.common.wait_ack(DIRECTORY/('ack_'+nonce+'.json'),owner,nonce)
    try:
        if module_pins()!=freeze['module_pins']or verify_runtime()!=freeze['frontend']:raise ValueError('frozen_preparation_implementation_changed')
        program.atomic(DIRECTORY/'state.json',{'stage':'source_only_audit','goal_complete':False})
        info=pool.prepare(POOL,INVENTORY)
        if not info['selected']:
            outcome={'stage':'no_fresh_source_family_next_repair_required','source_pool':str(POOL),'goal_complete':False,'dispatched':False}
        else:
            prepared=program.prepare(POOL,RUN)
            launched=program.launch(Path(prepared['program_dir']),4,900)
            outcome={'stage':'fixed_validation_then_gated_mass_launched','source_pool':str(POOL),'prepared':prepared,'program':launched,
                     'workers':4,'case_timeout_seconds':900,'samples_each':info['selected'],
                     'predeclared_gate':{'minimum_qualified_fraction':.20,'minimum_new_qualified':min(5,info['selected']),
                                         'maximum_regressions':0,'maximum_infrastructure_errors':0,'maximum_negative_false_acceptances':0},
                     'goal_complete':False,'model_calls':0,'watch':False}
        program.immutable(DIRECTORY/'handoff.json',raw(outcome))
        program.atomic(DIRECTORY/'state.json',outcome)
        print(json.dumps(outcome,ensure_ascii=False),flush=True)
    except BaseException as error:
        program.atomic(DIRECTORY/'failure.json',{'type':type(error).__name__,'reason':str(error),'goal_complete':False,'automatic_restart':False})
        raise


def launch():
    frontend=verify_runtime()
    DIRECTORY.mkdir(parents=True,exist_ok=False)
    nonce=uuid.uuid4().hex
    freeze={'nonce':nonce,'module_pins':module_pins(),'frontend':frontend,'runtime_proof':{'file':str(RUNTIME),'sha256':RUNTIME_SHA},
            'run_id':RUN,'source_scope':16862,'input':str(R/'release/manifest.jsonl'),'workers':4,'timeout':900,
            'scope_and_gate_frozen_before_unseen_results':True,'normal_source_attempts_per_frozen_frontend':1}
    program.immutable(DIRECTORY/'freeze.json',raw(freeze))
    argv=[sys.executable,'-B',str(Path(__file__).resolve()),'execute','--nonce',nonce]
    with(DIRECTORY/'chain.log').open('xb')as log:
        child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
                               env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    from initial_conversion_process_v1 import identity
    birth=identity(child.pid);deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if child.poll()is not None:raise RuntimeError('preparation_exited_before_identity_handshake')
        try:
            owner=json.loads((DIRECTORY/'owner.json').read_bytes());now=identity(child.pid)
            if birth and now and owner['pid']==child.pid and owner['start_ticks']==birth['start_ticks']==now['start_ticks']and owner['nonce']==nonce:
                program.immutable(DIRECTORY/('ack_'+nonce+'.json'),raw(owner))
                out={'pid':child.pid,'start_ticks':birth['start_ticks'],'argv':argv,'chain_dir':str(DIRECTORY),
                     'finite':True,'watch':False,'goal_complete':False,'automatic_unseen_then_gated_mass':True}
                program.immutable(DIRECTORY/'launch.json',raw(out))
                return out
        except (OSError,KeyError,ValueError):pass
        time.sleep(.05)
    raise RuntimeError('preparation_observation_timeout_inspect_same_handle_no_restart')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('launch','execute'));parser.add_argument('--nonce')
    args=parser.parse_args()
    result=launch()if args.action=='launch'else execute(args.nonce)
    if result is not None:print(json.dumps(result,ensure_ascii=False),flush=True)
