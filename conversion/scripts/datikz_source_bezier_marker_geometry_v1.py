"""Analytic bounds and an actual endpoint tip for one closed Bezier marker."""
import math
from fontTools.svgLib.path import parse_path
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from svg_convert_v2 import path_for
from tikz_literal_connectivity import Unsupported

def geometry(obj,endpoint,adjacent,side):
 dx,dy=endpoint[0]-adjacent[0],endpoint[1]-adjacent[1];length=math.hypot(dx,dy)
 if length<.1:raise Unsupported('marker_owner_has_no_actual_tangent')
 u=(dx/length,dy/length);v=(-u[1],u[0]);a,b,c,d,e,f=obj['matrix'];m=(u[0]*a+u[1]*b,v[0]*a+v[1]*b,u[0]*c+u[1]*d,v[0]*c+v[1]*d,u[0]*(e-endpoint[0])+u[1]*(f-endpoint[1]),v[0]*(e-endpoint[0])+v[1]*(f-endpoint[1]))
 bounds=BoundsPen(None);record=RecordingPen();parse_path(path_for(obj),TransformPen(bounds,m));parse_path(path_for(obj),TransformPen(record,m));ops=[op for op,p in record.value]
 if ops.count('moveTo')!=1 or ops[-1]!='closePath'or not set(ops)<={'moveTo','lineTo','curveTo','closePath'}or'curveTo'not in ops:raise Unsupported('marker_requires_one_closed_actual_cubic_contour')
 lo_x,lo_y,hi_x,hi_y=bounds.bounds;vertices=[points[-1]for op,points in record.value if op in('moveTo','lineTo','curveTo')];tips=[p for p in vertices if abs(p[0]-hi_x)<1e-5]
 if not tips or any(math.dist(p,tips[0])>1e-4 for p in tips)or abs(tips[0][1])>.05:raise Unsupported('source_marker_tip_not_unique_actual_endpoint_on_shaft_axis')
 if abs(lo_y+hi_y)>.1 or not(.1<hi_x-lo_x<=20 and .1<hi_y-lo_y<=20 and abs(hi_x)<=20):raise Unsupported('source_marker_bounds_or_axis_not_supported')
 p=tips[0];tip=[endpoint[0]+u[0]*p[0]+v[0]*p[1],endpoint[1]+u[1]*p[0]+v[1]*p[1]]
 return dict(tip=tip,length=hi_x-lo_x,width=hi_y-lo_y,actual_closed_cubic_source_contour=True,tip_is_actual_source_endpoint=True,analytic_extrema_used=True,source_curve_flattened=False,reference_or_candidate_pixels_used=False)
