"""Lower executed, nonpainting degree-two route coordinates without guessing.

Visible source nodes and branching junctions are never collapsed. Every point
comes from the original PGF softpath; this pass changes no source paint.
"""
import collections,copy,math
def normalize(graph,parse_points,parse_pt):
 out=copy.deepcopy(graph);nodes={n['name']:n for n in out['nodes']};degree=collections.Counter(e[k]for e in out['edges']for k in ('source','target')if e[k]is not None)
 def coordinate(name):
  n=nodes.get(name);return bool(n and n.get('shape')=='coordinate'and not n.get('expanded_label_tex','').strip()and degree[name]<=2)
 groups=collections.defaultdict(list)
 for e in out['edges']:groups[(e['picture'],e['path'])].append(e)
 edges=[];proofs=[]
 for key,group in groups.items():
  group.sort(key=lambda e:e['operation_number']);soft=out.get('executed_softpaths',{}).get(':'.join(key))
  if soft is None:edges.extend(group);continue
  try:points=parse_points(soft)
  except Exception:edges.extend(group);continue
  if len(group)>1:
   internal=[e['target']for e in group[:-1]]
   chain=all(a['target']==b['source']for a,b in zip(group,group[1:]))
   safe=chain and len(set(internal))==len(internal)and all(coordinate(n)for n in internal)
   safe=safe and not any(e.get('executed_label_nodes')for e in group)and not any(e['end_arrow']for e in group[:-1])and not any(e['start_arrow']for e in group[1:])
   if not safe:edges.extend(group);continue
   witnesses=[]
   for name in internal:
    center=[parse_pt(v)for v in nodes[name]['center_pt']];distance=min(math.dist(center,[parse_pt(v)for v in p])for p in points[1:-1]);witnesses.append(dict(name=name,center_pt=nodes[name]['center_pt'],distance_to_original_bend_TeXpt=distance,degree=degree[name],shape='coordinate',nonpainting=True))
   if any(w['distance_to_original_bend_TeXpt']>.03 for w in witnesses):edges.extend(group);continue
   edge=copy.deepcopy(group[0]);edge.update(target=group[-1]['target'],target_anchor=group[-1].get('target_anchor'),end_arrow=group[-1]['end_arrow'],operation='line',operation_number=group[-1]['operation_number'])
   proofs.append(dict(picture=key[0],path=key[1],kind='executed_nonpainting_degree_two_route_chain',original_edges=copy.deepcopy(group),coordinate_bends=witnesses,complete_softpath_points_pt=points,no_geometry_changed=True))
  else:edge=group[0]
  converted=[]
  for side,index in [('source',0),('target',-1)]:
   name=edge.get(side)
   if not coordinate(name):continue
   center=[parse_pt(v)for v in nodes[name]['center_pt']];point=[parse_pt(v)for v in points[index]]
   if math.dist(center,point)>.03:continue
   converted.append(dict(side=side,name=name,center_pt=nodes[name]['center_pt'],original_softpath_endpoint_pt=points[index],nonpainting=True,degree=degree[name]));edge[side]=None;edge[side+'_anchor']=None
  if converted:
   edge['terminal_kind']=('named'if edge.get('source')else'numeric')+'_'+('named'if edge.get('target')else'numeric')
   proofs.append(dict(picture=key[0],path=key[1],kind='explicit_executed_coordinate_endpoints',endpoints=converted,no_nearest_node_inference=True,no_geometry_changed=True))
  edges.append(edge)
 out.update(edges=edges,executed_coordinate_route_proofs=proofs,version='DaTikZ_executed_nonpainting_coordinate_routes_v1')
 return out
def controls():
 def pt(s):return float(s[:-2])
 def parse(s):return s
 def node(name,x,shape='coordinate'):return dict(name=name,shape=shape,expanded_label_tex='',center_pt=[str(x)+'pt','0pt'])
 def edge(a,b,i):return dict(picture='1',path='p',source=a,target=b,operation='line',operation_number=i,start_arrow=False,end_arrow=False,executed_label_nodes=[])
 g=dict(nodes=[node('a',0,'rectangle'),node('r',1),node('b',2,'rectangle')],edges=[edge('a','r',1),edge('r','b',2)],executed_softpaths={'1:p':[['0pt','0pt'],['1pt','0pt'],['2pt','0pt']]})
 positive=normalize(g,parse,pt);assert len(positive['edges'])==1
 visible=copy.deepcopy(g);visible['nodes'][1]['shape']='rectangle';assert len(normalize(visible,parse,pt)['edges'])==2
 branch=copy.deepcopy(g);other=edge('r','b',3);other['path']='q';branch['edges'].append(other);assert len(normalize(branch,parse,pt)['edges'])==3
 paint=copy.deepcopy(g);paint['edges'][0]['end_arrow']=True;assert len(normalize(paint,parse,pt)['edges'])==2
 changed=copy.deepcopy(g);changed['nodes'][1]['center_pt']=['1pt','1pt'];assert len(normalize(changed,parse,pt)['edges'])==2
 return dict(coordinate_chain_preserved_as_complete_polyline=True,visible_node_not_collapsed=True,branch_junction_not_collapsed=True,internal_arrow_not_dropped=True,unmatched_coordinate_not_invented=True)
