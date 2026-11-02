"""Generate immutable successor orchestration from unchanged dispatch contracts."""
from pathlib import Path
import argparse,json,re
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
p=argparse.ArgumentParser();p.add_argument('--closure',type=Path,required=True);a=p.parse_args();closure=json.loads(a.closure.read_text())
oldunit='general_svg_v12_analytic_endpoint_cubic_bezier_nested_groups_actual_shadow_layout_use_instances_source_compositing_order_guard_v8';newunit='general_svg_v13_native_symbol_viewport_source_compositing_order_guard_v9'
mapping={'svg_analytic_source_contract_v3':'svg_analytic_source_contract_v4','svg_analytic_cohort_refresh_v3':'svg_analytic_cohort_refresh_v4','svg_analytic_iteration_pool_v4':'svg_analytic_iteration_pool_v5','svg_analytic_iteration_case_v3':'svg_analytic_iteration_case_v4','svg_analytic_iteration_batch_v3':'svg_analytic_iteration_batch_v4','svg_analytic_iteration_program_v3':'svg_analytic_iteration_program_v4','svg_analytic_iteration_chain_v4':'svg_analytic_iteration_chain_v5','svg_analytic_iteration_controls_v4':'svg_analytic_iteration_controls_v5','compiler_svg_general_guard_v8':'compiler_svg_general_guard_v9','compiler_svg_scene_quality_ro_v13':'compiler_svg_scene_quality_ro_v15','compiler_svg_general_quality_adapter_v9':'compiler_svg_general_quality_adapter_v11','compiler_svg_scene_frontend_v12':'compiler_svg_scene_frontend_v13',oldunit:newunit,'svg_actual_shadow_runtime_controls_20261102_v3':'svg_symbol_runtime_controls_20261102_v1','svg_actual_shadow_runtime_preflight_20261102_v3':'svg_symbol_runtime_preflight_20261102_v1','svg_actual_shadow_unseen100_20261102_v4':'svg_complex_symbol_viewport_unseen100_20261102_v7'}
files=['svg_analytic_source_contract_v3','svg_analytic_cohort_refresh_v3','svg_analytic_iteration_pool_v4','svg_analytic_iteration_case_v3','svg_analytic_iteration_batch_v3','svg_analytic_iteration_program_v3','svg_analytic_iteration_chain_v4']
for old in files:
 s=(D/(old+'.py')).read_text()
 for src,dst in mapping.items():s=s.replace(src,dst)
 if old=='svg_analytic_source_contract_v3':
  for key,value in [('CATALOG',closure['catalog']['file']),('CATALOG_SHA256',closure['catalog']['sha256']),('CORE_KEY',closure['source_core']['key']),('CONTROLS',closure['proof']['file']),('CONTROLS_SHA256',closure['proof']['sha256'])]:s=re.sub('^'+key+r"=.*$",key+'='+repr(value),s,flags=re.M)
 if old=='svg_analytic_iteration_chain_v4':
  s=s.replace("name+'_v3.py'for name in('batch','program','case')", "name+'_v4.py'for name in('batch','program','case')")
  s=s.replace("CONSUMED='0dc3f8bb2a134a79aba055dc8cc6686f7d097b187bd08267a5bdc4f8d8bd633e'", "CONSUMED='6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb'")
  s=s.replace("'compiler_svg_general_quality_adapter_v11.py',", "'compiler_svg_general_quality_adapter_v11.py','svg_leaf_opacity_proof_v1.py','svg_source_use_instance_proof_v3.py',")
 if old=='svg_analytic_iteration_program_v3':
  s=s.replace("pins = {**base.pins(), **config['pins'], **info['method_pins']}","from compiler_svg_general_quality_adapter_v11 import configuration as QA_configuration\n    pins = {**base.pins(), **config['pins'], **QA_configuration()['pins'], **info['method_pins']}")
 target=D/(mapping[old]+'.py')
 if target.exists():assert target.read_text()==s,target
 else:target.write_text(s)
print('created seven successor dispatch modules; old runs preserved')
