"""Deterministic guard against disconnected draft canvases, no source mutation."""
import collections,math,hashlib,json
from arxiv_author_native_assets_v1 import models
POLICY='native_framework_repeated_disconnected_subgraphs_and_extreme_axis_gap_v2'
def check(blob):
 _,pages=models(blob)
 if len(pages)!=1:return dict(ok=False,policy=POLICY,reasons=['not_one_complete_native_page'])
 model=pages[0];owner={c:p for p in model.iter() for c in p};cells=list(model.iter('mxCell'))
 def ident(c):return c.get('id') or owner[c].get('id')
 vertices={ident(c):c for c in cells if c.get('vertex')=='1'}
 if None in vertices:return dict(ok=False,policy=POLICY,reasons=['unbound_vertex_ID'])
 if len(vertices)!=sum(c.get('vertex')=='1' for c in cells):return dict(ok=False,policy=POLICY,reasons=['duplicate_native_vertex_ID'])
 parent={i:i for i in vertices}
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):parent[find(a)]=find(b)
 for i,c in vertices.items():
  g=c.find('mxGeometry');p=c.get('parent')
  if g is not None and g.get('relative')=='1' and p in vertices:union(i,p)
 connected=set()
 for c in cells:
  if c.get('edge')!='1':continue
  a,b=c.get('source'),c.get('target')
  if a in vertices and b in vertices and a!=b:union(a,b);connected.update((a,b))
 components=collections.Counter(find(i) for i in connected);dominance=max(components.values(),default=0)/max(1,len(connected));reasons=[]
 cache={}
 def box(i,seen=()):
  if i in cache:return cache[i]
  if i in seen or len(seen)>100:raise ValueError('cyclic_or_excessive_parent_chain')
  c=vertices[i];g=c.find('mxGeometry')
  if g is None:raise ValueError('vertex_geometry_missing')
  x,y,w,h=[float(g.get(k,'0')) for k in ('x','y','width','height')]
  if not all(map(math.isfinite,(x,y,w,h))) or min(w,h)<0:raise ValueError('invalid_vertex_box')
  p=c.get('parent')
  if p in vertices:
   px,py,pw,ph=box(p,seen+(i,))
   if g.get('relative')=='1':x*=pw;y*=ph
   x+=px;y+=py
  cache[i]=(x,y,w,h);return cache[i]
 children=collections.Counter(c.get('parent') for c in vertices.values());rects=[]
 try:
  for i,c in vertices.items():
   if children[i]>=2 or c.get('visible')=='0':continue
   x,y,w,h=box(i)
   if w>0 and h>0:rects.append((x,y,w,h))
 except ValueError as error:reasons.append(str(error))
 # A multi-panel or multi-branch graph is legitimate. Hold only an actual
 # repeated complete disconnected subgraph, with labels/styles/topology and
 # geometry identical after uniform translation, not mere disconnectedness.
 repeated=collections.Counter()
 try:
  for component,count in components.items():
   if count<8:continue
   ids=[i for i in vertices if find(i)==component];positions={i:box(i) for i in ids};ox=min(b[0] for b in positions.values());oy=min(b[1] for b in positions.values())
   def token(i):
    c=vertices[i];x,y,w,h=positions[i];value=c.get('value') or owner[c].get('label') or ''
    return [round(x-ox,4),round(y-oy,4),round(w,4),round(h,4),value,c.get('style','')]
   ordered=sorted(ids,key=token);index={i:n for n,i in enumerate(ordered)};links=[]
   for edge in cells:
    a,b=edge.get('source'),edge.get('target')
    if edge.get('edge')=='1' and a in index and b in index:
     geo=edge.find('mxGeometry')
     points=[] if geo is None else [(n.tag,tuple(sorted((k,str(round(float(v)-(ox if k=='x' else oy),4)) if n.tag=='mxPoint' and k in ('x','y') else v) for k,v in n.attrib.items()))) for n in geo.iter()]
     links.append([index[a],index[b],edge.get('value',''),edge.get('style',''),points])
   signature=json.dumps([[token(i) for i in ordered],sorted(links)],sort_keys=True)
   repeated[hashlib.sha256(signature.encode()).hexdigest()]+=1
  if max(repeated.values(),default=0)>=2:reasons.append('identical_disconnected_native_subgraphs_repeat')
 except (ValueError,TypeError):reasons.append('invalid_component_geometry')
 gaps=[]
 for axis in (0,1):
  intervals=sorted((r[axis],r[axis]+r[axis+2]) for r in rects)
  if not intervals:continue
  low=intervals[0][0];end=intervals[0][1];maximum=0
  for a,b in intervals[1:]:maximum=max(maximum,a-end);end=max(end,b)
  span=end-low;ratio=maximum/max(1,span);gaps.append(dict(axis=axis,max_empty_interval=maximum,span=span,ratio=ratio))
  if maximum>=1000 and ratio>=.35:reasons.append('extreme_empty_axis_interval')
 return dict(ok=not reasons,policy=POLICY,reasons=sorted(set(reasons)),connected_vertices=len(connected),component_sizes=sorted(components.values(),reverse=True),dominant_component_ratio=dominance,repeated_component_counts=sorted(repeated.values(),reverse=True),axis_gaps=gaps,source_modified=False)
