"""Complete frozen analytic SOURCE/native-Bezier QA and real-control contract."""
import json
from pathlib import Path
from compiler_types_program_v1 import R,checked,sha
REQUIRED={'structure','resources','render','source','text_paint','fonts','visual','native_editing'}
def need(value,reason):
 if not value:raise ValueError(reason)
def qa_configuration(generation):
 import compiler_svg_general_quality_adapter_v9 as adapter
 from compiler_source_core_attempts_v3 import core_identity
 need(adapter.generation_configuration()==generation,'SVG_analytic_QA_adapter_changed_generation_CONFIGURATION')
 config=adapter.configuration()
 need(config.get('generation_source_core')==core_identity(generation),'SVG_analytic_QA_adapter_changed_generation_core_identity')
 return config

def check_generation_quality_binding(report,configuration):
 from compiler_source_core_attempts_v3 import core_identity
 need(report.get('generation_configuration')==configuration and report.get('generation_source_core')==core_identity(configuration),'SVG_analytic_RO8_not_bound_to_original_generation_core')
 qa=qa_configuration(configuration)
 need(report.get('profile_policy')==qa['policy']and all(report.get('implementation_pins',{}).get(path)==digest for path,digest in qa['pins'].items()),'SVG_analytic_quality_not_current_complete_SOURCE_core_and_QA_adapter')
 return True

def full_quality(report,record,configuration=None,native_info_ref=None):
 import compiler_svg_scene_quality_ro_v13 as quality
 checks=report.get('checks')or{};pins=report.get('implementation_pins')or{}
 need(report.get('version')==quality.VERSION and report.get('ok')is True and not report.get('failures')and REQUIRED<=set(checks),'SVG_analytic_incomplete_independent_8_stage_quality')
 need(report.get('id')==record['id']and report.get('canonical_mutations')==0 and report.get('model_calls')==0,'SVG_analytic_quality_original_identity_or_readonly_contract_changed')
 need(pins and report.get('quality_policy')==quality.VERSION+':'+quality.sha(quality.canonical(pins))[:20],'SVG_analytic_quality_policy_not_bound_to_exact_pins')
 if configuration is not None:
  check_generation_quality_binding(report,configuration)
 for key in ('source','visual','native_editing'):need(checks[key].get('ok')is True,'SVG_analytic_failed_mandatory_stage:'+key)
 source=checks['source']['evidence'];need(source.get('complete_source_coverage')is True and source.get('candidate_independent_source_scope')is True and source.get('original_reference_gates_still_required')is True and source.get('QA_source_session_owners_closed_before_next_observation')is True,'SVG_analytic_partial_SOURCE_coverage')
 need(source.get('candidate_code_sha256')==record['code_sha256'],'SVG_analytic_SOURCE_proof_candidate_revision_changed')
 primitive=source.get('checks')or{}
 for key in ('semantics','glyphs','physical_fonts','same_domain_pixels','source_primitive_pixels','actual_native_marker_geometry','complete_source_compositing_guard','actual_source_overlap_paint_order'):need(primitive.get(key,{}).get('ok')is True,'SVG_analytic_incomplete_SOURCE_native_gate:'+key)
 fresh=source.get('fresh_sourceproof')or{};need((fresh.get('source_code_sha256'),fresh.get('source_image_sha256'))==(record['source_code_sha256'],record['source_image_sha256']),'SVG_analytic_fresh_SOURCE_original_identity_changed')
 need(fresh.get('source_reference',{}).get('ok')is True and fresh.get('cairo_browser_physical_font_equivalence',{}).get('ok')is True and fresh.get('source_dom_extraction_preserved_all_pixels')is True and fresh.get('candidate_independent')is True and fresh.get('all_image_thresholds_unchanged')is True and fresh.get('parameter_search')is False and fresh.get('relayout')is False,'SVG_analytic_fresh_SOURCE_reproduction_or_physical_face_not_proved')
 need(checks['fonts'].get('all_rendered_fonts_embedded')is True,'SVG_analytic_unembedded_actual_physical_font')
 render=checks['render'];need((render.get('code_sha256'),render.get('image_sha256'))==(record['code_sha256'],record['image_sha256'])and render.get('strict_outside_page_pixels')==0,'SVG_analytic_fresh_render_not_bound_to_complete_candidate')
 if not render.get('strict_clip_canvas_proof'):
  need(native_info_ref is not None,'SVG_analytic_strict_native_pixel_artifact_missing')
  _,native_body=checked(native_info_ref);native_info=json.loads(native_body)
  from strict_native_canvas_evidence_v1 import validate as validate_native_canvas
  validate_native_canvas(native_info,*render['canvas'])
  manifest=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
  need(native_info.get('runtime_cache_manifest_sha256')==sha(manifest.read_bytes()),'SVG_analytic_strict_native_runtime_manifest_changed')
  need(native_info.get('viewer_bundle_sha256')==json.loads(manifest.read_bytes())['viewer_bundle_sha256'],'SVG_analytic_strict_native_viewer_changed')
 visual=checks['visual'];need(visual.get('all_original_nonlocal_thresholds_unchanged')is True and visual.get('fresh_source_reference_all_original_gates',{}).get('ok')is True and visual.get('same_browser_domain_full_gates',{}).get('ok')is True and visual.get('all_source_primitive_full_gates',{}).get('ok')is True and visual.get('source_native_marker_contours',{}).get('ok')is True,'SVG_analytic_original_reference_or_SOURCE_local_fidelity_not_proved')
 edits=checks['native_editing'];markers=edits.get('actual_marker_direction_edits')or{}
 need(markers.get('ok')is True and markers.get('all_actual_editing')is True and markers.get('code_sha256')==record['code_sha256']and bool(edits.get('all_endpoint_interventions')),'SVG_analytic_actual_endpoint_and_marker_editing_not_complete')
 for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_png','source_render_png_sha256')]:checked(dict(file=record[field],sha256=record[digest]),clean=True)
 need(record['source_render_png_sha256']==fresh.get('source_engine_png_sha256'),'SVG_analytic_clean_SOURCE_render_not_bound_to_fresh_reproduction')
 for font in record['native_embedded_fonts']:
  checked(dict(file=font['file'],sha256=font['sha256']),clean=True);checked(dict(file=font['original_file'],sha256=font['original_sha256']),clean=True)
 for path,digest in pins.items():need(sha(Path(path).read_bytes())==digest,'infrastructure_SVG_analytic_independent_QA_pin_changed:'+path)
 return True

