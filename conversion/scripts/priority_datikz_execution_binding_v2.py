"""Bind execution-proven named TikZ paths; preserves source-native objects.

This isolated prototype requires a verified execution sidecar and a fresh source
DOM. It never parses/expands source macros, writes jobs, or publishes candidates.
Only straight executed paths are currently supported. Curves fail explicitly.
"""
import collections,hashlib,html,json,math,re,statistics,xml.etree.ElementTree as E
from tikz_literal_connectivity import Unsupported,norm,polyline,boundary,relative_label,source_text_match
from svg_convert_v2 import num,color,stencil,style as svg_style
from svg_convert_v3 import unpack,pack,distance
from tikz_literal_graph import literal
from tikz_literal_connectivity import balanced
from tikz_execution_graph import graph_from_events as legacy_graph_from_events

TEX_PT_TO_PDF_BP=72/72.27


def executed_plain_text(value):
 """Decode formatting in already engine-expanded tokens; never expand macros.

 Unknown commands/math stay unsupported instead of deleting their glyphs.
 """
 directives={'protect','tiny','scriptsize','footnotesize','small','normalsize','large','Large','LARGE','huge','Huge','bfseries','mdseries','itshape','slshape','upshape','sffamily','rmfamily','ttfamily','normalfont','selectfont','centering','raggedright','raggedleft'}
 wrappers={'textbf','textit','textsl','textsf','textrm','texttt','textnormal','emph','underline'}
 output=[];i=0
 while i<len(value):
  ch=value[i]
  if ch=='$':raise Unsupported('Expanded mathematical text needs actual PDF glyph matching')
  if ch in '{}':i+=1;continue
  if ch!='\\':output.append(ch);i+=1;continue
  i+=1
  if i==len(value):raise Unsupported('Trailing backslash in expanded text')
  if value[i] in '%&#_{}':output.append(value[i]);i+=1;continue
  if value[i]=='\\':
   output.append(' ');i+=1
   while i<len(value) and value[i].isspace():i+=1
   if i<len(value) and value[i]=='[':_,end=balanced(value[i:],0,'[',']');i+=end
   continue
  match=re.match('[A-Za-z@]+',value[i:])
  if not match:raise Unsupported('Unknown expanded TeX text control')
  command=match[0];i+=len(command)
  while i<len(value) and value[i].isspace():i+=1
  if command in directives:continue
  if command in wrappers:continue
  arguments={'color':1,'textcolor':1,'fontfamily':1,'fontsize':2,'hspace':1,'vspace':1}.get(command)
  if arguments is None:raise Unsupported('Unverified expanded text command: '+command)
  for _ in range(arguments):
   while i<len(value) and value[i].isspace():i+=1
   _,i=balanced(value,i)
 return ''.join(output).strip()


def _pt(value):
 if not re.fullmatch(r'[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)pt',value):raise Unsupported('Execution coordinate is not a literal TeX dimension')
 return float(value[:-2])


def _nodes(dom,graph):
 objects=dom['objects'];shapes=[o for o in objects if o['type']=='shape'];found={}
 for node in graph['nodes']:
  label=executed_plain_text(node['expanded_label_tex']);matches=[]
  for shape in shapes:
   box=shape['bbox']
   if shape['style']['fill']=='none' or min(box['w'],box['h'])<8:continue
   texts=[]
   for item in objects[objects.index(shape)+1:]:
    if item['type']!='text':break
    texts.append(item)
   if texts and source_text_match(texts,label) and all(box['x']-.5<=t['bbox']['x']+t['bbox']['w']/2<=box['x']+box['w']+.5 and box['y']-.5<=t['bbox']['y']+t['bbox']['h']/2<=box['y']+box['h']+.5 for t in texts):matches.append(shape)
  if len(matches)!=1:raise Unsupported('Execution node not uniquely identified in PDF source paint: '+node['name'])
  found[node['name']]=matches[0]
 if len({o['id'] for o in found.values()})!=len(found):raise Unsupported('Two executed nodes share one PDF shape')
 return found


