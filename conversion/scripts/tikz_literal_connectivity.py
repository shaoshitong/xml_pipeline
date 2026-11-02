"""Conservative source-aware matrix TikZ connectivity; unsupported grammar stays explicit."""
import collections,html,math,re,unicodedata,xml.etree.ElementTree as E
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from svg_convert_v2 import num,color,path_for
from svg_convert_v3 import unpack,pack,distance

class Unsupported(ValueError):pass

def balanced(s,start,left='{',right='}'):
 if start>=len(s) or s[start]!=left:raise Unsupported('missing balanced delimiter')
 level=0
 for i in range(start,len(s)):
  if i and s[i-1]=='\\':continue
  if s[i]==left:level+=1
  elif s[i]==right:
   level-=1
   if not level:return s[start+1:i],i+1
 raise Unsupported('unclosed delimiter')
def norm(s):return ''.join(unicodedata.normalize('NFKC',html.unescape(s)).split())
def parse_matrix(code):
 code=re.sub(r'(?<!\\)%[^\n]*','',code)
 if re.search(r'\\(?:foreach|def|newcommand|renewcommand|input|include)\b',code):raise Unsupported('macro/loop/external source needs TeX-aware graph extraction')
 matches=list(re.finditer(r'\\matrix\s*\(([\w-]+)\)\s*',code))
 if len(matches)!=1:raise Unsupported('requires exactly one explicit named matrix')
 m=matches[0];pos=m.end();opts=''
 if code[pos]=='[':opts,pos=balanced(code,pos,'[',']')
 while pos<len(code) and code[pos].isspace():pos+=1
 body,_=balanced(code,pos)
 if 'matrix of nodes' not in opts:raise Unsupported('matrix is not matrix of nodes')
 nodes={}
 for ri,row in enumerate(body.split('\\\\'),1):
  for ci,cell in enumerate(row.split('&'),1):
   value=re.sub(r'^\s*\|\[[^\]]*\]\|','',cell).strip()
   if not value:continue
   if re.search(r'[\\{}$]',value):raise Unsupported('nonliteral matrix text')
   nodes[f'{m[1]}-{ri}-{ci}']=value
 if not nodes or len(set(map(norm,nodes.values())))!=len(nodes):raise Unsupported('ambiguous matrix labels')
 edges=[];pat=re.compile(r'^\s*\(([-\w]+)(?:\.([\w ]+))?\)\s*(--|\|-|-\|)\s*(?:node\s*(\[[^\]]*\])?\s*\{([^{}]*)\}\s*)?\(([-\w]+)(?:\.([\w ]+))?\)\s*$',re.S)
 for match in re.finditer(r'\\draw\b([^;]*);',code):
  statement=match[1].strip();options=''
  if statement.startswith('['):options,end=balanced(statement,0,'[',']');statement=statement[end:]
  parsed=pat.fullmatch(statement)
  if not parsed:raise Unsupported('unsupported draw grammar')
  a,anchor1,route,_,label,b,anchor2=parsed.groups()
  if a not in nodes or b not in nodes:raise Unsupported('unknown node terminal')
  if options.strip() not in ('','->','<-','<->'):raise Unsupported('draw options need source-style resolution')
  if label and re.search(r'[\\$]',label):raise Unsupported('nonliteral edge label')
  edges.append({'source':a,'target':b,'source_anchor':anchor1,'target_anchor':anchor2,'label':label or '', 'route':route,'start_arrow':'<' in options,'end_arrow':'>' in options})
 if not edges:raise Unsupported('no explicit source connections')
 if re.search(r'\\(?:path|node|coordinate)\b',code) or re.search(r'every\s+path\s*/',code):raise Unsupported('additional paths/nodes/styles need full TeX extraction')
 return {'nodes':nodes,'edges':edges,'parser':'literal_named_matrix_explicit_draw_v1'}

