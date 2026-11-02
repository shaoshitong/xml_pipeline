"""Source-owned SVG paths and marker triangles to bound native editable edges.

Bindings use unique actual source outline/containment distances. Geometry is
never fitted to reference pixels. Every source open path must be represented;
ambiguous bindings remain explicit conversion failures.
"""
from __future__ import annotations
import copy,math,re,xml.etree.ElementTree as ET
from svg_convert_v2 import build as base_build,num,color,style as source_style,path_for
from svg_convert_v3 import unpack,pack
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
POLICY='generic_source_svg_unique_bindings_explicit_marker_triangles_v2'

def require(value,reason):
 if not value:raise ValueError(reason)

def _parts(obj):
 pen=RecordingPen();parse_path(path_for(obj),TransformPen(pen,tuple(obj['matrix'])));parts=[];points=[];closed=False;curve=False
 for op,values in pen.value:
  if op=='moveTo':
   if points:parts.append({'points':points,'closed':closed,'curve':curve})
   points=[tuple(values[0])];closed=False;curve=False
  elif op=='lineTo':points.append(tuple(values[0]))
  elif op in ('curveTo','qCurveTo'):curve=True;points.append(tuple(values[-1]))
  elif op=='closePath':closed=True
  elif op!='endPath':raise ValueError('unsupported_source_path_operation:'+op)
 if points:parts.append({'points':points,'closed':closed,'curve':curve})
 for part in parts:
  points=part['points']
  if len(points)>1 and math.dist(points[0],points[-1])<1e-8:points.pop()
 return parts

def _inside_box(inner,outer,pad=.05):
 return inner['x']>=outer['x']-pad and inner['y']>=outer['y']-pad and inner['x']+inner['w']<=outer['x']+outer['w']+pad and inner['y']+inner['h']<=outer['y']+outer['h']+pad

def _segment_distance(p,a,b):
 d=(b[0]-a[0],b[1]-a[1]);den=d[0]**2+d[1]**2;t=max(0,min(1,((p[0]-a[0])*d[0]+(p[1]-a[1])*d[1])/den)) if den else 0
 return math.dist(p,(a[0]+t*d[0],a[1]+t*d[1]))

def _bind(point,nodes):
 choices=[]
 from svg_native_triangle_marker_v1 import _outline,_inside_convex
 for key,obj in nodes.items():
  try:
   contour,error=_outline(obj)
   dist=0 if _inside_convex(point,contour) else min(_segment_distance(point,a,b) for a,b in zip(contour,contour[1:]+contour[:1]))
   choices.append((dist+error,key))
  except Exception:continue
 choices.sort()
 require(choices and choices[0][0]<=12,'source_endpoint_has_no_nearby_native_node_outline')
 require(len(choices)==1 or choices[1][0]-choices[0][0]>=2.5,'source_endpoint_has_ambiguous_native_node_outline')
 return choices[0][1],{'nearest_outline_distance_upper_bound_px':choices[0][0],'next_outline_distance_lower_bound_px':choices[1][0] if len(choices)>1 else None,'rule':'unique_source_convex_outline_within12px_and2.5px_margin'}

def _triangle(head,owner,side):
 parts=_parts(head);require(len(parts)==1 and parts[0]['closed'] and not parts[0]['curve'] and len(parts[0]['points'])==3,'source_marker_not_one_filled_triangle')
 st=head['style'];require(st['fill']!='none' and st['stroke']=='none' and all(abs(float(st.get(k,1))-1)<1e-8 for k in ('opacity','fillOpacity')),'source_triangle_paint_not_solid_fill')
 points=owner.get('sampledPoints');require(points and len(points)>=2,'source_marker_owner_tangent_missing')
 endpoint,near=(points[0],points[1]) if side=='start' else (points[-1],points[-2]);length=math.dist(endpoint,near);require(length>1e-8,'source_marker_owner_tangent_degenerate');axis=((endpoint[0]-near[0])/length,(endpoint[1]-near[1])/length)
 corners=parts[0]['points'];projection=lambda p:p[0]*axis[0]+p[1]*axis[1];tip=max(corners,key=projection);base=[p for p in corners if p!=tip];mid=((base[0][0]+base[1][0])/2,(base[0][1]+base[1][1])/2);depth=projection(tip)-projection(mid);width=math.dist(*base)
 require(depth>.5 and width>.5 and abs(projection(base[0])-projection(base[1]))<=.03 and abs((tip[0]-mid[0])*(-axis[1])+(tip[1]-mid[1])*axis[0])<=.03,'source_triangle_not_symmetric_about_owner_tangent')
 variants=[]
 for kind,ratio in [('block',1.),('blockThin',2/3)]:
  native_depth=(4*depth+ratio*width)/(4+ratio*ratio)
  expected=[tip,(tip[0]-axis[0]*native_depth-axis[1]*ratio*native_depth/2,tip[1]-axis[1]*native_depth+axis[0]*ratio*native_depth/2),(tip[0]-axis[0]*native_depth+axis[1]*ratio*native_depth/2,tip[1]-axis[1]*native_depth-axis[0]*ratio*native_depth/2)]
  error=max(max(min(math.dist(p,q) for q in corners) for p in expected),max(min(math.dist(p,q) for q in expected) for p in corners));variants.append((error,kind,native_depth))
 error,kind,native_depth=min(variants)
 # This is only a candidate bound. Independent actual source/native contour
 # pixels still enforce the unchanged 1px/0.8..1.25 gate after fresh rendering.
 require(error<=1,'source_triangle_outside_native_marker_geometric_candidate_bound')
 matrix=owner['matrix'];scale=math.sqrt(abs(matrix[0]*matrix[3]-matrix[1]*matrix[2]));stroke=owner['style']['strokeWidth']*scale;size=native_depth-stroke;require(size>.1,'source_triangle_too_short_for_native_marker')
 return {'kind':kind,'size':size,'stroke':stroke,'tip':tip,'axis':axis,'length':native_depth,'source_length':depth,'source_width':width,'maximum_source_vertex_error_px':error,'fill':color(st['fill']),'native_endpoint':[tip[0]+axis[0]*stroke*1.118,tip[1]+axis[1]*stroke*1.118]}