def coordinate_mapping(dom,graph,root_matrix):
 if len(root_matrix)!=6:raise Unsupported('Missing actual source SVG root ScreenCTM')
 a,b,c,d,_,_=root_matrix
 if abs(b)>1e-8 or abs(c)>1e-8 or min(a,d)<=0:raise Unsupported('Source SVG root transform is not positive axis aligned')
 nodes=_nodes(dom,graph)
 anchors=[n for n in graph['nodes'] if n['shape'] in ('rectangle','circle','ellipse')]
 if len(anchors)<3:raise Unsupported('At least three symmetric named nodes required to verify the fixed-unit coordinate translation')
 sx=a*TEX_PT_TO_PDF_BP;sy=-d*TEX_PT_TO_PDF_BP;offsets=[]
 for node in anchors:
  box=nodes[node['name']]['bbox'];x,y=map(_pt,node['center_pt']);offsets.append((box['x']+box['w']/2-sx*x,box['y']+box['h']/2-sy*y))
 tx=statistics.median(x for x,y in offsets);ty=statistics.median(y for x,y in offsets)
 errors=[math.hypot(x-tx,y-ty) for x,y in offsets]
 if max(errors)>.05:raise Unsupported('Known TeXpt/PDFbp/SVG unit transform is inconsistent across named nodes: '+str(max(errors)))
 xvalues=[_pt(n['center_pt'][0]) for n in anchors];yvalues=[_pt(n['center_pt'][1]) for n in anchors]
 # Scale is independently fixed by PGFpt/PDFbp and the actual SVG ScreenCTM.
 # Three exact labeled symmetric centers prove translation even in a vertical
 # graph; horizontal spread is not required for this non-affine-fit proof.
 for node in graph['nodes']:
  box=nodes[node['name']]['bbox'];px=sx*_pt(node['center_pt'][0])+tx;py=sy*_pt(node['center_pt'][1])+ty
  if not (box['x']-.05<=px<=box['x']+box['w']+.05 and box['y']-.05<=py<=box['y']+box['h']+.05):raise Unsupported('Executed node center falls outside its uniquely matched source shape')
 return {'matrix':[sx,0,0,sy,tx,ty],'tex_pt_to_pdf_bp':TEX_PT_TO_PDF_BP,'actual_svg_root_screen_ctm':root_matrix,'node_centers_checked':len(anchors),'source_nodes_label_shape_matched':len(nodes),'maximum_node_center_error_px':max(errors),'node_cell_ids':{name:o['id'] for name,o in nodes.items()}}


def _mapped(point,mapping):
 sx,_,_,sy,tx,ty=mapping['matrix'];return [sx*_pt(point[0])+tx,sy*_pt(point[1])+ty]


def _softpath_points(value):
 pattern=r'\\pgfsyssoftpath@(moveto|lineto)token\s*\{([^{}]+)\}\{([^{}]+)\}'
 matches=list(re.finditer(pattern,value));remainder=re.sub(pattern,'',value).strip()
 if remainder or not matches or matches[0][1]!='moveto' or any(m[1]!='lineto' for m in matches[1:]):raise Unsupported('Non-straight or multi-subpath PGF path needs exact native bezier/route support')
 return [[m[2],m[3]] for m in matches]


def _path_matches_execution(points,expected,edge):
 if len(points)!=len(expected) or len(points)<2:return False
 if any(math.dist(a,b)>.05 for a,b in zip(points[1:-1],expected[1:-1])):return False
 for index,actual,target,adjacent,arrow in [(0,points[0],expected[0],expected[1],edge['start_arrow']),(-1,points[-1],expected[-1],expected[-2],edge['end_arrow'])]:
  dx,dy=(adjacent[0]-target[0],adjacent[1]-target[1]) if index==0 else (target[0]-adjacent[0],target[1]-adjacent[1]);length=math.hypot(dx,dy)
  if length<.1:return False
  ux,uy=dx/length,dy/length;vx,vy=actual[0]-target[0],actual[1]-target[1]
  if abs(vx*uy-vy*ux)>.05:return False
  along=vx*ux+vy*uy
  if not arrow and abs(along)>.05:return False
  if arrow and (abs(along)>20 or index==0 and along<-.05 or index==-1 and along>.05):return False
 return True

