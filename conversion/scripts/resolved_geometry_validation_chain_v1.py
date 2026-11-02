"""Finite source admission -> fresh validation -> gated whole-population conversion."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,value):
 tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,p)
def live(h):
 p=Path('/proc',str(h['pid']),'stat');return p.exists()and p.read_text().rsplit(') ',1)[1].split()[19]==str(h['birth_ticks'])
def execute(root):
 plan=json.loads((root/'plan.json').read_bytes());put(root/'owner.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]));start=time.monotonic()
 try:
  while True:
   source=[];ready=True
   for h in plan['admissions']:
    path=Path(h['root'])/'summary.json';summary=json.loads(path.read_bytes());source.append(summary)
    if not summary['finished']:
     ready=False
     if not live(h):raise RuntimeError('Source admission owner ended before completion: '+str(path))
   proof=R/'release/compiler_iterations/controls/svg_resolved_geometry_runtime_controls_20261102_v1/proof.json'
   if not proof.exists():
    ready=False
    if not live(plan['runtime']):raise RuntimeError('Runtime preflight ended without proof: '+(Path(plan['runtime']['parent'])/'output.log').read_text()[-2500:])
   put(root/'state.json',dict(stage='waiting_original_source_admissions_and_runtime_proof',sources=[dict(root=s['root'],completed=s['completed'],total=s['total'],finished=s['finished'])for s in source],runtime_proof=proof.exists(),goal_complete=False))
   if ready:break
   if time.monotonic()-start>7200:raise RuntimeError('Finite observation bound reached; preserve original handles, never automatically restart')
   time.sleep(5)
  for name,digest in plan['pins'].items():assert sha(Path(name).read_bytes())==digest,name
  import derive_resolved_geometry_source_pool_v1 as sourcepool
  import svg_analytic_iteration_program_v8 as program
  program.runtime_controls();put(root/'state.json',dict(stage='freeze_full_source_population_and_fresh_metadata_exclusions',goal_complete=False))
  pool=sourcepool.prepare([h['root']for h in plan['admissions']]);put(root/'source_pool.json',pool)
  if not pool['selected']:
   put(root/'state.json',dict(stage='no_remaining_unseen_family_in_frozen_scope',source_pool=pool,goal_complete=False,requires_source_scope_or_family_diagnosis=True));return
  prepared=program.prepare(Path(pool['pool']),pool['run_id']);put(root/'prepared.json',prepared)
  launch=program.launch(Path(prepared['program_dir']),12,900);put(root/'program_launch.json',launch)
  put(root/'state.json',dict(stage='fixed_fresh_validation_then_gated_mass_launched',program=launch,source_pool=pool,goal_complete=False,model_calls=0))
 except BaseException as e:
  put(root/'failure.json',dict(reason=str(e),type=type(e).__name__,goal_complete=False));put(root/'state.json',dict(stage='requires_repair',reason=str(e),goal_complete=False));raise

def launch(receipts):
 data=json.loads(receipts.read_bytes());assert len(data['admissions'])==2
 root=R/'conversion/resolved_geometry_validation_chain_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
 names=['resolved_geometry_validation_chain_v1','derive_resolved_geometry_source_pool_v1','svg_analytic_source_contract_v8','svg_analytic_cohort_refresh_v8','svg_analytic_iteration_pool_v9','svg_analytic_iteration_chain_v9','svg_analytic_iteration_controls_v9','svg_analytic_iteration_program_v8','svg_analytic_iteration_batch_v8','svg_analytic_iteration_case_v8']
 pins={}
 for name in names:
  p=S/(name+'.py');pins[str(p)]=sha(p.read_bytes());p.chmod(0o444)
 plan=dict(data,pins=pins,normal_attempts_per_original_per_source_core=1,workers=12,maximum_wait_seconds=7200,model_calls=0,goal_complete=False);put(root/'plan.json',plan);(root/'plan.json').chmod(0o444)
 with(root/'output.log').open('wb')as log:p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'execute','--path',str(root)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
 birth=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19];receipt=dict(root=str(root),pid=p.pid,birth_ticks=birth,finite=True,goal_complete=False);put(root/'launch.json',receipt);return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('launch','execute'));p.add_argument('--path',type=Path,required=True);a=p.parse_args();r=launch(a.path)if a.action=='launch'else execute(a.path);print(json.dumps(r))
