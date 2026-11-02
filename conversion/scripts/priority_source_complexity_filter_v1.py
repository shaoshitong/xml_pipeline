"""Static, remote-only source curation. Never execute source or read image payloads.
Four fixed workers; all output files contain only locators, hashes and derived metadata.
"""
import ast,base64,collections,concurrent.futures,datetime,hashlib,html,json,os,re,sqlite3,time,urllib.parse,zlib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
import pyarrow.parquet as pq
R=Path('/backup/shaoshitong/img2code_20261029')
RUN=R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources'
CAP=64*1024*1024
SOURCES={'yashengsun--SciDiagramRevision','VincentHancoder--RAP','miracle10--DwT_drawio','QijiaHe--VFIG-Data','nllg--DaTikZ-V4','ChartMimic--ChartMimic','CSU-JPG--Chart2Code'}
OLDER=['manifests/nllg--datikz-v3.jsonl','manifests/nllg--datikz.jsonl']
POLICY=R/'clean/complexity_curation_20261102T054553Z_v1/policy.json'
def dumps(d):return json.dumps(d,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def cleantext(s):return ' '.join(re.sub('<[^>]+>',' ',html.unescape(str(s))).split())
def labels_features(labels):
 labels=[cleantext(s) for s in labels if cleantext(s)];distinct=sorted(set(labels))
 panels=set()
 for label in distinct:
  m=re.match(r'^\s*\(?([a-lA-L])\)?[.)\s:]?(?:$|\s)',label)
  if m and (len(label)<100) and (len(label)>1 or label.lower() in 'abcdef'):panels.add(m.group(1).lower())
 return {'owner_label_count':len(labels),'distinct_owner_labels':len(distinct),'label_characters':sum(map(len,distinct)),'source_panel_label_clues':len(panels)}
def xml_local(e):return e.tag.rsplit('}',1)[-1]
def bounded_inflate(payload):
 dec=zlib.decompressobj(-15);b=dec.decompress(base64.b64decode(payload),CAP+1)
 if len(b)>CAP or dec.unconsumed_tail:raise ValueError('decoded_page_exceeds_64MiB_review_limit')
 return urllib.parse.unquote(b.decode('utf-8'))
def native(text):
 root=ET.fromstring(text);pages=[]
 if xml_local(root)=='mxfile':
  for d in root.findall('diagram'):
   m=d.find('mxGraphModel')
   if m is not None:pages.append(m)
   elif (d.text or '').strip():pages.append(ET.fromstring(bounded_inflate(d.text.strip())))
 else:pages=[root]
 cells=[]
 for p in pages:
  # Wrapper UserObject/object labels belong to their child mxCell.
  for e in p.iter():
   if xml_local(e) in ('object','UserObject'):
    c=e.find('mxCell')
    if c is not None and not c.get('value'):c.set('value',e.get('label') or e.get('value') or '')
  cells.extend(p.iter('mxCell'))
 vs=[c for c in cells if c.get('vertex')=='1'];es=[c for c in cells if c.get('edge')=='1'];ids={c.get('id') for c in vs}
 valid=[c for c in es if c.get('source') in ids and c.get('target') in ids and c.get('source')!=c.get('target')]
 conn={c.get(k) for c in valid for k in ('source','target')};deg=collections.Counter(c.get(k) for c in valid for k in ('source','target'))
 children=collections.defaultdict(list)
 for c in vs:children[c.get('parent')].append(c.get('id'))
 groups=[c.get('id') for c in vs if len(children[c.get('id')])>=2]
 images=[c for c in vs if 'image=' in c.get('style','') or 'shape=image' in c.get('style','')]
 f={'parser':'native_drawio_connected_structure_v1','native_pages':len(pages),'native_vertices':len(vs),'native_edges':len(es),'connected_edges':len(valid),'source_backed_logical_nodes':len(conn),'native_connected_groups':sum(sum(x in conn for x in children[g])>=2 for g in groups),'meaningful_groups':len(groups),'image_objects':len(images),'collapsed_drawing_objects':len(vs),'directed_chain_only':bool(conn) and len(valid)==len(conn)-1 and max(deg.values(),default=0)<=2,'topology_claim':'native connected vertices only; unconnected decoration excluded from logical nodes'}
 f.update(labels_features([c.get('value','') for c in vs]));return f
class HTMLFacts(HTMLParser):
 def __init__(self):
  super().__init__();self.ignore=0;self.labels=[];self.chunks=[];self.tags=collections.Counter();self.images=[];self.layout=0;self.stack=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs);self.tags[tag]+=1;self.stack.append(tag)
  if tag in ('script','style'):self.ignore+=1
  if tag=='img' and a.get('src'):self.images.append(a['src'])
  style=a.get('style','')
  if re.search(r'(?:display\s*:\s*(?:grid|flex)|grid-template|position\s*:\s*absolute|column-count)',style):self.layout+=1
  if tag in ('div','p','li','h1','h2','h3','h4','h5','h6','section','article','figcaption','td','th'):self.flush()
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.ignore=max(0,self.ignore-1)
  if tag in ('div','p','li','h1','h2','h3','h4','h5','h6','section','article','figcaption','td','th'):self.flush()
 def handle_data(self,s):
  if not self.ignore:self.chunks.append(s)
 def flush(self):
  t=' '.join(' '.join(self.chunks).split());self.chunks=[]
  if t:self.labels.append(t)
