"""Bind unchanged once-safe dispatch and gates to source core18 / independent QA24."""
from pathlib import Path
import ast,re
D=Path(__file__).parent
BASE=D if(D/'svg_analytic_iteration_program_v5.py').exists()else D.parent/'conversion/scripts'
mapping={
 'svg_analytic_source_contract_v5':'svg_analytic_source_contract_v6',
 'svg_analytic_cohort_refresh_v5':'svg_analytic_cohort_refresh_v6',
 'svg_analytic_iteration_pool_v6':'svg_analytic_iteration_pool_v7',
 'svg_analytic_iteration_case_v5':'svg_analytic_iteration_case_v6',
 'svg_analytic_iteration_batch_v5':'svg_analytic_iteration_batch_v6',
 'svg_analytic_iteration_program_v5':'svg_analytic_iteration_program_v6',
 'svg_analytic_iteration_chain_v6':'svg_analytic_iteration_chain_v7',
 'svg_analytic_iteration_controls_v6':'svg_analytic_iteration_controls_v7',
 'compiler_svg_general_guard_v11':'compiler_svg_general_guard_v14',
 'compiler_svg_scene_quality_ro_v17':'compiler_svg_scene_quality_ro_v24',
 'compiler_svg_general_quality_adapter_v13':'compiler_svg_general_quality_adapter_v20',
 'compiler_svg_scene_frontend_v15':'compiler_svg_scene_frontend_v18',
 'general_svg_v15_source_owned_edge_layers_untouched_UA_use_guard_v11':'general_svg_v18_source_background_interleaving_rotation_anchor_guard_v14',
 'svg_edge_use_runtime_controls_20261102_v1':'svg_background_rotation_runtime_controls_20261102_v1',
 'svg_edge_use_runtime_preflight_20261102_v1':'svg_background_rotation_runtime_preflight_20261102_v1',
 'svg_complex_semantic_admission_unseen_20261102_v8':'svg_complex_background_rotation_cached_unseen_20261102_v9',
}
old_names=['svg_analytic_source_contract_v5','svg_analytic_cohort_refresh_v5','svg_analytic_iteration_pool_v6','svg_analytic_iteration_case_v5','svg_analytic_iteration_batch_v5','svg_analytic_iteration_program_v5','svg_analytic_iteration_chain_v6']
for old in old_names:
 source=(BASE/(old+'.py')).read_text()
 for a,b in mapping.items():source=source.replace(a,b)
 if old=='svg_analytic_source_contract_v5':
  values={
   'CATALOG':'release/compiler_iterations/source_core_attempts/manual_catalog_svg_background_rotation_20261102_v9.json',
   'CATALOG_SHA256':'5ddf0e1863b4eba82cda15d0696463eea27f1784815f9d73426aaf751bf2d0c9',
   'CORE_KEY':'d82fa5c6e13e5f305a0c50bc2c358c4b91030e251e7dea6cdd2e775ba51b6086',
   'CONTROLS':'release/compiler_iterations/controls/svg_background_rotation_20261102_v1/proof.json',
   'CONTROLS_SHA256':'0a5cd20d32cb6a2862e223eb41da3168397a5590498a4a6a4841bfe128eec5ab'}
  for key,value in values.items():source=re.sub('^'+key+r'=.*$',key+'='+repr(value),source,flags=re.M)
 if old=='svg_analytic_iteration_chain_v6':
  source=source.replace("name+'_v5.py'for name in('batch','program','case')","name+'_v6.py'for name in('batch','program','case')")
  source=source.replace("CONSUMED='6bfea54fe17b524d3a15883bce122ceb1592312810394cafa67a9905cc339dce'","CONSUMED='af1e3e102c646d715ba7f6a037fa9715e237bd794bd652b4eae366ed41f27abd'")
  source=source.replace("POSITIVE='2a6f2b074d5050fc30f67a12a516aca7ab0ec7764a747b07a0846c020ded0251'","POSITIVE='957add973f1b7dfb1275150c907ef140763cf2fb0114919a20d5bb687d647c5a'")
  source=source.replace("'svg_source_edge_layers_v2.py'","'svg_source_edge_layers_v9.py','svg_background_interleaving_quality_contract_v2.py','svg_rotated_source_visual_scope_v1.py','compiler_svg_explicit_coordinates_v7.py','compiler_svg_explicit_coordinates_v7.js'")
 if old=='svg_analytic_iteration_case_v5':
  source=source.replace('accepted_complete_SVG_nested_groups_SOURCE_v8_orchestration_v2','accepted_complete_SVG_background_rotation_SOURCE_v18_orchestration_v3')
 ast.parse(source)
 target=D/(mapping[old]+'.py')
 if target.exists():assert target.read_text()==source,target
 else:target.write_text(source)
control='from svg_background_interleaving_quality_contract_v2 import (full_quality, check_controls, check_control_case, qa_configuration, check_generation_quality_binding)\n'
p=D/'svg_analytic_iteration_controls_v7.py'
if p.exists():assert p.read_text()==control
else:p.write_text(control)
print('source18 dispatch successors preserve once guards, source seals and unchanged release thresholds')