def _marker_stroke(marker,shaft,native_style):
 style=marker['style']
 if style['stroke']=='none':return 'transparent'
 if color(style['stroke'])!=color(shaft['style']['stroke']):raise Unsupported('Marker outline color differs from owning source shaft')
 a,b,c,d,_,_=marker['matrix'];width=style['strokeWidth']*math.sqrt(abs(a*d-b*c))
 if abs(width-float(native_style.get('strokeWidth',1)))>.001:raise Unsupported('Marker outline width differs from native shaft width')
 if abs(style['opacity']*style['strokeOpacity']-shaft['style']['opacity']*shaft['style']['strokeOpacity'])>1e-8:raise Unsupported('Marker outline opacity differs from source shaft')
 if style['linejoin']!='miter':raise Unsupported('Marker outline join requires another native marker representation')
 return color(style['stroke'])


def _verify_source_paint(xml,dom):
 cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
 for obj in dom['objects']:
  if obj['id'] not in cells:raise Unsupported('Source paint object missing from current native inventory')
  actual=unpack(cells[obj['id']].get('style'))
  expected=svg_style(obj) if obj['type']=='shape' else {'fontColor':color(obj['color']),'fontSize':num(obj['fontSize']),'opacity':num(obj['opacity']*100)} if obj['type']=='text' else {}
  for key in ('fillColor','strokeColor','strokeWidth','fillOpacity','strokeOpacity','opacity','fontColor','fontSize'):
   if key not in expected:continue
   found=actual.get(key,{'opacity':'100','fillOpacity':'100','strokeOpacity':'100','strokeWidth':'1'}.get(key))
   try:equal=abs(float(found)-float(expected[key]))<.001
   except (TypeError,ValueError):equal=found==expected[key]
   if not equal:raise Unsupported('Current native/source paint property mismatch: '+obj['id']+' '+key)


