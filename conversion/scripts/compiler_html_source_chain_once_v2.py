"""Finite HTML source audit -> reserve100 -> launch one fixed validation program.

The actual scan PID, birth, exact arguments, inputs, controls and implementation
are frozen before launch. Timeout/failure records evidence and never restarts.
"""
import argparse,fcntl,importlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
import compiler_html_iteration_program_v2 as program
from initial_conversion_process_v1 import identity
R,W=program.R,program.W
FLOOR=R/'release/compiler_iterations/preparations'
POOL_SCRIPT=W/'scripts/compiler_html_unseen_pool_v2.py'
SCOPE=R/'release/manifest.jsonl'
DEVELOPMENT=R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl'
GLOBAL_DEVELOPMENT=R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl'
raw,sha,atomic,immutable,asset=program.raw,program.sha,program.atomic,program.immutable,program.asset

def owned(path):
 p=Path(path).resolve()
 if not p.is_relative_to(FLOOR.resolve()) or p==FLOOR.resolve():raise ValueError('unowned_HTML_preparation')
 return p

def source_running(source):
 if source.get('kind')=='completed_source_pool':
  if sha(Path(source['summary']['file']).read_bytes())!=source['summary']['sha256']:raise RuntimeError('completed_source_summary_changed')
  return False
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

def parse_source_arguments(argv,pool,inventory):
 if len(argv)<2 or argv[0]!=sys.executable:raise RuntimeError('source_scan_interpreter_changed')
 args=argv[1:]
 if args and args[0]=='-B':args=args[1:]
 if len(args)!=5 or args[0]!=str(POOL_SCRIPT):raise RuntimeError('source_scan_does_not_match_exact_requested_pool_and_inventory')
 options=dict(zip(args[1::2],args[2::2]))
 if set(options)!={'--output','--inventory'} or options['--output']!=str(pool) or options['--inventory']!=str(inventory):
  raise RuntimeError('source_scan_does_not_match_exact_requested_pool_and_inventory')
 return True


def source_binding(pool,inventory,pid,birth):
 summary=Path(pool)/'summary.json'
 if summary.is_file():return {'kind':'completed_source_pool','summary':asset(summary)}
 actual=identity(pid)
 if not actual or actual['start_ticks']!=birth:raise RuntimeError('source_scan_missing_or_birth_changed_before_finalizer_launch')
 argv=[x.decode() for x in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if x]
 parse_source_arguments(argv,pool,inventory)
 source={**actual,'argv':argv};source_running(source);return source


def entrypoint_preflight():
 proof=W/'compiler_iterations/html_asset_binding_v2_development_preflight_20261101_v1/1/preflight_proof.json'
 detail=json.loads(proof.read_bytes());result=detail['case_result']
 if detail['actual_case_entrypoint']!=str(Path(program.case.__file__).resolve()) or detail['actual_case_sha256']!=sha(Path(program.case.__file__).read_bytes()):
  raise ValueError('HTML_actual_entrypoint_preflight_case_changed')
 if result.get('status')!='qualified' or result.get('infrastructure_failure'):raise ValueError('HTML_actual_entrypoint_preflight_not_qualified')
 proposal=proof.parent/'candidate_record.json';record=json.loads(proposal.read_bytes());qa_path=R/result['quality_report'];qa=json.loads(qa_path.read_bytes())
 if qa.get('id')!=record['id'] or qa.get('input_record_sha256')!=sha(proposal.read_bytes()):raise ValueError('HTML_entrypoint_preflight_QA_unbound')
 program.case.full_quality(qa,record)
 for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
  program.checked({'file':record[key],'sha256':record[digest]},clean=True)
 import sqlite3
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:original=db.execute('select input_record,input_manifest from jobs where id=?',(record['id'],)).fetchone()
 source,manifest=[json.loads(v) for v in original]
 if record['original_asset_root']!=(manifest.get('asset_root') or source.get('asset_root')):raise ValueError('HTML_entrypoint_preflight_resource_binding_changed')
 return {'entrypoint_preflight_proof':asset(proof),'entrypoint_preflight_candidate':asset(proposal),'entrypoint_preflight_QA':asset(qa_path)}


def wait_source(source,seconds):
 deadline=time.monotonic()+seconds
 while source_running(source):
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('finite_source_scan_wait_expired_no_restart')
  time.sleep(min(10,remaining))

def check_inputs(freeze):
 program.controller.check_pins(freeze['pins'])
 for ref in freeze['inputs'].values():program.checked(ref)
 compiler,_=program.case.bindings('html')
 if compiler.configuration()!=freeze['source_frontend_configuration']:raise RuntimeError('source_frontend_configuration_changed')
 controls=program.control_bundle(compiler);program.check_controls(controls)
 if controls['definition']!=freeze['controls_proof']:raise RuntimeError('source_controls_proof_changed')
 return compiler