def html_features(text,path):
 p=HTMLFacts();p.feed(text);p.flush();f={'parser':'html_text_assets_layout_v1','image_objects':len(p.images),'distinct_image_references':len(set(p.images)),'section_elements':p.tags['section']+p.tags['article'],'heading_elements':sum(p.tags['h'+str(i)] for i in range(1,7)),'source_layout_containers':p.layout,'embedded_svg_elements':p.tags['svg'],'collapsed_drawing_objects':p.tags['img']+p.tags['svg']+p.tags['table'],'logical_graph_nodes':'unavailable_from_html_surface'}
 f.update(labels_features(p.labels))
 missing=[];local=0;embedded=0;external=0
 for s in sorted(set(p.images)):
  if s.startswith('data:'):embedded+=1
  elif s.startswith(('http:','https:','//')):external+=1
  elif path:
   local+=1;z=(path.parent/urllib.parse.unquote(s.split('#')[0].split('?')[0])).resolve()
   if not z.is_file():missing.append(s)
 f.update(asset_reference_count_local=local,asset_reference_count_embedded=embedded,asset_reference_count_external=external,missing_local_asset_count=len(missing),asset_check='existence only, no image payload read');return f

def svg_features(text):
 root=ET.fromstring(text);els=list(root.iter());labs=[];parents={c:p for p in els for c in p};groups=[]
 for e in els:
  tag=xml_local(e)
  if tag=='text':labs.append(' '.join(e.itertext()))
  elif tag=='foreignObject':labs.append(' '.join(e.itertext()))
  elif tag=='g':groups.append(e)
 f={'parser':'svg_semantic_text_image_panel_v1','image_objects':sum(xml_local(e)=='image' for e in els),'svg_text_elements':sum(xml_local(e)=='text' for e in els),'foreign_object_elements':sum(xml_local(e)=='foreignObject' for e in els),'collapsed_drawing_objects':sum(xml_local(e) in ('rect','circle','ellipse','polygon','polyline','line','foreignObject','image') for e in els),'path_or_use_present':any(xml_local(e) in ('path','use') for e in els),'meaningful_groups':sum(sum(xml_local(x) in ('text','foreignObject','image') for x in list(e))>=2 for e in groups),'logical_graph_nodes':'unavailable_from_svg_surface; glyph/path counts excluded'}
 f.update(labels_features(labs))
 content=root.get('content')
 if content:
  for _ in range(3):
   if '<mxfile' in content or '<mxGraphModel' in content:break
   content=html.unescape(urllib.parse.unquote(content))
  try:f['embedded_native_graph']=native(content)
  except Exception as e:f['embedded_native_parse_error']=type(e).__name__
 return f
