"""Prospective source syntax domain; no reference/native image scores are inspected."""
import ast,re
NONLINEAR={'LogNorm','PowerNorm','SymLogNorm','TwoSlopeNorm','CenteredNorm','BoundaryNorm','FuncNorm','AsinhNorm','NoNorm'}
UNSUPPORTED_CALLS={'pie','polar','set_rasterized','set_hatch','text_path','set_path_effects','streamplot','quiver','barbs','contour','contourf','tripcolor','tricontour','tricontourf'}
def domain(code,static_audit):
 reasons=list(static_audit['security_issues'])
 if reasons:return {'supported_source_syntax':False,'reasons':reasons,'pixel_scores_used':False}
 tree=ast.parse(code)
 for n in ast.walk(tree):
  if isinstance(n,ast.Constant) and isinstance(n.value,str) and re.search('[\u3400-\u9fff]',n.value):reasons.append('CJK_requires_separate_observed_source_font_and_glyph_closure')
  if isinstance(n,ast.Call):
   name=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else '<dynamic>'
   if name in NONLINEAR:reasons.append('nonlinear_norm_colorbar_requires_another_component_contract')
   if name in UNSUPPORTED_CALLS:reasons.append('unsupported_source_primitive_family:'+name)
   for k in n.keywords:
    if k.arg=='hatch' and not (isinstance(k.value,ast.Constant) and k.value.value in {'',None}):reasons.append('source_hatch_pattern_requires_another_paint_family')
    if k.arg=='projection' and not (isinstance(k.value,ast.Constant) and k.value.value in {'rectilinear',None}):reasons.append('nonrectilinear_source_axes_projection')
    if k.arg=='rasterized' and not (isinstance(k.value,ast.Constant) and k.value.value is False):reasons.append('explicit_rasterized_data_artist_not_supported_as_vector')
 return {'supported_source_syntax':not reasons,'reasons':sorted(set(reasons)),'pixel_scores_used':False,'source_norm_still_requires_actual_capture_v5_verification':True,'actual_font_asset_source_SVG_Agg_and_native_gates_still_required':True}