def validate_summary(pool,freeze):
 info=json.loads((pool/'summary.json').read_bytes())
 if info.get('scope')!=24739 or info.get('source_only') is not True or info.get('conversion_or_rendering') is not False:
  raise ValueError('source_pool_scope_or_source_only_contract_changed')
 if info['scope_index_sha256']!=freeze['inputs']['scope']['sha256'] or info['development_input_sha256']!=freeze['inputs']['development']['sha256']:
  raise ValueError('source_pool_original_input_SHA_changed')
 if info['development_inputs'].get(str(GLOBAL_DEVELOPMENT))!=freeze['inputs']['global_development']['sha256']:
  raise ValueError('source_pool_global_development_SHA_changed')
 for name,digest in info['development_inputs'].items():
  if freeze['pins'].get(name)!=digest:raise ValueError('source_pool_development_input_not_frozen:'+name)
 if info['frozen_implementation']!=freeze['source_frontend_configuration'] or info['controls_proof']!=freeze['controls_proof']:
  raise ValueError('source_pool_frozen_configuration_or_controls_changed')
 for name,ref in info['files'].items():
  p=pool/name
  if sha(p.read_bytes())!=ref['sha256'] or p.stat().st_size!=ref['bytes']:raise ValueError('source_pool_incomplete_asset:'+name)
 counts={}
 for name in ('source_audit.jsonl','supported_population.jsonl','selected.jsonl'):
  with (pool/name).open('rb') as stream:counts[name]=sum(bool(line.strip()) for line in stream)
 if counts['source_audit.jsonl']!=24739 or info.get('audited_scope_rows')!=24739:raise ValueError('source_pool_did_not_account_for_all_24739')
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
   target=Path(prepared['program_dir'])
   # All prerequisites and controls were frozen before source selection. This
   # finite chain owns one launch, then the fixed program owns B/C and rollout.
   launched=program.launch(target,4,900)
   result={'prepared':prepared,'source_summary':asset(pool/'summary.json'),'launch':launched,'dispatched':True,'goal_complete':False,'model_calls':0}
   atomic(directory/'ready.json',result)
   atomic(directory/'state.json',{'stage':'fixed_validation_launched_auto_rollout_if_passed','ready':str(directory/'ready.json'),'goal_complete':False,'bulk_dispatch':'only_after_frozen_B_C_gate'})
  except BaseException as error:
   atomic(directory/'failure.json',{'type':type(error).__name__,'reason':str(error),'automatic_restart':False,'goal_complete':False,'bulk_dispatch':False})
   raise

def launch(pool,inventory,pid,birth,run_id,seconds):
 pool=Path(pool).resolve(strict=True);inventory=Path(inventory).resolve(strict=True)
 if not pool.is_relative_to(R/'release/compiler_iterations/source_pools') or not inventory.is_relative_to(R/'release/compiler_iterations'):raise ValueError('unowned_preparation_inputs')
 if not run_id or not all(x.isalnum() or x in '-_' for x in run_id):raise ValueError('invalid_HTML_preparation_run_id')
 if (program.PROGRAMS/run_id).exists():raise ValueError('validation_run_already_exists')
 source=source_binding(pool,inventory,pid,birth)
 compiler,quality=program.case.bindings('html');config=compiler.configuration();controls=program.control_bundle(compiler);program.check_controls(controls)
 qa=json.loads(Path(controls['positive_cases'][0]['qa']['file']).read_bytes())
 pins={**program.base.pins(),**config['pins'],**qa['implementation_pins']}
 for module in (program,program.case,program.controller,program.common,quality,sys.modules[__name__],importlib.import_module('compiler_validation_reservation_v1')):
  p=Path(module.__file__).resolve();pins[str(p)]=sha(p.read_bytes())
 for name in ('compiler_html_unseen_pool_v2.py','compiler_types_source_ir_v1.py','compiler_html_source_family_v1.py','compiler_iteration_inventory_v1.py','compiler_validation_cluster_audit_v1.py'):
  p=W/'scripts'/name;pins[str(p)]=sha(p.read_bytes())
 inputs={'scope':asset(SCOPE),'development':asset(DEVELOPMENT),'global_development':asset(GLOBAL_DEVELOPMENT),'inventory_summary':asset(inventory/'summary.json'),'qualified_manifest':asset(inventory/'qualified.jsonl')}
 inputs.update(entrypoint_preflight())
 for development_file in [DEVELOPMENT,GLOBAL_DEVELOPMENT]+sorted((R/'release/compiler_iterations/development_seen_v1').glob('*.jsonl')):pins[str(development_file)]=sha(development_file.read_bytes())
 freeze={'pins':pins,'source_frontend_configuration':config,'controls_proof':controls['definition'],'source_process':source,'pool':str(pool),'inventory':str(inventory),'inputs':inputs,'run_id':run_id,'wait_seconds':seconds,'prepare_only_once':True,'dispatch':'one_frozen_validation_program','goal_complete':False}
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
    result={'preparation':str(directory),'pid':child.pid,'start_ticks':expected['start_ticks'],'source_pid':pid,'source_start_ticks':birth,'finite_wait_seconds':seconds,'dispatched':False,'automatic_validation_launch_after_complete_source_audit':True,'watch':False,'goal_complete':False}
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