def check_control_case(row,role,configuration=None):
 from compiler_typed_runtime_failure_v1 import diagnose
 _,body=checked(row['candidate']);record=json.loads(body);_,body=checked(row['qa']);report=json.loads(body)
 need(report.get('id')==row['id']and report.get('input_record_sha256')==row['candidate']['sha256'],'SVG_analytic_control_QA_not_bound_to_actual_candidate')
 import compiler_svg_scene_quality_ro_v13 as quality
 need(report.get('version')==quality.VERSION,'SVG_analytic_control_uses_wrong_RO_quality_version')
 if configuration is not None:check_generation_quality_binding(report,configuration)
 for path,digest in report.get('implementation_pins',{}).items():need(sha(Path(path).read_bytes())==digest,'infrastructure_SVG_analytic_control_QA_pin_changed:'+path)
 need((record['id'],record['source_code_sha256'],record['source_image_sha256'])==(row['id'],row['source_code_sha256'],row['source_image_sha256']),'SVG_analytic_control_original_identity_changed')
 for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_png','source_render_png_sha256')]:checked(dict(file=record[field],sha256=record[digest]),clean=True)
 # Fresh QA artifacts are metadata/diagnostics under W; final payload stays clean.
 if row.get('fresh_png'):
  _,png=checked(row['fresh_png']);need(sha(png)==record['image_sha256'],'SVG_analytic_actual_fresh_PNG_not_candidate')
 if role=='positive':return full_quality(report,record,configuration,row.get('native_render'))
 need(role=='negative'and report.get('ok')is False and bool(report.get('failures')),'SVG_analytic_actual_negative_not_rejected')
 normalized={**report,'failures':[{**item,'exception_type':item.get('type')}for item in report['failures']]}
 need(not diagnose(normalized)['infrastructure_failure'],'SVG_analytic_negative_rejected_only_by_infrastructure')
 profile=report.get('checks',{}).get('source')or report.get('checks',{}).get('source_preliminary')or{}
 need(profile.get('ok')is False and bool(profile.get('failures')),'SVG_analytic_semantic_negative_not_rejected_by_fresh_SOURCE')
 need(row.get('code_and_image_rehashed')is True and row.get('actual_rerendered_pixels_changed')is True,'SVG_analytic_negative_not_actual_XML_PNG_intervention')
 return True

def check_controls(bundle):
 import compiler_svg_general_guard_v8 as contract
 if bundle.get('definition'):
  _,body=checked(bundle['definition']);need({k:v for k,v in bundle.items()if k!='definition'}==json.loads(body),'SVG_analytic_control_definition_changed')
 for path,digest in bundle['method_pins'].items():need(sha(Path(path).read_bytes())==digest,'SVG_control_closure_method_changed:'+path)
 need(bundle['frozen_frontend']==contract.configuration(),'SVG_analytic_control_SOURCE_configuration_changed')
 need(len(bundle['positive_cases'])>=2 and len({r['id']for r in bundle['positive_cases']})>=2 and len(bundle['negative_cases'])>=2 and len({r['name']for r in bundle['negative_cases']})>=2,'SVG_analytic_control_actual_profile_incomplete')
 for role in ('positive','negative'):
  for row in bundle[role+'_cases']:check_control_case(row,role,bundle['frozen_frontend'])
 checked(bundle['producer']);checked(bundle['qualified_manifest']);return True
