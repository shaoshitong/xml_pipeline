"""Finite source-pool finalizer: wait once, verify, reserve/prepare, never dispatch.

The actual scan PID, birth, exact arguments, inputs, controls and implementation
are frozen before launch. Timeout/failure records evidence and never restarts.
"""
import argparse,fcntl,importlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
import compiler_tikz_iteration_program_v1 as program
import compiler_tikz_handoff_metadata_v1 as handoff
from initial_conversion_process_v1 import identity
R,W=program.R,program.W
FLOOR=R/'release/compiler_iterations/preparations'
POOL_SCRIPT=W/'scripts/compiler_tikz_unseen_pool_v1.py'
SCOPE=R/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl'
DEVELOPMENT=R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl'
TYPED_DEVELOPMENT=W/'compiler_tikz_free_paths_v1/development/typed_graph_inventory.json'
raw,sha,atomic,immutable,asset=program.raw,program.sha,program.atomic,program.immutable,program.asset

def owned(path):
 p=Path(path).resolve()
 if not p.is_relative_to(FLOOR.resolve()) or p==FLOOR.resolve():raise ValueError('unowned_TikZ_preparation')
 return p

def source_running(source):
 actual=identity(source['pid'])
 if actual is None:return False
 if actual['start_ticks']!=source['start_ticks']:raise RuntimeError('source_scan_PID_reused')
 if actual['state']=='Z':return False
 try:command=[x.decode() for x in Path('/proc',str(source['pid']),'cmdline').read_bytes().split(b'\0') if x]
 except FileNotFoundError:
  if identity(source['pid']) is None:return False
  raise
 if command!=source['argv']:
  after=identity(source['pid'])
  if after is None or (after['start_ticks']==source['start_ticks'] and after['state']=='Z'):return False
  raise RuntimeError('source_scan_actual_arguments_changed')
 return True

def wait_source(source,seconds):
 deadline=time.monotonic()+seconds
 while source_running(source):
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('finite_source_scan_wait_expired_no_restart')
  time.sleep(min(10,remaining))

def check_inputs(freeze):
 program.controller.check_pins(freeze['pins'])
 for ref in freeze['inputs'].values():program.checked(ref)
 compiler,_=program.case.bindings('tikz')
 if compiler.configuration()!=freeze['source_frontend_configuration']:raise RuntimeError('source_frontend_configuration_changed')
 controls=program.control_bundle(compiler);program.check_controls(controls)
 if controls['definition']!=freeze['controls_proof']:raise RuntimeError('source_controls_proof_changed')
 return compiler

def validate_summary(pool,freeze):
 info=json.loads((pool/'summary.json').read_bytes())
 if info.get('scope')!=40746 or info.get('source_only') is not True or info.get('conversion_or_rendering') is not False:
  raise ValueError('source_pool_scope_or_source_only_contract_changed')
 if info['scope_index_sha256']!=freeze['inputs']['scope']['sha256'] or info['development_input_sha256']!=freeze['inputs']['development']['sha256']:
  raise ValueError('source_pool_original_input_SHA_changed')
 if info['additional_development_inventory']['sha256']!=freeze['inputs']['typed_development']['sha256']:
  raise ValueError('source_pool_additional_development_SHA_changed')
 if info['frozen_implementation']!=freeze['source_frontend_configuration'] or info['controls_proof']!=freeze['controls_proof']:
  raise ValueError('source_pool_frozen_configuration_or_controls_changed')
 for name,ref in info['files'].items():
  p=pool/name
  if sha(p.read_bytes())!=ref['sha256'] or p.stat().st_size!=ref['bytes']:raise ValueError('source_pool_incomplete_asset:'+name)
 counts={}
 for name in ('source_audit.jsonl','supported_population.jsonl','selected.jsonl'):
  with (pool/name).open('rb') as stream:counts[name]=sum(bool(line.strip()) for line in stream)
 if counts['source_audit.jsonl']+info['excluded_accepted']!=40746:raise ValueError('source_pool_did_not_account_for_all_40746')
 if counts['supported_population.jsonl']!=info['counters']['supported_remaining_population']:raise ValueError('source_pool_full_population_count_changed')
 if counts['selected.jsonl']!=100 or info['selected']!=100 or info.get('minimum100_met') is not True:raise ValueError('source_pool_has_fewer_than_100_fresh_cases')
 for name,digest in info['method_pins'].items():
  if freeze['pins'].get(name)!=digest:raise ValueError('source_pool_method_not_in_preparation_freeze:'+name)
 return info

