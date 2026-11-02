"""Finite source-only audit -> reserve/prepare B/C100 -> launch fixed program.

The preparation child exits after launching the autonomous fixed supervisor.
There is no agent watch, restart loop, gate adjustment or source model call.
"""
import argparse,fcntl,importlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
from compiler_types_program_v1 import R,W,raw,sha,asset,checked,immutable,atomic,wait_ack
from initial_conversion_process_v1 import identity
RUN_ID='svg_source_surface_unseen100_20261101_v1'
ROOT=R/'release/compiler_iterations/preparation'/(RUN_ID+'_source_frame_v1')
POOL=R/'release/compiler_iterations/source_pools'/(RUN_ID+'_sourceonly_v1')
CONTROLS=R/'release/compiler_iterations/controls/svg_source_surface_controls_20261101_v1'
NAMES=('compiler_svg_source_viewport_iteration_case_v1','compiler_svg_source_viewport_iteration_batch_v1','compiler_svg_source_viewport_iteration_program_v1','compiler_svg_source_viewport_iteration_controls_v1','compiler_svg_source_viewport_unseen_pool_v1','compiler_svg_source_viewport_iteration_launch_chain_v1','compiler_typed_runtime_failure_v1','compiler_svg_general_unseen_pool_v3','compiler_mermaid_alpha_qualifications_v2','compiler_mermaid_alpha_iteration_overlap_v2','compiler_iteration_inventory_v1','compiler_svg_source_viewport_source_contract_preflight_v2','compiler_svg_source_viewport_stale_lease_control_v1','compiler_svg_source_viewport_controller_preflight_v1')

def module_pins():
 import compiler_svg_source_viewport_frontend_v1 as c
 import fixed_batch_pipeline_v1 as base
 pins={**base.pins(),**c.configuration()['pins']}
 for name in NAMES:
  p=Path(importlib.import_module(name).__file__).absolute();pins[str(p)]=sha(p.read_bytes())
 return pins

def ensure(pins):
 for name,digest in pins.items():
  if sha(Path(name).read_bytes())!=digest:raise RuntimeError('infrastructure_chain_pin_changed:'+name)