def bind_execution(xml,dom,sidecar,events,root_matrix):
 report={'version':'execution_typed_named_and_free_path_binding_v3','complete':False,'issues':[]}
 try:
  if not sidecar.get('ok') or not sidecar['graph'].get('ok'):raise Unsupported('Execution sidecar did not pass its source/trace/PDF proof')
  if graph_from_events(events)!=sidecar['graph']:raise Unsupported('Execution graph no longer matches its actual trace')
  if dom.get('issues'):raise Unsupported('Fresh PDF SVG has unsupported visible features: '+json.dumps(dom['issues'][:10]))
  _verify_source_paint(xml,dom)
  native_cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
  if any(c.get('edge')=='1' for c in native_cells.values()):raise Unsupported('This version requires the original unbound native inventory')
  if any(c.get('vertex')=='1' and c.get('parent')!='1' for c in native_cells.values()):raise Unsupported('This version requires a flat source-painted vertex inventory')
  for obj in dom['objects']:
   if obj['type']!='text':continue
   cell=native_cells.get(obj['id'])
   if cell is None:raise Unsupported('Current native text object is absent')
   expected=obj.get('nativeRotation',0) if obj.get('rotationHandled') else 0
   if abs(float(unpack(cell.get('style')).get('rotation',0))-expected)>.01:raise Unsupported('Current native text has not preserved the actual source rotation')
  graph=sidecar['graph'];mapping=coordinate_mapping(dom,graph,root_matrix);report['coordinate_mapping']=mapping
  source_centers={n['name']:_mapped(n['center_pt'],mapping) for n in graph['nodes']}
  for reference in graph['reference_events']:
   if reference['name'] in source_centers and reference['anchor']=='center' and math.dist(_mapped(reference['point_pt'],mapping),source_centers[reference['name']])>.05:raise Unsupported('Executed named reference point disagrees with its source node center')
  finishes={(e['fields'][0],e['fields'][1]):e['fields'][-1] for e in events if e['kind']=='finish'}
  edges=[];by_path=collections.Counter((e['picture'],e['path']) for e in graph['edges'])
  for executed in graph['edges']:
   key=(executed['picture'],executed['path'])
   if executed['operation']!='line' or by_path[key]!=1:raise Unsupported('One executed straight/polyline path per source path required')
   points=[_mapped(p,mapping) for p in _softpath_points(finishes[key])]
   labels=executed['executed_label_nodes']
   if len(labels)>1:raise Unsupported('Multiple labels on one executed edge require grouped text matching')
   edges.append({**executed,'label':executed_plain_text(labels[0]['expanded_label_tex']) if labels else '', 'source_anchor':None,'target_anchor':None,'route':'--','_executed_points':points,'_execution_path':list(key),'_label_center':_mapped(labels[0]['center_pt'],mapping) if labels else None})
  retained_annotations=[];owned_annotations=[]
  for annotation in graph['decorative_nodes']:
   dependencies={d['name'] for d in annotation.get('executed_anchor_dependencies',[]) if d['name'] in mapping['node_cell_ids']}
   if len(dependencies)!=2:retained_annotations.append(annotation['serial']);continue
   choices=[e for e in edges if {e['source'],e['target']}==dependencies]
   if len(choices)!=1:raise Unsupported('Executed annotation depends on an ambiguous semantic node pair')
   edge=choices[0]
   center=_mapped(annotation['center_pt'],mapping);start,end=edge['_executed_points'][0],edge['_executed_points'][-1];dx,dy=end[0]-start[0],end[1]-start[1];length2=dx*dx+dy*dy;t=max(0,min(1,((center[0]-start[0])*dx+(center[1]-start[1])*dy)/(length2 or 1)));distance_to_path=math.dist(center,[start[0]+t*dx,start[1]+t*dy])
   if distance_to_path>40:
    # Reading an anchor in an at(...) expression does not prove the value was
    # used. For example, a standalone node's midway style can override at(...)
    # and actually place it at the origin. Preserve such original annotation
    # objects, and report the unresolved attachment instead of guessing.
    retained_annotations.append(annotation['serial']);report['issues'].append({'reason':'executed_annotation_position_not_on_its_anchor_pair_path','serial':annotation['serial'],'distance_px':distance_to_path});continue
   if edge['label']:raise Unsupported('Executed edge already has another label')
   edge['label']=executed_plain_text(annotation['expanded_label_tex']);edge['_label_center']=center;owned_annotations.append({'serial':annotation['serial'],'edge_path':edge['_execution_path'],'dependencies':sorted(dependencies)})
  required_names={e[k] for e in edges for k in ('source','target') if e[k] is not None}
  source={'nodes':{n['name']:(mapping.get('source_rendered_node_labels',{}).get(n['name']) if n['name'] in mapping.get('source_rendered_node_labels',{}) else executed_plain_text(n['expanded_label_tex'])) for n in graph['nodes'] if n['name'] in required_names},'edges':edges,'parser':'actual_pgf_execution_named_nodes_v1'}
  candidate,binding=_bind_objects(xml,dom,source)
  if not binding['complete']:report['issues'].extend(binding['issues']);return xml,report
  report.update(complete=True,coordinate_mapping=mapping,binding=binding,source_nodes=len(source['nodes']),source_edges=len(edges),typed_free_paths=graph.get('typed_free_paths',[]),closed_source_paint=graph.get('closed_source_paint',[]),owned_executed_annotations=owned_annotations,retained_free_annotation_serials=retained_annotations)
  return candidate,report
 except (ValueError,KeyError,TypeError) as exc:
  report['issues'].append({'reason':'execution_binding_unsupported','error':str(exc)})
  return xml,report