PLOT={'plot','scatter','bar','barh','hist','hist2d','pie','boxplot','violinplot','errorbar','fill_between','fill_betweenx','imshow','pcolor','pcolormesh','contour','contourf','stem','step','stackplot','quiver','streamplot','hexbin','eventplot','broken_barh','plot_surface','plot_wireframe','plot_trisurf'}
def name(n):
 if isinstance(n,ast.Name):return n.id
 if isinstance(n,ast.Attribute):return name(n.value)+'.'+n.attr
 if isinstance(n,ast.Subscript):return name(n.value)+'['+ast.dump(n.slice,include_attributes=False)+']'
 return ''
def number(n):
 if isinstance(n,ast.Constant) and isinstance(n.value,int) and not isinstance(n.value,bool):return n.value
 return None
def chart_features(text):
 tree=ast.parse(text);calls=[];dynamic=0;inactive=0;defined_calls=0;axes_bounds=[];axis_receivers=set();axes_decls=[]
 class Visitor(ast.NodeVisitor):
  def __init__(self):self.ambiguous=0;self.in_def=0
  def visit_FunctionDef(self,n):
   nonlocal defined_calls
   defined_calls+=sum(isinstance(x,ast.Call) and name(x.func).split('.')[-1] in PLOT for x in ast.walk(n))
  visit_AsyncFunctionDef=visit_FunctionDef
  def visit_ClassDef(self,n):self.visit_FunctionDef(n)
  def visit_If(self,n):
   # A literal false branch is not active; main guard counts as script entry.
   if isinstance(n.test,ast.Constant):
    for s in (n.body if n.test.value else n.orelse):self.visit(s)
   elif isinstance(n.test,ast.Compare) and any(isinstance(x,ast.Constant) and x.value=='__main__' for x in ast.walk(n.test)):
    for s in n.body:self.visit(s)
   else:
    self.ambiguous+=1
    for s in n.body+n.orelse:self.visit(s)
    self.ambiguous-=1
  def visit_For(self,n):
   nonlocal dynamic
   dynamic+=1;self.ambiguous+=1;self.generic_visit(n);self.ambiguous-=1
  visit_AsyncFor=visit_For;visit_While=visit_For;visit_ListComp=visit_For;visit_SetComp=visit_For;visit_DictComp=visit_For;visit_GeneratorExp=visit_For
  def visit_Call(self,n):
   fn=name(n.func);m=fn.split('.')[-1];recv=fn.rsplit('.',1)[0] if '.' in fn else ''
   if m in PLOT:calls.append((m,recv,self.ambiguous,ast.dump(n,include_attributes=False)));axis_receivers.add(recv)
   if m=='subplots' and not self.ambiguous:
    vals={k.arg:number(k.value) for k in n.keywords};r=number(n.args[0]) if n.args else vals.get('nrows',1);c=number(n.args[1]) if len(n.args)>1 else vals.get('ncols',1)
    if r and c and 0<r*c<=1000:axes_bounds.append(r*c)
   if m in ('subplot','add_subplot') and not self.ambiguous:
    args=[number(x) for x in n.args]
    if args and all(x is not None for x in args):axes_decls.append((m,tuple(args)))
   self.generic_visit(n)
 Visitor().visit(tree)
 direct=[c for c in calls if not c[2]];methods=sorted({c[0] for c in direct});distinct_calls=len({c[3] for c in direct});recv=sorted({c[1] for c in direct if c[1]})
 # Separate constant subplot declarations are evidence of realized layout, not definition bodies.
 axes=max(axes_bounds+[len(set(axes_decls)),1])
 f={'parser':'python_ast_active_script_chart_evidence_v1','constant_subplot_axes_lower_bound':axes,'direct_plot_call_sites':len(direct),'distinct_direct_plot_call_sites':distinct_calls,'direct_plot_methods':methods,'direct_plot_receivers':len(recv),'ambiguous_plot_call_sites':len(calls)-len(direct),'unexecuted_definition_plot_calls_excluded':defined_calls,'dynamic_loop_or_comprehension_constructs':dynamic,'execution_performed':False,'series_claim':'direct top-level active-script call sites only; method calls in definitions/ambiguous branches are not realized series'}
 return f

