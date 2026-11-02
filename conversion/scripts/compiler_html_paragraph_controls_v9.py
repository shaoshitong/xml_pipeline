"""Hash-bound whole-paragraph SOURCE controls and strict export/full-QA contract."""
import datetime,json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
OUTPUT=R/'release/compiler_iterations/controls/html_source_paragraph_controls_20261101_v9'
EXPECTED_NEGATIVES={'removed_original_character','wrong_portable_physical_face','extra_native_paint_outside_source_viewport'}
REQUIRED={'resources','structure','render','text_paint','fonts','source','visual','native_editing'}

def require(value,reason):
 if not value:raise ValueError(reason)

def full_quality(report,record):
 from compiler_types_program_v1 import checked,sha
 checks=report.get('checks',{});require(report.get('ok')is True and report.get('accepted')is True and not report.get('failures') and REQUIRED<=set(checks),'incomplete_HTML_paragraph_independent_full_quality')
 for key in ('source','visual','native_editing'):require(checks[key].get('ok')is True,'failed_HTML_paragraph_mandatory_stage:'+key)
 source=checks['source']['evidence'];require(all(source.get(k)is True for k in ('complete_source_coverage','all_original_source_Text_nodes_and_raw_Unicode_preserved','all_original_text_objects_partitioned_once','all_original_nontext_shapes_and_assets_preserved','no_reference_pixel_parameter_fitting')),'partial_HTML_paragraph_original_source_coverage')
 require(source['all_fresh_HTML_native_text_ink'].get('exact_same_domain_source_native_ink')is True,'nonexact_HTML_source_native_signed_ink')
 fonts=checks['fonts'];require(all(fonts.get(k)is True for k in ('all_rendered_fonts_embedded','complete_original_Text_node_physical_PS_and_glyph_inventory_preserved','before_after_actual_native_pixels_exact','all_original_Unicode_Text_nodes_and_markup_preserved','all_element_and_host_primary_physical_struts_bound_to_embedded_faces')),'incomplete_HTML_original_physical_fonts_and_struts')
 require(bool(fonts.get('physical_sfnt_tables_and_original_font_bytes_verified')) and fonts.get('actual_custom_font_glyphs',0)>0,'HTML_physical_sfnt_or_custom_glyphs_missing')
 require(bool(fonts.get('source_glyph_checks')) and all(row.get('maximum_grapheme_Range_error',999)<=.03 and row.get('direct_original_Text_PostScript_and_glyph_inventory_preserved')is True and row.get('original_source_border_box_exact')is True for row in fonts['source_glyph_checks']),'HTML_original_grapheme_geometry_or_physical_face_changed')
 require(bool(fonts.get('independent_original_SOURCE_native_portable_primary_M_element_checks')) and all(row.get('SOURCE_native_portable_face_and_glyph_exact')is True for row in fonts['independent_original_SOURCE_native_portable_primary_M_element_checks']),'HTML_primary_element_strut_unproved')
 render=checks['render'];require((render.get('code_sha256'),render.get('image_sha256'))==(record['code_sha256'],record['image_sha256']),'HTML_fresh_render_not_bound_to_actual_XML_and_PNG')
 require(render.get('export_mode')=='original_HTML_source_viewport_complete_native_inspection_v9' and render.get('paint_safety_frame')=='full_native_model_inspection_viewport','HTML_original_source_export_mode_not_proved')
 require(render.get('strict_outside_inspection_pixels')==0 and render.get('strict_outside_export_pixels')==0 and type(render.get('unclipped_native_outside_original_source_viewport_pixels'))is int and render['unclipped_native_outside_original_source_viewport_pixels']>=0,'HTML_native_inspection_or_export_incomplete')
 require(all(render.get(k)is True for k in ('complete_source_paint_retained','complete_native_model_paint_inspected','model_geometry_preserved_by_export','inspection_to_export_crop_RGBA_exact','actual_upstream_drawio')),'HTML_native_model_or_source_viewport_not_independently_proved')
 width,height=render['canvas'];require(render.get('model_frame')==render.get('inspection_frame')==dict(x=0,y=0,width=width+64,height=height+64) and render.get('export_frame')==dict(x=32,y=32,width=width,height=height) and render.get('original_source_viewport')==dict(x=0,y=0,width=width,height=height) and render.get('source_to_model_translation')==[32,32],'HTML_source_model_inspection_export_coordinate_contract_changed')
 declaration=render['original_source_viewport_declaration'];require(declaration==dict(source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],capture_viewport=[width,height]),'HTML_original_SOURCE_viewport_identity_changed')
 require(render.get('native_svg_kind')=='actual_official_graph_getSvg_diagnostic_preserving_native_model','HTML_real_native_SVG_evidence_missing')
 for key in ('inspection','export_proof','native_svg'):checked(render['clean_replayable_evidence'][key],clean=True)
 require(render['renderer_sha256']==sha((W/'rendering_html_source_paragraph_v9/remote_render.py').read_bytes()),'HTML_native_renderer_changed')
 editing=checks['native_editing'];require(all(editing.get(k)is True for k in ('every_native_vertex_actually_moved_and_restored','every_native_paragraph_actual_text_and_pixels_edited_and_restored','whole_encoded_model_restored','whole_actual_native_pixels_restored_exactly')),'HTML_actual_native_object_edit_or_restore_incomplete')
 require(editing['actual_native_object_moves']==record['vertices'] and editing['actual_native_text_edits']==record['text_objects'],'HTML_not_every_original_native_object_edited')
 for file,digest in report['implementation_pins'].items():require(sha(Path(file).read_bytes())==digest,'infrastructure_HTML_independent_quality_pin_changed:'+file)
 return True

