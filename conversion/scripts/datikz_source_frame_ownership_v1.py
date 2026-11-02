"""Prove a complete source-vector frame and exact boxed/text-only node owners.

No candidate emission, raster fitting, inferred connections, or source changes.
Text-only names require exact executed labels and their actual source glyph block
at the execution-proven center. Their descriptor is a nonpainting logical group.
"""
import collections,math
import priority_datikz_execution_binding_v5 as binding
from tikz_literal_connectivity import Unsupported,polyline,source_text_match
from datikz_source_node_glyph_prefix_v1 import collect

def frame(dom,graph,root_matrix):
 a,b,c,d,_,_=root_matrix
 if abs(b)>1e-8 or abs(c)>1e-8 or min(a,d)<=0:raise Unsupported('source_frame_requires_known_positive_PDF_units')
 sx=a*binding.TEX_PT_TO_PDF_BP;sy=-d*binding.TEX_PT_TO_PDF_BP;vectors=[]
 for obj in dom['objects']:
  if obj['type']!='shape'or obj['style']['fill']!='none'or obj['style']['stroke']=='none':continue
  # Closed node outlines cannot become open semantic shafts.
  if binding._node_surface(obj):continue
  try:points=polyline(obj)
  except Unsupported:continue
  if len(points)>=2 and math.dist(points[0],points[-1])>.1:vectors.append((obj,points))
 paths=[];seen=set()
 for edge in graph['edges']:
  key=edge['picture']+':'+edge['path']
  if key in seen:raise Unsupported('source_path_has_multiple_unlowered_semantic_edges')
  seen.add(key);points=binding._softpath_points(graph['executed_softpaths'][key]);paths.append((edge,[[sx*binding._pt(x),sy*binding._pt(y)]for x,y in points]))
 if len(paths)!=len(vectors):raise Unsupported('complete_source_open_vector_inventory_mismatch:'+str((len(paths),len(vectors))))
 anchors=[p for p in paths if not p[0]['start_arrow']and not p[0]['end_arrow']]or[p for p in paths if len(p[1])>=3]
 if not anchors:raise Unsupported('source_frame_has_no_unarrowed_endpoint_or_unchanged_interior_bend')
 first,points=anchors[0];index=0 if not first['start_arrow']and not first['end_arrow']else 1;offsets=[]
 for obj,actual in vectors:
  if len(actual)!=len(points):continue
  tx=actual[index][0]-points[index][0];ty=actual[index][1]-points[index][1]
  if binding._path_matches_execution(actual,[[x+tx,y+ty]for x,y in points],first)and not any(math.dist([tx,ty],p)<.01 for p in offsets):offsets.append([tx,ty])
 viable=[]
 for tx,ty in offsets:
  used=set();owned=[]
  for edge,points in paths:
   expected=[[x+tx,y+ty]for x,y in points];matches=[obj['id']for obj,p in vectors if binding._path_matches_execution(p,expected,edge)]
   if len(matches)!=1 or matches[0]in used:break
   used.add(matches[0]);owned.append(dict(picture=edge['picture'],path=edge['path'],source_PDF_object=matches[0]))
  else:
   if len(used)==len(vectors):viable.append((tx,ty,owned))
 if len(viable)!=1:raise Unsupported('source_vector_frame_translation_not_unique:'+str(len(viable)))
 tx,ty,owned=viable[0]
 return dict(matrix=[sx,0,0,sy,tx,ty],complete_source_vector_ownership=owned,source_open_vector_count=len(vectors),source_raster_or_candidate_used=False,scale_fixed_by_PGFpt_PDFbp_and_actual_SVG_root=True)

def ownership(dom,graph,root_matrix):
 proved=frame(dom,graph,root_matrix);sx,_,_,sy,tx,ty=proved['matrix'];objects=dom['objects'];shapes=[o for o in objects if o['type']=='shape'and binding._node_surface(o)];text_groups=collections.defaultdict(list)
 for o in objects:
  if o['type']=='text':text_groups[o['sourceId'].split('_')[0]].append(o)
 required={e[k]for e in graph['edges']for k in('source','target')if e[k]is not None};owners={};used=set()
 for node in graph['nodes']:
  if node['name']not in required:continue
  label=binding.executed_plain_text(node['expanded_label_tex']);cx=sx*binding._pt(node['center_pt'][0])+tx;cy=sy*binding._pt(node['center_pt'][1])+ty;options=[]
  for shape in shapes:
   box=shape['bbox']
   if min(box['w'],box['h'])<8 or math.dist([cx,cy],[box['x']+box['w']/2,box['y']+box['h']/2])>.05:continue
   texts,prefix=collect(shape,objects)
   if source_text_match(texts,label):options.append(dict(kind='painted_source_node',shape=shape['id'],glyphs=[t['id']for t in texts],bbox=box,prefix=prefix))
  if not options and node['shape']in('rectangle','circle','ellipse'):
   # Absence of a symmetric painted node at this exact execution center,
   # combined with a unique complete label block, proves a text-only terminal.
   if any(math.dist([cx,cy],[s['bbox']['x']+s['bbox']['w']/2,s['bbox']['y']+s['bbox']['h']/2])<=.05 for s in shapes):raise Unsupported('painted_source_node_at_center_has_unmatched_label:'+node['name'])
   for texts in text_groups.values():
    if not source_text_match(texts,label):continue
    x=min(t['bbox']['x']for t in texts);y=min(t['bbox']['y']for t in texts);w=max(t['bbox']['x']+t['bbox']['w']for t in texts)-x;h=max(t['bbox']['y']+t['bbox']['h']for t in texts)-y
    if x-.05<=cx<=x+w+.05 and y-.05<=cy<=y+h+.05:options.append(dict(kind='source_text_only_named_terminal',glyphs=[t['id']for t in texts],bbox=dict(x=x,y=y,w=w,h=h),new_visible_paint=False,exact_executed_label_matched=True))
  if len(options)!=1:raise Unsupported('source_node_owner_not_unique:'+node['name']+':'+str(len(options)))
  owner=options[0];keys=set(owner['glyphs'])|({owner['shape']}if owner.get('shape')else set())
  if keys&used:raise Unsupported('source_node_owner_claimed_twice')
  used|=keys;owners[node['name']]={**owner,'executed_center':[cx,cy]}
 return dict(frame=proved,nodes=owners,all_required_named_nodes_owned=len(owners)==len(required),source_paint_or_glyphs_changed=False,new_normal_calls=0,new_QA_calls=0)