def _bind_objects(xml,dom,source):
 report={'version':'tikz_executed_named_and_explicit_numeric_paths_v3','complete':False,'issues':[]}
 try:
  report['source_graph']={k:v for k,v in source.items() if not k.startswith('_')};root=E.fromstring(xml);cr=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in cr};objs=dom['objects'];shapes=[o for o in objs if o['type']=='shape'];texts=[o for o in objs if o['type']=='text'];groups=collections.defaultdict(list)
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
    try:pts=polyline(o)
    except Unsupported:continue
    if len(pts)>=2 and distance(pts[0],pts[-1])>.1:paths.append((o,pts))
  if len(paths)!=len(source['edges']):raise Unsupported(f'path/edge coverage differs: {len(paths)} versus {len(source["edges"])}')
  bindings=[];used=set()
  for edge in source['edges']:
   matches=[]
   for o,pts in paths:
    if _path_matches_execution(pts,edge['_executed_points'],edge):matches.append((o,pts))
   if len(matches)!=1 or matches[0][0]['id'] in used:raise Unsupported('executed source path not uniquely matched to PDF shaft: '+str(edge['_execution_path']))
   o,pts=matches[0];used.add(o['id']);bindings.append((edge,o,[list(p) for p in pts]))
  # All semantic matches must pass before changing the XML.
  arrow_reports=[];label_reports=[];coverage={};consumed=set()
  for edge,o,points in bindings:
   c=cells[o['id']];s=unpack(c.get('style'));s.pop('shape',None);s.update(fillColor='none',endArrow='none',startArrow='none',edgeStyle='none',rounded='0');c.attrib.pop('vertex',None);c.set('edge','1');
   if edge['source'] is not None:c.set('source',node_objs[edge['source']]['id'])
   if edge['target'] is not None:c.set('target',node_objs[edge['target']]['id'])
   c.remove(c.find('mxGeometry'))
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
     if len(poly) not in (3,4):raise Unsupported('marker contour requires separate native representation')
     marker_stroke=_marker_stroke(a,o,s)
     if abs(a['style']['opacity']*a['style']['fillOpacity']-o['style']['opacity']*o['style']['strokeOpacity'])>1e-8:raise Unsupported('marker opacity differs from shaft')
     base='block' if len(poly)==3 else 'classic';marker=base+'Thin' if abs(awidth/alen-2/3)<abs(awidth/alen-1) else base
     s.update({side+'Arrow':marker,side+'Size':num(max(.1,alen-sw)),side+'Fill':'1',side+'FillColor':color(a['style']['fill']),side+'StrokeColor':marker_stroke});points[index]=[tip[0]+ux*sw*1.118,tip[1]+uy*sw*1.118];cr.remove(cells[a['id']]);consumed.add(a['id']);arrow_reports.append({'source_object':a['id'],'edge':c.get('id'),'side':side,'marker':marker,'source_width_length_ratio':awidth/alen,'source_marker_stroke':a['style']['stroke'],'native_marker_stroke':marker_stroke,'source_polygon_vertices':len(poly),'note':'Source fill/outline colors, opacity and shaft-matched stroke width retained; native notch contour requires a separate local-raster gate'})
    if terminal is not None:
     b=node_objs[terminal]['bbox'];prefix='exit' if side=='start' else 'entry';s.update({prefix+'X':num((points[index][0]-b['x'])/b['w']),prefix+'Y':num((points[index][1]-b['y'])/b['h']),prefix+'Perimeter':'0'})
   c.set('style',pack(s));g=E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});arr=E.SubElement(g,'Array',{'as':'points'})
   for x,y in points[1:-1]:E.SubElement(arr,'mxPoint',{'x':num(x),'y':num(y)})
   for side,endpoint in [('source',points[0]),('target',points[-1])]:
    if edge[side] is None:E.SubElement(g,'mxPoint',{'as':side+'Point','x':num(endpoint[0]),'y':num(endpoint[1])})
   if edge['label']:
    options=[ts for ts in groups.values() if source_text_match(ts,edge['label'])]
    if not options:
     node_text_ids={t['id'] for ts in node_texts.values() for t in ts};seen_options=set()
     for background in shapes:
      if background['id'] in {v['id'] for v in node_objs.values()} or background['style']['fill']=='none':continue
      bb=background['bbox'];ts=[t for t in texts if t['id'] not in node_text_ids and bb['x']<=t['bbox']['x']+t['bbox']['w']/2<=bb['x']+bb['w'] and bb['y']<=t['bbox']['y']+t['bbox']['h']/2<=bb['y']+bb['h']]
      ids=tuple(t['id'] for t in ts)
      if ts and source_text_match(ts,edge['label']) and ids not in seen_options:options.append(ts);seen_options.add(ids)
    if edge.get('_label_center') and options:
     center=edge['_label_center'];ranked=[]
     for ts in options:
      x0=min(t['bbox']['x'] for t in ts);y0=min(t['bbox']['y'] for t in ts);x1=max(t['bbox']['x']+t['bbox']['w'] for t in ts);y1=max(t['bbox']['y']+t['bbox']['h'] for t in ts);delta=math.hypot((x0+x1)/2-center[0],(y0+y1)/2-center[1]);ranked.append((delta,max(2,(y1-y0)*.75+1),ts))
     ranked.sort(key=lambda x:x[0])
     if ranked[0][0]>ranked[0][1] or len(ranked)>1 and ranked[1][0]-ranked[0][0]<1:raise Unsupported('executed label position does not uniquely match PDF glyphs')
     options=[ranked[0][2]]
    if len(options)!=1:raise Unsupported('edge label not uniquely matched')
    ts=options[0];paintboxes=[t.get('originalBoundingBox',t['bbox']) for t in ts];tx=min(b['x'] for b in paintboxes);ty=min(b['y'] for b in paintboxes);tr=max(b['x']+b['w'] for b in paintboxes);tb=max(b['y']+b['h'] for b in paintboxes)
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
   coverage[c.get('id')]={'source':edge['source'],'target':edge['target'],'source_pdf_path':o['sourceId'],'kind':edge.get('terminal_kind','named_named'),'source_coordinate_points':edge['_executed_points']}
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