def check_control_case(row,role,configuration):
 from compiler_types_program_v1 import checked,sha
 from compiler_typed_runtime_failure_v1 import diagnose
 candidate,body=checked(row['candidate']);record=json.loads(body);_,body=checked(row['qa']);qa=json.loads(body)
 require(qa['id']==row['id'] and qa['input_record_sha256']==row['candidate']['sha256'] and qa['implementation_pins']==configuration['pins'] and qa['quality_policy']==configuration['policy'],'HTML_control_actual_QA_or_core_not_bound')
 require((record['id'],record['source_code_sha256'],record['source_image_sha256'])==(row['id'],row['source_code_sha256'],row['source_image_sha256']),'HTML_control_original_identity_changed')
 for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:checked(dict(file=record[field],sha256=record[digest]),clean=True)
 for font in record['native_embedded_fonts']:
  checked(dict(file=font['file'],sha256=font['sha256']),clean=True);checked(dict(file=font['original_file'],sha256=font['original_sha256']),clean=True)
 meta=record['html_source_paragraph_v9']
 for prefix in ('inspection','export_proof','native_svg'):checked(dict(file=meta[prefix+'_file'],sha256=meta[prefix+'_sha256']),clean=True)
 _,pixels=checked(row['fresh_png'],clean=True);require(sha(pixels)==record['image_sha256'],'HTML_control_actual_PNG_changed')
 if role=='positive':full_quality(qa,record)
 else:
  normalized={**qa,'failures':[{**item,'exception_type':item['type']}for item in qa.get('failures',[])]}
  require(row['name']in EXPECTED_NEGATIVES and qa.get('ok')is False and not diagnose(normalized)['infrastructure_failure'] and any('paragraph_candidate_not_fresh_original_source_physical_font_and_declared_viewport_XML'in item['reason']for item in qa.get('failures',[])),'HTML_actual_semantic_negative_not_rejected')
  require(row['actual_complete_native_paint_changed']is True and row['code_and_image_rehashed']is True,'HTML_negative_not_actual_rerendered_paint')
  require(row['original_view_PNG_changed']is (row['name']!='extra_native_paint_outside_source_viewport'),'HTML_outside_source_viewport_negative_wrong_render_domain')
 return True

