"""Freeze current full8 positive, historical regression and four real negatives."""
from pathlib import Path
import hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def put(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b,str(p)
 else:p.write_bytes(b);p.chmod(0o444)
def main():
 import compiler_svg_general_guard_v14 as core
 import compiler_svg_general_quality_adapter_v20 as adapter
 import compiler_source_core_attempts_v3 as history
 import svg_background_interleaving_quality_contract_v2 as checker
 root=R/'conversion/svg_background_rotation_quality_controls_v1/63d8031dfd3b4076abe1f3362034aeba'
 cfg=core.configuration();freeze=json.loads((root/'freeze.json').read_bytes())
 assert freeze==dict(generation=cfg,quality=adapter.configuration())
 names=['positive_symbol','negative_text','negative_geometry','negative_opacity','negative_order']
 cases=[json.loads((root/name/'case/summary.json').read_bytes())for name in names]
 for index,value in enumerate(cases):
  assert value['control_contract_passed']and value['canonical_unchanged']and value['normal_conversion_calls']==0
  checker.check_control_case(value['control'],'positive'if index==0 else'negative',cfg)
 evidence=R/'conversion/source_background_rotation_quality_review_v3/99ddf3f373de42cbb0ce81a55724e102/summary.json'
 current=json.loads(evidence.read_bytes());assert current['quality_ok']and current['original_candidate_unchanged']and current['canonical_unchanged']
 candidate=Path(current['candidate_file']);record=json.loads(candidate.read_bytes());qa=Path(current['quality_report'])
 direct=dict(id=current['id'],name='positive_current_background_rotation',source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],candidate=asset(candidate),qa=asset(qa),native_render=asset(qa.parent/'native_render.json'),fresh_png=asset(qa.parent/'fresh.png'),code_and_image_rehashed=True,actual_rerendered_pixels_changed=False,normal_conversion_calls=0,already_completed_full8_reused_without_reexecution=True)
 checker.check_control_case(direct,'positive',cfg)
 target=R/'release/compiler_iterations/controls/svg_background_rotation_20261102_v1';manifest=target/'qualified.jsonl'
 put(manifest,b''.join((json.dumps(row,sort_keys=True)+'\n').encode()for row in [cases[0]['qualified_manifest'],current['qualified_manifest']]))
 catalog=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_background_rotation_20261102_v9.json'
 events=history.collect(cfg,root=R,catalog=str(catalog.relative_to(R)));history.validate(events,cfg,root=R)
 assert len(events)==2
 methods=[Path(__file__),S/'svg_background_interleaving_quality_contract_v2.py',S/'svg_background_rotation_quality_control_v1.py',S/'svg_rotated_source_visual_scope_v1.py',S/'compiler_svg_explicit_coordinates_v7.py',S/'compiler_svg_explicit_coordinates_v7.js']
 proof=dict(schema='actual_source_background_interleaving_rotation_full8_controls_v1',frozen_frontend=cfg,source_core=history.core_identity(cfg),positive_cases=[cases[0]['control'],direct],negative_cases=[row['control']for row in cases[1:]],qualified_manifest=asset(manifest),producer=asset(Path(__file__)),method_pins={str(p):sha(p.read_bytes())for p in methods},source_core_manual_catalog=asset(catalog),current_core_normal_attempts_preserved=len(events),reused_completed_positive_without_reexecution=asset(evidence),new_normal_calls=0,new_QA_calls=0,model_calls=0,goal_complete=False)
 checker.check_controls(proof);put(target/'proof.json',raw(proof));print(json.dumps(dict(proof=asset(target/'proof.json'),source_core=history.core_identity(cfg),positive_cases=2,negative_cases=4,normal_calls=0,QA_calls=0)),flush=True)
if __name__=='__main__':main()
