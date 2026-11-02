"""Freeze source-semantic eligibility without using candidate/QA outcomes."""
from pathlib import Path
import hashlib,inspect,json,shutil,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
PARENT=R/'release/compiler_iterations/source_pools/svg_complex_symbol_viewport_unseen100_20261102_v7';RUN='svg_complex_background_rotation_cached_unseen_20261102_v9';OUT=R/'release/compiler_iterations/source_pools'/RUN
sha=lambda b:hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(p):return[json.loads(x)for x in p.read_bytes().splitlines()if x]
def prepare(audit):
 import svg_analytic_source_contract_v6 as contract
 import svg_analytic_cohort_refresh_v6 as refresh
 import compiler_source_core_attempts_v3 as history
 import compiler_validation_identity_alias_v1 as aliases
 import compiler_svg_scene_frontend_v13 as old
 import compiler_svg_scene_frontend_v18 as new
 audit=Path(audit).resolve(strict=True);assert audit.is_relative_to(R/'conversion/source_cached_admission_v1');summary=json.loads((audit/'summary.json').read_bytes());plan=json.loads((audit/'plan.json').read_bytes());cfg=contract.configuration();assert summary['finished']and summary.get('files')and summary['completed']==summary['total']==2365
 assert plan['configuration']==cfg and json.loads((audit/'configuration.json').read_bytes())==cfg
 assert plan['input_sha256']==sha((PARENT/'supported_population.jsonl').read_bytes())==sha((audit/'input.jsonl').read_bytes())
 assert sha((S/'svg_source_cached_admission_v1.py').read_bytes())==plan['producer_sha256']
 for name,ref in summary['files'].items():assert sha((R/ref['file']).read_bytes())==ref['sha256'],name
 admitted={r['id']:r for r in rows(audit/'admitted.jsonl')};assert admitted
 for r in admitted.values():assert r['normal_conversion_calls']==r['candidate_emissions']==r['QA_calls']==0 and r['source_only_semantic_admission']and r['source_reference_and_physical_font_reproduced']and r['current_source_semantics_recomputed']and r['source_observation_reused_from_frozen_v15']and not r['source_observation_fresh_for_current_core']
 info=json.loads((PARENT/'summary.json').read_bytes());assert info['scope']==26754 and info['full_scope_manifest']['unique_scope']==131904
 for name,ref in info['files'].items():assert sha((PARENT/name).read_bytes())==ref['sha256'],name
 for name,digest in info['method_pins'].items():assert sha(Path(name).read_bytes())==digest,name
 for name in('static_support','source_admission','_inputs'):assert inspect.getsource(getattr(old,name))==inspect.getsource(getattr(new,name)),name
 full=rows(PARENT/'supported_population.jsonl');population=[]
 for row in full:
  decision=admitted.get(row['id'])
  if decision:
   assert(row['source']['code_sha256'],row['source']['image_sha256'])==(decision['source_code_sha256'],decision['source_image_sha256']);population.append({**row,'compiler_unit':contract.UNIT})
 assert len(population)==len(admitted)
 snapshot=refresh.knowledge_snapshot(PARENT,cfg)
 with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as d:registry=set(d.execute('select kind,value from reservation_keys'))
 seal=json.loads((PARENT/'sealed_source_components.json').read_bytes());choice=refresh.choose(seal,population,snapshot,aliases.normalize_keys(registry),seed=info['seed'],limit=100)
 if not choice['selected']:return dict(pool=None,selected=0,reason='no_remaining_independent_source_semantic_families',admission_summary=summary,goal_complete=False)
 OUT.mkdir(parents=True,exist_ok=False)
 excluded={'supported_population.jsonl','selected.jsonl','target_selection_snapshot.json','complex_source_policy.json','summary.json','prior_candidate_attempts.jsonl'}
 for name in info['files']:
  if name not in excluded:shutil.copyfile(PARENT/name,OUT/name)
 shutil.copyfile(PARENT/'supported_population.jsonl',OUT/'all_complex_raw_supported_population.jsonl');shutil.copyfile(PARENT/'prior_candidate_attempts.jsonl',OUT/'preserved_parent_other_core_history.jsonl')
 (OUT/'supported_population.jsonl').write_bytes(b''.join(raw(r)for r in population));(OUT/'selected.jsonl').write_bytes(b''.join(raw(r)for r in choice['selected']));(OUT/'target_selection_snapshot.json').write_bytes(raw(choice))
 events=history.collect(cfg,root=R,catalog=contract.CATALOG);history.validate(events,cfg,root=R);(OUT/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(r)for r in events))
 for name in('admitted.jsonl','unsupported.jsonl','error.jsonl','plan.json','configuration.json','summary.json'):shutil.copyfile(audit/name,OUT/('source_admission_'+name))
 policy={**info['source_value_policy'],'source_semantic_admission_preregistered_before_unseen_selection':True,'source_admission_plan_sha256':sha((audit/'plan.json').read_bytes()),'raw_complex_source_targets_preserved':len(full),'source_semantically_admitted':len(population),'source_unsupported_retained':summary['counts'].get('unsupported',0),'source_admission_errors_retained_pending':summary['counts'].get('error',0),'hash_verified_unchanged_source_observation_reused':True,'fresh_source_browser_capture_in_candidate_QA_still_mandatory':True,'prior_source_rejections_and_errors_retained_with_origin_core':True,'candidate_or_QA_outcomes_used_for_source_eligibility':False,'quality_thresholds_changed':False,'not_a_format_completion':True};(OUT/'complex_source_policy.json').write_bytes(raw(policy))
 methods={**info['method_pins'],str(Path(__file__).resolve()):sha(Path(__file__).read_bytes())}
 for name in('svg_source_cached_admission_v1.py','svg_analytic_source_contract_v6.py','svg_analytic_cohort_refresh_v6.py','svg_analytic_iteration_pool_v7.py'):
  p=S/name;methods[str(p)]=sha(p.read_bytes())
 for name in('source_admission_admitted.jsonl','source_admission_unsupported.jsonl','source_admission_error.jsonl','source_admission_plan.json','source_admission_configuration.json','source_admission_summary.json'):
  p=OUT/name;methods[str(p)]=sha(p.read_bytes())
 files={p.name:dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)for p in OUT.iterdir()if p.is_file()}
 final={**info,'schema':'complex_SVG_cached_source_semantic_admission_pool_v2','frontend_module':'svg_analytic_source_contract_v6','frozen_implementation':cfg,'method_pins':methods,'source_value_policy':policy,'files':files,'counters':{**info['counters'],'supported_remaining_population':len(population)},'prior_same_SOURCE_frontend_distinct_candidate_attempts':len(events),'eligible_observed_families':choice['eligible_observed_families'],'selected':len(choice['selected']),'minimum100_met':len(choice['selected'])>=100,'all_remaining_observed_families_selected':choice['all_remaining_observed_families_selected']};(OUT/'summary.json').write_bytes(raw(final))
 for p in OUT.iterdir():p.chmod(0o444)
 return dict(pool=str(OUT),run_id=RUN,selected=len(choice['selected']),eligible_observed_families=choice['eligible_observed_families'],policy=policy)