def preconditions():
 import compiler_svg_source_viewport_iteration_program_v1 as program
 import compiler_svg_source_viewport_frontend_v1 as c
 bundle=program.control_bundle(c);program.check_controls(bundle)
 p=CONTROLS/'case_preflight.json';q=json.loads(p.read_bytes())
 if not q.get('all_expected_outcomes')or q.get('frozen_frontend')!=c.configuration():raise ValueError('exact_iteration_preflight_not_valid')
 for key in ('case_module','controller_module','typed_failure_module'):checked(q[key])
 for row in q['cases']:
  for key in ('result','request','isolation'):checked(row[key])
  if row.get('infrastructure_failure')is not False:raise ValueError('case_preflight_runtime_failure')
 tests=json.loads((CONTROLS/'mechanism_tests_v1.json').read_bytes())
 if tests.get('returncode')!=0 or tests.get('passed',0)<42:raise ValueError('mechanism_tests_not_passed')
 for name,digest in tests['modules'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('mechanism_test_module_changed:'+name)
 locator=json.loads((CONTROLS/'source_locator_profile_v2.json').read_bytes())
 if locator.get('all_match_frozen_frontend')is not True:raise ValueError('canonical_staged_source_locator_not_proven')
 checked(locator['pool_module'])
 contract=json.loads((CONTROLS/'source_contract_v2.json').read_bytes())
 if not contract.get('ok')or contract.get('frozen_frontend')!=c.configuration()or len(contract.get('cases',[]))!=3:raise ValueError('actual_full_canonical_source_contract_not_proven')
 for row in contract['cases']:
  if not row.get('full_canonical_source_passed')or not row.get('baseline_snapshot_verified')or not row.get('canonical_metadata_unchanged')or len(row.get('mutations_rejected',{}))!=4:raise ValueError('actual_source_constructor_or_snapshot_mutation_controls_incomplete')
 for value in contract['producers'].values():checked(value)
 stale=json.loads((CONTROLS/'private_stale_lease_full_ro_v1.json').read_bytes())
 if not stale.get('ok')or not stale.get('real_canonical_raw13_unchanged')or not stale.get('private_fixture_raw13_unchanged')or not stale.get('all8_full_QA_passed'):raise ValueError('private_stale_lease_RO_control_not_proven')
 checked(stale['case_module']);checked(stale['quality']);checked(stale['owner_guard_audit'])
 return {'controls':bundle['definition'],'exact_case_preflight':asset(p),'mechanism_tests':asset(CONTROLS/'mechanism_tests_v1.json'),'source_locator_profile':asset(CONTROLS/'source_locator_profile_v2.json'),'actual_source_contract':asset(CONTROLS/'source_contract_v2.json')}

def supervise(inventory,nonce):
 with(ROOT/'chain.lock').open('a+')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  owner={**identity(os.getpid()),'pid':os.getpid(),'nonce':nonce,'argv':sys.argv,'watch':False};atomic(ROOT/'owner.json',owner);wait_ack(ROOT/('ack_'+nonce+'.json'),owner,nonce)
  pins=json.loads((ROOT/'pins.json').read_bytes())
  try:
   ensure(pins);pre=preconditions();atomic(ROOT/'status.json',{'stage':'source_only_audit','goal_complete':False,'watch':False,'source_pool':str(POOL),'program_run_id':RUN_ID})
   import compiler_svg_source_viewport_unseen_pool_v1 as pool
   info=pool.prepare(POOL,inventory);ensure(pins)
   if not info.get('minimum100_met')or info.get('selected')!=100:raise ValueError('source_only_exhaustive_audit_has_fewer_than100_fresh_independent_families')
   atomic(ROOT/'status.json',{'stage':'prepare_B100_C100','source_pool_summary':asset(POOL/'summary.json'),'goal_complete':False})
   import compiler_svg_source_viewport_iteration_program_v1 as program
   prepared=program.prepare(POOL,RUN_ID);ensure(pins)
   atomic(ROOT/'status.json',{'stage':'launch_fixed_program','prepared':prepared,'goal_complete':False})
   launch=program.launch(Path(prepared['program_dir']),4,900)
   value={'stage':'fixed_program_launched','program_launch':launch,'program_status':str(Path(prepared['program_dir'])/'state.json'),'program_failure':str(Path(prepared['program_dir'])/'infrastructure_stop.json'),'program_summary':str(Path(prepared['program_dir'])/'summary.json'),'source_pool_summary':asset(POOL/'summary.json'),'preconditions':pre,'workers':4,'case_timeout_seconds':900,'B100':100,'C100':100,'auto_mass_after_gate':True,'models':0,'agent_watch':False,'goal_complete':False}
   immutable(ROOT/'ready.json',raw(value));atomic(ROOT/'status.json',value)
  except BaseException as error:
   from compiler_typed_runtime_failure_v1 import diagnose
   failure={'stage':'preparation_failed','reason':str(error),'error_type':type(error).__name__,'runtime_diagnosis':diagnose(exception=error),'new_gate_not_relaxed':True,'watch':False,'goal_complete':False,'source_pool':str(POOL)};atomic(ROOT/'failure.json',failure);atomic(ROOT/'status.json',failure);raise

def launch(inventory):
 inventory=Path(inventory).resolve(strict=True);preconditions();pins=module_pins();ensure(pins);ROOT.mkdir(parents=True,exist_ok=False);immutable(ROOT/'pins.json',raw(pins));nonce=uuid.uuid4().hex
 argv=[sys.executable,'-B',str(Path(__file__).absolute()),'supervise','--inventory',str(inventory),'--nonce',nonce]
 with(ROOT/'chain.log').open('ab')as log:child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'PYTHONPATH':str(R/'env')+':'+str(W/'scripts'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
 birth=identity(child.pid);deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  if child.poll()is not None:raise RuntimeError('chain_exited_before_identity_handshake')
  try:
   owner=json.loads((ROOT/'owner.json').read_bytes());now=identity(child.pid)
   if birth and now and owner['pid']==child.pid and owner['nonce']==nonce and owner['start_ticks']==birth['start_ticks']==now['start_ticks']:
    immutable(ROOT/('ack_'+nonce+'.json'),raw(owner));value={'pid':child.pid,'start_ticks':birth['start_ticks'],'argv':argv,'preparation':str(ROOT),'ready':str(ROOT/'ready.json'),'failure':str(ROOT/'failure.json'),'status':str(ROOT/'status.json'),'log':str(ROOT/'chain.log'),'pins':asset(ROOT/'pins.json'),'source_only_audit_then_auto_prepare_launch':True,'finite':True,'agent_watch':False,'models':0};immutable(ROOT/'launch.json',raw(value));return value
  except(OSError,KeyError,ValueError):pass
  time.sleep(.05)
 raise RuntimeError('chain_launch_handshake_timeout_inspect_same_PID_no_restart')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('launch','supervise'));p.add_argument('--inventory',type=Path,required=True);p.add_argument('--nonce');a=p.parse_args();result=launch(a.inventory)if a.action=='launch'else supervise(a.inventory,a.nonce);print(json.dumps(result),flush=True)
