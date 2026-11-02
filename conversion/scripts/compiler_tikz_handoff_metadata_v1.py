"""Publish only implementation/evidence metadata; all sample assets stay remote."""
from pathlib import Path
import argparse,datetime,inspect,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
import compiler_tikz_poppler_source_v2 as frontend
import compiler_tikz_quality_ro_v2 as quality
import compiler_tikz_iteration_program_v1 as program
from compiler_types_program_v1 import asset,immutable,raw

def main(pool=None,prepared=None):
 controls=program.control_bundle(frontend);program.check_controls(controls)
 qa=json.loads(Path(controls['positive_cases'][0]['qa']['file']).read_bytes())
 config=frontend.configuration()
 modules=('compiler_tikz_poppler_source_v2.py','compiler_tikz_quality_ro_v2.py','compiler_tikz_iteration_case_v1.py','compiler_tikz_iteration_batch_v1.py','compiler_tikz_iteration_program_v1.py','compiler_tikz_unseen_pool_v1.py','compiler_tikz_iteration_controls_v1.py')
 result={
  'schema':'tikz_pdftex2025_complete_source_preparation_metadata_v1',
  'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'data_location':'HKUST3','root':str(R),'scope_all_TikZ':40746,
  'model_calls':0,'sample_assets_downloaded_locally':False,'goal_complete':False,
  'source_frontend':frontend.__name__,'source_frontend_configuration':config,
  'unit':frontend.UNITS['tikz'],'readonly_quality_api':str(Path(quality.__file__)),
  'quality_version':quality.VERSION,'complete_full_QA_dependency_pins':qa['implementation_pins'],
  'api':{name:str(inspect.signature(getattr(frontend,name))) for name in ('convert','configuration','static_support','check_source','audit_editing','registration_record')},
  'verify_api':str(inspect.signature(quality.verify)),
  'source_only_static_scope':{
   'format':'tikz','provider':'Y36521478Y--omnidiagram_train_sft','original_PNG_pHYs_DPI':100,
   'maximum_source_bytes':250000,'maximum_reference_side':8192,'maximum_reference_pixels':64000000,
   'static_eligibility_is_not_qualification':True,
   'required_per_candidate':['unchanged_original_source_execution','actual_Poppler_PDF_reference_reproduction','complete_actual_PDF_paint_and_glyph_display_list','complete_PGF_named_or_free_endpoint_roles','fresh_canonical_source_replay','strict_actual_native_PNG','all_source_text_actual_embedded_fonts','actual_vertex_and_both_endpoint_interventions','independent_local_and_global_image_quality']},
  'controls_proof':controls['definition'],'actual_full_quality_positives':len(controls['positive_cases']),
  'actual_rehashed_XML_native_PNG_negatives_rejected':len(controls['negative_cases']),
  'qualified_development_manifest':controls['qualified_manifest'],
  'verification':{'HKUST_core_and_orchestration_tests':50,'HKUST_preparation_finalizer_tests':8,'local_orchestration_tests':30,'local_pure_source_tests':12,'local_preparation_finalizer_tests':8},
  'release_conditions':{'minimum_fresh_cases':100,'minimum_full_quality_fraction':.20,'minimum_new_qualified':5,'maximum_positive_regressions':0,'maximum_infrastructure_errors':0,'maximum_negative_false_acceptances':0,'then_automatic_bulk_on_all_applicable_pending':True,'round_end_is_overall_goal_completion':False},
  'delivery_modules':{name:asset(W/'scripts'/name) for name in modules},
  'known_failed_development':'Other seen cases retain source compile, rotated text, native padding, frame ambiguity and relative-vector failures as retryable inputs for the next generic compiler version; no threshold was reduced.'}
 if pool:
  pool=Path(pool).resolve(strict=True);info=json.loads((pool/'summary.json').read_bytes());result['source_only_pool']={'summary':asset(pool/'summary.json'),'scope':info['scope'],'selected':info['selected'],'counters':info['counters'],'excluded_accepted':info['excluded_accepted'],'eligible_observed_families':info['eligible_observed_families'],'files':info['files']}
 if prepared:
  prepared=program.owned(prepared);result['prepared_program']={'directory':str(prepared),'dispatched':False,'implementation':asset(prepared/'implementation.json'),'protocol':asset(prepared/'protocol.json'),'reservation':asset(prepared/'reservation.json'),'launch_command':'/home/shaoshitong/anaconda3/bin/python '+str(W/'scripts/compiler_tikz_iteration_program_v1.py')+' launch --program-dir '+str(prepared)+' --workers 4 --case-timeout 900'}
 assert frontend.configuration()==config
 target=R/'release/compiler_iterations/handoffs/tikz_pdftex2025_v2_20261101_v1.json'
 immutable(target,raw(result));print(json.dumps({'handoff':asset(target),'source_only_pool':result.get('source_only_pool'),'prepared_program':result.get('prepared_program')},ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pool',type=Path);p.add_argument('--prepared',type=Path);a=p.parse_args();main(a.pool,a.prepared)
