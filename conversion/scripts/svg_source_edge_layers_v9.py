"""Source-owned edge nesting and overlap order, with exact world geometry."""
from collections import defaultdict
from decimal import Decimal
import heapq,math,xml.etree.ElementTree as ET

def _paint_box(obj):
 b=obj.get('originalBoundingBox',obj['bbox'])if obj.get('rotationHandled')else obj['bbox'];s=obj.get('style',{});m=obj.get('matrix',[1,0,0,1,0,0]);scale=math.sqrt(abs(m[0]*m[3]-m[1]*m[2]));pad=float(s.get('strokeWidth',0))*scale/2 if s.get('stroke')!='none'else 0
 return(b['x']-pad,b['y']-pad,b['x']+b['w']+pad,b['y']+b['h']+pad)
def _overlap(a,b):return min(a[2],b[2])>max(a[0],b[0])and min(a[3],b[3])>max(a[1],b[1])
def _ancestors(key,cells):
 result=[]
 while key is not None:
  if key in result:raise ValueError('source_layer_native_parent_cycle')
  result.append(key);key=cells[key].get('parent')
 return result

def world_edge_points(edge,cells,rectangles):
 from svg_convert_v3 import unpack
 st=unpack(edge.get('style',''));geo=edge.find('mxGeometry');parent=edge.get('parent');origin=rectangles[parent][:2]if parent in rectangles else(Decimal(0),Decimal(0));points=[]
 for side,prefix in [('source','exit'),('target','entry')]:
  terminal=edge.get(side)
  if terminal:
   x,y,w,h=rectangles[terminal];p=(x+Decimal(st[prefix+'X'])*w,y+Decimal(st[prefix+'Y'])*h)
  else:
   item=geo.find("mxPoint[@as='"+side+"Point']");assert item is not None
   p=tuple(Decimal(item.get(k,'0'))+origin[i]for i,k in enumerate(('x','y')))
  points.append(p)
 bends=[tuple(Decimal(item.get(k,'0'))+origin[i]for i,k in enumerate(('x','y')))for item in geo.findall("Array[@as='points']/mxPoint")]
 return[points[0],*bends,points[1]]

