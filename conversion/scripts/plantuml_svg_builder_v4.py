"""v2 geometry plus native Graphviz arrowheads and connector-owned labels."""
import collections,math,re,xml.etree.ElementTree as E
from svg_convert_v2 import build as build_v2,num,color

def unpack(style):return dict(x.split('=',1) for x in style.split(';') if '=' in x)
def pack(style):return ';'.join(k+'='+str(v) for k,v in style.items())+';'
def distance(p,q):return math.hypot(p[0]-q[0],p[1]-q[1])
def _triangle(obj,points,side):
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj['pointsAttr'] or '')]
 if len(vals)%2:return None
 a,b,c,d,e,f=obj['matrix'];poly=[]
 for x,y in zip(vals[::2],vals[1::2]):
  p=(a*x+c*y+e,b*x+d*y+f)
  if not any(distance(p,q)<.01 for q in poly):poly.append(p)
 if len(poly)!=3:return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);dx,dy=end[0]-near[0],end[1]-near[1];length=math.hypot(dx,dy)
 if length<.001:return None
 dx/=length;dy/=length;tip=max(poly,key=lambda p:p[0]*dx+p[1]*dy);base=[p for p in poly if p!=tip];mid=((base[0][0]+base[1][0])/2,(base[0][1]+base[1][1])/2);ax,ay=tip[0]-mid[0],tip[1]-mid[1];alen=math.hypot(ax,ay);width=distance(*base)
 if alen<.1 or distance(mid,end)>max(4,alen*.25) or (ax*dx+ay*dy)/alen<.97:return None
 ratio=width/alen;arrow='blockThin' if abs(ratio-2/3)<abs(ratio-1) else 'block';nominal=2/3 if arrow=='blockThin' else 1
 if abs(ratio-nominal)>.08:return None
 return {'tip':tip,'axis':(ax/alen,ay/alen),'length':alen,'width':width,'arrow':arrow,'native_width_ratio':nominal,'source_width_ratio':ratio}

def triangle(obj,points,side):
 original=_triangle(obj,points,side)
 if original is not None:return original
 from plantuml_marker_minimax_v1 import classic
 return classic(obj,points,side)

def build(dom,width,height):
 xml,stats=build_v2(dom,width,height);root=E.fromstring(xml);cells_root=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in cells_root.findall('mxCell')};paths=collections.defaultdict(list);arrows=collections.defaultdict(list);labels=collections.defaultdict(list)
 for obj in dom['objects']:
  edge=obj.get('edge')
  if not edge:continue
  if obj.get('tag')=='path' and obj.get('sampledPoints') and cells.get(obj['id']) is not None and cells[obj['id']].get('edge')=='1':paths[edge['id']].append(obj)
  elif obj.get('tag')=='polygon':arrows[edge['id']].append(obj)
  elif obj['type']=='text':labels[edge['id']].append(obj)
 conversions=[];removed=set();label_count=0
 for group,items in paths.items():
  if len(items)!=1:continue
  obj=items[0];edge=cells[obj['id']];style=unpack(edge.get('style',''));points=[list(p) for p in obj['sampledPoints']];used_sides=set();new_endpoints={}
  for arrow in arrows[group]:
   if color(arrow['style']['fill'])!=color(obj['style']['stroke']):continue
   options=[(side,triangle(arrow,points,side)) for side in ['start','end'] if side not in used_sides];options=[(side,t) for side,t in options if t]
   if len(options)!=1:continue
   side,t=options[0];sw=float(style.get('strokeWidth',1));size=t['length']-sw
   if size<=0:continue
   terminal=cells.get(edge.get('source' if side=='start' else 'target'));g=terminal.find('mxGeometry') if terminal is not None else None
   if g is None:continue
   x,y,w,h=[float(g.get(k,0)) for k in ['x','y','width','height']];tip=t['tip'];ux,uy=t['axis'];endpoint=(tip[0]+ux*sw*1.118,tip[1]+uy*sw*1.118);prefix='exit' if side=='start' else 'entry';style.update({side+'Arrow':t['arrow'],side+'Size':num(size),side+'Fill':'1',prefix+'X':num((endpoint[0]-x)/max(w,.01)),prefix+'Y':num((endpoint[1]-y)/max(h,.01)),prefix+'Perimeter':'0'});ac=cells.get(arrow['id'])
   if ac is not None:cells_root.remove(ac);removed.add(arrow['id']);used_sides.add(side);new_endpoints[side]=endpoint;conversions.append({'source_arrow_object':arrow['id'],'native_edge':obj['id'],'side':side,**t})
  edge.set('style',pack(style))
  if 'start' in new_endpoints:points[0]=new_endpoints['start']
  if 'end' in new_endpoints:points[-1]=new_endpoints['end']
  # Edge label children retain position while following their semantic connector.
  segments=[distance(a,b) for a,b in zip(points,points[1:])];total=sum(segments)
  if total<=0:continue
  for label in labels[group]:
   c=cells.get(label['id'])
   if c is None:continue
   g=c.find('mxGeometry');x,y,w,h=[float(g.get(k,0)) for k in ['x','y','width','height']];cx,cy=x+w/2,y+h/2;best=None;along=0
   for a,b,length in zip(points,points[1:],segments):
    if length<=0:continue
    t=max(0,min(1,((cx-a[0])*(b[0]-a[0])+(cy-a[1])*(b[1]-a[1]))/(length*length)));q=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]));candidate=(distance((cx,cy),q),along+t*length,q)
    if best is None or candidate[0]<best[0]:best=candidate
    along+=length
   if best is None:continue
   _,along,q=best;c.set('parent',edge.get('id'));g.set('relative','1');g.set('x',num(2*along/total-1));g.set('y','0');E.SubElement(g,'mxPoint',{'as':'offset','x':num(x-q[0]),'y':num(y-q[1])});label_count+=1
 if removed:
  remaining=[o for group in arrows.values() for o in group if o['id'] not in removed]
  if not remaining:stats['issues']=[i for i in stats['issues'] if i['reason']!='edge_arrowheads_separate_vector_objects_require_editing_review']
  stats['counts']['vector_shapes']-=len(removed)
 stats['native_graphviz_arrowheads']=conversions;stats['edge_child_labels']=label_count;stats['converter_version']='svg_native_v3_group_paint_order_and_native_arrows';stats['counts']['native_arrowheads']=len(conversions)
 return E.tostring(root,encoding='unicode'),stats
