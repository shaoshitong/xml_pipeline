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
POLICY='generic_source_svg_source_group_owned_edge_layers_interleaving_background_rotated_text_stroke_outline_crossing_support_v15'

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

def _node_distance(point,obj):
 from svg_native_triangle_marker_v1 import _outline,_inside_convex
 matrix=obj['matrix'];a,b,c,d,e,f=matrix;det=a*d-b*c;sx=math.hypot(a,b);sy=math.hypot(c,d)
 if obj['tag'] in ('circle','ellipse') and abs(sx-sy)<=max(1,sx,sy)*1e-7 and abs(a*c+b*d)<=max(1,sx*sy)*1e-7 and abs(det)>1e-12:
  attrs=obj['attrs'];x=(d*(point[0]-e)-c*(point[1]-f))/det-attrs['cx'];y=(-b*(point[0]-e)+a*(point[1]-f))/det-attrs['cy'];rx=attrs['r'] if obj['tag']=='circle' else attrs['rx'];ry=attrs['r'] if obj['tag']=='circle' else attrs['ry'];require(min(rx,ry)>0,'degenerate_source_ellipse')
  if (x/rx)**2+(y/ry)**2<=1:return 0.,0.
  def equation(value):return (rx*x/(value+rx*rx))**2+(ry*y/(value+ry*ry))**2-1
  lo=0.;hi=max(rx*rx,ry*ry,1.)
  for _ in range(64):
   if equation(hi)<=0:break
   hi*=2
  else:raise ValueError('source_ellipse_distance_bracket_resource_bound')
  for _ in range(80):
   mid=(lo+hi)/2
   if equation(mid)>0:lo=mid
   else:hi=mid
  value=(lo+hi)/2;qx=rx*rx*x/(value+rx*rx);qy=ry*ry*y/(value+ry*ry)
  return math.hypot(x-qx,y-qy)*sx,1e-8*max(1,sx)
 try:contour,error=_outline(obj)
 except Exception:
  geometry=obj.get('sceneGeometry',{});contour=[tuple(p) for p in geometry.get('sampledPoints') or []];step=geometry.get('arcStepDeviceUpperBound');require(contour and step and step<=2+1e-6,'source_node_contour_has_no_bounded_native_binding_measurement');error=step/2
  if math.dist(contour[0],contour[-1])<1e-8:contour.pop()
 dist=0 if _inside_convex(point,contour) else min(_segment_distance(point,a,b) for a,b in zip(contour,contour[1:]+contour[:1]))
 return dist,error


def _bind(point,nodes):
 choices=[]
 for key,obj in nodes.items():
  try:
   distance,error=_node_distance(point,obj);choices.append((max(0,distance-error),distance+error,key))
  except Exception:continue
 choices.sort(key=lambda row:(row[1],row[2]))
 require(choices and choices[0][1]<=12,'source_endpoint_has_no_nearby_native_node_outline')
 lower,upper,key=choices[0];require(all(other_lower-upper>=2.5 for other_lower,_,_ in choices[1:]),'source_endpoint_has_ambiguous_native_node_outline')
 return key,{'nearest_outline_distance_upper_bound_px':upper,'next_outline_distance_lower_bound_px':min((row[0] for row in choices[1:]),default=None),'rule':'source_contour_interval_proof_within12px_and2.5px_lower_bound_margin'}


