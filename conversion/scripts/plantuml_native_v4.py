"""Conservative handwritten classic markers; pinned source geometry remains authoritative."""
import copy,math,re,xml.etree.ElementTree as E
from svg_convert_v3 import unpack,pack
from svg_convert_v2 import num
import plantuml_native as base
from svg_convert_v3 import distance

def point_segment(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];n=dx*dx+dy*dy
 t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/n)) if n else 0
 return distance(p,(a[0]+t*dx,a[1]+t*dy))
def rdp(points,epsilon):
 if len(points)<=2:return points
 scores=[point_segment(p,points[0],points[-1]) for p in points[1:-1]];m=max(scores)
 if m<=epsilon:return [points[0],points[-1]]
 i=scores.index(m)+1;return rdp(points[:i+1],epsilon)[:-1]+rdp(points[i:],epsilon)
def handwritten(obj,points,side):
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj.get('pointsAttr') or '')]
 if len(vals)%2:return None
 a,b,c,d,e,f=obj['matrix'];poly=[(a*x+c*y+e,b*x+d*y+f) for x,y in zip(vals[::2],vals[1::2])]
 if len(poly)<8 or len(poly)>200:return None
 if distance(poly[0],poly[-1])>.1:return None
 poly=poly[:-1];diameter=max(distance(p,q) for p in poly for q in poly)
 if not 5<=diameter<=35:return None
 i,j=max(((i,j) for i in range(len(poly)) for j in range(i+1,len(poly))),key=lambda ij:distance(poly[ij[0]],poly[ij[1]]))
 epsilon=min(.6,diameter*.06);simple=rdp(poly[i:j+1],epsilon)[:-1]+rdp(poly[j:]+poly[:i+1],epsilon)[:-1]
 if len(simple)!=4:return None
 candidate=dict(obj,matrix=[1,0,0,1,0,0],pointsAttr=','.join(str(x) for p in simple for x in p))
 found=base.classic(candidate,points,side)
 if found:
  found.update(source_type='plantuml_handwritten_classic_bounded_simplification',source_vertex_count=len(poly),simplified_vertex_count=4,max_simplification_error_px=max(min(point_segment(p,a,b) for a,b in zip(simple,simple[1:]+simple[:1])) for p in poly),simplification_tolerance_px=epsilon)
 return found

def build(dom,width,height,metadata):
 previous=base.core.triangle;base.core.triangle=lambda obj,points,side:previous(obj,points,side) or handwritten(obj,points,side)
 try:xml,stats=base.build(dom,width,height,metadata)
 finally:base.core.triangle=previous
 matches=[x for x in stats['native_graphviz_arrowheads'] if x.get('source_type')=='plantuml_handwritten_classic_bounded_simplification']
 stats['handwritten_native_markers']=matches
 if matches:stats['issues'].append({'reason':'handwritten_arrow_jitter_normalized_requires_visual_review','count':len(matches)})
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};shadows=[]
 for obj in dom['objects']:
  definition=obj.get('filterDefinition')
  if not definition or obj.get('type')!='shape' or obj.get('edge') or obj['id'] not in cells:continue
  info=shadow_filter(definition,obj['matrix'])
  if not info:continue
  cell=cells[obj['id']];style=unpack(cell.get('style',''));style.update({'shadow':'1','shadowColor':'#000000','shadowOpacity':num(info['opacity']*100),'shadowOffsetX':num(info['dx']),'shadowOffsetY':num(info['dy']),'shadowBlur':num(info['blur'])});cell.set('style',pack(style));shadows.append({'object':obj['id'],'filter_id':definition['id'],**info})
 stats['native_source_shadows']=shadows
 if shadows:stats['issues'].append({'reason':'native_css_drop_shadow_source_filter_mapping_requires_visual_review','count':len(shadows)})
 stats['converter_version']='plantuml_native_handwritten_markers_and_shadows_v4';return E.tostring(root,encoding='unicode'),stats

def shadow_filter(definition,matrix):
 try:
  f=definition['children']
  if [x['tag'] for x in f]!=['feGaussianBlur','feColorMatrix','feOffset','feBlend']:return None
  blur,col,offset,blend=[x['attrs'] for x in f]
  if blur.get('in','SourceGraphic')!='SourceGraphic' or col.get('in')!=blur.get('result') or offset.get('in')!=col.get('result') or blend.get('in')!='SourceGraphic' or blend.get('in2')!=offset.get('result') or blend.get('mode','normal')!='normal' or col.get('type')!='matrix':return None
  values=[float(v) for v in col['values'].split()]
  if len(values)!=20 or any(abs(v)>1e-9 for i,v in enumerate(values) if i!=18) or not 0<=values[18]<=1:return None
  std=[float(v) for v in blur['stdDeviation'].split()]
  if len(std) not in (1,2) or min(std)<0 or max(std)>20 or len(std)==2 and std[0]!=std[1]:return None
  a,b,c,d,e,f=matrix;s=math.hypot(a,b);t=math.hypot(c,d)
  if abs(s-t)>.0001 or abs(a*c+b*d)>.0001 or a*d-b*c<=0:return None
  dx,dy=float(offset.get('dx',0)),float(offset.get('dy',0))
  return {'dx':a*dx+c*dy,'dy':b*dx+d*dy,'blur':s*std[0],'opacity':values[18]}
 except (KeyError,ValueError,TypeError):return None
