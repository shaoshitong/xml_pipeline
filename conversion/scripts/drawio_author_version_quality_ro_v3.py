"""Independent original-source/author-export/fonts/visual/editing full QA."""
from pathlib import Path
import hashlib,json,sqlite3,time
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='independent_author_metadata_native_raw_template_complete_source_export_fonts_and_layout_owner_editing_v3'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def verify(identifier,record_file,data_root,plugin_file,work,database=W/'jobs.sqlite'):
 import drawio_author_version_frontend_v3 as frontend
 import drawio_author_version_fonts_v4 as fonts
 from drawio_author_version_editing_v3 import structure_checks,audit as editing
 from native_source_font_profile_v4 import verify_assets,_models
 from auto_quality_common import resource_checks,image_quality,require_rendered_text
 from fixed_batch_case_v1 import checked
 from compiler_plantuml_engine_canonical_claim_v1 import require_available
 from compiler_typed_runtime_failure_v1 import diagnose
 started=time.monotonic();record_file=Path(record_file).resolve(strict=True);work=Path(work).resolve();require(Path(data_root).resolve()==R,'author_RO_requires_HKUST_root');require(Path(plugin_file).resolve()==Path(frontend.__file__).resolve(),'author_RO_wrong_frontend');require(work.is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve())and not work.exists(),'author_RO_evidence_not_new_owned_work');work.mkdir(parents=True)
 blob=record_file.read_bytes();record=json.loads(blob);cfg=frontend.configuration();report={'id':identifier,'version':VERSION,'input_record_sha256':sha(blob),'implementation_pins':cfg['pins'],'quality_policy':cfg['policy'],'checks':{},'failures':[],'ok':False,'accepted':False,'canonical_mutations':0,'model_calls':0}
 try:
  require(all(sha(Path(p).read_bytes())==h for p,h in cfg['pins'].items()),'infrastructure_author_RO_implementation_changed')
  with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True,timeout=30)as db:
   db.row_factory=sqlite3.Row;row=db.execute('select*from jobs where id=?',(identifier,)).fetchone();require(row is not None,'author_RO_original_missing');job=dict(row)
  report['checks']['canonical_claim']=require_available(job);seed,inputs=frontend.original(record,job,database);source=inputs['source']
  require(tuple(record.get(k)for k in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256','category','source'))==(identifier,identifier,'drawio',source['code_sha256'],source['image_sha256'],source['category'],source['source']),'author_RO_original_source_identity_changed')
  xml=checked(record['code_file'],record['code_sha256']).decode();proposed=checked(record['image_file'],record['image_sha256']);reference=checked(record['original_reference'],record['source_image_sha256']);checked(record['original_source_code'],record['source_code_sha256']);report['checks']['resources']=resource_checks(R,record,xml,reference)
  fresh=fonts.compile(inputs['normalized_author_XML'],inputs['source_profile'],work/'independent_original_source_font_binding');require(fresh['xml']==xml,'author_RO_candidate_not_independently_rederived_original_font_only_XML');require(fresh['png']==proposed,'author_RO_proposed_PNG_not_exact_fresh_official_author_export')
  files={};faces=verify_assets(R,record,_models(inputs['normalized_author_XML'])[1],_models(xml)[1],files);require(all(sha(Path(p).read_bytes())==h for p,h in files.items()),'author_RO_physical_font_asset_changed');proof=fresh['proof'];info=fresh['info'];no_op=proof.get('no_op')is True
  evidence={'complete_source_coverage':True,'current_code_sha256':record['code_sha256'],'source_pages':1,'normalized_original_and_font_only_XML_delta_independently_rederived':True,'fresh_source_RGBA_equals_portable_RGBA':no_op or proof.get('source_RGBA_equals_portable_RGBA')is True,'physical_faces_and_glyph_counts_preserved':no_op or proof.get('complete_physical_PS_and_glyph_inventory_preserved')is True,'all_original_markup_and_text_nodes_preserved':no_op or proof.get('original_source_markup_recovers_exactly')is True,'raw_source_templates_and_XML_properties_preserved':no_op or proof.get('raw_source_templates_and_XML_properties_preserved')is True,'native_actual_placeholder_expansion_DOM_mapping_proved':no_op or proof.get('native_actual_placeholder_expansion_DOM_mapping_proved')is True,'author_metadata_Gold_complete_native_semantics_equal':inputs['snapshot']['Gold_author_complete_cell_semantics']['ok'],'author_export_profile':inputs['source_profile'],'actual_official_export_pristine_owned_RGBA_equal':info['author_export_pristine_RGBA_equals_owned_RGBA'],'complete_source_paint_within_author_export':info['author_source_no_paint_outside_original_export_frame']and info['author_source_full_inspection_center_RGBA_exact'],'source_snapshot':inputs['snapshot'],'physical_fonts':faces,'glyph_max_error_px':proof.get('glyph_max_error_px',0.)}
  require(all(evidence[k]for k in ('fresh_source_RGBA_equals_portable_RGBA','physical_faces_and_glyph_counts_preserved','all_original_markup_and_text_nodes_preserved','raw_source_templates_and_XML_properties_preserved','native_actual_placeholder_expansion_DOM_mapping_proved','author_metadata_Gold_complete_native_semantics_equal','actual_official_export_pristine_owned_RGBA_equal','complete_source_paint_within_author_export')),'author_RO_complete_original_source_proof_failed')
  coverage={'supported':True,'ok':True,'profile':'author_metadata_original_native_raw_template_per_text_node_physical_fonts_v2','failures':[],'evidence':evidence,'accepted':False};report['checks']['source']=coverage;report['checks']['structure']=structure_checks(xml,record=record,source_profile=coverage)
  report['checks']['render']={'code_sha256':record['code_sha256'],'image_sha256':record['image_sha256'],'mode':'actual_unmodified_author_metadata_version_export','source_metadata_export':info['source_metadata_export'],'strict_outside_export_pixels':0,'actual_original_and_portable_RGBA_equal':True,'actual_pristine_and_owned_RGBA_equal':True,'source_only_expanded_inspection_center_RGBA_equal':True,'complete_original_source_paint_fits_natural_export_frame':True}
  report['checks']['text_paint']=require_rendered_text(xml,info)
  usage=[font for row in info['actual_platform_font_usage']for font in row.get('fonts',[])if font.get('glyphCount',0)];require(not info['actual_text_positions']or usage and all(font.get('isCustomFont')for font in usage),'author_RO_nonportable_actual_text_face')
  report['checks']['fonts']={'all_rendered_fonts_embedded':True,'actual_custom_font_glyphs':sum(f['glyphCount']for f in usage),'physical_sfnt_tables_verified':True,'source_complete_text_node_PS_and_glyph_inventory_preserved':True,'exact_source_RGBA_preserved':True,'glyph_geometry_tolerance_px':.03,'glyph_max_error_px':evidence['glyph_max_error_px']}
  visual=image_quality(reference,proposed,record,info['actual_text_positions']);report['checks']['visual']=visual;require(visual['ok'],'author_RO_original_reference_raster_anomaly:'+','.join(visual['failures']))
  moves=editing(xml,record=record,source_profile=coverage);require(moves['ok']and len(moves['moves'])==2*report['checks']['structure']['edges'],'author_RO_incomplete_actual_endpoint_editing');fonts.save(work/'actual_endpoint_editing.json',fonts.raw(moves));report['checks']['native_editing']={'ok':True,'endpoint_moves':len(moves['moves']),'model_and_all_live_states_restored':moves['model_and_all_live_states_restored'],'actual_author_runtime_version':inputs['source_profile']['version'],'actual_native_layout_manager_kept_enabled':moves['actual_layout_manager_kept_enabled'],'actual_layout_owner_moves':sum(bool(row.get('layout_owner_resolution'))for row in moves['moves']),'source_actual_constraints_ports_perimeters_and_free_endpoints_verified':True}
  require(record_file.read_bytes()==blob,'author_RO_candidate_metadata_changed_during_QA');require(all(sha(Path(p).read_bytes())==h for p,h in cfg['pins'].items()),'infrastructure_author_RO_implementation_changed')
  with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True,timeout=30)as db:
   db.row_factory=sqlite3.Row;require(dict(db.execute('select*from jobs where id=?',(identifier,)).fetchone())==job,'infrastructure_author_RO_original_job_changed')
  fonts.save(work/'fresh.png',fresh['png']);report['ok']=True
 except Exception as e:
  d=diagnose(e);report.update(infrastructure_failure=d['infrastructure_failure'],infrastructure_diagnosis=d);report['failures'].append({'type':type(e).__name__,'reason':str(e)[:6500]})
 report['seconds']=round(time.monotonic()-started,3);fonts.save(work/'report.json',fonts.raw(report));return report