def polyline(o):
 p=RecordingPen();parse_path(path_for(o),TransformPen(p,tuple(o['matrix'])));pts=[]
 for op,values in p.value:
  if op=='moveTo':
   if pts:raise Unsupported('multiple path subpaths')
   pts.append(values[0])
  elif op=='lineTo':pts.append(values[0])
  elif op in ['endPath','closePath']:pass
  else:raise Unsupported('curved connector requires exact bezier conversion')
 return pts

def boundary(point,obj):
 pts=obj.get('sampledPoints') or [];best=float('inf')
 for a,b in zip(pts,pts[1:]):
  dx,dy=b[0]-a[0],b[1]-a[1];length2=dx*dx+dy*dy;t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(length2 or 1)));best=min(best,distance(point,(a[0]+t*dx,a[1]+t*dy)))
 return best

def relative_label(c,edge,points):
 g=c.find('mxGeometry');x,y,w,h=[float(g.get(k,0)) for k in ['x','y','width','height']];cx,cy=x+w/2,y+h/2;lengths=[distance(a,b) for a,b in zip(points,points[1:])];total=sum(lengths);best=None;along=0
 for a,b,length in zip(points,points[1:],lengths):
  if length<=0:continue
  t=max(0,min(1,((cx-a[0])*(b[0]-a[0])+(cy-a[1])*(b[1]-a[1]))/(length*length)));q=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]));candidate=(distance((cx,cy),q),along+t*length,q)
  if best is None or candidate[0]<best[0]:best=candidate
  along+=length
 if best is None:raise Unsupported('zero length label connector')
 _,along,q=best;c.set('parent',edge.get('id'));g.set('relative','1');g.set('x',num(2*along/total-1));g.set('y','0');E.SubElement(g,'mxPoint',{'as':'offset','x':num(x-q[0]),'y':num(y-q[1])})

def source_text_match(texts,label):
 raw=''.join(t['text'] for t in texts)
 if norm(raw)==norm(label):return True
 pieces=[]
 for i,t in enumerate(texts):
  value=t['text']
  if i+1<len(texts) and value.endswith('-'):
   nxt=texts[i+1];a=t['bbox'];b=nxt['bbox']
   # Match TeX discretionary hyphenation only across a measured new line.
   # Original rendered glyphs (including the hyphen) remain untouched in XML.
   left=''.join(pieces)+value[:-1]
   if left and left[-1].isalpha() and nxt['text'] and nxt['text'][0].isalpha() and b['y']-a['y']>=.5*max(a['h'],b['h']):value=value[:-1]
  pieces.append(value)
 return norm(''.join(pieces))==norm(label)