def repair(dom,xml,size,*,semantic,binding,_depth=0):
 if _depth>32:raise ValueError("source_interleaving_nesting_depth_bound")
 from svg_source_group_nesting_v1 import _world_rectangles,_style
 source_objects={o['id']:o for o in dom['objects']};heads={m['head']:m['owner']for m in binding['markers']}
 tree=ET.fromstring(xml);root=tree.find('.//mxGraphModel/root');ordered=list(root);cells={c.get('id'):c for c in ordered};before_rectangles=_world_rectangles(cells);edges={key:c for key,c in cells.items()if c.get('edge')=='1'};before_edges={key:world_edge_points(c,cells,before_rectangles)for key,c in edges.items()};before_attrs={key:dict(c.attrib)for key,c in cells.items()};before_nonedge={key:ET.tostring(c)for key,c in cells.items()if c.get('edge')!='1'}
 ancestors=dom['sceneMetadata']['ancestors'];groups={};source_order={o['id']:i for i,o in enumerate(dom['objects'])}
 for key,c in cells.items():
  if not key.startswith('node_source_')or _style(c).get('group')!='1':continue
  source=source_objects.get(key[len('node_source_'):]);lineage=source.get('sceneAncestry',[])if source else[]
  if not source or source.get('sceneMarkerContexts'):continue
  if source.get('sceneUseContexts'):
   from svg_source_use_instance_proof_v5 import require_owner
   require_owner(dom,source)
  witnesses=[ref for ref in lineage[:-1]if ancestors[ref]['tag']=='g']
  if witnesses:groups[key]=(witnesses[-1],before_rectangles[key])
  elif 'source_'+source['id']in semantic.get('nodes',{}) and source.get('style',{}).get('fill')!='none' and float(source.get('style',{}).get('opacity',1))==1 and float(source.get('style',{}).get('fillOpacity',1))==1 and all(float(ancestors[ref]['opacity'])==1 for ref in lineage):
   groups[key]=('source_background:'+source['id'],before_rectangles[key])
 primitive_changes=[]
 for key,c in cells.items():
  if c.get('vertex')!='1' or c.get('parent')!='1' or key not in source_objects:continue
  source=source_objects[key]
  if source.get('sceneMarkerContexts'):continue
  if source.get('sceneUseContexts'):
   from svg_source_use_instance_proof_v5 import require_owner
   require_owner(dom,source)
  bounds=_paint_box(source);candidates=[]
  for group,(witness,region)in groups.items():
   if witness.startswith('source_background:'):
    if source_order[witness.split(':',1)[1]]>=source_order[key]:continue
   elif witness not in source.get('sceneAncestry',[]):continue
   x,y,w,h=map(float,region)
   if bounds[0]>=x and bounds[1]>=y and bounds[2]<=x+w and bounds[3]<=y+h:candidates.append((w*h,group,witness))
  candidates.sort()
  if not candidates or len(candidates)>1 and candidates[0][0]==candidates[1][0]:continue
  _,parent,witness=candidates[0];geo=c.find('mxGeometry');origin=before_rectangles[parent][:2]
  if geo is None or geo.get('relative','0')!='0':continue
  c.set('parent',parent)
  for i,k in enumerate(('x','y')):geo.set(k,str(Decimal(geo.get(k,'0'))-origin[i]))
  primitive_changes.append(dict(cell=key,old_parent='1',new_parent=parent,source_group_witness=witness))
 changes=[]
 for key,c in edges.items():
  source=source_objects[key]
  if source.get('sceneMarkerContexts'):continue
  if source.get('sceneUseContexts'):
   from svg_source_use_instance_proof_v5 import require_owner
   require_owner(dom,source)
  paint=[source,*[source_objects[h]for h,owner in heads.items()if owner==key]];boxes=[_paint_box(o)for o in paint];candidates=[]
  for group,(witness,box)in groups.items():
   x,y,w,h=map(float,box)
   if witness.startswith('source_background:'):
    if source_order[witness.split(':',1)[1]]>=source_order[key]:continue
   elif witness not in source.get('sceneAncestry',[]):continue
   if not all(b[0]>=x and b[1]>=y and b[2]<=x+w and b[3]<=y+h for b in boxes):continue
   if any(group not in _ancestors(c.get(side),cells)for side in('source','target')if c.get(side)):continue
   candidates.append((w*h,group,witness))
  candidates.sort()
  if not candidates or len(candidates)>1 and candidates[0][0]==candidates[1][0]:continue
  _,parent,witness=candidates[0];old=c.get('parent')
  if parent==old:continue
  old_origin=before_rectangles[old][:2]if old in before_rectangles else(Decimal(0),Decimal(0));new_origin=before_rectangles[parent][:2];geo=c.find('mxGeometry')
  # Label offsets are vectors, not parent coordinates. Do not translate them.
  for item in geo.iter('mxPoint'):
   if item.get('as')=='offset':continue
   for i,k in enumerate(('x','y')):item.set(k,str(Decimal(item.get(k,'0'))+old_origin[i]-new_origin[i]))
  c.set('parent',parent);changes.append(dict(edge=key,old_parent=old,new_parent=parent,source_group_witness=witness))
 children=defaultdict(list)
 for c in ordered:
  if c.get('parent')is not None:children[c.get('parent')].append(c.get('id'))
 constraints=defaultdict(set);paint_pairs=0
 painted=[(obj,heads.get(obj['id'],obj['id']))for obj in semantic['objects']]
 for i,(a,ka)in enumerate(painted):
  for b,kb in painted[i+1:]:
   if ka==kb or not _overlap(_paint_box(a),_paint_box(b)):continue
   pa=list(reversed(_ancestors(ka,cells)));pb=list(reversed(_ancestors(kb,cells)));j=0
   while j<min(len(pa),len(pb))and pa[j]==pb[j]:j+=1
   if j==0 or j==min(len(pa),len(pb)):raise ValueError('source_layer_painted_ancestor_mapping_unsupported')
   constraints[pa[j-1]].add((pa[j],pb[j]));paint_pairs+=1
 serial={c.get('id'):i for i,c in enumerate(ordered)};sorted_children={}
 for parent,items in children.items():
  successors=defaultdict(set);degree={key:0 for key in items}
  for a,b in constraints[parent]:
   if b not in successors[a]:successors[a].add(b);degree[b]+=1
  heap=[(serial[key],key)for key in items if degree[key]==0];heapq.heapify(heap);result=[]
  while heap:
   _,key=heapq.heappop(heap);result.append(key)
   for successor in successors[key]:
    degree[successor]-=1
    if degree[successor]==0:heapq.heappush(heap,(serial[successor],successor))
  if len(result)!=len(items):
   pairs=constraints[parent];promote=defaultdict(list)
   for group,key in pairs:
    if (key,group)not in pairs or group not in groups or key in groups or cells[key].get('parent')!=parent or cells[group].get('parent')!=parent:continue
    background=source_objects[group[len('node_source_'):]];bgstyle=background.get('style',{})
    if bgstyle.get('fill')=='none' or float(bgstyle.get('opacity',1))!=1 or float(bgstyle.get('fillOpacity',1))!=1:continue
    if any(float(ancestors[ref]['opacity'])!=1 for ref in background.get('sceneAncestry',[])):continue
    members=[o for o in semantic['objects']if heads.get(o['id'],o['id'])==key]
    if not members or any(source_order[o['id']]<=source_order[background['id']]for o in members):continue
    promote[key].append(group)
   applied=[]
   for key,candidates in promote.items():
    if len(set(candidates))!=1:continue
    group=candidates[0];cell=cells[key];geo=cell.find('mxGeometry')
    if geo is None or cell.get('vertex')=='1'and geo.get('relative','0')!='0':continue
    old_origin=before_rectangles[parent][:2]if parent in before_rectangles else(Decimal(0),Decimal(0));new_origin=before_rectangles[group][:2]
    if cell.get('edge')=='1':points=[p for p in geo.iter('mxPoint')if p.get('as')!='offset']
    else:points=[geo]
    for point in points:
     for i,k in enumerate(('x','y')):point.set(k,str(Decimal(point.get(k,'0'))+old_origin[i]-new_origin[i]))
    cell.set('parent',group);applied.append(dict(cell=key,old_parent=parent,new_parent=group,source_background=group[len('node_source_'):],source_paint_order_two_way_interleaving_witness=True))
   if not applied:raise ValueError('source_layer_interleaving_needs_compound_paint_representation')
   nested,proof=repair(dom,ET.tostring(tree,encoding='unicode'),size,semantic=semantic,binding=binding,_depth=_depth+1)
   finalcells={c.get('id'):c for c in ET.fromstring(nested).iter('mxCell')};finalrects=_world_rectangles(finalcells)
   assert before_rectangles==finalrects,'source_interleaving_nesting_vertex_world_geometry_changed'
   for key,edge in edges.items():
    assert before_edges[key]==world_edge_points(finalcells[key],finalcells,finalrects),'source_interleaving_nesting_edge_world_geometry_changed'
    assert all(finalcells[key].get(k)==v for k,v in before_attrs[key].items()if k!='parent'),'source_interleaving_nesting_edge_style_or_binding_changed'
   for key,body in before_nonedge.items():
    original=ET.fromstring(body);clone=ET.fromstring(ET.tostring(finalcells[key]));
    if original.get('parent')is None:clone.attrib.pop('parent',None)
    else:clone.set('parent',original.get('parent'))
    oldgeo=original.find('mxGeometry');newgeo=clone.find('mxGeometry')
    if oldgeo is not None and newgeo is not None:
     for k in('x','y'):
      if oldgeo.get(k)is None:newgeo.attrib.pop(k,None)
      else:newgeo.set(k,oldgeo.get(k))
    assert ET.tostring(clone)==body,'source_interleaving_nesting_nonedge_payload_changed'
   proof['source_interleaving_paint_promotions']=applied+proof.get('source_interleaving_paint_promotions',[])
   proof['primitive_parent_changes']=primitive_changes+proof.get('primitive_parent_changes',[])
   proof['edge_parent_changes']=changes+proof.get('edge_parent_changes',[])
   proof['nonedge_cells_unchanged']=False
   return nested,proof
  sorted_children[parent]=result
 result=[]
 def visit(key):
  result.append(cells[key])
  for child in sorted_children.get(key,[]):visit(child)
 visit('0');assert len(result)==len(ordered)
 root[:]=result;after_rectangles=_world_rectangles(cells);assert before_rectangles==after_rectangles,'source_layer_vertex_world_geometry_changed'
 for key,c in edges.items():
  assert before_edges[key]==world_edge_points(c,cells,after_rectangles),'source_layer_edge_world_geometry_changed'
  assert all(c.get(k)==v for k,v in before_attrs[key].items()if k!='parent'),'source_layer_edge_binding_or_style_changed'
 changed_primitives={r['cell']for r in primitive_changes}
 for key,body in before_nonedge.items():
  clone=ET.fromstring(ET.tostring(cells[key]));original=ET.fromstring(body)
  if key in changed_primitives:
   clone.set('parent',original.get('parent'))
   for k in('x','y'):
    value=original.find('mxGeometry').get(k)
    if value is None:clone.find('mxGeometry').attrib.pop(k,None)
    else:clone.find('mxGeometry').set(k,value)
  assert ET.tostring(clone)==body,'source_layer_nonedge_payload_changed'
 return ET.tostring(tree,encoding='unicode'),dict(policy='source_paint_order_witnessed_solid_background_interleaving_rotated_paint_bounds_v9',edge_parent_changes=changes,overlap_pairs_constrained=paint_pairs,vertex_world_geometry_exact=True,edge_world_geometry_and_binding_exact=True,nonedge_cells_unchanged=not primitive_changes,primitive_parent_changes=primitive_changes,nonedge_payloads_unchanged_except_proven_parent_coordinate_translation=True,source_only=True,reference_pixels_used=False)
