"""Native Mermaid markers whose actual SVG reference lies inside the triangle.

Mermaid 11 places its reference at the marker midpoint. Geometry is derived
from the freshly expanded original marker and actual shaft tangent, without
changing AST, fill/stroke, relative positions, source paths, or reference pixels.
"""
import math,re
import mermaid_native_v1 as base
import mermaid_native_v2 as prior
from svg_convert_v3 import distance

def marker(obj,points,side):
 if not obj.get('mermaidMarker'):return None
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj['pointsAttr'])]
 a,b,c,d,e,f=obj['matrix'];poly=list(dict.fromkeys((a*x+c*y+e,b*x+d*y+f) for x,y in zip(vals[::2],vals[1::2])))
 if len(poly)!=3:return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);dx,dy=end[0]-near[0],end[1]-near[1];n=math.hypot(dx,dy)
 if n<.001:return None
 dx/=n;dy/=n;tip=max(poly,key=lambda p:p[0]*dx+p[1]*dy);other=[p for p in poly if p!=tip];mid=((other[0][0]+other[1][0])/2,(other[0][1]+other[1][1])/2);ax,ay=tip[0]-mid[0],tip[1]-mid[1];length=math.hypot(ax,ay);width=distance(*other)
 if length<.1 or (ax*dx+ay*dy)/length<.97 or abs(width/length-1)>.08:return None
 # The exact source SVG reference point must lie on the marker axis, between
 # the painted base and tip. This covers tip, midpoint, and base references;
 # an unrelated nearby polygon or off-axis/floating marker is rejected.
 along=(tip[0]-end[0])*dx+(tip[1]-end[1])*dy;normal=abs((tip[0]-end[0])*dy-(tip[1]-end[1])*dx)
 if normal>.05 or along<-.02 or along>length+.02:return None
 return {'tip':tip,'axis':(ax/length,ay/length),'length':length,'width':width,'arrow':'block','source_type':'mermaid_svg_marker_triangle','source_fill':obj['sourceMarkerFill'],'source_stroke':obj['sourceMarkerStroke'],'source_marker_reference_within_axis':True,'source_tip_reference_distance':along,'source_reference_perpendicular_error':normal,'contour_approximation':True}

def build(dom,w,h,metadata):
 original=base.marker;base.marker=marker
 try:xml,stats,processed=prior.build(dom,w,h,metadata)
 finally:base.marker=original
 stats['converter_version']='mermaid_source_geometry_midpoint_or_tip_native_markers_v3';return xml,stats,processed

check_backgrounds=prior.check_backgrounds
MOVE_SCRIPT=prior.MOVE_SCRIPT