def bind(xml,dom,code):
 report={'version':'tikz_literal_nodes_binding_v1','complete':False,'issues':[]}
 try:
  from tikz_literal_graph import parse_literal
  source=parse_literal(code);report['source_graph']=source;root=E.fromstring(xml);cr=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in cr};objs=dom['objects'];shapes=[o for o in objs if o['type']=='shape'];texts=[o for o in objs if o['type']=='text'];groups=collections.defaultdict(list)
  for t in texts:groups[t['sourceId'].split('_')[0]].append(t)
  # Bind only a current native object set that still matches the actual source DOM.
  if {c.get('id') for c in cr if c.get('vertex')=='1'}!={o['id'] for o in objs}:raise Unsupported('native/source object inventory differs')
  from svg_convert_v2 import stencil
  for obj in shapes:
   expected,bounds=stencil(obj);cell=cells[obj['id']];geometry=cell.find('mxGeometry')
   if unpack(cell.get('style')).get('shape')!=expected or any(abs(float(geometry.get(k,'0'))-v)>1e-4 for k,v in zip(('x','y','width','height'),bounds)):raise Unsupported('native/source shape geometry changed')
  for obj in texts:
   if norm(cells[obj['id']].get('value',''))!=norm(obj['text']):raise Unsupported('native/source text changed')
  node_objs={};node_texts={}
  for name,label in source['nodes'].items():
   candidates=[]
   for o in shapes:
    b=o['bbox']
    if o['style']['fill']=='none' or min(b['w'],b['h'])<8:continue
    inside=[]
    for t in objs[objs.index(o)+1:]:
     if t['type']!='text':break
     inside.append(t)
    # TikZ paints its node shape followed by its complete text block. Preserve all
    # contiguous PDF text traces, including wrapping, without capturing overlapping
    # labels belonging to later source drawing operations.
    if inside and source_text_match(inside,label) and all(b['x']-.5<=t['bbox']['x']+t['bbox']['w']/2<=b['x']+b['w']+.5 and b['y']-.5<=t['bbox']['y']+t['bbox']['h']/2<=b['y']+b['h']+.5 for t in inside):candidates.append((o,inside))
   if len(candidates)!=1:raise Unsupported('node label not uniquely matched: '+name)
   node_objs[name],node_texts[name]=candidates[0]
  if len({o['id'] for o in node_objs.values()})!=len(node_objs):raise Unsupported('multiple source nodes mapped to same shape')
  paths=[]
  for o in shapes:
   if o['style']['fill']=='none' and o['style']['stroke']!='none':
    pts=polyline(o)
    if len(pts)>=2 and distance(pts[0],pts[-1])>.1:paths.append((o,pts))
  if len(paths)!=len(source['edges']):raise Unsupported(f'path/edge coverage differs: {len(paths)} versus {len(source["edges"])}')
  bindings=[];used=set()
  for edge in source['edges']:
   scores=[]
   for o,pts in paths:
    scores.append((boundary(pts[0],node_objs[edge['source']])+boundary(pts[-1],node_objs[edge['target']]),o,pts))
   scores.sort(key=lambda s:s[0]);score,o,pts=scores[0]
   if score>18 or (len(scores)>1 and scores[1][0]-score<3) or o['id'] in used:raise Unsupported('ambiguous or distant source edge geometry')
   used.add(o['id']);bindings.append((edge,o,[list(p) for p in pts]))
  # All semantic matches must pass before changing the XML.
  arrow_reports=[];label_reports=[];coverage={};consumed=set()
  for edge,o,points in bindings:
   c=cells[o['id']];s=unpack(c.get('style'));s.pop('shape',None);s.update(fillColor='none',endArrow='none',startArrow='none',edgeStyle='none',rounded='0');c.attrib.pop('vertex',None);c.set('edge','1');c.set('source',node_objs[edge['source']]['id']);c.set('target',node_objs[edge['target']]['id']);c.remove(c.find('mxGeometry'))
   for side,terminal,index in [('start',edge['source'],0),('end',edge['target'],-1)]:
    if edge[side+'_arrow']:
     # PDF paint order keeps an arrow adjacent to its own shaft, even when tips overlap.
     index_o=objs.index(o);following=objs[index_o+1:index_o+3];arrow_options=[];p=points[index];q=points[1 if side=='start' else -2];dx,dy=p[0]-q[0],p[1]-q[1];length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
     for a in following:
      if a['type']!='shape' or a['style']['fill']=='none' or a['id'] in consumed or color(a['style']['fill'])!=color(o['style']['stroke']):continue
      b=a['bbox']
      if max(b['w'],b['h'])>20:continue
      try:poly=polyline(a)
      except Unsupported:continue
      tip=max(poly,key=lambda z:z[0]*ux+z[1]*uy);back=min(z[0]*ux+z[1]*uy for z in poly);alen=tip[0]*ux+tip[1]*uy-back;awidth=max(-z[0]*uy+z[1]*ux for z in poly)-min(-z[0]*uy+z[1]*ux for z in poly)
      if distance(tip,p)>20 or alen<.1:continue
      arrow_options.append((a,tip,alen,awidth))
     if len(arrow_options)!=1:raise Unsupported('arrowhead not uniquely matched in PDF paint order')
     a,tip,alen,awidth=arrow_options[0];sw=float(s.get('strokeWidth',1));poly=polyline(a)
     if len(poly)>1 and distance(poly[0],poly[-1])<1e-6:poly=poly[:-1]
     if len(poly) not in (3,4) or a['style']['stroke']!='none':raise Unsupported('marker contour/stroke requires separate native representation')
     if abs(a['style']['opacity']*a['style']['fillOpacity']-o['style']['opacity']*o['style']['strokeOpacity'])>1e-8:raise Unsupported('marker opacity differs from shaft')
     base='block' if len(poly)==3 else 'classic';marker=base+'Thin' if abs(awidth/alen-2/3)<abs(awidth/alen-1) else base
     s.update({side+'Arrow':marker,side+'Size':num(max(.1,alen-sw)),side+'Fill':'1',side+'FillColor':color(a['style']['fill']),side+'StrokeColor':'transparent'});points[index]=[tip[0]+ux*sw*1.118,tip[1]+uy*sw*1.118];cr.remove(cells[a['id']]);consumed.add(a['id']);arrow_reports.append({'source_object':a['id'],'edge':c.get('id'),'side':side,'marker':marker,'source_width_length_ratio':awidth/alen,'source_marker_stroke':'none','native_marker_stroke':'transparent','source_polygon_vertices':len(poly),'note':'Native fill-only marker preserves source color/outer size; notch geometry may differ and requires visual review'})
    b=node_objs[terminal]['bbox'];prefix='exit' if side=='start' else 'entry';s.update({prefix+'X':num((points[index][0]-b['x'])/b['w']),prefix+'Y':num((points[index][1]-b['y'])/b['h']),prefix+'Perimeter':'0'})
   c.set('style',pack(s));g=E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});arr=E.SubElement(g,'Array',{'as':'points'})
   for x,y in points[1:-1]:E.SubElement(arr,'mxPoint',{'x':num(x),'y':num(y)})
   if edge['label']:
    options=[ts for ts in groups.values() if source_text_match(ts,edge['label'])]
    if not options:
     node_text_ids={t['id'] for ts in node_texts.values() for t in ts};seen_options=set()
     for background in shapes:
      if background['id'] in {v['id'] for v in node_objs.values()} or background['style']['fill']=='none':continue
      bb=background['bbox'];ts=[t for t in texts if t['id'] not in node_text_ids and bb['x']<=t['bbox']['x']+t['bbox']['w']/2<=bb['x']+bb['w'] and bb['y']<=t['bbox']['y']+t['bbox']['h']/2<=bb['y']+bb['h']]
      ids=tuple(t['id'] for t in ts)
      if ts and source_text_match(ts,edge['label']) and ids not in seen_options:options.append(ts);seen_options.add(ids)
    if len(options)!=1:raise Unsupported('edge label not uniquely matched')
    ts=options[0];tx=min(t['bbox']['x'] for t in ts);ty=min(t['bbox']['y'] for t in ts);tr=max(t['bbox']['x']+t['bbox']['w'] for t in ts);tb=max(t['bbox']['y']+t['bbox']['h'] for t in ts)
    # Own the original label's painted background as well as every text fragment.
    backgrounds=[]
    for obj in shapes:
     if obj['id'] in {v['id'] for v in node_objs.values()} or obj['id'] in consumed or obj['style']['fill']=='none':continue
     bb=obj['bbox'];aa,ab,ac,ad,_,_=obj['matrix'];paint_pad=float(obj['style']['strokeWidth'])*math.sqrt(abs(aa*ad-ab*ac))/2
     # SVG geometry bounds exclude the actual stroke; text line boxes may reach into it.
     if objs.index(obj)<min(objs.index(t) for t in ts) and bb['x']-paint_pad<=tx and bb['y']-paint_pad<=ty and bb['x']+bb['w']+paint_pad>=tr and bb['y']+bb['h']+paint_pad>=tb and bb['w']*bb['h']<=4*max(1,(tr-tx)*(tb-ty)):backgrounds.append(obj)
    if len(backgrounds)>1:raise Unsupported('edge label background ambiguous')
    first_text=min(objs.index(t) for t in ts);prior=objs[first_text-1] if first_text else None
    if prior and prior['type']=='shape' and prior['style']['fill']!='none' and prior['id'] not in {v['id'] for v in node_objs.values()}:
     bb=prior['bbox'];cx=(tx+tr)/2;cy=(ty+tb)/2
     if bb['x']<=cx<=bb['x']+bb['w'] and bb['y']<=cy<=bb['y']+bb['h'] and prior not in backgrounds:raise Unsupported('source label paint background is not safely owned')
    owned=backgrounds+ts;box=[min(o['bbox']['x'] for o in owned),min(o['bbox']['y'] for o in owned),max(o['bbox']['x']+o['bbox']['w'] for o in owned),max(o['bbox']['y']+o['bbox']['h'] for o in owned)]
    gid='tikz_label_'+c.get('id');assert gid not in cells
    group=E.Element('mxCell',{'id':gid,'vertex':'1','parent':'1','connectable':'0','style':'group;fillColor=none;strokeColor=none;container=1;recursiveResize=1;'})
    E.SubElement(group,'mxGeometry',{'x':num(box[0]),'y':num(box[1]),'width':num(box[2]-box[0]),'height':num(box[3]-box[1]),'as':'geometry'})
    relative_label(group,c,points);cr.append(group)
    for obj in owned:
     child=cells[obj['id']];child.set('parent',gid);cg=child.find('mxGeometry');cg.set('x',num(float(cg.get('x',0))-box[0]));cg.set('y',num(float(cg.get('y',0))-box[1]));consumed.add(obj['id'])
    label_reports.append({'source_label':edge['label'],'edge':c.get('id'),'label_group':gid,'children':[t['id'] for t in ts],'backgrounds':[o['id'] for o in backgrounds]})
   coverage[c.get('id')]={'source':edge['source'],'target':edge['target'],'source_pdf_path':o['sourceId']}
  for name,o in node_objs.items():
   b=o['bbox'];c=cells[o['id']];s=unpack(c.get('style'));s['container']='1';s['recursiveResize']='1';c.set('style',pack(s))
   for t in node_texts[name]:
    tc=cells[t['id']];tc.set('parent',o['id']);g=tc.find('mxGeometry');g.set('x',num(float(g.get('x',0))-b['x']));g.set('y',num(float(g.get('y',0))-b['y']))
  # Stable topological ordering retains all peer paint order and ensures parent decoding.
  pending=list(cr);ordered=[];seen=set()
  while pending:
   progressed=False
   for child in pending[:]:
    if child.get('parent') is None or child.get('parent') in seen:
     ordered.append(child);seen.add(child.get('id'));pending.remove(child);progressed=True
   if not progressed:raise Unsupported('cyclic or missing parent')
  for child in list(cr):cr.remove(child)
  cr.extend(ordered)
  report.update(complete=True,nodes={k:v['id'] for k,v in node_objs.items()},bound_edges=coverage,native_arrowheads=arrow_reports,edge_child_labels=label_reports,source_text_nodes=len(source['nodes']),source_edges=len(source['edges']),source_hyphenation_matches=[{'source_node':name,'source_label':source['nodes'][name],'rendered_fragments':[t['text'] for t in ts],'native_glyphs_preserved':True} for name,ts in node_texts.items() if norm(''.join(t['text'] for t in ts))!=norm(source['nodes'][name])])
  if arrow_reports:report['issues'].append({'reason':'native_arrow_contour_approximation_requires_visual_review','count':len(arrow_reports)})
  return E.tostring(root,encoding='unicode'),report
 except (Unsupported,ValueError,KeyError) as e:
  report['issues'].append({'reason':'tikz_source_connectivity_unresolved','error':str(e)});return xml,report