def graph_from_events(events):
 """Keep source free paths free; reject missing/ambiguous named references.

 Typed roles derive from executed callbacks and the complete PGF softpath.
 The preserved legacy graph failures are removed only with a matching complete
 typed path proof. No geometric proximity is used to invent an attachment.
 """
 original=legacy_graph_from_events(events);graph=__import__('copy').deepcopy(original)
 paths={};node_events={}
 for index,e in enumerate(events):
  f=e['fields'];kind=e['kind']
  if kind=='node':node_events[f[2]]={'picture':f[0],'path':f[1],'serial':f[2],'role':f[3],'name':f[4],'shape':f[5],'expanded_label_tex':f[6],'center_pt':f[7:9],'operation':int(f[9])}
  if kind in ('path','operation','ref','finish','node'):
   k=(f[0],f[1]);p=paths.setdefault(k,{'operations':[],'references':[],'finishes':[],'nodes':[]})
   if kind=='operation':p['operations'].append((index,f[2],int(f[3])))
   if kind=='ref':p['references'].append((index,{'callback':f[2],'name':f[3],'anchor':f[4],'point_pt':f[5:7],'auto_shape_border':f[7]=='1'}))
   if kind=='finish':p['finishes'].append(f)
   if kind=='node':p['nodes'].append(node_events[f[2]])
 good=set();typed=[];named_polylines=[];closed=[];extra_edges=[];extra_annotations=[]
 existing_edge_paths={(e['picture'],e['path']) for e in original['edges']}
 known_names={n['name'] for n in original['nodes']}
 for key,p in paths.items():
  if len(p['finishes'])!=1:continue
  f=p['finishes'][0];soft=f[-1].strip();operators=collections.Counter(re.findall(r'\\pgfsyssoftpath@([A-Za-z]+)token',soft))
  if operators['closepath'] or operators['rectcorner'] or operators['rectsize']:
   good.add(key);closed.append({'picture':key[0],'path':key[1],'kind':'source_closed_paint','softpath_sha256':hashlib.sha256(soft.encode()).hexdigest(),'arrow_flags_do_not_invent_connections':True});extra_annotations.extend(p['nodes']);continue
  if not soft:
   if all(x[1]=='move' for x in p['operations']):good.add(key);extra_annotations.extend(p['nodes'])
   continue
  if key in existing_edge_paths:continue
  try:points=_softpath_points(soft)
  except (ValueError,Unsupported):continue
  ops=p['operations'];refs=[(i,r) for i,r in p['references'] if r['callback'] in {'\\tikz@@moveto','\\tikz@@lineto'}]
  if len(ops)!=len(points) or ops[0][1]!='move' or any(x[1]!='line' for x in ops[1:]):continue
  if len(refs)!=len(p['references']):continue
  attached={};valid=True
  for ri,ref in refs:
   candidates=[o for o in ops if o[0]>ri]
   if not candidates:valid=False;break
   op=candidates[0];expected='move' if ref['callback']=='\\tikz@@moveto' else 'line'
   if op[1]!=expected or op[2] in attached or ref['name'] not in known_names:valid=False;break
   attached[op[2]]=ref
  if not valid or any(k not in (ops[0][2],ops[-1][2]) for k in attached):continue
  start=attached.get(ops[0][2]);end=attached.get(ops[-1][2]);kind=('named' if start else 'numeric')+'_'+('named' if end else 'numeric')
  # Named endpoints are execution-bound; complete multi-segment softpath is retained.
  # A missing callback cannot turn a named path into a free one: the trace's
  # complete source program, paint, and complete operation counters are pinned.
  edge={'picture':key[0],'path':key[1],'source':start['name'] if start else None,'target':end['name'] if end else None,'source_anchor':start['anchor'] if start else None,'target_anchor':end['anchor'] if end else None,'operation':'line','operation_number':ops[-1][2],'start_arrow':f[3]=='1','end_arrow':f[4]=='1','executed_label_nodes':[], 'terminal_kind':kind,'explicit_source_numeric_points_pt':points}
  extra_edges.append(edge);good.add(key);(named_polylines if kind=='named_named' else typed).append({'picture':key[0],'path':key[1],'kind':kind,'points_pt':points,'source':edge['source'],'target':edge['target'],'start_arrow':edge['start_arrow'],'end_arrow':edge['end_arrow'],'named_reference_count':len(refs),'no_inferred_node_attachment':True});extra_annotations.extend(p['nodes'])
 failures=[]
 for f in original['failures']:
  reason=f['reason'];key=(str(f.get('picture')),str(f.get('path')))
  if key in good and reason in ('numeric_or_unbound_path_terminal','uncovered_executed_softpath_operations','painted_path_without_named_semantic_operations','edge_label_operation_ambiguous'):continue
  if reason=='node_or_label_event_coverage_incomplete':continue
  failures.append(f)
 graph['edges']+=extra_edges
 used={n['serial'] for n in graph['nodes']}|{n['serial'] for n in graph['decorative_nodes']}|{n['serial'] for e in graph['edges'] for n in e['executed_label_nodes']}
 for n in extra_annotations:
  if n['serial'] not in used:graph['decorative_nodes'].append({**n,'role':'source_free_annotation'});used.add(n['serial'])
 if len(node_events)!=sum(e['kind']=='node' for e in events):failures.append({'reason':'duplicate_source_node_serial'})
 if used!=set(node_events):failures.append({'reason':'typed_source_node_event_coverage_incomplete','missing':sorted(set(node_events)-used)})
 graph.update(version='priority_DaTikZ_actual_pgf_typed_named_polylines_and_free_paths_v1',ok=not failures,failures=failures,typed_free_paths=typed,typed_named_polylines=named_polylines,closed_source_paint=closed,executed_softpaths={e['fields'][0]+':'+e['fields'][1]:e['fields'][-1] for e in events if e['kind']=='finish'},source_semantics='Numeric endpoints remain explicit free endpoints; no nearest-node inference; named endpoints preserve executed node identity.')
 return graph

