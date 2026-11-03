"""Prove unchanged source admission; this never proves candidate fidelity."""
from pathlib import Path
import ast,hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
def sha(b):return hashlib.sha256(b).hexdigest()
def functions(p):return {n.name:ast.dump(n,include_attributes=False)for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
def main():
    old=S/'compiler_svg_scene_frontend_v22.py';new=S/'compiler_svg_scene_frontend_v24.py';a,b=functions(old),functions(new);changed=sorted(k for k in a if a[k]!=b.get(k));assert changed==['_apply_offsets','_preserve_source_whitespace','convert'];assert a.keys()==b.keys()
    ga,gb=functions(S/'compiler_svg_general_guard_v18.py'),functions(S/'compiler_svg_general_guard_v20.py');assert ga==gb
    x=ast.parse(old.read_text());y=ast.parse(new.read_text())
    globals_for=lambda t:{n.targets[0].id:ast.dump(n.value,include_attributes=False)for n in t.body if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
    x,y=globals_for(x),globals_for(y);global_changes=sorted(k for k in x if x[k]!=y.get(k));assert global_changes==['DEPENDENCIES','VERSION']
    source_methods=['source_admission','static_support','_inputs','_render_source','_screenshot','_bind_actual_cairo_faces','_normalize_paint_alpha','_wrap_source_runs','_observe_runs','_observe_general','_capture_issue_gate','_capture','_expected_text_regions','prepare_source','_cairo_font_check','source_reproduction']
    for k in source_methods:assert a[k]==b[k]
    root=R/'conversion/svg_whitespace_source_admission_equivalence_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    out=dict(root=str(root),old_frontend_sha256=sha(old.read_bytes()),new_frontend_sha256=sha(new.read_bytes()),changed_functions=changed,changed_globals=global_changes,source_admission_methods_AST_equal=source_methods,source_guard_methods_AST_equal=sorted(ga),source_eligibility_predicates_unchanged=True,source_behavior_VERSION_changes_namespace_and_proof_label=True,old_admission_results_reusable_only_with_exact_original_source_and_reference_hashes=True,candidate_qualification_or_unseen_validation_proved=False,new_normal_calls=0,new_QA_calls=0,goal_complete=False)
    (root/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
if __name__=='__main__':main()