def check_controls(bundle):
 from compiler_types_program_v1 import checked
 import html_source_paragraph_frontend_v9 as frontend
 if bundle.get('definition'):
  _,payload=checked(bundle['definition']);require({k:v for k,v in bundle.items()if k!='definition'}==json.loads(payload),'HTML_control_definition_changed')
 require(bundle['schema']=='compiler_html_source_paragraph_controls_v9' and bundle['frozen_frontend']==frontend.configuration(),'HTML_control_frontend_changed')
 require(len(bundle['positive_cases'])==2 and len({row['id']for row in bundle['positive_cases']})==2 and {row['name']for row in bundle['negative_cases']}==EXPECTED_NEGATIVES and len(bundle['negative_cases'])==3,'HTML_finite_control_profile_incomplete')
 for role in ('positive','negative'):
  for row in bundle[role+'_cases']:check_control_case(row,role,bundle['frozen_frontend'])
 checked(bundle['producer']);checked(bundle['positive_receipt']);checked(bundle['negative_receipt']);checked(bundle['qualified_manifest']);return True

def run(positive_receipt,negative_receipt):
 from compiler_types_program_v1 import checked,asset,raw,immutable,sha
 from qualified_index_v4 import manifest_row,require_source
 import compiler_iteration_inventory_v1 as inventory
 import html_source_paragraph_frontend_v9 as frontend
 positive_receipt=Path(positive_receipt);negative_receipt=Path(negative_receipt);pos=json.loads(positive_receipt.read_bytes());neg=json.loads(negative_receipt.read_bytes());config=frontend.configuration();require(pos['configuration']==neg['implementation']==config,'HTML_actual_control_receipts_changed')
 positive=[];negative=[];manifests=[];hashes={}
 for role,entries in [('positive',pos['cases']),('negative',neg['controls'])]:
  for entry in entries:
   candidate=Path(entry['record_file']);record=json.loads(candidate.read_bytes());report=Path(entry['quality_report']);row=dict(id=record['id'],candidate=asset(candidate),qa=asset(report),code=asset(R/record['code_file']),fresh_png=asset(R/record['image_file']),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'])
   if role=='negative':row.update(name=entry['mutation'],actual_complete_native_paint_changed=entry['actual_complete_native_paint_changed'],original_view_PNG_changed=entry['original_view_PNG_changed'],code_and_image_rehashed=True,change=entry['change'])
   check_control_case(row,role,config);(positive if role=='positive'else negative).append(row)
   if role!='positive':continue
   qa=json.loads(report.read_bytes())
   with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:job=database.execute('select*from jobs where id=?',(record['id'],)).fetchone()
   source=json.loads(job[4]);require_source(record,source);require((report.parent/'fresh.png').read_bytes()==(R/record['image_file']).read_bytes(),'HTML_actual_fresh_QA_PNG_changed');accepted={**record,'quality_state':'accepted_original_HTML_whole_paragraph_SOURCE_exact_ink_v9','automatic_quality_policy':qa['quality_policy'],'automatic_quality_audit':str(report.relative_to(R)),'accepted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':None,'model_configuration':dict(external_model_calls=0,deterministic_compiler=True)};manifest=manifest_row(accepted,R)[0];inventory.check_manifest(R,record['id'],source,manifest,hashes);manifests.append(manifest)
   with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:require(database.execute('select*from jobs where id=?',(record['id'],)).fetchone()==job,'infrastructure_HTML_canonical_original_changed_during_publication')
 OUTPUT.mkdir(parents=True,exist_ok=False);immutable(OUTPUT/'qualified.jsonl',b''.join(raw(row)for row in sorted(manifests,key=lambda row:row['id'])));bundle=dict(schema='compiler_html_source_paragraph_controls_v9',frozen_frontend=config,producer=asset(Path(__file__)),positive_receipt=asset(positive_receipt),negative_receipt=asset(negative_receipt),positive_cases=positive,negative_cases=negative,actual_object_editing_reports=[row['qa']for row in positive],qualified_manifest=asset(OUTPUT/'qualified.jsonl'),normal_conversions_in_this_publication=0,new_unique_development_qualified=0,new_heldout_consumed=0,canonical_mutations=0,model_calls=0,goal_complete=False);check_controls(bundle);immutable(OUTPUT/'proof.json',raw(bundle));return dict(proof=asset(OUTPUT/'proof.json'),positive_cases=len(positive),actual_semantic_negatives=len(negative),checked_clean_asset_hashes=len(hashes),goal_complete=False)
if __name__=='__main__':
 import sys
 print(json.dumps(run(*sys.argv[1:]),ensure_ascii=False))