def _triangle(head,owner,side):
 parts=_parts(head);require(len(parts)==1 and parts[0]['closed'] and not parts[0]['curve'] and len(parts[0]['points'])==3,'source_marker_not_one_filled_triangle')
 st=head['style'];require(st['fill']!='none' and st['stroke']=='none' and all(abs(float(st.get(k,1))-1)<1e-8 for k in ('opacity','fillOpacity')),'source_triangle_paint_not_solid_fill')
 points=owner.get('sampledPoints');require(points and len(points)>=2,'source_marker_owner_tangent_missing')
 from svg_source_endpoint_direction_v1 import directions
 axis=tuple(directions(path_for(owner),owner['matrix'])[side]['outward_screen'])
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
 # SVG applies the default fill to an open straight line too, but an exactly
 # collinear contour encloses no painted area. Preserve its stroke as an edge;
 # filled noncollinear open contours still require a separate native mapping.
 for obj in dom['objects']:
  if obj['type']!='shape' or obj.get('markerOwner') or obj.get('sceneMarkerContexts') or obj['style']['fill']=='none':continue
  parts=_parts(obj)
  if len(parts)!=1 or parts[0]['closed'] or parts[0]['curve'] or len(parts[0]['points'])<2:continue
  points=parts[0]['points'];a=points[0];b=next((p for p in points[1:] if math.dist(p,a)>1e-9),None)
  if b and all(abs((b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]))<=1e-8 for q in points):
   obj['source_zero_area_fill']={'paint':obj['style']['fill'],'proof':'all_original_linear_path_points_collinear'};obj['style']['fill']='none'
 for obj in dom['objects']:
  if obj['type']!='shape' or obj.get('markerOwner') or obj.get('sceneMarkerContexts'):continue
  parts=_parts(obj);b=obj['bbox']
  from auto_quality_svg_closed_scene_v1 import _basic_closed_geometry
  if _basic_closed_geometry(obj) and len(parts)==1 and parts[0]['closed'] and (obj['style']['fill']!='none' or obj['style']['stroke']!='none' and obj['style']['strokeWidth']>0) and b['w']>=8 and b['h']>=8 and b['w']*b['h']<size[0]*size[1]*.65:
   nodes[obj['id']]=obj
 # Source SVG may contain free-coordinate relations without any filled nodes.
 for key,obj in nodes.items():obj['node']='source_'+key
 dom['nodes']={'source_'+key:{'id':'source_'+key,'title':key,'bbox':obj['bbox']} for key,obj in nodes.items()}
 for obj in dom['objects']:
  if obj['type']!='text':continue
  text_box=obj.get('originalBoundingBox',obj['bbox'])if obj.get('rotationHandled')else obj['bbox']
  candidates=[(node['bbox']['w']*node['bbox']['h'],key) for key,node in nodes.items() if _inside_box(text_box,node['bbox'])]
  candidates.sort()
  if candidates and (len(candidates)==1 or candidates[0][0]<candidates[1][0]-.01):obj['node']='source_'+candidates[0][1]
 pending={};heads=set()
 for context,ctx in contexts.items():
  require(ctx['side'] in ('start','end'),'source_marker_mid_unsupported')
  hs=[o for o in dom['objects'] if context in o.get('sceneMarkerContexts',[])];require(len(hs)==1,'source_marker_has_compound_or_missing_paint')
  owner=objects.get(ctx['owner']);from svg_source_use_instance_proof_v5 import require_owner
  instance_proof=require_owner(dom,owner)
  require(not ctx.get('selectorRisks') and not set(ctx.get('risks',[]))-{'synthetic_clone_does_not_apply_marker_viewport_clip'},'source_marker_css_or_instance_mapping_unproved')
  require(ctx.get('refCoordinateInterpretationProven'),'source_marker_reference_coordinates_unproved')
  geo=_triangle(hs[0],owner,ctx['side'])
  from svg_native_triangle_marker_v1 import _inside_convex
  viewport=[tuple(p) for p in ctx.get('viewportScreenPolygon',[])];require(len(viewport)==4 and all(_inside_convex(p,viewport,.001) for p in _parts(hs[0])[0]['points']),'source_marker_paint_clipped_by_viewport')
  marker={'source_instance_proof':instance_proof,'context':context,'owner':owner['id'],'head':hs[0]['id'],'side':ctx['side'],'geometry':geo};markers.append(marker);heads.add(hs[0]['id']);pending[(owner['id'],ctx['side'])]=geo
 bindings=[];annotations=[]
 for obj in dom['objects']:
  if obj['id'] in heads or obj['type']!='shape':continue
  parts=_parts(obj)
  annotation=_brace_annotation(obj,dom)
  if annotation:annotations.append(annotation);continue
  if obj['style']['fill']!='none' or not any(not p['closed'] for p in parts):continue
  require(len(parts)==1 and not parts[0]['closed'],'source_open_path_has_multiple_subpaths')
  points=obj.get('sampledPoints');require(points and len(points)>=2,'source_open_path_missing_screen_samples')
  a=pending.get((obj['id'],'start'),{}).get('tip',points[0]);b=pending.get((obj['id'],'end'),{}).get('tip',points[-1]);src,sa=_bind_optional(a,nodes);dst,sb=_bind_optional(b,nodes)
  obj['_source_original_tag']=obj['tag'];obj['d']=path_for(obj);obj['tag']='path'
  obj['edge']={'id':'source_edge_'+obj['id'],'title':(src or '__source_coordinate__')+'->'+(dst or '__target_coordinate__')};bindings.append({'owner':obj['id'],'source_node':src,'target_node':dst,'source_evidence':sa,'target_evidence':sb})
 for marker in markers:
  owner=objects[marker['owner']];require(owner.get('edge'),'source_marker_owner_not_bound_to_nodes');head=objects[marker['head']];head['edge']=copy.deepcopy(owner['edge']);corners=_parts(head)[0]['points'];head['_source_original_tag']=head['tag'];head['tag']='polygon';head['pointsAttr']=' '.join(str(x)+','+str(y) for x,y in corners);head['matrix']=[1,0,0,1,0,0]
 from svg_native_bezier_ir_v1 import compile_path
 for binding in bindings:
  obj=objects[binding['owner']];ir=compile_path(path_for(obj),obj['matrix'])
  if ir['mode']=='native_cubic_bezier':obj['native_curve_ir']=ir
 require(bindings,'general_svg_has_no_source_open_paths')
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