_named_coordinate_mapping=coordinate_mapping

def coordinate_mapping(dom,graph,root_matrix):
 """Prove the fixed PGF/PDF units using complete source paths if needed.

 Only a global translation is solved, from exact vector control points. It must
 be uniquely consistent with every executed open source path. No raster data,
 node proximity, arbitrary scaling, or per-object fitting is used.
 """
 required={e[k] for e in graph['edges'] for k in ('source','target') if e[k] is not None}
 try:
  needed={**graph,'nodes':[n for n in graph['nodes']if n['name']in required]}
  result=_named_coordinate_mapping(dom,needed,root_matrix)
  result['nonterminal_named_nodes_preserved_as_original_native_paint']=sorted({n['name'] for n in graph['nodes']}-required)
  return result
 except (Unsupported,ValueError) as error:named_error=str(error)
 a,b,c,d,_,_=root_matrix
 if abs(b)>1e-8 or abs(c)>1e-8 or min(a,d)<=0:raise Unsupported('Source frame must preserve known PGF/PDF axis-aligned units')
 sx=a*TEX_PT_TO_PDF_BP;sy=-d*TEX_PT_TO_PDF_BP
 vectors=[]
 for obj in dom['objects']:
  if obj['type']!='shape' or obj['style']['fill']!='none' or obj['style']['stroke']=='none':continue
  try:points=polyline(obj)
  except Unsupported:continue
  if len(points)>=2 and math.dist(points[0],points[-1])>.1:vectors.append((obj,points))
 rawpaths=[];seen=set()
 for edge in graph['edges']:
  key=edge['picture']+':'+edge['path']
  if key in seen:raise Unsupported('Source path with multiple semantic edges requires complete polyline ownership')
  seen.add(key);soft=graph.get('executed_softpaths',{}).get(key)
  if soft is None:raise Unsupported('Original executed source softpath missing from typed graph')
  points=_softpath_points(soft);rawpaths.append((edge,[[sx*_pt(x),sy*_pt(y)] for x,y in points]))
 anchors=[x for x in rawpaths if not x[0]['start_arrow'] and not x[0]['end_arrow']]
 if not anchors:raise Unsupported('No exact unarrowed source path or symmetric named nodes to establish the global source frame: '+named_error)
 if len(vectors)!=len(rawpaths):raise Unsupported('Complete open source/PDF path inventory differs')
 first,points=anchors[0];offsets=[]
 for obj,actual in vectors:
  if len(actual)!=len(points):continue
  tx=actual[0][0]-points[0][0];ty=actual[0][1]-points[0][1]
  if max(math.dist(p,[q[0]+tx,q[1]+ty]) for p,q in zip(actual,points))>.05:continue
  if not any(math.dist([tx,ty],o)<.01 for o in offsets):offsets.append([tx,ty])
 viable=[]
 for tx,ty in offsets:
  used=set();ownership=[]
  for edge,pts in rawpaths:
   expected=[[x+tx,y+ty] for x,y in pts];matches=[obj['id'] for obj,p in vectors if _path_matches_execution(p,expected,edge)]
   if len(matches)!=1 or matches[0] in used:break
   used.add(matches[0]);ownership.append({'picture':edge['picture'],'path':edge['path'],'source_PDF_object':matches[0]})
  else:
   if len(used)==len(vectors):viable.append((tx,ty,ownership))
 if len(viable)!=1:raise Unsupported('Global source vector translation is not unique and complete: '+str(len(viable)))
 tx,ty,ownership=viable[0];needed={**graph,'nodes':[n for n in graph['nodes'] if n['name'] in required]};nodes={};rendered_labels={}
 # Binding uses exact executed centers in the independently proved global frame.
 # Original TeX math is never stripped or guessed; every actual source PDF glyph
 # following its unique source node shape remains an editable native text cell.
 for node in needed['nodes']:
  cx=sx*_pt(node['center_pt'][0])+tx;cy=sy*_pt(node['center_pt'][1])+ty;options=[]
  for obj in dom['objects']:
   if obj['type']!='shape' or obj['style']['fill']=='none':continue
   bb=obj['bbox']
   if min(bb['w'],bb['h'])<8 or math.dist([bb['x']+bb['w']/2,bb['y']+bb['h']/2],[cx,cy])>.05:continue
   ts=[]
   for item in dom['objects'][dom['objects'].index(obj)+1:]:
    if item['type']!='text':break
    ts.append(item)
   if not ts or any(not(bb['x']-.5<=t['bbox']['x']+t['bbox']['w']/2<=bb['x']+bb['w']+.5 and bb['y']-.5<=t['bbox']['y']+t['bbox']['h']/2<=bb['y']+bb['h']+.5) for t in ts):continue
   options.append((obj,ts))
  if len(options)!=1:raise Unsupported('Executed node center/source PDF glyph group not unique: '+node['name'])
  obj,ts=options[0];nodes[node['name']]=obj;rendered_labels[node['name']]=''.join(t['text'] for t in ts)
 if len({x['id'] for x in nodes.values()})!=len(nodes):raise Unsupported('Two executed nodes claim one actual PDF shape')
 return {'matrix':[sx,0,0,sy,tx,ty],'tex_pt_to_pdf_bp':TEX_PT_TO_PDF_BP,'actual_svg_root_screen_ctm':root_matrix,'node_cell_ids':{name:o['id'] for name,o in nodes.items()},'source_rendered_node_labels':rendered_labels,'source_node_ownership':'exact executed center in independently proven global vector frame and complete contiguous PDF glyph group; TeX math is not stripped','complete_executed_source_vector_frame':ownership,'global_translation_uniquely_proven_from_complete_source_vector_inventory':True,'source_raster_or_proximity_used':False,'nonterminal_named_nodes_preserved_as_original_native_paint':sorted({n['name'] for n in graph['nodes']}-required)}

_original_typed_graph_from_events=graph_from_events
def graph_from_events(events):
 from datikz_coordinate_routes_v1 import normalize
 return normalize(_original_typed_graph_from_events(events),_softpath_points,_pt)