def tikz_features(text):
 t=re.sub(r'(?m)(?<!\\)%.*$','',text)
 named=set(re.findall(r'\\node(?:\s*\[[^\]]*\])?\s*\(([^)]+)\)',t));labels=[]
 for m in re.finditer(r'\\node\b[^;]*;',t,flags=re.S):
  s=m.group();pos=s.rfind('{');end=s.rfind('}')
  if pos>=0 and end>pos:labels.append(re.sub(r'\\[A-Za-z]+',' ',s[pos+1:end]))
 edges=re.findall(r'\(([^)]+)\)\s*(?:--|edge(?:\s*\[[^\]]*\])?)\s*\(([^)]+)\)',t)
 edges=[(a,b) for a,b in edges if a in named and b in named and a!=b];conn={x for e in edges for x in e};macro=bool(re.search(r'\\(?:def|gdef|edef|newcommand|renewcommand|DeclareRobustCommand|input|include|foreach)\b',t))
 f={'parser':'tikz_explicit_constructs_static_v1','explicit_named_nodes':len(named),'source_backed_logical_nodes':len(conn),'explicit_named_edges':len(edges),'node_construct_sites':len(re.findall(r'\\node\b|(?<![\\\w])node\s*(?:\[|\(|\{)',t)),'draw_or_path_command_sites':len(re.findall(r'\\(?:draw|path|filldraw)\b',t)),'macro_or_loop_expansion_required':macro,'has_plot_or_axis':bool(re.search(r'\\(?:addplot|begin\{axis\}|begin\{groupplot\})',t)),'image_objects':len(re.findall(r'\\includegraphics\b',t)),'meaningful_groups':len(re.findall(r'\\begin\{scope\}',t)),'logical_graph_caution':'Only explicit named connected nodes/edges counted; macros and loops are not executed'}
 f.update(labels_features(labels));return f

def classify(f,fmt,d):
 if d.get('structurally_complete') is False:return 'incomplete',['manifest_structurally_incomplete']
 if f.get('missing_local_asset_count',0):return 'incomplete',['missing_referenced_local_html_assets']
 if fmt=='python':
  if f['constant_subplot_axes_lower_bound']>=2:return 'complex_candidate',['multiple_constant_subplot_axes_in_active_script']
  if f['distinct_direct_plot_call_sites']>=3:return 'complex_candidate',['multiple_distinct_direct_chart_calls_static_evidence']
  if len(f['direct_plot_methods'])>=2 and f['distinct_direct_plot_call_sites']>=2:return 'complex_candidate',['combined_chart_methods_in_active_script']
  if f['ambiguous_plot_call_sites'] or f['dynamic_loop_or_comprehension_constructs'] or (not f['direct_plot_call_sites']):return 'structure_review',['dynamic_or_indirect_chart_construction_unexecuted']
  return 'simple_deprioritized',['single_axes_few_direct_plot_calls_static_evidence']
 g=f.get('embedded_native_graph',f);n=g.get('source_backed_logical_nodes',0);edges=g.get('connected_edges',g.get('explicit_named_edges',0));chars=g.get('label_characters',0);clusters=g.get('native_connected_groups',0)
 if n>=20 and edges>=15 and chars>=200 and not g.get('directed_chain_only'):return 'complex_candidate',['rich_source_backed_connected_graph']
 if n>=30 and chars>=200:return 'complex_candidate',['large_source_backed_connected_graph']
 if n>=12 and edges>=12 and clusters>=2 and chars>=250:return 'complex_candidate',['clustered_source_backed_graph']
 im=f.get('image_objects',0);chars=f.get('label_characters',0);labels=f.get('distinct_owner_labels',0)
 if im>=8 and chars>=400:return 'complex_candidate',['rich_labeled_image_composite']
 if im>=4 and chars>=200 and labels>=8:return 'complex_candidate',['labeled_image_composite']
 if fmt=='html' and chars>=1000 and im>=3 and labels>=8:return 'complex_candidate',['complex_reconstructed_poster_template']
 if fmt=='html':
  if chars>=1000 and labels>=8 and (f.get('heading_elements',0)>=4 or f.get('source_layout_containers',0)>=3):return 'complex_candidate',['rich_text_multisection_reconstructed_poster_layout']
  return 'structure_review',['poster_template_layout_requires_visual_review']
 if fmt=='tikz':
  if f.get('macro_or_loop_expansion_required'):return 'structure_review',['tikz_macro_or_loop_expansion_unresolved']
  if labels>=20 and chars>=350:return 'structure_review',['dense_tikz_explicit_labels_static_review']
  if f.get('node_construct_sites',0)<=5 and f.get('draw_or_path_command_sites',0)<=8 and not f.get('has_plot_or_axis'):return 'simple_deprioritized',['few_explicit_tikz_constructs_no_detected_dynamic_expansion']
  return 'structure_review',['tikz_semantic_structure_requires_review']
 if labels>=20 and chars>=350 and (f.get('collapsed_drawing_objects',0)>=25 or f.get('source_panel_label_clues',0)>=2 or f.get('meaningful_groups',0)>=2):return 'structure_review',['structurally_dense_labeled_drawing_not_graph_certified']
 if f.get('source_panel_label_clues',0)>=2 and labels>=8:return 'structure_review',['source_backed_multi_panel_label_clues']
 if fmt=='svg' and (f.get('embedded_native_parse_error') or (f.get('path_or_use_present') and labels<4)):return 'structure_review',['svg_surface_or_outlined_text_insufficient_for_simple_decision']
 if fmt=='drawio' and g.get('native_vertices',0)>=12:return 'structure_review',['native_objects_without_rich_connected_graph_threshold']
 if labels<12 and chars<200 and f.get('collapsed_drawing_objects',0)<25 and im<3:return 'simple_deprioritized',['small_labeled_source_surface_static_evidence']
 return 'structure_review',['insufficient_semantic_structure_for_complex_or_simple_decision']

