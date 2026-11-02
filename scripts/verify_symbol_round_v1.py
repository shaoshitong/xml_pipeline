from pathlib import Path
import base64,subprocess,json,hashlib
helper=Path('work/takeover/check_svg_progress_v3.py').read_text()
D=Path('work/svg_group_order_fix')
names=['svg_source_symbol_viewport_v1.py','svg_source_symbol_viewport_v1.js','svg_dom_v9.js','svg_dom_source_scene_v4.js','svg_source_endpoint_bridge_v3.py','svg_source_use_instance_proof_v4.py','compiler_svg_scene_frontend_v13.py','compiler_svg_general_guard_v9.py','compiler_svg_general_quality_adapter_v11.py','compiler_svg_scene_quality_ro_v15.py','svg_leaf_opacity_proof_v1.py','svg_analytic_iteration_controls_v5.py','svg_analytic_source_contract_v4.py','svg_analytic_cohort_refresh_v4.py','svg_analytic_iteration_pool_v5.py','svg_analytic_iteration_case_v4.py','svg_analytic_iteration_batch_v4.py','svg_analytic_iteration_program_v4.py','svg_analytic_iteration_chain_v5.py','derive_symbol_complex_source_pool_v1.py','launch_symbol_validation_after_controls_v1.py']
expected={n:hashlib.sha256((D/n).read_bytes()).hexdigest()for n in names}
code='''from pathlib import Path
import contextlib,io,json,hashlib
scope={'__name__':'progress_helper'}
exec(HELPER,scope)
buffer=io.StringIO()
with contextlib.redirect_stdout(buffer):scope['main']()
d=json.loads(buffer.getvalue());R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
expected=EXPECTED
assert all(hashlib.sha256((S/n).read_bytes()).hexdigest()==value for n,value in expected.items())
d['deployed_runtime_files_exact']=len(expected)
proof=R/'release/compiler_iterations/controls/svg_symbol_runtime_controls_20261102_v1/proof.json'
d['runtime_dispatch_proof']=dict(file=str(proof.relative_to(R)),sha256=hashlib.sha256(proof.read_bytes()).hexdigest())
r=json.loads(proof.read_bytes());assert r['normal_source_conversion_calls']==0 and r['same_core_normal_history_unchanged']
d['normal_history_unchanged_and_prevented_reexecution']=True
assert d['failure']is None and d['B']['infrastructure_failures']==0 and d['C']['infrastructure_failures']==0
print(json.dumps(d))
'''.replace('HELPER',repr(helper)).replace('EXPECTED',repr(expected))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20)
if r.returncode==0:
 d=json.loads(r.stdout);Path('outputs/symbol-validation-progress2-20261102.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
else:print(r.stderr)
raise SystemExit(r.returncode)
