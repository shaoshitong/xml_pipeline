"""Acceptance contract for independently replayed metadata-author native pairs."""
from pathlib import Path
import hashlib
REQUIRED={'canonical_claim','source','structure','resources','render','text_paint','fonts','visual','native_editing'}
def require(ok,reason):
 if not ok:raise ValueError(reason)
def full_quality(report,record):
 checks=report.get('checks',{});require(report.get('ok')is True and not report.get('failures')and REQUIRED<=set(checks),'incomplete_author_native_independent_full_quality')
 require(checks['canonical_claim'].get('conversion_allowed')is True and checks['canonical_claim'].get('canonical_fields_changed')is False,'author_native_canonical_claim_not_readonly_safe')
 for name in ('source','visual','native_editing'):require(checks[name].get('ok')is True,'author_native_failed_required_stage:'+name)
 source=checks['source'];require(source.get('profile')=='author_metadata_original_native_raw_template_per_text_node_physical_fonts_v2','author_native_wrong_source_contract')
 ev=source['evidence']
 for name in ('complete_source_coverage','normalized_original_and_font_only_XML_delta_independently_rederived','fresh_source_RGBA_equals_portable_RGBA','physical_faces_and_glyph_counts_preserved','all_original_markup_and_text_nodes_preserved','raw_source_templates_and_XML_properties_preserved','native_actual_placeholder_expansion_DOM_mapping_proved','author_metadata_Gold_complete_native_semantics_equal','actual_official_export_pristine_owned_RGBA_equal','complete_source_paint_within_author_export'):require(ev.get(name)is True,'author_native_incomplete_source_proof:'+name)
 require(ev['current_code_sha256']==record['code_sha256'],'author_native_source_not_current_code')
 fonts=checks['fonts'];require(all(fonts.get(k)is True for k in ('all_rendered_fonts_embedded','physical_sfnt_tables_verified','source_complete_text_node_PS_and_glyph_inventory_preserved','exact_source_RGBA_preserved'))and fonts.get('glyph_geometry_tolerance_px')==.03 and fonts.get('glyph_max_error_px',1)<=.03,'author_native_font_or_glyph_proof_incomplete')
 render=checks['render'];require(render.get('code_sha256')==record['code_sha256']and render.get('image_sha256')==record['image_sha256']and render.get('strict_outside_export_pixels')==0,'author_native_actual_render_not_bound')
 for name in ('actual_original_and_portable_RGBA_equal','actual_pristine_and_owned_RGBA_equal','source_only_expanded_inspection_center_RGBA_equal','complete_original_source_paint_fits_natural_export_frame'):require(render.get(name)is True,'author_native_complete_actual_paint_proof_missing:'+name)
 profile=ev['author_export_profile'];require(all(render['source_metadata_export'][k]==profile[k]for k in ('version','scale','border')),'author_native_export_not_exact_metadata_profile')
 edit=checks['native_editing'];require(edit.get('endpoint_moves')==2*checks['structure']['edges']and edit.get('model_and_all_live_states_restored')is True and edit.get('actual_native_layout_manager_kept_enabled')is True and edit.get('actual_author_runtime_version')==profile['version'],'author_native_actual_editing_incomplete')
 for name,digest in report.get('implementation_pins',{}).items():require(hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,'author_native_QA_implementation_changed:'+name)
 return True