def locator(d):
 return {k:d.get(k) for k in ('clean_file','clean_row','code_key','image_key','code_file','image_file','reference_image','asset_root','original_poster','panel_assets','source_file','source_row','raw_file','raw_row','source_manifest','source_manifest_line') if d.get(k) is not None}
def process(task):
 d=task['row'];loc=task['locator'];c={'id':d['pair_sha256'],'source':d['source'],'category':d['category'],'source_format':d['format'],'source_locator':loc,'code_sha256_manifest':d.get('code_sha256'),'image_sha256_manifest':d.get('image_sha256'),'pair_dedup_key':sha((str(d.get('code_sha256'))+'|'+str(d.get('image_sha256'))).encode()),'aliases':task['aliases'],'provenance':{k:d.get(k) for k in ('catalog_kind','pairing','pairing_evidence','image_provenance','gold_code_provenance','code_provenance','provenance','alignment_verification','code_execution_checked','structurally_complete') if d.get(k) is not None},'conversion_qualification':'not_assessed_by_source_curation'}
 if d['source']=='VincentHancoder--RAP':c['reference_kind']='reconstructed_template_render_and_editable_html; original_poster_is_auxiliary'
 else:c['reference_kind']='dataset_selected_complete_source_and_paired_image'
 try:
  raw=task.get('raw');p=None
  if raw is None:
   p=R/loc['resolved_source_code'];size=p.stat().st_size
   if size>CAP:c.update(status='structure_review',reasons=['source_above_64MiB_requires_explicit_review'],source_bytes=size,read_status='not_read_over_cap');return c
   raw=p.read_bytes()
  if isinstance(raw,str):raw=raw.encode('utf-8')
  if len(raw)>CAP:c.update(status='structure_review',reasons=['source_above_64MiB_requires_explicit_review'],source_bytes=len(raw),read_status='parquet_value_over_cap');return c
  c.update(source_bytes=len(raw),source_code_sha256_observed=sha(raw),read_status='read_code_only')
  c['source_hash_matches_manifest']=not d.get('code_sha256') or sha(raw)==d['code_sha256']
  if not c['source_hash_matches_manifest']:c.update(status='incomplete',reasons=['source_code_hash_mismatch']);return c
  text=raw.decode('utf-8');fmt=d['format']
  f=native(text) if fmt=='drawio' else svg_features(text) if fmt=='svg' else html_features(text,p) if fmt=='html' else chart_features(text) if fmt=='python' else tikz_features(text) if fmt=='tikz' else {'parser':'unsupported'}
  c['features']=f;c['status'],c['reasons']=classify(f,fmt,d)
 except Exception as e:c.update(status='incomplete' if isinstance(e,(OSError,KeyError,UnicodeDecodeError)) else 'structure_review',reasons=['source_unavailable' if isinstance(e,(OSError,KeyError)) else 'source_static_parse_error'],error=type(e).__name__+':'+str(e)[:180])
 return c

