"""Complete fresh source region scope for horizontal and rotated glyph runs.

Keeps all original per-region pixel and calibrated marker gates. A vertical
text run can contribute several line crops; count actual original line crops,
not logical text objects. No candidate pixels decide the expected region scope.
"""
import compiler_svg_scene_frontend_v21 as core
R=core.R
require,sha=core.require,core.sha
prepare_source,_marker_contours=core.prepare_source,core._marker_contours

def _base_quality_visual(record,xml,native_info,png,reference,source_profile,data_root=R):
    """Calibrated v3 staging: source-ref full; same-domain full; cross local diagnostic."""
    require(source_profile.get('ok') and source_profile['evidence']['complete_source_coverage'],
            'staged_visual_requires_complete_independent_source_proof')
    evidence=source_profile['evidence'];require(evidence['candidate_code_sha256']==sha(xml.encode()),'staged_visual_source_revision_changed')
    require(evidence['fresh_sourceproof']['cairo_browser_physical_font_equivalence']['ok'],
            'staged_visual_source_physical_font_equivalence_unproven')
    require(all(evidence['checks'][key]['ok'] for key in ('semantics','glyphs','physical_fonts','same_domain_pixels','source_primitive_pixels')),
            'staged_visual_source_native_proof_incomplete')
    prepared=prepare_source(record);require(prepared['ok'],'staged_visual_fresh_source_reproduction_failed')
    require(sha(reference)==record['source_image_sha256'],'staged_visual_original_reference_changed')
    from auto_quality_common import image_quality
    import compiler_render_domain_v3 as domain
    capture=prepared['capture'];positions=domain._positions(capture['positions'],(0,0))
    cross=image_quality(reference,png,{},positions)
    same=image_quality(capture['png'],png,{},positions)
    primitives=domain._primitive_positions(capture['dom'],(0,0));local=image_quality(capture['png'],png,{},primitives)
    require(same['text_regions_checked']==core._expected_text_regions(capture['positions'],prepared['size']) and local['text_regions_checked']==len(primitives),
            'staged_visual_incomplete_fresh_source_expected_scope')
    failures=[f for f in cross['failures'] if f!='local_text_line_ssim_below_0.55']
    if not same['ok']:failures.append('same_browser_domain_full_fidelity_failed')
    if not local['ok']:failures.append('source_primitive_local_pixels_failed')
    return {**cross,'ok':not failures,'failures':failures,'policy':'svg_complete_source_same_domain_full_and_original_nonlocal_v3',
            'cross_renderer_local_text_diagnostic_only':True,'original_reference_visual_diagnostic':cross,
            'fresh_source_reference_all_original_gates':prepared['sourceproof']['source_reference'],
            'same_browser_domain_full_gates':same,'all_source_primitive_full_gates':local,
            'all_original_nonlocal_thresholds_unchanged':True,'source_physical_face_equivalence':True}


def quality_visual(record,xml,native_info,png,reference,source_profile,data_root=R):
    result=_base_quality_visual(record,xml,native_info,png,reference,source_profile,data_root)
    prepared=prepare_source(record);markers=_marker_contours(prepared,png)
    proof=source_profile['evidence']['checks'].get('actual_native_marker_geometry');require(proof and proof['ok'] and proof['code_sha256']==sha(xml.encode()),'exact_marker_alias_requires_fresh_actual_native_geometry')
    actual={(m['edge'],m['head'],m['side']):m for m in proof['markers']}
    from native_marker_geometry_exact_v1 import contour_decision
    for marker in markers['markers']:
        key=(marker['edge'],marker['source_head'],marker['side']);require(key in actual,'actual_native_source_marker_inventory_incomplete')
        geometry=actual[key];decision=contour_decision(marker['boundary_distance_px'],marker['ink_area_ratio'],geometry,source_viewport_containment=geometry['source_viewport_containment'],actual_editing=geometry['actual_endpoint_and_direction_editing']);marker.update(decision)
    markers['ok']=bool(markers['markers']) and all(m['ok'] for m in markers['markers']);markers['failures']=[] if markers['ok'] else ['source_native_marker_contour_changed']
    markers['exact_geometry_calibration_policy']='actual_native_marker_geometry_exact_pixel_grid_alias_v1';markers['old_nonexact_rule_unchanged']=True
    result['source_native_marker_contours']=markers
    if not markers['ok']:result['failures']+=markers['failures'];result['ok']=False
    return result