def _brace_annotation(obj,dom):
    """One open, mirrored curly brace beside source text; never a marker owner."""
    if obj.get('markerStart','none')!='none' or obj.get('markerEnd','none')!='none':return None
    parts=obj.get('sceneGeometry',{}).get('topology',{}).get('subpaths',[])
    if len(parts)!=1 or parts[0].get('closed'):return None
    ops=parts[0].get('operations',[])
    if sum(o['operation'] in ('curveTo','qCurveTo') for o in ops)<2:return None
    m=obj['matrix'];controls=[(m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]) for o in ops for p in o['points']]
    if len(controls)<6:return None
    start,end=controls[0],controls[-1];box=obj['bbox'];vertical=box['h']>=2*max(box['w'],1) and box['w']>=1
    if not vertical or abs(start[0]-end[0])>.03 or abs(abs(start[1]-end[1])-box['h'])>.03:return None
    cy=(start[1]+end[1])/2
    if not all(any(math.dist((p[0],2*cy-p[1]),q)<=.03 for q in controls) for p in controls):return None
    if not (all(p[0]>=start[0]-.03 for p in controls) or all(p[0]<=start[0]+.03 for p in controls)):return None
    nearby=[]
    for other in dom['objects']:
        if other['type']!='text':continue
        b=other['bbox'];center=(b['x']+b['w']/2,b['y']+b['h']/2)
        horizontal=max(box['x']-b['x']-b['w'],b['x']-box['x']-box['w'],0)
        if abs(center[1]-cy)<=max(b['h'],box['h']/3) and horizontal<=max(30,b['h']*2):nearby.append(other['id'])
    if not nearby:return None
    return {'id':obj['id'],'role':'source_symmetric_curly_brace_annotation','source_control_reflection_verified':True,'nearby_source_text':nearby}