def run(directory,nonce):
 directory=owned(directory)
 with (directory/'owner.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   owner={**program.controller.process_identity(),'nonce':nonce,'watch':False,'bulk_dispatch':False}
   atomic(directory/'owner.json',owner);program.common.wait_ack(directory/('ack_'+nonce+'.json'),owner,nonce)
   freeze=json.loads((directory/'freeze.json').read_bytes());check_inputs(freeze)
   atomic(directory/'state.json',{'stage':'fixed_program_waiting_for_bound_source_scan','source':freeze['source_process'],'goal_complete':False,'bulk_dispatch':False})
   wait_source(freeze['source_process'],freeze['wait_seconds'])
   check_inputs(freeze);pool=Path(freeze['pool']);info=validate_summary(pool,freeze)
   target=program.PROGRAMS/freeze['run_id']
   if target.exists():raise ValueError('validation_run_already_exists_no_duplicate_prepare')
   atomic(directory/'state.json',{'stage':'source_pool_complete_preparing_once','source_scope':info['scope'],'goal_complete':False,'bulk_dispatch':False})
   prepared=program.prepare(pool,freeze['run_id'])
   if prepared.get('dispatched') is not False:raise RuntimeError('preparation_must_not_dispatch')
   handoff.main(pool,Path(prepared['program_dir']))
   handoff_file=R/'release/compiler_iterations/handoffs/tikz_pdftex2025_v2_20261101_v1.json'
   atomic(directory/'ready.json',{'prepared':prepared,'handoff':asset(handoff_file),'source_summary':asset(pool/'summary.json'),'dispatched':False,'goal_complete':False})
   atomic(directory/'state.json',{'stage':'ready_for_root_review_and_launch','ready':str(directory/'ready.json'),'goal_complete':False,'bulk_dispatch':False})
  except BaseException as error:
   atomic(directory/'failure.json',{'type':type(error).__name__,'reason':str(error),'automatic_restart':False,'goal_complete':False,'bulk_dispatch':False})
   raise

def launch(pool,inventory,pid,birth,run_id,seconds):
 pool=Path(pool).resolve(strict=True);inventory=Path(inventory).resolve(strict=True)
 if not pool.is_relative_to(R/'release/compiler_iterations/source_pools') or not inventory.is_relative_to(R/'release/compiler_iterations'):raise ValueError('unowned_preparation_inputs')
 if not run_id or not all(x.isalnum() or x in '-_' for x in run_id):raise ValueError('invalid_TikZ_preparation_run_id')
 if (program.PROGRAMS/run_id).exists():raise ValueError('validation_run_already_exists')
 actual=identity(pid)
 if not actual or actual['start_ticks']!=birth:raise RuntimeError('source_scan_missing_or_birth_changed_before_finalizer_launch')
 argv=[x.decode() for x in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if x]
 if argv[1:]!=[str(POOL_SCRIPT),'--output',str(pool),'--inventory',str(inventory)]:raise RuntimeError('source_scan_does_not_match_exact_requested_pool_and_inventory')
 source={**actual,'argv':argv};source_running(source)
 compiler,quality=program.case.bindings('tikz');config=compiler.configuration();controls=program.control_bundle(compiler);program.check_controls(controls)
 qa=json.loads(Path(controls['positive_cases'][0]['qa']['file']).read_bytes())
 pins={**program.base.pins(),**config['pins'],**qa['implementation_pins']}
 for module in (program,program.case,program.controller,program.common,quality,handoff,sys.modules[__name__],importlib.import_module('compiler_validation_reservation_v1')):
  p=Path(module.__file__).resolve();pins[str(p)]=sha(p.read_bytes())
 for name in ('compiler_tikz_unseen_pool_v1.py','compiler_types_source_ir_v1.py','tikz_literal_graph.py','tikz_connectivity.py','compiler_validation_dot_ir_v2.py','compiler_validation_cluster_audit_v1.py'):
  p=W/'scripts'/name;pins[str(p)]=sha(p.read_bytes())
 inputs={'scope':asset(SCOPE),'development':asset(DEVELOPMENT),'typed_development':asset(TYPED_DEVELOPMENT),'inventory_summary':asset(inventory/'summary.json'),'qualified_manifest':asset(inventory/'qualified.jsonl')}
 freeze={'pins':pins,'source_frontend_configuration':config,'controls_proof':controls['definition'],'source_process':source,'pool':str(pool),'inventory':str(inventory),'inputs':inputs,'run_id':run_id,'wait_seconds':seconds,'prepare_only_once':True,'dispatch':False,'goal_complete':False}
 check_inputs(freeze);directory=owned(FLOOR/run_id);directory.mkdir(parents=True,exist_ok=False);immutable(directory/'freeze.json',raw(freeze))
 nonce=uuid.uuid4().hex;command=[sys.executable,'-B',str(Path(__file__).resolve()),'run','--preparation-dir',str(directory),'--nonce',nonce]
 try:
  with (directory/'finalizer.log').open('ab') as log:
   child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
 except BaseException as error:
  atomic(directory/'launch_failure.json',{'type':type(error).__name__,'reason':str(error),'automatic_restart':False,'dispatch':False});raise
 expected=identity(child.pid);deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  if child.poll() is not None:
   atomic(directory/'launch_failure.json',{'reason':'preparation_finalizer_exited_before_handshake','automatic_restart':False,'dispatch':False})
   raise RuntimeError('preparation_finalizer_exited_before_handshake')
  try:
   owner=json.loads((directory/'owner.json').read_bytes());now=identity(child.pid)
   if expected and now and owner['pid']==child.pid and owner['start_ticks']==expected['start_ticks']==now['start_ticks'] and owner['nonce']==nonce:
    immutable(directory/('ack_'+nonce+'.json'),raw(owner))
    result={'preparation':str(directory),'pid':child.pid,'start_ticks':expected['start_ticks'],'source_pid':pid,'source_start_ticks':birth,'finite_wait_seconds':seconds,'dispatched':False,'watch':False,'goal_complete':False}
    immutable(directory/'launch.json',raw(result));return result
  except (OSError,ValueError,KeyError):pass
  time.sleep(.05)
 atomic(directory/'launch_failure.json',{'reason':'preparation_finalizer_launch_handshake_failed_no_restart','automatic_restart':False,'dispatch':False})
 raise RuntimeError('preparation_finalizer_launch_handshake_failed_no_restart')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('launch','run'));p.add_argument('--pool',type=Path);p.add_argument('--inventory',type=Path);p.add_argument('--source-pid',type=int);p.add_argument('--source-start-ticks',type=int);p.add_argument('--run-id');p.add_argument('--wait-seconds',type=int,default=7200);p.add_argument('--preparation-dir',type=Path);p.add_argument('--nonce');a=p.parse_args()
 if not 1<=a.wait_seconds<=21600:p.error('finite_wait_seconds_out_of_range')
 result=launch(a.pool,a.inventory,a.source_pid,a.source_start_ticks,a.run_id,a.wait_seconds) if a.action=='launch' else run(a.preparation_dir,a.nonce)
 print(json.dumps(result),flush=True)
