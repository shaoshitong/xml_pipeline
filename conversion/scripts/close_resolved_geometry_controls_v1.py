"""Close current full-eight controls, preserving and reusing the one completed normal."""
from pathlib import Path
import hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def asset(p):return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 root=Path(sys.argv[1]).resolve();assert root.is_relative_to(R/'conversion/svg_resolved_geometry_quality_controls_v1')
 import compiler_svg_general_guard_v18 as core
 import svg_resolved_geometry_quality_contract_v1 as checker
 from compiler_source_core_attempts_v3 import core_identity
 cases=[json.loads((root/name/'summary.json').read_bytes())for name in('positive','negative_resolved_geometry','negative_compound_missing')];cfg=core.configuration()
 for i,case in enumerate(cases):
  assert case['control_contract_passed']and case['canonical_unchanged']and case['normal_conversion_calls']==0
  checker.check_control_case(case['control'],'positive'if i==0 else'negative',cfg)
 launch=json.loads((root/'launch.json').read_bytes());summary=Path(launch['reused_full8_normal_summary']);current=json.loads(summary.read_bytes());assert current['quality_ok']and current['canonical_unchanged']and current['normal_frontend_calls']==1
 candidate=Path(current['candidate_file']);record=json.loads(candidate.read_bytes());qa=Path(current['quality_report'])
 direct=dict(id=current['id'],name='positive_actual_CSS_geometry_and_compound_paths',source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],candidate=asset(candidate),qa=asset(qa),native_render=asset(qa.parent/'native_render.json'),fresh_png=asset(R/record['image_file']),code_and_image_rehashed=True,actual_rerendered_pixels_changed=False,normal_conversion_calls=0,already_completed_full8_reused_without_reexecution=True)
 checker.check_control_case(direct,'positive',cfg)
 destination=R/'release/compiler_iterations/controls/svg_resolved_geometry_20261102_v1';destination.mkdir(parents=True,exist_ok=False);manifest=destination/'qualified.jsonl';manifest.write_text(''.join(json.dumps(row,sort_keys=True)+'\n'for row in[cases[0]['qualified_manifest'],current['qualified_manifest']]));manifest.chmod(0o444)
 methods=[Path(__file__),S/'svg_resolved_geometry_quality_control_v1.py',S/'svg_resolved_geometry_quality_contract_v1.py',S/'svg_resolved_geometry_v1.js']
 proof=dict(schema='actual_resolved_geometry_full8_controls_v1',frozen_frontend=cfg,source_core=core_identity(cfg),positive_cases=[cases[0]['control'],direct],negative_cases=[r['control']for r in cases[1:]],qualified_manifest=asset(manifest),producer=asset(Path(__file__)),method_pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in methods},positive_regressions=0,normal_conversion_calls=0,QA_calls=0,model_calls=0,historical_positive_revalidated_not_regenerated=True,scientific_value_qualification_not_implied=True)
 checker.check_controls(proof);p=destination/'proof.json';p.write_text(json.dumps(proof,sort_keys=True,indent=2)+'\n');p.chmod(0o444);print(json.dumps(dict(proof=asset(p),positive_cases=2,negative_cases=2,source_core=proof['source_core'],new_normal_calls=0,new_QA_calls=0)))
if __name__=='__main__':main()
