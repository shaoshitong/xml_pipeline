"""v3 plus conservatively recognized Graphviz vee polygons as attached native open markers."""
import copy,math,re,xml.etree.ElementTree as E
import svg_convert_v3 as core
from svg_convert_v3 import distance

def vee(obj,points,side):
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj.get('pointsAttr') or '')]
 if len(vals)%2:return None
 a,b,c,d,e,f=obj['matrix'];poly=[]
 for x,y in zip(vals[::2],vals[1::2]):
  p=(a*x+c*y+e,b*x+d*y+f)
  if not any(distance(p,q)<.01 for q in poly):poly.append(p)
 if len(poly) not in (5,8):return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);dx,dy=end[0]-near[0],end[1]-near[1];length=math.hypot(dx,dy)
 if length<.001:return None
 dx/=length;dy/=length;tip=max(poly,key=lambda p:p[0]*dx+p[1]*dy)
 sideval=lambda p:(p[0]-tip[0])*(-dy)+(p[1]-tip[1])*dx
 left=min(poly,key=sideval);right=max(poly,key=sideval);mid=((left[0]+right[0])/2,(left[1]+right[1])/2);ax,ay=tip[0]-mid[0],tip[1]-mid[1];alen=math.hypot(ax,ay);width=distance(left,right)
 if alen<.1 or distance(mid,end)>max(4,alen*.25) or (ax*dx+ay*dy)/alen<.97:return None
 ux,uy=ax/alen,ay/alen
 # Graphviz's eight-point filled vee, including its narrow central shaft.
 template=[(0,0),(-.45,1),(-.025,.318),(-.025,1),(0,1),(.025,1),(.025,.318),(.45,1)] if len(poly)==8 else [(0,0),(-.45,1),(0,.5),(0,1),(.45,1)]
 normalized=[(((p[0]-tip[0])*(-uy)+(p[1]-tip[1])*ux)/alen,((tip[0]-p[0])*ux+(tip[1]-p[1])*uy)/alen) for p in poly]
 if any(min(distance(p,q) for q in normalized)>.025 for p in template):return None
 return {'tip':tip,'axis':(ux,uy),'length':(alen+width)/2,'width':width,'arrow':'open','native_width_ratio':1,'source_width_ratio':width/alen,'source_type':'graphviz_vee_polygon','source_unique_points':len(poly),'source_length':alen,'contour_approximation':True}

triangle=core.triangle
def marker(obj,points,side):return triangle(obj,points,side) or vee(obj,points,side)
def build(dom,width,height):
 dom=copy.deepcopy(dom);names={n['title'] for n in dom['nodes'].values()};port_mappings=[]
 for obj in dom['objects']:
  edge=obj.get('edge')
  if not edge:continue
  parts=re.split(r'->|--',edge.get('title') or '')
  if len(parts)!=2:continue
  resolved=[]
  for name in parts:
   choices=[n for n in names if name.startswith(n+':')]
   resolved.append(name if name in names else choices[0] if len(choices)==1 else name)
  if resolved!=parts:
   port_mappings.append({'object':obj['id'],'source_title':edge['title'],'node_terminals':resolved});edge['title']='->'.join(resolved)
 # This module runs in independent worker processes; restore dependency after each build.
 previous=core.triangle;core.triangle=marker
 try:xml,stats=core.build(dom,width,height)
 finally:core.triangle=previous
 approximations=[a for a in stats['native_graphviz_arrowheads'] if a.get('contour_approximation')]
 if approximations:stats['issues'].append({'reason':'native_open_vee_contour_approximation_requires_visual_review','count':len(approximations)})
 stats['graphviz_port_mappings']=port_mappings
 stats['converter_version']='svg_native_v5_graphviz_vee_native_open_markers';return xml,stats