def write_json(path,d):path.write_text(dumps(d)+'\n')
def main():
 started=time.monotonic();RUN.mkdir(parents=True,exist_ok=False);rows=[];outside=[];inventory=collections.Counter();manifest_sha=hashlib.sha256()
 with (R/'release/manifest.jsonl').open('rb') as f:
  for lineno,b in enumerate(f,1):
   manifest_sha.update(b);d=json.loads(b);s=d.get('source','')
   if s not in SOURCES:continue
   inventory[(s,d['category'])]+=1;d['_release_line']=lineno
   if s=='nllg--DaTikZ-V4' and d['category']!='scientific_diagram':outside.append(d);continue
   rows.append(d)
 extra_hashes={}
 for n in OLDER:
  data=(R/n).read_bytes();extra_hashes[n]=sha(data)
  for lineno,b in enumerate(data.splitlines(),1):
   d=json.loads(b);inventory[(d['source'],d['category'])]+=1;d.setdefault('source_manifest',n);d.setdefault('source_manifest_line',lineno)
   d.setdefault('pair_sha256',sha((d['source']+'|'+d['code_sha256']+'|'+d['image_sha256']).encode()));d['_id_kind']='source_manifest_id' if 'pair_sha256' in json.loads(b) else 'generated_source_plus_code_image_sha256'
   if d['category']=='scientific_diagram':rows.append(d)
   else:outside.append(d)
 # Canonical chosen by V4 priority, then release row, then older version order.
 order={'nllg--DaTikZ-V4':0,'nllg--datikz-v3':1,'nllg--datikz':2}
 rows.sort(key=lambda d:(order.get(d['source'],0),d['source'],d['pair_sha256']))
 groups=collections.OrderedDict()
 for d in rows:groups.setdefault((d.get('code_sha256'),d.get('image_sha256')),[]).append(d)
 db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=10)
 tasks=[];fallback=collections.defaultdict(list);aliases=[]
 for rr in groups.values():
  d=rr[0];ls=locator(d);als=[{'id':x['pair_sha256'],'id_kind':x.get('_id_kind','release_pair_sha256'),'source':x['source'],'source_locator':locator(x)} for x in rr[1:]]
  # Indexed lookup once per canonical selected ID only, no broad DB scans.
  hit=db.execute('select input_manifest from jobs where id=?',(d['pair_sha256'],)).fetchone()
  if hit and hit[0]:
   m=json.loads(hit[0]);ls.update({('resolved_'+k if k in ('source_code','reference_image') else 'canonical_'+k):v for k,v in m.items() if k in ('source_code','reference_image','asset_root','panel_assets') and v is not None})
  if not ls.get('resolved_source_code') and d.get('code_file'):ls['resolved_source_code']=d['code_file']
  task={'row':d,'locator':ls,'aliases':als}
  if ls.get('resolved_source_code'):tasks.append(task)
  elif d.get('clean_file') and d.get('code_key'):fallback[d['clean_file']].append(task)
  else:tasks.append(task)
  for x in rr:aliases.append({'input_id':x['pair_sha256'],'input_source':x['source'],'input_id_kind':x.get('_id_kind','release_pair_sha256'),'canonical_id':d['pair_sha256'],'code_sha256':d.get('code_sha256'),'image_sha256':d.get('image_sha256'),'dedup_basis':'exact_code_sha256_and_image_sha256','source_locator':locator(x)})
 db.close();results=[];read_fallback_files=0;read_fallback_columns=set()
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for c in pool.map(process,tasks):results.append(c)
  for file,tt in sorted(fallback.items()):
   # Only requested code columns, never image/panel/binary columns. Read needed row groups once.
   pf=pq.ParquetFile(R/file);bygroup=collections.defaultdict(list);bounds=[];start=0
   for gi in range(pf.num_row_groups):end=start+pf.metadata.row_group(gi).num_rows;bounds.append((start,end));start=end
   for t in tt:
    ix=int(t['row']['clean_row']);gi=next(g for g,(a,b) in enumerate(bounds) if a<=ix<b);bygroup[gi].append(t)
   read_fallback_files+=1
   for gi,ts in bygroup.items():
    cols=sorted({t['row']['code_key'] for t in ts});read_fallback_columns.update(cols);table=pf.read_row_group(gi,columns=cols,use_threads=False);start=bounds[gi][0]
    for t in ts:t['raw']=table[t['row']['code_key']][int(t['row']['clean_row'])-start].as_py();t['locator']['code_only_parquet_row_group']=gi
    results.extend(pool.map(process,ts))
   print(dumps({'progress':'parquet_code_only_file_complete','file':file,'rows':len(tt)}),flush=True)
 results.sort(key=lambda c:(c['source'],c['id']));aliasmap={x['input_id']:x for x in aliases};bystatus=collections.Counter(c['status'] for c in results);bysource=collections.defaultdict(collections.Counter);reason=collections.Counter()
 out=RUN/'index.jsonl'
 with out.open('w') as f:
  for c in results:f.write(dumps(c)+'\n');bysource[c['source']][c['status']]+=1;reason.update(c['reasons'])
 with (RUN/'input_aliases.jsonl').open('w') as f:
  for x in sorted(aliases,key=lambda x:(x['input_source'],x['input_id'])):f.write(dumps(x)+'\n')
 with (RUN/'outside_primary_scope_inventory.jsonl').open('w') as f:
  for d in sorted(outside,key=lambda d:(d['source'],d['pair_sha256'])):f.write(dumps({'id':d['pair_sha256'],'source':d['source'],'category':d['category'],'code_sha256':d.get('code_sha256'),'image_sha256':d.get('image_sha256'),'source_locator':locator(d),'status':'inventory_only_outside_primary_scientific_diagram_scope','payload_read':False})+'\n')
 for status in ('complex_candidate','structure_review','simple_deprioritized','incomplete'):
  with (RUN/(status+'.jsonl')).open('w') as f:
   for c in results:
    if c['status']==status:f.write(dumps(c)+'\n')
 reps=[]
 for source in sorted(bysource):
  for status in ('complex_candidate','structure_review','simple_deprioritized','incomplete'):
   cc=[c for c in results if c['source']==source and c['status']==status]
   cc.sort(key=lambda c:(-c.get('features',{}).get('label_characters',0),c['id']))
   for c in cc[:2]:reps.append(c)
 write_json(RUN/'representatives.json',reps)
 files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(RUN.iterdir()) if p.is_file()}
 summary={'schema':'priority_source_complexity_curation_v1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_rows':len(rows),'unique_code_image_pairs':len(results),'alias_rows_removed_from_unique_index':len(rows)-len(results),'input_alias_mapping_rows':len(aliases),'status_counts':dict(bystatus),'by_source':{k:dict(v) for k,v in sorted(bysource.items())},'reason_counts':dict(reason),'input_inventory_source_category':{s+'|'+c:n for (s,c),n in sorted(inventory.items())},'outside_primary_scope_inventory_rows':len(outside),'input_release_manifest_sha256':manifest_sha.hexdigest(),'older_manifest_sha256':extra_hashes,'code_fallback_parquet_files':read_fallback_files,'code_fallback_parquet_columns':sorted(read_fallback_columns),'workers':4,'source_bytes_limit':CAP,'source_bytes_read':sum(c.get('source_bytes',0) for c in results if c.get('read_status')=='read_code_only'),'code_hash_mismatch_rows':sum(c.get('source_hash_matches_manifest') is False for c in results),'parse_or_read_error_rows':sum('error' in c for c in results),'boundaries':{'images_read':0,'source_payload_exported':False,'source_execution':False,'render_or_model_calls':0,'conversions':0,'sqlite_read_only_per_selected_id':True,'existing_pair_or_qualification_indices_changed':False},'files':files,'seconds':time.monotonic()-started}
 write_json(RUN/'summary.json',summary);print(dumps(summary),flush=True)
if __name__=='__main__':main()
