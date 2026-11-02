"""Precommit a metadata-only, unseen, grouped heldout; never run conversion/QA.

Only this sampler's new release files are written. Both input SQLite databases
are opened mode=ro. Raw source code is read on HKUST solely for hashing and
structural fingerprints and is never included in an output manifest.
"""
import argparse,ast,base64,collections,datetime,hashlib,heapq,html,json,os,re,sqlite3,urllib.parse,uuid,xml.etree.ElementTree as ET,zlib
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path('/backup/shaoshitong/img2code_20261029')
SEED='hkust-img2code-heldout-20261101-v1'
METHOD='metadata_source_structure_group_holdout_v2_locator_corrected'
MAX_CODE=4*1024*1024
HEX=re.compile(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])')
NUM=re.compile(r'(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
COLOR=re.compile(r'#[0-9a-fA-F]{3,8}\b')
STRUCTURAL={'shape','endArrow','startArrow','arrowhead','arrowtail','dir','rankdir','style','fontFamily','fontname','display','position','overflow','text-anchor','dominant-baseline','stroke-linecap','stroke-linejoin'}
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def rank(*parts):return sha(raw([SEED,*parts]))
def scalar(value):
 value=COLOR.sub('<COLOR>',str(value))
 return re.sub(r'\s+',' ',NUM.sub('<N>',value)).strip()
def style(value):
 pairs=[]
 for part in str(value).split(';'):
  if not part:continue
  if '=' in part:key,v=part.split('=',1)
  elif ':' in part:key,v=part.split(':',1)
  else:pairs.append((part,''));continue
  pairs.append((key,scalar(v)))
 return sorted(pairs)
def expanded_xml(code):
 root=ET.fromstring(code)
 if root.tag.rsplit('}',1)[-1]=='mxfile':
  for page in root.findall('diagram'):
   if len(page):continue
   content=(page.text or '').strip()
   if not content:raise ValueError('empty_drawio_page')
   if not content.startswith('<'):
    decoder=zlib.decompressobj(-15);content=decoder.decompress(base64.b64decode(content),MAX_CODE+1)
    if len(content)>MAX_CODE or not decoder.eof:raise ValueError('compressed_drawio_page_too_large')
    content=urllib.parse.unquote(content.decode())
   page.text=None;page.append(ET.fromstring(content))
 return root
class HtmlStructure(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.events=[];self.in_style=0;self.ids={};self.classes={}
 def handle_starttag(self,tag,attrs):
  values=[]
  for k,v in attrs:
   if v is None:values.append((k,None));continue
   if k=='id':v=self.ids.setdefault(v,'id'+str(len(self.ids)))
   elif k=='class':v=' '.join(self.classes.setdefault(x,'class'+str(len(self.classes))) for x in v.split())
   elif k=='style':v=style(v)
   elif k in ('src','href','alt','title','value','placeholder'):v='<ASSET_OR_TEXT>'
   else:v=scalar(v)
   values.append((k,v))
  self.events.append(('start',tag,sorted(values)));self.in_style+=tag=='style'
 def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
 def handle_endtag(self,tag):self.events.append(('end',tag));self.in_style=max(0,self.in_style-(tag=='style'))
 def handle_data(self,data):
  if not data.strip():return
  if self.in_style:
   css=scalar(re.sub(r'/\*.*?\*/','',data,flags=re.S))
   css=re.sub(r'#([A-Za-z_]\w*)',lambda m:'#'+self.ids.setdefault(m[1],'id'+str(len(self.ids))),css)
   css=re.sub(r'\.([A-Za-z_]\w*)',lambda m:'.'+self.classes.setdefault(m[1],'class'+str(len(self.classes))),css)
   self.events.append(('css',css))
  else:self.events.append(('text','<TEXT>'))
def html_structure(code):
 p=HtmlStructure();p.feed(code);p.close()
 if not any(x[0]=='start' for x in p.events):raise ValueError('html_has_no_elements')
 return p.events
def xml_structure(code):
 root=expanded_xml(code);nodes=list(root.iter())
 if len(nodes)>100000:raise ValueError('too_many_xml_nodes')
 ids={n.attrib['id']:'id'+str(i) for i,n in enumerate(nodes) if 'id' in n.attrib}
 def walk(n):
  attrs=[]
  for k,v in sorted(n.attrib.items()):
   name=k.rsplit('}',1)[-1]
   if name in ('id','parent','source','target'):v=ids.get(v,'unknown_ref')
   elif name=='value':
    v=html_structure(html.unescape(v)) if '<' in html.unescape(v) else '<TEXT>'
   elif name in ('name','label','title','aria-label'):v='<TEXT>'
   elif name=='style':v=style(v)
   elif name in ('d','points'):v=re.sub(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?','<N>',v)
   elif name in ('href','src'):
    v=ids.get(v[1:],'unknown_ref') if v.startswith('#') else '<ASSET>'
   else:
    v=re.sub(r'url\(#([^)]*)\)',lambda m:'url('+ids.get(m[1],'unknown_ref')+')',v);v=scalar(v)
   attrs.append((name,v))
  tag=n.tag.rsplit('}',1)[-1]
  text=None
  if (n.text or '').strip():text=scalar(n.text) if tag=='style' else '<TEXT>'
  return (tag,attrs,text,[walk(c) for c in n])
 return walk(root)
DOT_TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|->|--|[A-Za-z_][\w.]*|[-+]?\d+(?:\.\d*)?|[{}\[\];,:=<>]')
def dot_structure(code):
 code=re.sub(r'/\*.*?\*/|//[^\n]*','',code,flags=re.S);tokens=DOT_TOKEN.findall(code)
 if not re.search(r'\b(?:di)?graph\b',code) or code.count('{')!=code.count('}') or '{' not in code:raise ValueError('unparsed_embedded_dot')
 names={};result=[];bracket=0
 reserved={'strict','digraph','graph','subgraph','node','edge'}
 for i,t in enumerate(tokens):
  if t=='[':bracket+=1
  if t==']':bracket-=1
  if t in reserved or t in '{}[];,:=<>->--':result.append(t);continue
  previous=tokens[i-1] if i else '';following=tokens[i+1] if i+1<len(tokens) else ''
  if following=='=':result.append(t);continue
  if previous=='=':
   key=tokens[i-2] if i>1 else ''
   result.append(scalar(t.strip('"')) if key in STRUCTURAL else '<VALUE>');continue
  if bracket:result.append('<VALUE>');continue
  result.append(names.setdefault(t,'n'+str(len(names))))
 if bracket:raise ValueError('unbalanced_dot_attributes')
 return result
class PythonStructure(ast.NodeTransformer):
 def __init__(self,tree):
  local=list(dict.fromkeys(n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)))
  self.locals={n:'var'+str(i) for i,n in enumerate(local)};self.graph_names={}
 def graph_id(self,s):return self.graph_names.setdefault(s,'node'+str(len(self.graph_names)))
 def visit_Name(self,node):
  if node.id in self.locals:node.id=self.locals[node.id]
  return node
 def visit_Constant(self,node):
  v=node.value
  if isinstance(v,str):
   if re.search(r'\b(?:di)?graph\s+(?:\w+\s*)?\{',v):node.value='DOT:'+json.dumps(dot_structure(v),separators=(',',':'))
   elif v.lstrip().startswith(('<svg','<mxfile','<mxGraphModel')):node.value='XML:'+sha(raw(xml_structure(v)))
   else:node.value='<STR>'
  elif isinstance(v,bytes):node.value=b'<BYTES>'
  elif isinstance(v,(int,float,complex)) and not isinstance(v,bool):node.value=0
  return node
 def visit_JoinedStr(self,node):
  if any(isinstance(v,ast.Constant) and isinstance(v.value,str) and re.search(r'\b(?:di)?graph\b',v.value) for v in node.values):raise ValueError('dynamic_embedded_graph_template_unknown')
  return self.generic_visit(node)
 def visit_Call(self,node):
  originals=[n.value if isinstance(n,ast.Constant) and isinstance(n.value,str) else None for n in node.args]
  original_keywords={k.arg:k.value.value for k in node.keywords if isinstance(k.value,ast.Constant) and isinstance(k.value.value,str)};method=node.func.attr if isinstance(node.func,ast.Attribute) else ''
  node=self.generic_visit(node)
  n=1 if method=='node' else 2 if method=='edge' else 0
  for i in range(min(n,len(originals))):
   old=originals[i]
   if old is not None:node.args[i]=ast.Constant(self.graph_id(old))
  for keyword in node.keywords:
   old=original_keywords.get(keyword.arg)
   if keyword.arg in STRUCTURAL and old is not None:keyword.value=ast.Constant(scalar(old))
  return node
def python_structure(code):
 tree=ast.parse(code)
 if len(list(ast.walk(tree)))>100000:raise ValueError('too_many_python_nodes')
 return ast.dump(PythonStructure(tree).visit(tree),include_attributes=False)
def lexical_structure(code,fmt):
 # Conservative grouping, not a semantic parser or proof of generator identity.
 if fmt=='mermaid':
  if not re.search(r'(?im)^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|mindmap|gantt|journey)\b',code):raise ValueError('unrecognized_mermaid_grammar')
  code=re.sub(r'(?m)%%.*$','',code)
 elif fmt=='plantuml':
  if '@start' not in code:raise ValueError('unrecognized_plantuml_grammar')
  code=re.sub(r"(?m)^\s*'.*$",'',code)
 elif fmt=='tikz':
  if '\\begin{tikzpicture}' not in code and '\\tikz' not in code:raise ValueError('unrecognized_tikz_grammar')
  code=re.sub(r'(?m)(?<!\\)%.*$','',code)
 else:raise ValueError('unsupported_template_format')
 code=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'','<TEXT>',code)
 names={}
 if fmt=='tikz':
  code=re.sub(r'\(([A-Za-z_][\w:-]*)\)',lambda m:'('+names.setdefault(m[1],'id'+str(len(names)))+')',code)
  code=re.sub(r'\{([^{}\\]*)\}',lambda m:m[0] if m[1] in ('tikzpicture','document','axis','scope') else '{<TEXT>}',code)
 else:
  reserved={'graph','flowchart','LR','RL','TD','TB','BT','node','subgraph','end','class','classDef','style','linkStyle','state','note','as','participant','actor','sequenceDiagram','classDiagram','stateDiagram','stateDiagram-v2','erDiagram','mindmap','gantt','journey','startuml','enduml','start','stop','if','then','else','endif','rectangle','package','interface','usecase','entity','component','database','skinparam','title'}
  code=re.sub(r'\b[A-Za-z_][\w-]*\b',lambda m:m[0] if m[0] in reserved else names.setdefault(m[0],'id'+str(len(names))),code)
 return scalar(code)
def fingerprint(code,fmt):
 try:
  if len(code.encode())>MAX_CODE:raise ValueError('source_exceeds_template_budget')
  if fmt in ('drawio','xml','svg'):structure=xml_structure(code);certainty='parsed_structure'
  elif fmt=='html':structure=html_structure(code);certainty='parsed_structure'
  elif fmt=='python':structure=python_structure(code);certainty='parsed_structure'
  else:structure=lexical_structure(code,fmt);certainty='recognized_conservative_lexical_structure'
  return {'template_family':fmt+':'+sha(raw(structure)),'template_status':certainty,'template_method':METHOD}
 except Exception as e:return {'template_family':None,'template_status':'template_unknown','template_reason':str(e)[:300],'template_method':METHOD}
def source_fingerprint(root,identifier,expected,fmt,database=None):
 p=Path(root)/'conversion/inputs'/identifier[:2]/identifier/'source.txt'
 resolution='standard_verified'
 try:
  try:
   target=p.resolve(strict=True)
   if target.stat().st_size>MAX_CODE:raise OverflowError('source_exceeds_template_budget')
   if sha(target.read_bytes())!=expected:raise ValueError('standard_source_sha256_mismatch')
  except (OSError,ValueError):
   if database is None:raise
   row=database.execute('select input_manifest from jobs where id=?',(identifier,)).fetchone()
   if not row or not row[0]:raise ValueError('authoritative_source_locator_unavailable')
   manifest=json.loads(row[0]);locator=Path(manifest['source_code'])
   if manifest.get('code_sha256')!=expected or manifest.get('id')!=identifier:raise ValueError('authoritative_source_manifest_identity_mismatch')
   if locator.is_absolute() or '..' in locator.parts:raise ValueError('invalid_authoritative_source_locator')
   p=Path(root)/locator;target=p.resolve(strict=True);resolution='authoritative_input_manifest_verified'
  if not target.is_relative_to(Path(root).resolve()):raise ValueError('source_outside_data_root')
  if target.stat().st_size>MAX_CODE:raise ValueError('source_exceeds_template_budget')
  b=target.read_bytes()
  if sha(b)!=expected:raise ValueError('source_sha256_mismatch')
  return {**fingerprint(b.decode(),fmt),'source_locator':str(p.relative_to(root)),'verified_source_sha256':expected,'source_locator_resolution':resolution}
 except Exception as e:return {'template_family':None,'template_status':'template_unknown','template_reason':str(e)[:300],'source_locator':str(p.relative_to(root)),'template_method':METHOD}
def reservoir(rows,limit):
 # Fixed hash bottom-k, independent of input ordering and any validation result.
 heaps=collections.defaultdict(list)
 for row in rows:
  key=row['stratum'];score=int(rank('reservoir',key,row['id']),16);item=(-score,row['id'],row);heap=heaps[key]
  if len(heap)<limit:heapq.heappush(heap,item)
  elif item>heap[0]:heapq.heapreplace(heap,item)
 return {k:[x[2] for x in sorted(h,key=lambda x:-x[0])] for k,h in heaps.items()}
def balanced_groups(rows,limit):
 by_provider=collections.defaultdict(list)
 for row in rows:by_provider[row['provider']].append(row)
 for provider in by_provider:by_provider[provider].sort(key=lambda x:rank('family',x['stratum'],x['template_family'],x['id']))
 providers=sorted(by_provider,key=lambda p:rank('provider',p));used=set();selected=[]
 while len(selected)<limit:
  progressed=False
  for provider in providers:
   queue=by_provider[provider]
   while queue and queue[0]['template_family'] in used:queue.pop(0)
   if queue and len(selected)<limit:
    row=queue.pop(0);selected.append(row);used.add(row['template_family']);progressed=True
  if not progressed:break
 return selected
def artifact_paths(work):
 paths=set()
 patterns=['*handoff*.json','*smoke*.json','*pilot*.json','*research*manifest*.json','*review*.json','prototype/*/*handoff*.json','prototype/*/*manifest*.json','prototype/*/*smoke*.json','prototype/*/*pilot*.json','prototype/*/*/*handoff*.json']
 for pattern in patterns:paths.update(Path(work).glob(pattern))
 paths.add(Path(work)/'round2_font_repair_v1/handoff.json')
 return sorted(p for p in paths if p.is_file())
def bounded_round2_artifacts(root,universe):
 """IDs/metadata only; stop below an ID directory, never walk font/media trees."""
 root=Path(root);work=root/'conversion';namespaces=[p for p in work.glob('round2_*') if p.is_dir()]
 namespaces.extend([work/'auto_quality_font_repair_v1/round2_v1',work/'auto_quality_canvas_repair_v1/round2_v1'])
 seen=collections.defaultdict(set);files=set();visited=0;limited=False
 for namespace in sorted(set(namespaces)):
  if not namespace.exists():continue
  stack=[(namespace,0)]
  while stack:
   path,depth=stack.pop();visited+=1
   if visited>10000:limited=True;stack=[];break
   ids=set(HEX.findall(path.name))&universe
   if ids:
    for i in ids:seen[i].add('explicit_round2_artifact_directory:'+str(path.relative_to(root)))
    continue
   try:children=sorted(path.iterdir(),key=lambda p:p.name)
   except OSError:continue
   for child in children:
    if child.is_file() and child.suffix=='.json':files.add(child)
    elif child.is_dir() and not child.is_symlink() and depth<5:stack.append((child,depth+1))
 return seen,files,{'directory_limit_reached':limited,'visited_directories':visited,'maximum_depth':5}
def metadata_for(db,identifier):
 row=db.execute('select source,input_record from jobs where id=?',(identifier,)).fetchone()
 if row is None:raise ValueError('missing_original_source_metadata:'+identifier)
 source=json.loads(row[1]);return row[0],source
def write_frozen(path,blob):
 path=Path(path)
 with path.open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 path.chmod(0o444)
 return {'file':path.name,'sha256':sha(blob),'bytes':len(blob)}
def correct_frozen_locators(root,old_output,output):
 """Correct metadata only on the already committed oversample; no new IDs."""
 root=Path(root).resolve();old_output=Path(old_output).resolve();output=Path(output).resolve()
 if not old_output.is_relative_to(root/'release/round2_heldout_v1') or not output.is_relative_to(root/'release/round2_heldout_v1'):raise ValueError('locator_correction_outside_owned_root')
 if old_output==output:raise ValueError('retain_original_sampling_audit')
 output.mkdir(parents=True,exist_ok=True)
 if any((output/p).exists() for p in ['protocol.json','manifest.jsonl','selection.json']):raise ValueError('corrected_sampling_already_frozen')
 complete=json.loads((old_output/'SAMPLING_COMPLETE.json').read_bytes())
 for f in complete['files']:
  if sha((old_output/f['file']).read_bytes())!=f['sha256']:raise ValueError('old_frozen_sampling_file_changed')
 old_protocol=json.loads((old_output/'protocol.json').read_bytes());old_summary=json.loads((old_output/'selection.json').read_bytes())
 old_manifest=[json.loads(x) for x in (old_output/'manifest.jsonl').read_text().splitlines()];old_ids={r['id'] for r in old_manifest}
 exclusions=[json.loads(x) for x in (old_output/'exclusions.jsonl').read_text().splitlines()]
 candidates=[json.loads(x) for x in (old_output/'oversample.jsonl').read_text().splitlines()]
 universe={}
 with (root/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl').open() as f:
  for line in f:r=json.loads(line);universe[r['id']]=r
 db=sqlite3.connect('file:'+str(root/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=30);families=set();new_exclusions=[];new_candidates=[];selected=[];strata={}
 second=root/'release/round2_fixed_v1/repair_pass_20261101_0627';ledger=sqlite3.connect('file:'+str(second/'status.sqlite')+'?mode=ro',uri=True,timeout=30)
 try:
  stale={'template_family','template_status','template_reason','template_method','source_locator','verified_source_sha256','source_locator_resolution'}
  for r in exclusions:
   u=universe[r['id']];fp=source_fingerprint(root,r['id'],r['source_code_sha256'],u['format'],db);item={**{k:v for k,v in r.items() if k not in stale},**fp};new_exclusions.append(item)
   if fp['template_family']:families.add(fp['template_family'])
  by_stratum=collections.defaultdict(list)
  for r in candidates:
   fp=source_fingerprint(root,r['id'],r['source']['code_sha256'],r['source']['format'],db);item={**{k:v for k,v in r.items() if k not in stale},**fp}
   if not fp['template_family']:item['selection_disposition']='template_unknown'
   elif fp['template_family'] in families:item['selection_disposition']='development_template_overlap'
   else:item['selection_disposition']='eligible_known_structure';by_stratum[r['stratum']].append(item)
   new_candidates.append(item)
  for stratum,old_stats in sorted(old_summary['strata'].items()):
   pool=by_stratum[stratum];n=old_protocol['families_per_stratum']
   # Non-HTML IDs remain frozen; newly detected leakage can only remove them.
   # HTML previously had no selected IDs, so choose from the SAME150 committed
   # candidates after correcting authoritative source locators. No reservoir rerun.
   if stratum.startswith('html|'):chosen=balanced_groups(pool,n)
   else:chosen=[r for r in pool if r['id'] in old_ids]
   for r in chosen:
    state=ledger.execute('select source,first_result,attempts,status from samples where id=?',(r['id'],)).fetchone()
    if not state or state[2:]!=(0,'queued'):raise ValueError('frozen_candidate_was_dispatched_before_validation')
    if json.loads(state[0])!=r['source'] or sha(state[1].encode())!=r['first_result_sha256']:raise ValueError('frozen_candidate_source_or_first_result_changed')
    selected.append({**r,'first_result':json.loads(state[1])})
   same=[r for r in new_candidates if r['stratum']==stratum]
   strata[stratum]={**old_stats,'template_unknown':sum(r['template_status']=='template_unknown' for r in same),'development_family_overlap':sum(r['selection_disposition']=='development_template_overlap' for r in same),'available_distinct_structure_families':len({r['template_family'] for r in pool}),'selected':len(chosen),'selected_providers':dict(collections.Counter(r['provider'] for r in chosen)),'low_evidence':len(chosen)<n}
 finally:db.close();ledger.close()
 if len({r['id'] for r in selected})!=len(selected) or any(r['template_family'] in families for r in selected):raise ValueError('corrected_holdout_leakage')
 for path,h in old_protocol.get('implementation_pins',{}).items():
  if sha(Path(path).read_bytes())!=h:raise ValueError('original_comparison_implementation_changed')
 protocol={**old_protocol,'method':METHOD,'created_at':now(),'sampler_sha256':sha(Path(__file__).read_bytes()),'metadata_locator_correction':{'previous_directory':str(old_output),'previous_protocol_sha256':sha((old_output/'protocol.json').read_bytes()),'previous_manifest_sha256':sha((old_output/'manifest.jsonl').read_bytes()),'oversample_candidate_ids_unchanged':True,'random_reservoir_not_rerun':True,'conversion_outcomes_not_viewed':True},'requires_provenance_or_cluster_audit_before_rollout':True,'automatic_rollout_permitted':False,'template_families_are_statistically_independent':False,'development_unfingerprinted':sum(r['template_family'] is None for r in new_exclusions),'family_measurement':'Distinct heuristic source-structure fingerprints; not statistical independence. Thresholds remain exploratory until provenance/cluster audit.'}
 files=[write_frozen(output/'population.jsonl',(old_output/'population.jsonl').read_bytes())]
 for name,rows in [('exclusions.jsonl',new_exclusions),('oversample.jsonl',new_candidates),('manifest.jsonl',sorted(selected,key=lambda r:(r['stratum'],rank('selected_order',r['id']))))]:files.append(write_frozen(output/name,b''.join(raw(r) for r in rows)))
 files.append(write_frozen(output/'protocol.json',raw(protocol)))
 summary={'at':now(),'method':METHOD,'seed':SEED,'heldout_samples':len(selected),'queued_population':old_summary['queued_population'],'development_ids_excluded':len(exclusions),'strata':strata,'files':list(files),'manifest':str(output/'manifest.jsonl'),'protocol':str(output/'protocol.json'),'sampling_only_no_results_viewed':True,'requires_provenance_or_cluster_audit_before_rollout':True,'automatic_rollout_permitted':False,'residual_template_risk':True,'model_calls':0,'metadata_locator_correction_from':str(old_output)}
 files.append(write_frozen(output/'selection.json',raw(summary)));write_frozen(output/'SAMPLING_COMPLETE.json',raw({'files':files,'manifest_sha256':next(x['sha256'] for x in files if x['file']=='manifest.jsonl'),'at':now()}));return summary
def select(root,second,output,target_n=30,oversample_n=150,extra_exclusions=()):
 root=Path(root).resolve();second=Path(second).resolve();output=Path(output).resolve();work=root/'conversion'
 if target_n<1 or oversample_n<target_n:raise ValueError('invalid_precommitted_sample_sizes')
 if not output.is_relative_to(root/'release/round2_heldout_v1'):raise ValueError('sampling_output_outside_owned_heldout_root')
 output.mkdir(parents=True,exist_ok=True)
 if any((output/x).exists() for x in ['protocol.json','manifest.jsonl','selection.json','population.jsonl']):raise ValueError('sampling_already_frozen_do_not_resample')
 if json.loads((second/'control.json').read_bytes()).get('stop_dispatch') is not True:raise ValueError('second_round_must_stop_dispatch_before_selection')
 universe={}
 with (root/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl').open() as f:
  for line in f:
   r=json.loads(line);universe[r['id']]=r
 if len(universe)!=131904:raise ValueError('original_universe_mismatch')
 d=sqlite3.connect('file:'+str(second/'status.sqlite')+'?mode=ro',uri=True,timeout=30)
 try:
  d.execute('begin')
  if d.execute('select count(*) from samples where status="running"').fetchone()[0]:raise ValueError('second_round_inflight_cases_must_finish_before_freeze')
  rows=d.execute('select seq,id,source,first_result,initial_actions,attempts,status from samples order by seq').fetchall();d.rollback()
 finally:d.close()
 seen=collections.defaultdict(set);artifact_evidence=[];universe_ids=set(universe)
 for seq,identifier,s,first,actions,attempts,state in rows:
  if attempts>0:seen[identifier].add('second_round_dispatched')
 directory_ids,round2_files,directory_scan=bounded_round2_artifacts(root,universe_ids)
 for identifier,reasons in directory_ids.items():seen[identifier].update(reasons)
 paths=artifact_paths(work)+list(round2_files)+[second/'preflight_ids.json',second/'preflight_receipt.json']+[Path(p) for p in extra_exclusions]
 for path in sorted(set(paths)):
  if not path.exists():continue
  size=path.stat().st_size
  if size>16*1024*1024:artifact_evidence.append({'file':str(path),'skipped':'artifact_over_16MiB','bytes':size});continue
  blob=path.read_bytes();found=set(HEX.findall(blob.decode(errors='replace')))&universe_ids
  for identifier in found:seen[identifier].add(str(path.relative_to(root)) if path.is_relative_to(root) else str(path))
  artifact_evidence.append({'file':str(path),'sha256':sha(blob),'bytes':size,'seen_ids':len(found)})
 excluded_code={universe[i]['source_code_sha256'] for i in seen};excluded_image={universe[i]['source_image_sha256'] for i in seen};population=[];raw_first={};counts=collections.Counter();eligible=[]
 for seq,identifier,s,first,actions,attempts,state in rows:
  if attempts or state!='queued':continue
  source=json.loads(s);actions=json.loads(actions)
  if not actions:continue
  u=universe[identifier]
  if seq!=u['seq'] or (source['code_sha256'],source['image_sha256'],source['format'],source['category'])!=(u['source_code_sha256'],u['source_image_sha256'],u['format'],u['category']):raise ValueError('population_source_identity_mismatch')
  stratum=source['format']+'|'+actions[0];counts[stratum]+=1
  row={'id':identifier,'seq':seq,'source':source,'stratum':stratum,'initial_actions':actions,'first_result_sha256':sha(first.encode())};population.append(row);raw_first[identifier]=first
  if identifier in seen:continue
  if source['code_sha256'] in excluded_code or source['image_sha256'] in excluded_image:continue
  eligible.append(row)
 pools=reservoir(eligible,oversample_n);dev_families=set();exclusions=[]
 for identifier in sorted(seen):
  u=universe[identifier];fp=source_fingerprint(root,identifier,u['source_code_sha256'],u['format'])
  if fp['template_family']:dev_families.add(fp['template_family'])
  exclusions.append({'id':identifier,'source_code_sha256':u['source_code_sha256'],'source_image_sha256':u['source_image_sha256'],'reasons':sorted(seen[identifier]),**fp})
 db=sqlite3.connect('file:'+str(work/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);candidates=[];chosen=[];strata={}
 try:
  for stratum,pool in sorted(pools.items()):
   valid=[];unknown=0;dev_overlap=0
   for original in pool:
    row=dict(original);source=row['source'];provider,old=metadata_for(db,row['id'])
    if (old.get('pair_sha256'),old.get('code_sha256'),old.get('image_sha256'),old.get('format'),old.get('category'))!=(row['id'],source['code_sha256'],source['image_sha256'],source['format'],source['category']):raise ValueError('provider_metadata_source_mismatch')
    fp=source_fingerprint(root,row['id'],source['code_sha256'],source['format']);row.update(provider=provider,**fp)
    if fp['template_family'] is None:row['selection_disposition']='template_unknown';unknown+=1
    elif fp['template_family'] in dev_families:row['selection_disposition']='development_template_overlap';dev_overlap+=1
    else:row['selection_disposition']='eligible_known_structure';valid.append(row)
    candidates.append(row)
   selection=balanced_groups(valid,target_n)
   for row in selection:chosen.append({**row,'first_result':json.loads(raw_first[row['id']])})
   strata[stratum]={'population_queued':counts[stratum],'after_exact_id_code_image_exclusions':sum(r['stratum']==stratum for r in eligible),'oversampled':len(pool),'template_unknown':unknown,'development_family_overlap':dev_overlap,'available_distinct_structure_families':len({r['template_family'] for r in valid}),'selected':len(selection),'selected_providers':dict(collections.Counter(r['provider'] for r in selection)),'low_evidence':len(selection)<target_n}
 finally:db.close()
 if len({r['id'] for r in chosen})!=len(chosen):raise ValueError('duplicate_heldout_id')
 if any(r['id'] in seen or r['source']['code_sha256'] in excluded_code or r['source']['image_sha256'] in excluded_image or r['template_family'] in dev_families for r in chosen):raise ValueError('heldout_development_leakage')
 implementation=json.loads((second/'launch_receipt.json').read_bytes()).get('pins',{})
 for path,h in implementation.items():
  if sha(Path(path).read_bytes())!=h:raise ValueError('frozen_implementation_changed:'+path)
 protocol={'method':METHOD,'seed':SEED,'created_at':now(),'input_universe':131904,'population_scope':'Frozen round2 queued attempts=0 only; future first-round intakes are not automatically covered.','stratification':'format x first initial repair action; source-provider-balanced selection within a fixed hash bottom-k oversample','families_per_stratum':target_n,'oversample_per_stratum':oversample_n,'unknown_templates_count_as_independent':False,'sampling_has_viewed_no_heldout_outcomes':True,'success_gate_precommitted':{'minimum_independent_structure_families':30,'minimum_full_qualified_incremental':3,'wilson95_lower_bound_greater_than':0.01,'old_success_control_regression_allowed':False,'negative_control_false_accept_allowed':False,'infrastructure_errors_allowed':False},'sampler_sha256':sha(Path(__file__).read_bytes()),'implementation_pins':implementation,'artifact_exclusion_scan':artifact_evidence,'bounded_round2_artifact_scan':directory_scan,'development_ids':len(seen),'development_unfingerprinted':sum(x['template_family'] is None for x in exclusions),'limitations':['Structural fingerprints are a heuristic proxy, not proof of procedural-template or generator independence.','Mermaid/PlantUML/TikZ use explicitly labelled conservative lexical structure; residual hidden-template leakage remains possible.','Python dynamic embedded graph payloads, invalid syntax, missing/oversized/changed sources are template_unknown and excluded.','Provider diversity is balanced only among the precommitted150 oversampled candidates, so rare providers can be absent.','No unweighted or population-weighted global yield claim is justified from provider-balanced/template-capped samples without the corresponding inclusion weights.','Default metadata scan is bounded to named pilot/smoke/handoff/review files; skipped artifacts and all known explicit cohort files must be checked in this protocol or supplied through --exclude-file.','Any inspected heldout is spent: changing code, thresholds or sample membership afterwards requires a new disjoint heldout.'],'model_calls':0,'conversion_or_QA_executed':False,'old_DB_or_ledger_written':False}
 files=[]
 for name,items in [('population.jsonl',population),('exclusions.jsonl',exclusions),('oversample.jsonl',candidates),('manifest.jsonl',sorted(chosen,key=lambda x:(x['stratum'],rank('selected_order',x['id']))))]:files.append(write_frozen(output/name,b''.join(raw(x) for x in items)))
 files.append(write_frozen(output/'protocol.json',raw(protocol)))
 summary={'at':now(),'method':METHOD,'seed':SEED,'heldout_samples':len(chosen),'queued_population':len(population),'development_ids_excluded':len(seen),'strata':strata,'files':list(files),'manifest':str(output/'manifest.jsonl'),'protocol':str(output/'protocol.json'),'sampling_only_no_results_viewed':True,'model_calls':0,'residual_template_risk':True}
 files.append(write_frozen(output/'selection.json',raw(summary)));write_frozen(output/'SAMPLING_COMPLETE.json',raw({'files':files,'manifest_sha256':next(x['sha256'] for x in files if x['file']=='manifest.jsonl'),'at':now()}));return summary
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default=str(ROOT));p.add_argument('--second-run',default='repair_pass_20261101_0627');p.add_argument('--run-id',required=True);p.add_argument('--per-stratum',type=int,default=30);p.add_argument('--oversample',type=int,default=150);p.add_argument('--exclude-file',action='append',default=[]);p.add_argument('--correct-from');a=p.parse_args()
 if any(not x or not all(c.isalnum() or c in '-_' for c in x) for x in [a.run_id,a.second_run]):p.error('invalid run ID')
 root=Path(a.root).resolve()
 if a.correct_from:result=correct_frozen_locators(root,root/'release/round2_heldout_v1'/a.correct_from,root/'release/round2_heldout_v1'/a.run_id)
 else:result=select(root,root/'release/round2_fixed_v1'/a.second_run,root/'release/round2_heldout_v1'/a.run_id,a.per_stratum,a.oversample,a.exclude_file)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
