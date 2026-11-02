"""PlantUML source-SVG geometry and engine terminal identities to native drawio."""
import math,re,xml.etree.ElementTree as E
import svg_convert_v3 as core
from svg_convert_v3 import distance,unpack,pack
from svg_convert_v2 import num

def classic(obj,points,side):
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj.get('pointsAttr') or '')];a,b,c,d,e,f=obj['matrix'];poly=[]
 for x,y in zip(vals[::2],vals[1::2]):
  p=(a*x+c*y+e,b*x+d*y+f)
  if not any(distance(p,q)<.01 for q in poly):poly.append(p)
 if len(poly)!=4:return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);dx,dy=end[0]-near[0],end[1]-near[1];length=math.hypot(dx,dy)
 if length<.001:return None
 dx/=length;dy/=length;tip=max(poly,key=lambda p:p[0]*dx+p[1]*dy);sideval=lambda p:(p[0]-tip[0])*(-dy)+(p[1]-tip[1])*dx;left=min(poly,key=sideval);right=max(poly,key=sideval);mid=((left[0]+right[0])/2,(left[1]+right[1])/2);ax,ay=tip[0]-mid[0],tip[1]-mid[1];alen=math.hypot(ax,ay);width=distance(left,right)
 if alen<.1 or distance(end,tip)>max(10,alen) or (ax*dx+ay*dy)/alen<.97:return None
 norm=[(((p[0]-tip[0])*(-ay/alen)+(p[1]-tip[1])*(ax/alen))/alen,((tip[0]-p[0])*(ax/alen)+(tip[1]-p[1])*(ay/alen))/alen) for p in poly]
 template=[(0,0),(-4/9,1),(0,5/9),(4/9,1)]
 if any(min(distance(p,q) for q in norm)>.04 for p in template):return None
 # Minimax source geometry fit, derived before rendering. The source's
 # classic notch lies at 5/9 of the depth; mxMarker classic's lies at 3/4.
 # Balance base-depth error L-N against notch error 3N/4-5L/9.
 native_depth=(alen+5*alen/9)/(1+3/4)
 return {'tip':tip,'axis':(ax/alen,ay/alen),'length':native_depth,'width':width,'arrow':'classic','source_type':'plantuml_classic_four_point_minimax_native_depth','source_length':alen,'source_notch_depth':5*alen/9,'native_notch_depth':3*native_depth/4,'maximum_depth_fit_error':max(abs(alen-native_depth),abs(3*native_depth/4-5*alen/9)),'contour_approximation':True}

def build(dom,width,height,metadata):
 previous=core.triangle;core.triangle=lambda obj,points,side:previous(obj,points,side) or classic(obj,points,side)
 try:xml,stats=core.build(dom,width,height)
 finally:core.triangle=previous
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};groups={g['uid']:g for g in metadata['groups']}
 # Reparent native entity groups without changing their absolute source positions.
 for rel in metadata['parents']:
  cell=cells['node_'+rel['child']];g=cell.find('mxGeometry');parent=groups[rel['parent']]['bbox'];g.set('x',num(float(g.get('x'))-parent['x']));g.set('y',num(float(g.get('y'))-parent['y']));cell.set('parent','node_'+rel['parent'])
 stats['plantuml_source_metadata']=metadata;stats['issues']+=metadata['issues'];stats['issues'].append({'reason':'plantuml_engine_geometry_requires_original_visual_validation'})
 if metadata['parents']:stats['issues'].append({'reason':'plantuml_nested_membership_requires_source_review','count':len(metadata['parents'])})
 if any(x.get('contour_approximation') for x in stats['native_graphviz_arrowheads']):stats['issues'].append({'reason':'native_plantuml_classic_contour_approximation_requires_visual_review'})
 if len(metadata['links'])!=metadata['expectedLinkCount']:stats['issues'].append({'reason':'plantuml_unresolved_link_metadata_count'})
 stats['converter_version']='plantuml_2025_7_source_geometry_native_v1';return E.tostring(root,encoding='unicode'),stats