def _bind_optional(point,nodes):
 try:
  key,proof=_bind(point,nodes)
  return key,{'mode':'unique_source_outline_binding',**proof}
 except ValueError as error:
  reason=str(error)
  if reason not in ('source_endpoint_has_no_nearby_native_node_outline','source_endpoint_has_ambiguous_native_node_outline'):raise
  return None,{'mode':'explicit_source_coordinate','source_point':list(point),'binding_not_inferred_reason':reason}


def build(dom,size):
 semantic,proof=derive(dom,size)
 # The shared emitter is used only for exact per-object paint and groups.
 # Suppress its proximity inference; free coordinates are emitted explicitly
 # below, from the fresh original source path and no reference pixels.
 base=copy.deepcopy(semantic)
 for obj in base['objects']:
  if obj.get('edge') and obj['tag']=='path':
   obj['edge']={'id':obj['edge']['id'],'title':'__explicit_source__->__explicit_target__'}
   obj['markerStart']=obj['markerEnd']='none'
 xml,stats=base_build(base,*size);tree=ET.fromstring(xml);root=tree.find('.//mxGraphModel/root');cells={c.get('id'):c for c in tree.iter('mxCell')};objects={o['id']:o for o in semantic['objects']};mapping=[]
 for obj in semantic['objects']:
  if obj['type']=='text'and obj.get('rotationHandled'):
   angle=float(obj['nativeRotation']);require(math.isfinite(angle),'source_native_text_rotation_nonfinite');style=unpack(cells[obj['id']].get('style',''));style['rotation']=num(angle);cells[obj['id']].set('style',pack(style))
 for binding in proof['bindings']:
  obj=objects[binding['owner']];edge=cells[obj['id']];edge.attrib.pop('vertex',None);edge.set('edge','1');edge.set('parent','1');st=source_style(obj);st.update(fillColor='none',endArrow='none',startArrow='none',edgeStyle='none',rounded='0');points=obj.get('native_curve_ir',{}).get('points',obj['sampledPoints'])
  if obj.get('native_curve_ir'):st.update(obj['native_curve_ir']['style'])
  for child in list(edge):edge.remove(child)
  geo=ET.SubElement(edge,'mxGeometry',{'relative':'1','as':'geometry'});bends=ET.SubElement(geo,'Array',{'as':'points'})
  for x,y in points[1:-1]:ET.SubElement(bends,'mxPoint',{'x':num(x),'y':num(y)})
  for side,prefix,index,role in [('source','exit',0,'source_node'),('target','entry',-1,'target_node')]:
   terminal=binding[role];point=points[index]
   if terminal is None:ET.SubElement(geo,'mxPoint',{'as':side+'Point','x':num(point[0]),'y':num(point[1])})
   else:
    target='node_source_'+terminal;edge.set(side,target);g=cells[target].find('mxGeometry');x,y,w,h=[float(g.get(k,0)) for k in ('x','y','width','height')];st.update({prefix+'X':num((point[0]-x)/w),prefix+'Y':num((point[1]-y)/h),prefix+'Perimeter':'0'})
  edge.set('style',pack(st))
 for m in proof['markers']:
  geo=m['geometry'];edge=cells[m['owner']];st=unpack(edge.get('style'));prefix='exit' if m['side']=='start' else 'entry';point=geo['native_endpoint'];key='source' if m['side']=='start' else 'target';st.update({m['side']+'Arrow':geo['kind'],m['side']+'Size':num(geo['size']),m['side']+'Fill':'1',m['side']+'FillColor':geo['fill'],m['side']+'StrokeColor':'transparent'})
  if edge.get(key):
   terminal=cells[edge.get(key)];g=terminal.find('mxGeometry');x,y,w,h=[float(g.get(k,0)) for k in ('x','y','width','height')];st.update({prefix+'X':num((point[0]-x)/w),prefix+'Y':num((point[1]-y)/h),prefix+'Perimeter':'0'})
  else:
   p=edge.find("mxGeometry/mxPoint[@as='"+key+"Point']");p.set('x',num(point[0]));p.set('y',num(point[1]))
  edge.set('style',pack(st));root.remove(cells[m['head']]);mapping.append({'source_arrow_object':m['head'],'native_edge':m['owner'],'side':m['side'],**geo})
 stats['native_graphviz_arrowheads']=mapping;stats['generic_svg_source_bindings']=proof;stats['converter_version']=POLICY
 from svg_source_group_nesting_v1 import nest_source_groups
 xml,nesting=nest_source_groups(ET.tostring(tree,encoding='unicode'));stats['source_group_nesting']=nesting
 from svg_source_edge_layers_v17 import repair
 xml,layers=repair(dom,xml,size,semantic=semantic,binding=proof);stats['source_edge_layers']=layers
 return xml,stats
