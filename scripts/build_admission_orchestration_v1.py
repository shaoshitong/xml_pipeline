"""Successor dispatch fixes current-core history before reservation and closure."""
from pathlib import Path
import re,json
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
mapping={'svg_analytic_source_contract_v4':'svg_analytic_source_contract_v5','svg_analytic_cohort_refresh_v4':'svg_analytic_cohort_refresh_v5','svg_analytic_iteration_pool_v5':'svg_analytic_iteration_pool_v6','svg_analytic_iteration_case_v4':'svg_analytic_iteration_case_v5','svg_analytic_iteration_batch_v4':'svg_analytic_iteration_batch_v5','svg_analytic_iteration_program_v4':'svg_analytic_iteration_program_v5','svg_analytic_iteration_chain_v5':'svg_analytic_iteration_chain_v6','svg_analytic_iteration_controls_v5':'svg_analytic_iteration_controls_v6','compiler_svg_general_guard_v9':'compiler_svg_general_guard_v11','compiler_svg_scene_quality_ro_v15':'compiler_svg_scene_quality_ro_v17','compiler_svg_general_quality_adapter_v11':'compiler_svg_general_quality_adapter_v13','compiler_svg_scene_frontend_v13':'compiler_svg_scene_frontend_v15','general_svg_v13_native_symbol_viewport_source_compositing_order_guard_v9':'general_svg_v15_source_owned_edge_layers_untouched_UA_use_guard_v11','svg_symbol_runtime_controls_20261102_v1':'svg_edge_use_runtime_controls_20261102_v1','svg_symbol_runtime_preflight_20261102_v1':'svg_edge_use_runtime_preflight_20261102_v1','svg_complex_symbol_viewport_unseen100_20261102_v7':'svg_complex_semantic_admission_unseen_20261102_v8'}
for old in ['svg_analytic_source_contract_v4','svg_analytic_cohort_refresh_v4','svg_analytic_iteration_pool_v5','svg_analytic_iteration_case_v4','svg_analytic_iteration_batch_v4','svg_analytic_iteration_program_v4','svg_analytic_iteration_chain_v5']:
 s=(D/(old+'.py')).read_text()
 for a,b in mapping.items():s=s.replace(a,b)
 if old=='svg_analytic_source_contract_v4':
  values={'CATALOG':'release/compiler_iterations/source_core_attempts/manual_catalog_svg_edge_layers_untouched_use_20261102_v8.json','CATALOG_SHA256':'f94e6a69e6c7628ccf2151d39258a7969cffe2fa879458fa1587b4038be9e470','CORE_KEY':'a26deb4ee449f8df0abc7f7b48ad42f95939a47e40f5496bf8d310663b444f5f','CONTROLS':'release/compiler_iterations/controls/svg_source_edge_layers_untouched_use_20261102_v1/proof.json','CONTROLS_SHA256':'fb73462f9964da0bcad2051ac5db18d2267e86717d2789d7ff555af0c300376b'}
  for key,value in values.items():s=re.sub('^'+key+r'=.*$',key+'='+repr(value),s,flags=re.M)
 if old=='svg_analytic_iteration_chain_v5':
  s=s.replace("name+'_v4.py'for name in('batch','program','case')", "name+'_v5.py'for name in('batch','program','case')").replace("CONSUMED='6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb'","CONSUMED='6bfea54fe17b524d3a15883bce122ceb1592312810394cafa67a9905cc339dce'")
  s=s.replace("'svg_source_use_instance_proof_v3.py',", "'svg_source_use_instance_proof_v5.py','svg_source_use_instance_proof_v6.py','svg_source_edge_layers_v2.py',")
 if old=='svg_analytic_iteration_program_v4':
  s=s.replace("prior_ids={x['id']for x in readrows(pool/'prior_candidate_attempts.jsonl')}","pool_prior=readrows(pool/'prior_candidate_attempts.jsonl');history.validate(pool_prior,compiler.configuration(),root=R)\n    prior_ids={x['id']for x in pool_prior}")
  s=s.replace("for name in ('supported_population.jsonl','preserved_qualified.jsonl','prior_candidate_attempts.jsonl'):","immutable(p/'prior_candidate_attempts.jsonl',b''.join(raw(row)for row in current_prior))\n    for name in ('supported_population.jsonl','preserved_qualified.jsonl'):")
 target=D/(mapping[old]+'.py')
 if target.exists():assert target.read_text()==s,target
 else:target.write_text(s)
print('successor metadata/history validation now precedes reservation and dispatch')
