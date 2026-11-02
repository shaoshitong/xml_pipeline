"""Rebuild the sealed 2624-case calibration from actual recorded SVG geometry."""
import functools,hashlib,json,math
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');ROOT=R/'conversion/plantuml_closed_paint_calibration_v2'
PLAN=ROOT/'preregistered_plan.json'
REPORT=ROOT/'runs/7d73fe148aa14d328d98b23f0047de4c/report.json'
PLAN_SHA='5222a190f655b753883da0a33f9892021572fb1c5b0f70649086bb3b8433492f'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)

@functools.lru_cache(maxsize=1)
def _verified():
 from plantuml_marker_closed_paint_v1 import outline,certificate
 from plantuml_marker_grid_rule_v1 import POLICY,decision
 from compiler_plantuml_native_paint_quality_v1 import native_polygon
 from tikz_execution_binding_v2 import native_marker_polygon
 plan_bytes=PLAN.read_bytes();require(sha(plan_bytes)==PLAN_SHA,'preregistered_marker_plan_changed');plan=json.loads(plan_bytes);report_bytes=REPORT.read_bytes();report=json.loads(report_bytes)
 require(report['plan_sha256']==PLAN_SHA and report['policy']==POLICY==plan['policy'],'marker_calibration_policy_or_plan_changed');require(report['passed'] is True,'marker_calibration_not_passed');require(report['total_cases']==2624 and report['positive_translation_cases']==1728 and report['template_cases']==64 and report['negative_cases']==256 and report['unsupported_stroke_cases']==576,'marker_calibration_scope_incomplete')
 inputs_file=Path(report['inputs']['file']);inputs_bytes=inputs_file.read_bytes();require(sha(inputs_bytes)==report['inputs']['sha256'],'marker_calibration_inputs_changed');inputs=json.loads(inputs_bytes);rows=report['results'];require(len(rows)==len(inputs)==2624 and {r['index'] for r in rows}==set(range(2624)),'marker_calibration_ids_missing_or_repeated')
 expected_counts={'known_translation':1728,'plantuml_template':64,'negative':256,'unsupported_stroke':576};counts={k:0 for k in expected_counts};aliases=accepted=0;parity_max=0;negatives=0
 for row in rows:
  item=inputs[row['index']];require(item['index']==row['index'] and item['category']==row['category'],'marker_calibration_source_case_identity_changed');counts[row['category']]+=1;require(row['actual_native_factory_executed'] is True,'native_marker_factory_was_not_executed');ss=row['source_style'];ns=row['actual_native_style'];style=all(ss[k]==ns[k] for k in ('fill','stroke','strokeWidth','linejoin','miterlimit','opacity','fillOpacity','strokeOpacity'));require(style==row['source_native_style_equivalent'],'marker_calibration_style_claim_changed');source=row['source_DOM_polygon'];require(len(source)==len(item['source_polygon']) and max(math.dist(a,b) for a,b in zip(source,item['source_polygon']))<=1e-5,'marker_calibration_source_DOM_geometry_changed')
  native=native_polygon({'d':row['actual_native_path'],'transform':None},0);predicted,_=native_marker_polygon(item['kind'],item['depth']-item['stroke'],item['stroke'],item['native_point'],item['native_unit']);parity=max(max(min(math.dist(p,q) for q in predicted) for p in native),max(min(math.dist(p,q) for q in native) for p in predicted));parity_max=max(parity_max,parity);require(parity<=.03 and abs(parity-row['actual_factory_geometry_max_vertex_error_px'])<=1e-8,'marker_calibration_actual_factory_geometry_changed')
  closed=certificate(outline(source,ss['strokeWidth'],ss['linejoin'],ss['miterlimit']),outline(native,ns['strokeWidth'],ns['linejoin'],ns['miterlimit'])) if style else {'ok':False,'both_full_closed_paint_boundaries':False,'reason':'actual_paint_style_or_opaque_fill_topology_changed_not_certified'}
  require(closed['ok']==row['full_paint_certificate']['ok'],'marker_calibration_continuous_geometry_decision_changed')
  if style:require(abs(closed['upper_bound_px']-row['full_paint_certificate']['upper_bound_px'])<=1e-8 and abs(closed['lower_bound_px']-row['full_paint_certificate']['lower_bound_px'])<=1e-8,'marker_calibration_continuous_geometry_bounds_changed')
  actual=decision(row['raster_boundary_distance_px'],row['ink_area_ratio'],closed,opaque_paint_style_equivalent=style)
  require(all(row[k]==v for k,v in actual.items()),'marker_calibration_rebuilt_rule_decision_changed')
  if row['category'] in ('known_translation','plantuml_template'):require(closed['ok'],'known_positive_continuous_certificate_failed');aliases+=actual['grid_alias_used']
  if row['category']=='known_translation':accepted+=actual['ok']
  if row['category'] in ('negative','unsupported_stroke'):negatives+=actual['ok']
 require(counts==expected_counts and negatives==0 and accepted/1728>=.8 and aliases>=10,'marker_calibration_preregistered_pass_conditions_failed');require(aliases==report['actual_alias_acceptances'] and negatives==report['actual_negative_false_acceptances'],'marker_calibration_totals_changed')
 pins={**plan['pins'],str(PLAN):sha(plan_bytes),str(REPORT):sha(report_bytes),str(inputs_file):sha(inputs_bytes),str(Path(__file__).resolve()):sha(Path(__file__).read_bytes())}
 return {'pins':pins,'plan_sha256':PLAN_SHA,'policy':POLICY,'positive_geometry_certificates':1792,'negative_rejections':832,'actual_alias_acceptances':aliases,'positive_rule_acceptance_fraction':accepted/1728,'actual_factory_parity_max_error_px':parity_max,'actual_source_and_native_DOM_geometry_rebuilt':True}

def verified():
 result=_verified()
 # Cache only expensive pure proof reconstruction. Every caller still verifies
 # all exact evidence/implementation bytes before using the cached result.
 for name,digest in result['pins'].items():require(sha(Path(name).read_bytes())==digest,'infrastructure_marker_calibration_pin_changed:'+name)
 return result
