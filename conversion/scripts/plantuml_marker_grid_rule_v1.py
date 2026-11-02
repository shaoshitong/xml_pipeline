"""Conditional marker-grid decision; source, graph and live editing remain required.

The physical boundary cap stays one pixel for both full closed visible paint
contours. Only the observed raster-grid distance may reach sqrt(2), under that
independent certificate and exact opaque paint/style equivalence. Area limits
stay 0.8..1.25. This function cannot publish or certify a graph conversion.
"""
import math
POLICY='certified_full_visible_marker_paint_one_pixel_with_grid_alias_v1'
PHYSICAL_LIMIT_PX=1.
GRID_LIMIT_PX=math.sqrt(2)
AREA_INTERVAL=(.8,1.25)

def decision(distance,ratio,continuous,*,opaque_paint_style_equivalent):
 finite=lambda v:type(v) in (int,float) and math.isfinite(v)
 certificate=bool(continuous and continuous.get('ok') is True and continuous.get('both_full_closed_paint_boundaries') is True and finite(continuous.get('upper_bound_px')) and 0<=continuous['upper_bound_px']<=PHYSICAL_LIMIT_PX+1e-10 and all(continuous.get(k,{}).get('ok') is True and continuous[k].get('whole_closed_perimeter') is True for k in ('source_to_native','native_to_source')))
 area=finite(ratio) and AREA_INTERVAL[0]<=ratio<=AREA_INTERVAL[1];old=finite(distance) and distance<=1+1e-8 and area;eligible=certificate and opaque_paint_style_equivalent is True;ok=eligible and finite(distance) and distance<=GRID_LIMIT_PX+1e-8 and area
 return {'ok':ok,'old_one_pixel_raster_rule_passed':old,'closed_physical_paint_certificate_passed':certificate,'grid_alias_eligible':eligible,'grid_alias_used':ok and not old,'policy':POLICY,'physical_closed_paint_limit_px':PHYSICAL_LIMIT_PX,'raster_grid_cap_px':GRID_LIMIT_PX,'unchanged_ink_area_interval':list(AREA_INTERVAL),'graph_source_fonts_canvas_and_actual_editing_still_required':True}