def derive(dom,size):
 dom=copy.deepcopy(dom);objects={o['id']:o for o in dom['objects']};nodes={};contexts=dom.get('sceneMetadata',{}).get('markerContexts',{});markers=[]
 require(not dom.get('nodes'),'general_svg_path_requires_no_predeclared_graphviz_roles')
 for obj in dom['objects']:
  if obj['type']!='shape' or obj.get('markerOwner') or obj.get('sceneMarkerContexts'):continue
  parts=_parts(obj);b=obj['bbox']
  from auto_quality_svg_closed_scene_v1 import _basic_closed_geometry
  if _basic_closed_geometry(obj) and len(parts)==1 and parts[0]['closed'] and (obj['style']['fill']!='none' or obj['style']['stroke']!='none' and obj['style']['strokeWidth']>0) and b['w']>=8 and b['h']>=8 and b['w']*b['h']<size[0]*size[1]*.65:
   nodes[obj['id']]=obj
 require(nodes,'general_svg_has_no_filled_source_nodes')
 for key,obj in nodes.items():obj['node']='source_'+key
 dom['nodes']={'source_'+key:{'id':'source_'+key,'title':key,'bbox':obj['bbox']} for key,obj in nodes.items()}
 for obj in dom['objects']:
  if obj['type']!='text':continue
  candidates=[(node['bbox']['w']*node['bbox']['h'],key) for key,node in nodes.items() if _inside_box(obj['bbox'],node['bbox'])]
  candidates.sort()
  if candidates and (len(candidates)==1 or candidates[0][0]<candidates[1][0]-.01):obj['node']='source_'+candidates[0][1]
 pending={};heads=set()
 for context,ctx in contexts.items():
  require(ctx['side'] in ('start','end'),'source_marker_mid_unsupported')
  hs=[o for o in dom['objects'] if context in o.get('sceneMarkerContexts',[])];require(len(hs)==1,'source_marker_has_compound_or_missing_paint')
  owner=objects.get(ctx['owner']);require(owner is not None and not owner.get('sceneUseContexts'),'source_marker_owner_not_original_source_instance')
  require(not ctx.get('selectorRisks') and not set(ctx.get('risks',[]))-{'synthetic_clone_does_not_apply_marker_viewport_clip'},'source_marker_css_or_instance_mapping_unproved')
  require(ctx.get('refCoordinateInterpretationProven'),'source_marker_reference_coordinates_unproved')
  geo=_triangle(hs[0],owner,ctx['side'])
  from svg_native_triangle_marker_v1 import _inside_convex
  viewport=[tuple(p) for p in ctx.get('viewportScreenPolygon',[])];require(len(viewport)==4 and all(_inside_convex(p,viewport,.001) for p in _parts(hs[0])[0]['points']),'source_marker_paint_clipped_by_viewport')
  marker={'context':context,'owner':owner['id'],'head':hs[0]['id'],'side':ctx['side'],'geometry':geo};markers.append(marker);heads.add(hs[0]['id']);pending[(owner['id'],ctx['side'])]=geo
 bindings=[];annotations=[]
 for obj in dom['objects']:
  if obj['id'] in heads or obj['type']!='shape':continue
  parts=_parts(obj)
  annotation=_brace_annotation(obj,dom)
  if annotation:annotations.append(annotation);continue
  if obj['style']['fill']!='none' or not any(not p['closed'] for p in parts):continue
  require(len(parts)==1 and not parts[0]['closed'],'source_open_path_has_multiple_subpaths')
  points=obj.get('sampledPoints');require(points and len(points)>=2,'source_open_path_missing_screen_samples')
  a=pending.get((obj['id'],'start'),{}).get('tip',points[0]);b=pending.get((obj['id'],'end'),{}).get('tip',points[-1]);src,sa=_bind(a,nodes);dst,sb=_bind(b,nodes)
  obj['_source_original_tag']=obj['tag'];obj['d']=path_for(obj);obj['tag']='path'
  obj['edge']={'id':'source_edge_'+obj['id'],'title':src+'->'+dst};bindings.append({'owner':obj['id'],'source_node':src,'target_node':dst,'source_evidence':sa,'target_evidence':sb})
 for marker in markers:
  owner=objects[marker['owner']];require(owner.get('edge'),'source_marker_owner_not_bound_to_nodes');objects[marker['head']]['edge']=copy.deepcopy(owner['edge'])
 require(bindings,'general_svg_has_no_unique_bound_open_paths')
 return dom,{'policy':POLICY,'nodes':sorted(nodes),'bindings':bindings,'annotations':annotations,'markers':markers,'complete_explicit_source_markers':len(markers)==len(contexts)}

def translate_frame(xml,dx,dy):
 tree=ET.fromstring(xml)
 for cell in tree.iter('mxCell'):
  geo=cell.find('mxGeometry')
  if geo is None:continue
  if cell.get('vertex')=='1' and cell.get('parent')=='1' and geo.get('relative')!='1':
   geo.set('x',num(float(geo.get('x',0))+dx));geo.set('y',num(float(geo.get('y',0))+dy))
  if cell.get('edge')=='1':
   for point in geo.iter('mxPoint'):
    if point.get('as')=='offset':continue
    point.set('x',num(float(point.get('x',0))+dx));point.set('y',num(float(point.get('y',0))+dy))
 return ET.tostring(tree,encoding='unicode')

def build(dom,size):
 semantic,proof=derive(dom,size);xml,stats=base_build(semantic,*size);tree=ET.fromstring(xml);root=tree.find('.//mxGraphModel/root');cells={c.get('id'):c for c in tree.iter('mxCell')};mapping=[]
 for m in proof['markers']:
  geo=m['geometry'];edge=cells[m['owner']];st=unpack(edge.get('style'));terminal=cells[edge.get('source' if m['side']=='start' else 'target')];g=terminal.find('mxGeometry');x,y,w,h=[float(g.get(k,0)) for k in ('x','y','width','height')];prefix='exit' if m['side']=='start' else 'entry';point=geo['native_endpoint'];st.update({m['side']+'Arrow':geo['kind'],m['side']+'Size':num(geo['size']),m['side']+'Fill':'1',m['side']+'FillColor':geo['fill'],m['side']+'StrokeColor':'transparent',prefix+'X':num((point[0]-x)/w),prefix+'Y':num((point[1]-y)/h),prefix+'Perimeter':'0'});edge.set('style',pack(st));root.remove(cells[m['head']]);mapping.append({'source_arrow_object':m['head'],'native_edge':m['owner'],'side':m['side'],**geo})
 stats['native_graphviz_arrowheads']=mapping;stats['generic_svg_source_bindings']=proof;stats['converter_version']=POLICY
 return ET.tostring(tree,encoding='unicode'),stats
