"""Pure source-only operational input graphs; never render/convert/execute sources."""
import collections,hashlib,html,json,re,xml.etree.ElementTree as E
from html.parser import HTMLParser
import networkx as nx
VERSION='compiler_types_source_semantic_v1'
def raw(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def add(g,key,kind,attrs):g.add_node(key,signature=sha(raw([kind,attrs])))
def link(g,a,b,kind):g.add_edge(a,b,signature=kind)
def style(s):
 out=[]
 for p in s.split(';'):
  if not p:continue
  k,sep,v=p.partition('=')
  if k in ('sourcePort','targetPort'):continue
  if v.startswith('data:'):v='data:'+sha(v.encode())
  out.append((k,v if sep else True))
 return sorted(out)
def texttype(s):
 if '<' in html.unescape(s or ''):
  return re.sub(r'>[^<]*<','>TEXT<',html.unescape(s or ''))
 return bool(s)
def native(code,old):
 rt=old.expanded_xml(code);pages=rt.findall('diagram') if rt.tag.rsplit('}',1)[-1]=='mxfile' else [rt]
 g=nx.MultiDiGraph();add(g,'ROOT','native_document',{'pages':len(pages)})
 totalnodes=totaledges=0
 for pi,page in enumerate(pages):
  cells=list(page.iter('mxCell'))
  if not cells:raise ValueError('native_missing_cells')
  ids={c.get('id'):('cell',pi,i) for i,c in enumerate(cells)}
  if None in ids or len(ids)!=len(cells):raise ValueError('native_duplicate_or_missing_cell_ID')
  pk=('page',pi);add(g,pk,'native_page',{});link(g,'ROOT',pk,'page')
  for i,c in enumerate(cells):
   key=ids[c.get('id')];attrs={k:v for k,v in c.attrib.items() if k not in ('id','parent','source','target','value','style')};attrs.update(style=style(c.get('style','')),label=texttype(c.get('value','')))
   geometry=[]
   for n in c:
    geometry.append([n.tag,sorted(n.attrib.items()),[[x.tag,sorted(x.attrib.items())] for x in n.iter() if x is not n]])
   attrs['geometry']=geometry;add(g,key,'edge' if c.get('edge')=='1' else 'vertex' if c.get('vertex')=='1' else 'layer_or_cell',attrs)
   totalnodes+=c.get('vertex')=='1';totaledges+=c.get('edge')=='1'
  for i,c in enumerate(cells):
   key=ids[c.get('id')];par=c.get('parent')
   if par:
    if par not in ids:raise ValueError('native_parent_unresolved')
    link(g,ids[par],key,'parent')
   else:link(g,pk,key,'page_cell')
   for role in ('source','target'):
    ref=c.get(role)
    if ref:
     if ref not in ids:raise ValueError('native_endpoint_unresolved')
     link(g,key,ids[ref],role)
   for part in c.get('style','').split(';'):
    k,sep,v=part.partition('=')
    if k in ('sourcePort','targetPort') and sep:
     if v not in ids:raise ValueError('native_named_port_unresolved')
     link(g,key,ids[v],k)
 if not totalnodes:raise ValueError('native_no_editable_vertices')
 if totalnodes==1 and any('shape=image' in c.get('style','') or 'image=' in c.get('style','') for page in pages for c in page.iter('mxCell')):raise ValueError('native_whole_image_wrapper')
 return 'native_drawio_graph_v1',g,{'nodes':totalnodes,'edges':totaledges,'complete_source_structure':True}

def _flat_graph(ir,unit):
 g=nx.MultiDiGraph();add(g,'ROOT','language_graph',{k:v for k,v in ir.items() if k not in ('nodes','edges','statements_total','statements_recognized')})
 for n in ir['nodes']:add(g,('n',n['id']),'node',{k:v for k,v in n.items() if k not in ('id','text','label')});link(g,'ROOT',('n',n['id']),'node')
 for i,e in enumerate(ir['edges']):
  k=('e',i);add(g,k,'edge',{k:v for k,v in e.items() if k not in ('source','target','label','text')});link(g,('n',e['source']),k,'source');link(g,k,('n',e['target']),'target')
 return unit,g,{'nodes':len(ir['nodes']),'edges':len(ir['edges']),'complete_static_program':True}
def language(code,fmt,native_parser):
 # Complete declared grammar subset: strip only recognized style declarations,
 # parse all graph statements with the existing strict complete parser.
 if fmt=='plantuml':return _flat_graph(native_parser.parse_plantuml(code),'plantuml_flat_engine_entity_svg_v1')
 statements=native_parser.statements(code);program=[];directives=[]
 for s in statements:
  if re.match(r'^(style|classDef|class|linkStyle)\b',s):directives.append(s)
  else:program.append(s)
 ir=native_parser.parse_mermaid('\n'.join(program));byid={n['id']:n for n in ir['nodes']};classes={};pending=[]
 for s in directives:
  m=re.fullmatch(r'classDef\s+([A-Za-z_]\w*)\s+(.+)',s)
  if m:classes[m[1]]=m[2];continue
  m=re.fullmatch(r'style\s+([A-Za-z_]\w*)\s+(.+)',s)
  if m:
   if m[1] not in byid:raise ValueError('mermaid_style_unknown_node')
   byid[m[1]]['source_style']=m[2];continue
  m=re.fullmatch(r'class\s+([A-Za-z_][\w,]*)\s+([A-Za-z_]\w*)',s)
  if m:pending.append((m[1].split(','),m[2]));continue
  m=re.fullmatch(r'linkStyle\s+(default|[0-9,]+)\s+(.+)',s)
  if m:
   indices=range(len(ir['edges'])) if m[1]=='default' else [int(x) for x in m[1].split(',')]
   for i in indices:
    if i>=len(ir['edges']):raise ValueError('mermaid_style_unknown_edge')
    ir['edges'][i]['source_style']=m[2]
   continue
  raise ValueError('mermaid_style_statement_unsupported')
 for ids,cls in pending:
  if cls not in classes:raise ValueError('mermaid_class_unknown')
  for identifier in ids:
   if identifier not in byid:raise ValueError('mermaid_class_unknown_node')
   byid[identifier]['source_style']=classes[cls]
 return _flat_graph(ir,'mermaid_flat_source_svg_v1')

def svg(code):
 root=E.fromstring(code);allowed={'svg','g','title','desc','path','polygon','polyline','rect','circle','ellipse','line','text'};nodes={};edges=[]
 for e in root.iter():
  tag=e.tag.rsplit('}',1)[-1]
  if tag not in allowed:raise ValueError('svg_role_unit_unsupported_tag:'+tag)
  if any(k.rsplit('}',1)[-1] in ('href','src','filter','clip-path','mask','marker-start','marker-end') or 'url(' in v.lower() for k,v in e.attrib.items()):raise ValueError('svg_role_unit_effect_or_reference')
  if tag=='g' and e.get('class') in ('node','edge'):
   titles=[x.text or '' for x in e if x.tag.rsplit('}',1)[-1]=='title']
   if len(titles)!=1:raise ValueError('svg_role_missing_title')
   if e.get('class')=='node':
    if titles[0] in nodes:raise ValueError('svg_role_duplicate_node')
    nodes[titles[0]]=e
   else:edges.append((titles[0],e))
  elif tag=='g' and e.get('class','') not in ('','graph'):raise ValueError('svg_role_nested_or_unknown_class')
 if not nodes or not edges:raise ValueError('svg_no_explicit_graphviz_roles')
 def signature(e):
  arr=[]
  for n in e.iter():
   tag=n.tag.rsplit('}',1)[-1]
   if tag in ('title','desc'):continue
   attrs=[]
   for k,v in sorted(n.attrib.items()):
    if k in ('id','class'):continue
    if k in ('d','points','x','y','cx','cy','rx','ry','width','height','transform','viewBox'):v=re.sub(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?','N',v)
    attrs.append((k,v))
   arr.append([tag,attrs,bool((n.text or '').strip())])
  return arr
 g=nx.MultiDiGraph();add(g,'ROOT','svg_graphviz_roles',{})
 for name,e in nodes.items():add(g,('n',name),'node',signature(e));link(g,'ROOT',('n',name),'node')
 def terminal(name):
  if name in nodes:return name,''
  found=[n for n in nodes if name.startswith(n+':')]
  if len(found)!=1:raise ValueError('svg_terminal_ambiguous')
  return found[0],name[len(found[0])+1:]
 for i,(title,e) in enumerate(edges):
  parts=re.split(r'->|--',title)
  if len(parts)!=2:raise ValueError('svg_edge_title_unsupported')
  a,pa=terminal(parts[0]);b,pb=terminal(parts[1]);k=('e',i);add(g,k,'edge',[signature(e),bool('->' in title),pa,pb]);link(g,('n',a),k,'source');link(g,k,('n',b),'target')
 return 'direct_svg_graphviz_roles_v1',g,{'nodes':len(nodes),'edges':len(edges),'role_topology_complete':True,'geometry_numbers_normalized_for_conservative_family':True}

class HTMLGraph(HTMLParser):
 def __init__(self):super().__init__();self.g=nx.MultiDiGraph();self.stack=[];self.tags=[];self.ids={};self.classes={};self.css=[];self.in_style=False;self.issues=[];self.counter=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','canvas','iframe','object','embed'):self.issues.append('html_dynamic_or_embedded_program')
  key=self.counter;self.counter+=1;values=[]
  for k,v in attrs:
   if k.startswith('on'):self.issues.append('html_event_handler')
   if k=='id':v=self.ids.setdefault(v,'id'+str(len(self.ids)))
   elif k=='class':v=' '.join(self.classes.setdefault(x,'class'+str(len(self.classes))) for x in (v or '').split())
   elif k in ('src','href','alt','title','value'):v='<ASSET_OR_TEXT>'
   values.append((k,v))
  add(self.g,key,'html_'+tag,sorted(values))
  if self.stack:link(self.g,self.stack[-1],key,'child:'+str(sum(1 for _ in self.g.out_edges(self.stack[-1]))))
  if tag not in ('img','br','hr','meta','link','input','source','wbr','area','base','col','param','track'):self.stack.append(key);self.tags.append(tag)
  self.in_style=tag=='style' or self.in_style
 def handle_endtag(self,tag):
  if tag=='style':self.in_style=False
  if tag in self.tags:
   while self.tags:
    last=self.tags.pop();self.stack.pop()
    if last==tag:break
 def handle_startendtag(self,tag,attrs):
  self.handle_starttag(tag,attrs)
  if tag not in ('img','br','hr','meta','link','input','source','wbr','area','base','col','param','track'):self.handle_endtag(tag)
 def handle_data(self,data):
  if self.in_style:self.css.append(data)
  elif data.strip() and self.stack:
   key=self.counter;self.counter+=1;add(self.g,key,'text',{'present':True});link(self.g,self.stack[-1],key,'textchild')
def html_ir(code):
 p=HTMLGraph();p.feed(code);p.close()
 if p.issues:raise ValueError(p.issues[0])
 if not p.g:raise ValueError('html_no_DOM')
 css='\n'.join(p.css)
 if re.search(r'@import|expression\s*\(|javascript:',css,re.I):raise ValueError('html_external_or_dynamic_CSS')
 for name,alias in sorted(p.ids.items(),key=lambda x:-len(x[0])):css=css.replace('#'+name,'#'+alias)
 for name,alias in sorted(p.classes.items(),key=lambda x:-len(x[0])):css=re.sub(r'\.'+re.escape(name)+r'(?![\w-])','.'+alias,css)
 add(p.g,'CSS','css_heuristic',re.sub(r'\s+',' ',re.sub(r'/\*.*?\*/','',css,flags=re.S)).strip())
 return 'html_poster_DOM_CSS_heuristic_v1',p.g,{'heuristic':True,'unknown_boundaries':['computed CSS/layout','font shaping','asset completeness','paint overlap and clipping'],'DOM_objects':p.counter,'not_source_execution_or_compiler_success':True}

def tikz_body(code):
 s=re.sub(r'(?<!\\)%[^\n]*','',code)
 if re.search(r'\\(?:foreach|def|newcommand|renewcommand|input|include|tikzset|tikzstyle|addplot)\b',s):raise ValueError('tikz_dynamic_macro_or_external')
 a=list(re.finditer(r'\\begin\{tikzpicture\}',s));b=list(re.finditer(r'\\end\{tikzpicture\}',s))
 if len(a)!=1 or len(b)!=1:raise ValueError('tikz_requires_one_picture')
 return s[a[0].end():b[0].start()].strip()
def closed_basic(code):
 body=tikz_body(code)
 if body.startswith('['):
  level=0;end=None
  for i,c in enumerate(body):
   level+=c=='[';level-=c==']'
   if not level:end=i+1;break
  if end is None:raise ValueError('tikz_options_unclosed')
  globalstyle=body[:end];body=body[end:].strip()
 else:globalstyle=''
 statements=[x.strip() for x in body.split(';') if x.strip()]
 if not statements:raise ValueError('tikz_no_closed_paint')
 g=nx.MultiDiGraph();add(g,'ROOT','tikz_closed_static',globalstyle)
 number=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)';point=r'\(\s*'+number+r'\s*,\s*'+number+r'\s*\)'
 for i,s in enumerate(statements):
  if not re.fullmatch(r'\\(?:draw|fill|filldraw|path)(?:\[[^\[\]{}]*\])?\s*'+point+r'\s*(?:(?:rectangle|ellipse|circle)\s*(?:'+point+r'|\('+number+r'\))|(?:--\s*'+point+r'\s*)+--\s*cycle)',s):raise ValueError('tikz_not_literal_closedbasic')
  add(g,('p',i),'closed_basic_primitive',re.sub(r'\s+',' ',s));link(g,'ROOT',('p',i),'paint')
 return 'tikz_literal_closedbasic_inventory_v1',g,{'static_only':True,'closed_basic_primitives':len(statements),'source_compilation_proven':False}
def tikz(code,parser):
 try:
  ir=parser.parse_literal(code)
  body=tikz_body(code)
  # Identity/text-normalized literal program, with actual endpoint/anchor graph.
  for name,label in sorted(ir['nodes'].items(),key=lambda x:-len(x[0])):
   body=body.replace('{'+label+'}','{TEXT}');body=re.sub(r'(?<![\w-])'+re.escape(name)+r'(?![\w-])','ID',body)
  for e in ir['edges']:
   if e.get('label'):body=body.replace('{'+e['label']+'}','{TEXT}')
  ir2={'nodes':[{'id':k,'shape':'literal_named'} for k in ir['nodes']],'edges':ir['edges'],'program_shape_style_geometry':re.sub(r'\s+',' ',body),'parser':ir['parser']}
  unit,g,info=_flat_graph(ir2,'tikz_literal_named_graph_inventory_v1');info.update(static_only=True,source_compilation_proven=False,named_straight=all(e['route']=='--' for e in ir['edges']));return unit,g,info
 except ValueError:return closed_basic(code)

def partial_key(code,fmt):
 # Actual source object counts only; never generic wrapper-token similarity.
 try:
  if fmt in ('drawio','svg'):
   r=E.fromstring(code);tags=collections.Counter(x.tag.rsplit('}',1)[-1] for x in r.iter());roles=collections.Counter(x.get('class','') for x in r.iter() if x.tag.rsplit('}',1)[-1]=='g');return sha(raw([fmt,sorted(tags.items()),sorted(roles.items())]))
  if fmt=='tikz':return sha(raw([fmt,len(re.findall(r'\\node\b',code)),len(re.findall(r'\\draw\b',code)),len(re.findall(r'\\path\b',code))]))
 except Exception:pass
 return None
