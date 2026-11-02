import copy,math,re,xml.etree.ElementTree as E
import svg_convert_v3 as core
from svg_convert_v3 import unpack,pack,distance
from svg_convert_v2 import color,num

def marker(obj,points,side):
 if not obj.get('mermaidMarker'):return None
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj['pointsAttr'])];a,b,c,d,e,f=obj['matrix'];poly=list(dict.fromkeys((a*x+c*y+e,b*x+d*y+f) for x,y in zip(vals[::2],vals[1::2])))
 if len(poly)!=3:return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);dx,dy=end[0]-near[0],end[1]-near[1];n=math.hypot(dx,dy)
 if n<.001:return None
 dx/=n;dy/=n;tip=max(poly,key=lambda p:p[0]*dx+p[1]*dy);other=[p for p in poly if p!=tip];mid=((other[0][0]+other[1][0])/2,(other[0][1]+other[1][1])/2);ax,ay=tip[0]-mid[0],tip[1]-mid[1];length=math.hypot(ax,ay);width=distance(*other)
 if length<.1 or distance(tip,end)>max(3,length*.4)+.02 or (ax*dx+ay*dy)/length<.97 or abs(width/length-1)>.08:return None
 return {'tip':tip,'axis':(ax/length,ay/length),'length':length,'width':width,'arrow':'block','source_type':'mermaid_svg_marker_triangle','source_fill':obj['sourceMarkerFill'],'source_stroke':obj['sourceMarkerStroke'],'contour_approximation':True}

def build(dom,w,h,metadata):
 dom=copy.deepcopy(dom);by={o['id']:o for o in dom['objects']};markers=[]
 for o in dom['objects']:
  if not o.get('markerOwner'):continue
  owner=by[o['markerOwner']]
  if not owner.get('edge'):continue
  d=o.get('d') or '';commands=re.findall('[a-zA-Z]',re.sub(r'[eE][-+]?\d+','',d))
  if o['tag']=='path' and commands in (['M','L','L','Z'],['M','L','L','z']):
   o.update(tag='polygon',pointsAttr=','.join(re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',d)),edge=owner['edge'],mermaidMarker=True,sourceMarkerFill=color(o['style']['fill']),sourceMarkerStroke=color(o['style']['stroke']));o['style']['fill']=owner['style']['stroke'];markers.append(o['id'])
 previous=core.triangle;core.triangle=lambda obj,points,side:marker(obj,points,side) if obj.get('mermaidMarker') else previous(obj,points,side)
 try:xml,stats=core.build(dom,w,h)
 finally:core.triangle=previous
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};converted=[]
 for m in stats['native_graphviz_arrowheads']:
  if m.get('source_type')!='mermaid_svg_marker_triangle':continue
  c=cells[m['native_edge']];s=unpack(c.get('style'));s[m['side']+'FillColor']=m['source_fill'];s[m['side']+'StrokeColor']=m['source_stroke'];c.set('style',pack(s));converted.append(m['source_arrow_object'])
 for g in metadata['groups']:cells['node_'+g['uid']].set('mermaidId','n:'+g['sourceId'])
 stats['mermaid_source_metadata']=metadata;stats['native_mermaid_markers']=converted;stats['issues'].append({'reason':'mermaid_v10_geometry_font_and_marker_fidelity_requires_review','marker_count':len(converted)})
 if set(markers)-set(converted):stats['issues'].append({'reason':'unconverted_mermaid_arrowheads','ids':sorted(set(markers)-set(converted))})
 stats['converter_version']='mermaid10_source_geometry_native_v1';return E.tostring(root,encoding='unicode'),stats,dom
