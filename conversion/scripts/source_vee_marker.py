"""Recognize parameterized symmetric Graphviz vee contours, not a single notch template."""
import copy,math,re
import svg_convert_v3 as core
from svg_convert_v3 import triangle,distance
from svg_convert_v5 import vee as fixed_vee

def vee(obj,points,side):
 known=fixed_vee(obj,points,side)
 if known:return known
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj.get('pointsAttr') or '')]
 if len(vals)%2:return None
 a,b,c,d,e,f=obj['matrix'];poly=[]
 for x,y in zip(vals[::2],vals[1::2]):
  p=(a*x+c*y+e,b*x+d*y+f)
  if not any(distance(p,q)<.01 for q in poly):poly.append(p)
 if len(poly)!=8:return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);dx,dy=end[0]-near[0],end[1]-near[1];length=math.hypot(dx,dy)
 if length<.001:return None
 dx/=length;dy/=length;tip=max(poly,key=lambda p:p[0]*dx+p[1]*dy);sideval=lambda p:(p[0]-tip[0])*(-dy)+(p[1]-tip[1])*dx;left=min(poly,key=sideval);right=max(poly,key=sideval);mid=((left[0]+right[0])/2,(left[1]+right[1])/2);ax,ay=tip[0]-mid[0],tip[1]-mid[1];alen=math.hypot(ax,ay);width=distance(left,right)
 if alen<.1 or distance(mid,end)>max(4,alen*.25) or (ax*dx+ay*dy)/alen<.97:return None
 ux,uy=ax/alen,ay/alen;norm=[(((p[0]-tip[0])*(-uy)+(p[1]-tip[1])*ux)/alen,((tip[0]-p[0])*ux+(tip[1]-p[1])*uy)/alen) for p in poly];i=poly.index(tip);norm=norm[i:]+norm[:i]
 if norm[1][0]>0:norm=[(-x,y) for x,y in norm]
 half=width/(2*alen);shaft=sum(abs(norm[i][0]) for i in [2,3,5,6])/4;notch=(norm[2][1]+norm[6][1])/2
 if abs(half-.45)>.01 or not 0<shaft<half/3 or not 0<notch<1:return None
 template=[(0,0),(-half,1),(-shaft,notch),(-shaft,1),(0,1),(shaft,1),(shaft,notch),(half,1)];residual=max(distance(p,q) for p,q in zip(norm,template))
 if residual>.005:return None
 return {'tip':tip,'axis':(ux,uy),'length':(alen+width)/2,'width':width,'arrow':'open','native_width_ratio':1,'source_width_ratio':width/alen,'source_type':'symmetric_graphviz_vee_parameterized_polygon','source_unique_points':8,'source_length':alen,'shaft_half_width_ratio':shaft,'notch_depth_ratio':notch,'template_max_residual':residual,'contour_approximation':True}

def build(dom,width,height):
 previous=core.triangle;core.triangle=lambda o,p,s:triangle(o,p,s) or vee(o,p,s)
 try:xml,stats=core.build(copy.deepcopy(dom),width,height)
 finally:core.triangle=previous
 stats['converter_version']='source_parameterized_vee_native_markers';return xml,stats
