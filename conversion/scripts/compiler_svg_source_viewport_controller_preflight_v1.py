"""Four exact controller roles on consumed data; no fresh cohort/reservation."""
from pathlib import Path
import importlib,json,os,sqlite3,subprocess,sys
import compiler_svg_source_viewport_iteration_case_v1 as case
import compiler_svg_source_viewport_iteration_batch_v1 as controller
import compiler_svg_source_viewport_iteration_program_v1 as program
import compiler_svg_source_viewport_unseen_pool_v1 as pool
import compiler_svg_source_viewport_frontend_v1 as compiler
import fixed_batch_pipeline_v1 as base
from compiler_types_program_v1 import R,W,asset,immutable,raw,sha
DIRECTORY=program.CONTROLS.parent

def main():
 cfg=compiler.configuration();pins={**base.pins(),**cfg['pins']}
 modules=('compiler_svg_source_viewport_iteration_case_v1','compiler_svg_source_viewport_iteration_batch_v1','compiler_svg_source_viewport_iteration_program_v1','compiler_svg_source_viewport_unseen_pool_v1','compiler_svg_source_viewport_quality_ro_v1','compiler_typed_runtime_failure_v1','compiler_mermaid_alpha_qualifications_v2','compiler_mermaid_alpha_iteration_overlap_v2','compiler_iteration_inventory_v1','initial_conversion_process_v1')
 for name in modules:
  p=Path(importlib.import_module(name).__file__).absolute();pins[str(p)]=sha(p.read_bytes())
 positive=R/'clean/compiler_svg_source_viewport_graphviz_v1/04/04cba845625f3d4970ef5390ea775bd92210fc3a00c7580f83f261431033a523/852423a34cd84b7f822668c527be1cec/record.json';negative=json.loads((W/'svg_source_viewport_actual_controls_v1/ae1c3dec43294b859b7d0f2575de51aa/candidate_record.json').read_bytes());negative_source=W/'svg_source_viewport_actual_controls_v1/ae1c3dec43294b859b7d0f2575de51aa/candidate_record.json';negative_path=(R/negative['code_file']).parent/'actual_controller_negative_record.json';immutable(negative_path,negative_source.read_bytes())
 definitions=[('B','8547d4470360c1b4016a904cef03dd8b40e55f9fe607a5313705170c847ba288','baseline',{}),('positive','04cba845625f3d4970ef5390ea775bd92210fc3a00c7580f83f261431033a523','control_positive',{'existing_development_candidate':str(positive)}),('negative','2e7a3239abab0f76415a23602e1e611e7c9f6b4fedf265ef1a7739fffc7007e6','control_negative',{'negative_control':True,'development_candidate':str(negative_path)}),('normal_source_failure','8547d4470360c1b4016a904cef03dd8b40e55f9fe607a5313705170c847ba288','candidate',{})]
 cases=[]
 for role,id,phase,extra in definitions:
  name='svg_source_surface_exact_preflight_20261101_v1_'+role;run=controller.FLOOR/name
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as d:job=d.execute('select * from jobs where id=?',(id,)).fetchone()
  request=pool.request_from_job(job,json.loads(job[4]),compiler.UNITS['svg']);request.update(seq=1,evaluation_phase=phase,cluster='consumed_exact_controller_preflight:'+id,**extra);program.validate_source_requests([request]);payload=raw(request);manifest=DIRECTORY/('preflight_'+role+'.jsonl');immutable(manifest,payload)
  freeze={'pins':pins,'input_sha256':sha(payload),'qa_policy_sha256':sha(raw({'source_policy':cfg['policy'],'case':pins[str(Path(case.__file__).absolute())]})),'predicate_hashes':{compiler.UNITS['svg']:sha(raw(cfg))}};freeze['implementation_identity']=controller.implementation_identity(freeze);freeze['implementation_identity_sha256']=controller.implementation_digest(freeze);fp=DIRECTORY/('preflight_'+role+'.freeze.json');immutable(fp,raw(freeze));controller.create(run,manifest,fp,'development')
  argv=[sys.executable,'-B',str(Path(controller.__file__).absolute()),'run','--run-id',name,'--workers','1','--case-timeout','900']
  with(DIRECTORY/('preflight_'+role+'.log')).open('ab')as log:p=subprocess.run(argv,stdout=log,stderr=log,env={**os.environ,'PYTHONPATH':str(R/'env')+':'+str(W/'scripts'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
  if p.returncode:raise RuntimeError('actual_controller_role_failed:'+role)
  snapshot=controller.snapshot(run)
  with sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)as d:result=json.loads(d.execute('select result from samples').fetchone()[0])
  work=W/'compiler_iterations'/name/('000001_'+id);isolation=json.loads((work/'isolation.json').read_bytes());assert snapshot['metadata']['finished']and not snapshot['infrastructure_stop']and isolation['cleanup_complete']is True
  if role=='positive':assert result['status']=='qualified',result
  elif role=='negative':assert result['reason']=='negative_correctly_rejected'and result.get('negative_false_acceptance')is False,result
  else:assert result['status']=='abandoned'and not result.get('infrastructure_failure'),result
  normal=(work/'frontend_result.json').is_file();cases.append(dict(id=id,role=role,status=result['status'],phase=result.get('phase'),reason=result['reason'],normal_frontend_attempt=normal,infrastructure_failure=result.get('infrastructure_failure',False),result=asset(work/'result.json'),request=asset(work/'request.json'),isolation=asset(work/'isolation.json'),source_code_sha256=result['source_code_sha256'],source_image_sha256=result['source_image_sha256']))
  print(json.dumps({'role':role,'status':result['status'],'reason':result['reason'],'phase':result.get('phase'),'normal_frontend_attempt':normal}),flush=True)
 proof={'schema':'exact_svg_source_surface_controller_preflight_v1','cases':cases,'all_expected_outcomes':True,'case_module':asset(case.__file__),'controller_module':asset(controller.__file__),'typed_failure_module':asset(importlib.import_module('compiler_typed_runtime_failure_v1').__file__),'frozen_frontend':cfg,'models':0,'new_heldout':0,'canonical_mutations':0};immutable(DIRECTORY/'case_preflight.json',raw(proof));print(json.dumps({'preflight':asset(DIRECTORY/'case_preflight.json')}),flush=True)
if __name__=='__main__':main()
