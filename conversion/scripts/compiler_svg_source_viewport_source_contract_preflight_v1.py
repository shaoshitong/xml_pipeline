"""Actual consumed SVG metadata: constructor -> validator -> strict mutations.

No reservation, source/native conversion, QA dispatch or canonical write.
"""
import copy,json,sqlite3
from pathlib import Path
import compiler_svg_source_viewport_frontend_v1 as compiler
import compiler_svg_source_viewport_iteration_program_v1 as program
import compiler_svg_source_viewport_unseen_pool_v1 as pool
IDS=('8547d4470360c1b4016a904cef03dd8b40e55f9fe607a5313705170c847ba288','04cba845625f3d4970ef5390ea775bd92210fc3a00c7580f83f261431033a523','2e7a3239abab0f76415a23602e1e611e7c9f6b4fedf265ef1a7739fffc7007e6')

def main():
 rows=[];locators=[]
 with sqlite3.connect('file:'+str(program.W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as d:
  for id in IDS:
   job=d.execute('select * from jobs where id=?',(id,)).fetchone();source=json.loads(job[4]);request=pool.request_from_job(job,source,compiler.UNITS['svg']);program.validate_source_requests([request]);mutations={}
   bad=copy.deepcopy(request);bad['source']={k:source[k]for k in ('category','format','source','code_sha256','image_sha256')}
   for name,candidate,reason in [('five_field_summary',bad,'selected_worker_requires_complete_canonical_source_record'),('baseline_record_mutation',{**request,'source_record_sha256':'0'*64},'selected_baseline_record_snapshot_changed'),('baseline_code_mutation',{**request,'baseline_code_sha256':'wrong'},'selected_baseline_asset_snapshot_changed'),('baseline_image_mutation',{**request,'baseline_image_sha256':'wrong'},'selected_baseline_asset_snapshot_changed')]:
    try:program.validate_source_requests([candidate])
    except ValueError as error:
     if str(error)!=reason:raise
     mutations[name]=reason
    else:raise RuntimeError('invalid_worker_source_would_be_dispatched:'+name)
   manifest=json.loads(job[11]);text=pool.checked_original_code(manifest['source_code'],source['code_sha256']);path=(program.R/manifest['source_code']).resolve(strict=True)
   if text!=path.read_bytes().decode('utf-8-sig'):raise ValueError('staged_source_locator_not_original')
   if d.execute('select * from jobs where id=?',(id,)).fetchone()!=job:raise RuntimeError('canonical_metadata_changed')
   rows.append(dict(id=id,source_fields=len(source),source_input_record_sha256=program.sha(job[4].encode()),request_sha256=pool.sha(pool.raw(request)),full_canonical_source_passed=True,mutations_rejected=mutations,baseline_snapshot_verified=True,canonical_metadata_unchanged=True));locators.append(dict(id=id,original_source_code=manifest['source_code'],source_code_sha256=source['code_sha256'],registered_root_containment=True,clean_only_assumption=False))
 directory=program.CONTROLS.parent;proof=dict(schema='svg_source_surface_actual_source_contract_v1',ok=True,cases=rows,reservations=0,candidate_dispatches=0,model_calls=0,frozen_frontend=compiler.configuration(),producers={n:program.asset(p)for n,p in [('preflight',Path(__file__).resolve()),('pool',Path(pool.__file__).resolve()),('program',Path(program.__file__).resolve()),('controller',Path(program.controller.__file__).resolve()),('case',Path(program.case.__file__).resolve())]})
 program.immutable(directory/'source_contract_v1.json',program.raw(proof));program.immutable(directory/'source_locator_profile_v1.json',program.raw({'all_match_frozen_frontend':True,'cases':locators,'pool_module':program.asset(pool.__file__),'actual_source_contract':program.asset(directory/'source_contract_v1.json')}));print(json.dumps({'proof':program.asset(directory/'source_contract_v1.json'),'source_locator_profile':program.asset(directory/'source_locator_profile_v1.json'),'cases':rows}),flush=True)
if __name__=='__main__':main()
