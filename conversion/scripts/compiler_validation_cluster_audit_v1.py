"""Read-only source/provenance audit. Never executes source, compiler, QA or models.

Creates only new compiler_validation_* metadata files. Frozen v2 is never changed.
The candidate pool remains unconsumed. A source skeleton cluster is an operational
leakage unit, not a claim of generator independence or a population yield sample.
"""
import argparse, ast, collections, hashlib, importlib.util, json, math, re, sqlite3, sys
import xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
OLD=R/'release/round2_heldout_v1/unseen_protocol_20261101_v2'
SEED='hkust-compiler-cluster-audit-20261101-v1'
MIN_SIM=.85
MAX_CODE=4*1024*1024
HEX=re.compile(r'^[0-9a-f]{64}$')
def blob(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def tokens(s):return re.findall(r'[A-Za-z_][\w.-]*|--?>|[{}\[\]();,:=<>/\\*+!?-]',s)
def shingles(ts):
 if len(ts)>40000:raise ValueError('audit_token_budget')
 # Removing adjacent exact repeated tokens and repeated statements intentionally
 # overclusters variable-length generated lists rather than claiming independence.
 ts=[x for i,x in enumerate(ts) if i==0 or x!=ts[i-1]]
 return frozenset(sha(blob(ts[i:i+3]))[:16] for i in range(max(1,len(ts)-2)))
def norm_text(s):
 s=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',' TEXT ',s)
 s=re.sub(r'#[0-9a-fA-F]{3,8}\b',' COLOR ',s)
 return re.sub(r'(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',' N ',s)
class ProgramSkeleton(ast.NodeTransformer):
 def visit_alias(self,n):
  if n.asname is not None:n.asname='ALIAS'
  return n
 def visit_Name(self,n):return ast.copy_location(ast.Name(id='IDENT',ctx=n.ctx),n)
 def visit_arg(self,n):n.arg='ARG';return n
 def visit_FunctionDef(self,n):n.name='FUNCTION';return self.generic_visit(n)
 def visit_Constant(self,n):
  n.value='TEXT' if isinstance(n.value,(str,bytes)) else 0 if isinstance(n.value,(int,float,complex)) else n.value
  return n
 def visit_List(self,n):
  if all(isinstance(x,(ast.Constant,ast.List,ast.Tuple)) for x in n.elts):n.elts=[ast.Constant('DATA')];return n
  return self.generic_visit(n)
 visit_Tuple=visit_List
 def visit_Dict(self,n):
  if all(isinstance(x,ast.Constant) for x in n.values):n.keys=[ast.Constant('KEY')];n.values=[ast.Constant('DATA')];return n
  return self.generic_visit(n)
def tree_skeleton(code,fmt,oldmod):
 if fmt=='python':return ast.dump(ProgramSkeleton().visit(ast.parse(code)),include_attributes=False)
 if fmt in ('svg','drawio','xml'):
  root=oldmod.expanded_xml(code)
  def walk(n):
   attrs=[]
   for k,v in sorted(n.attrib.items()):
    k=k.rsplit('}',1)[-1]
    if k in ('id','source','target','parent','name','value','label','title','aria-label','href','src'):v='REF_OR_TEXT'
    elif k=='style':v=oldmod.style(v)
    else:v=oldmod.scalar(v)
    attrs.append((k,v))
   children=[walk(c) for c in n]
   # Repeated equal children are one generator operation plus a repetition flag.
   children=list(dict.fromkeys(json.dumps(x,sort_keys=True) for x in children))
   return (n.tag.rsplit('}',1)[-1],attrs,'TEXT' if (n.text or '').strip() else None,children)
  return json.dumps(walk(root),sort_keys=True)
 if fmt=='html':
  events=oldmod.html_structure(code)
  # Normalize text/classes/IDs a second time and ignore multiplicities in repeated
  # element/style events: conservative DOM-program family, not content identity.
  rows=[]
  for e in events:
   s=re.sub(r'(?:class|id)\d+','IDENT',json.dumps(e,sort_keys=True))
   if s not in rows:rows.append(s)
  return '\n'.join(rows)
 if fmt in ('mermaid','plantuml'):
  s=norm_text(code)
  s=re.sub(r'(?m)^\s*%%.*$|^\s*\'.*$','',s)
  # All labels normalize completely, including unquoted variable-length labels.
  s=re.sub(r'\[([^\[\]]*)\]','[TEXT]',s)
  s=re.sub(r'\|[^|\n]*\|','|TEXT|',s)
  s=re.sub(r':[^\n]*',':TEXT',s)
  reserved={'graph','flowchart','TB','TD','BT','LR','RL','subgraph','end','class','classDef','style','linkStyle','click','component','rectangle','node','database','cloud','queue','interface','as','startuml','enduml','participant','actor','note','left','right','of','package','skinparam','title','if','else','endif','start','stop','sequenceDiagram','classDiagram','stateDiagram','erDiagram','gantt','mindmap','journey','TEXT','N','COLOR'}
  s=re.sub(r'\b[A-Za-z_][\w-]*\b',lambda m:m[0] if m[0] in reserved else 'IDENT',s)
  lines=sorted(set(re.sub(r'\s+',' ',x).strip() for x in s.splitlines() if x.strip()))
  return '\n'.join(lines)
 raise ValueError('unaudited_format')
def feature_group(code,fmt):
 if fmt=='mermaid':
  h=re.sub(r'(?m)^\s*%%.*$','',code).lstrip();m=re.match(r'(graph|flowchart)\s+(TB|TD|BT|LR|RL)\b',h)
  if m:
   blocks=re.findall(r'(?im)^\s*(subgraph|classDef|class|style|linkStyle|click|direction)\b|%%\{|^---',code)
   return 'mermaid_flowchart',{'header':m[1],'direction':m[2],'advanced_statements':sum(bool(x) for x in blocks),'html':bool(re.search(r'</?[A-Za-z]',code))}
  m=re.match(r'([A-Za-z][\w-]*)',h);return 'mermaid_other',{'dialect':m[1] if m else 'unknown'}
 if fmt=='plantuml':
  if re.search(r'(?im)^\s*(component|rectangle|node|database|cloud|queue|interface)\b|^\s*\[[^\]]+\]\s+as\b',code):return 'plantuml_component',{'nested':bool(re.search(r'(?im)^\s*(package|folder|frame)\b',code))}
  if re.search(r'(?im)^\s*(class|abstract\s+class|enum)\b',code):return 'plantuml_class',{}
  if re.search(r'(?im)^\s*(participant|actor)\b',code):return 'plantuml_sequence',{}
  return 'plantuml_other',{}
 if fmt=='python':
  t=ast.parse(code);imports=sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)}|{a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names})
  return ('python_graphviz' if any('graphviz' in x for x in imports) else 'python_matplotlib' if any('matplotlib' in x for x in imports) else 'python_other'),{'imports':imports}
 if fmt=='svg':
  rt=ET.fromstring(code);tags=sorted({n.tag.rsplit('}',1)[-1] for n in rt.iter()});return 'svg_scene',{'tags':tags,'foreignObject':'foreignObject' in tags,'raster':'image' in tags}
 if fmt=='html':return 'html_dom',{'javascript':bool(re.search(r'<script\b',code,re.I)),'canvas':bool(re.search(r'<canvas\b',code,re.I))}
 return 'native_drawio',{}
class DSU:
 def __init__(self,n):self.p=list(range(n))
 def find(self,x):
  while x!=self.p[x]:self.p[x]=self.p[self.p[x]];x=self.p[x]
  return x
 def union(self,x,y):
  a,b=self.find(x),self.find(y)
  if a!=b:self.p[max(a,b)]=min(a,b)
def source(root,db,identifier,expected,locator=None):
 p=root/(locator or ('conversion/inputs/'+identifier[:2]+'/'+identifier+'/source.txt'))
 try:b=p.read_bytes()
 except OSError:b=None
 if b is None or sha(b)!=expected:
  r=db.execute('select input_manifest from jobs where id=?',(identifier,)).fetchone();m=json.loads(r[0])
  if m.get('id')!=identifier or m.get('code_sha256')!=expected:raise ValueError('source_manifest_identity')
  p=root/m['source_code'];b=p.read_bytes()
 if not p.resolve().is_relative_to(root.resolve()):raise ValueError('source_outside_root')
 if len(b)>MAX_CODE or sha(b)!=expected:raise ValueError('source_hash_or_budget')
 return b.decode(),str(p.relative_to(root))
def provenance(record,provider):
 # A tar archive/shard, split, row number or provider is not a template identity.
 ann=record.get('annotation') or {};keys=[]
 for k in ('arxiv_id','paper_id','openreview_forum_id'):
  if ann.get(k):keys.append('document:'+k+':'+sha(blob(ann[k])))
 # Only explicit source-provided template/generator identity can be such evidence.
 for obj in [record,record.get('metadata') or {},record.get('source_metadata') or {}]:
  if not isinstance(obj,dict):continue
  for k in ('generator_id','generator_family','template_id','template_family','source_document_id','original_id'):
   if obj.get(k):keys.append('provenance:'+k+':'+sha(blob([provider,obj[k]])))
 return keys

def audit(root,output,development_files=(),development_complete=False,predicate_path=None):
 root=Path(root).resolve();old=root/'release/round2_heldout_v1/unseen_protocol_20261101_v2';output=Path(output)
 if not output.is_relative_to(root/'release/compiler_validation_v1'):raise ValueError('invalid_new_output')
 output.mkdir(parents=True,exist_ok=False)
 complete=json.loads((old/'SAMPLING_COMPLETE.json').read_text())
 for f in complete['files']:
  if sha((old/f['file']).read_bytes())!=f['sha256']:raise ValueError('frozen_v2_changed')
 spec=importlib.util.spec_from_file_location('pinned_old_sampler',old/'frozen_sampler.py');oldmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(oldmod)
 candidates=[json.loads(x) for x in (old/'manifest.jsonl').read_text().splitlines()];ex=[json.loads(x) for x in (old/'exclusions.jsonl').read_text().splitlines()]
 universe={r['id']:r for r in map(json.loads,(root/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl').read_text().splitlines())}
 dev={r['id']:{**r,'role':'development'} for r in ex};newdevpins=[]
 for p in development_files:
  p=Path(p);b=p.read_bytes();newdevpins.append({'path':str(p),'sha256':sha(b)})
  for line in b.decode().splitlines():
   d=json.loads(line);i=d['id']
   if i not in universe:raise ValueError('unknown_new_development_id')
   u=universe[i]
   for k,uk in [('code_sha256','source_code_sha256'),('image_sha256','source_image_sha256')]:
    if d.get(k) and d[k]!=u[uk]:raise ValueError('new_development_sha_mismatch')
   dev.setdefault(i,{'id':i,'source_code_sha256':u['source_code_sha256'],'source_image_sha256':u['source_image_sha256'],'reasons':[],'role':'development'})['reasons'].append(d.get('reason','new_compiler_development'))
 rows=list(dev.values())+[{**r,'role':'unconsumed_candidate'} for r in candidates];ndev=len(dev)
 pred=None;predpin=None
 if predicate_path:
  pp=Path(predicate_path);ps=importlib.util.spec_from_file_location('compiler_validation_frozen_support',pp);pred=importlib.util.module_from_spec(ps);ps.loader.exec_module(pred);predpin={'path':str(pp),'sha256':sha(pp.read_bytes()),'call':'support_predicate(source,language)'}
 db=sqlite3.connect('file:'+str(root/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 aud=[];feat=[];keys={};du=DSU(len(rows));edges=[]
 try:
  for idx,r in enumerate(rows):
   u=universe[r['id']];fmt=u['format'];codehash=u['source_code_sha256'];imagehash=u['source_image_sha256'];meta=db.execute('select source,input_record from jobs where id=?',(r['id'],)).fetchone()
   provider=meta[0];record=json.loads(meta[1]);item={'id':r['id'],'role':r['role'],'format':fmt,'provider':provider,'code_sha256':codehash,'image_sha256':imagehash,'old_heuristic_family':r.get('template_family'),'old_stratum':r.get('stratum'),'provenance_keys':provenance(record,provider)}
   keylist=['code:'+codehash,'image:'+imagehash]+item['provenance_keys']
   if r.get('template_family'):keylist.append('old_family:'+r['template_family'])
   try:
    code,loc=source(root,db,r['id'],codehash,r.get('source_locator'));sk=tree_skeleton(code,fmt,oldmod);fs=shingles(tokens(sk));group,features=feature_group(code,fmt)
    item.update(source_locator=loc,source_hash_verified=True,program_skeleton_sha256=sha(sk.encode()),feature_group=group,features=features,cluster_parse_status='audited_operational_structure')
    keylist.append('skeleton:'+fmt+':'+item['program_skeleton_sha256'])
    if idx>=ndev and pred is not None and fmt in ('mermaid','plantuml'):
     support=pred.support_predicate(code,fmt);item.update(support_unit=support['unit'],supported_by_predeclared_predicate=support['supported'],support_unsupported_reasons=support.get('unsupported',[]))
   except Exception as e:item.update(source_hash_verified=False,cluster_parse_status='unknown',audit_error=str(e)[:200]);fs=frozenset()
   item['cluster_keys']=keylist;aud.append(item);feat.append(fs)
   for k in keylist:
    if k in keys:du.union(idx,keys[k]);edges.append({'left':rows[keys[k]]['id'],'right':r['id'],'evidence':k.split(':',1)[0]})
    else:keys[k]=idx
  # Exhaustive candidate-to-development/candidate set Jaccard, not probabilistic
  # MinHash. Matching is only within format; exact source/image links cross formats.
  for i in range(ndev,len(aud)):
   a=feat[i]
   if len(a)<5:continue
   for j in range(i):
    b=feat[j]
    if aud[i]['format']!=aud[j]['format'] or len(b)<5:continue
    if min(len(a),len(b))/max(len(a),len(b))<MIN_SIM:continue
    inter=len(a&b);sim=inter/(len(a)+len(b)-inter)
    if sim>=MIN_SIM:
     du.union(i,j);edges.append({'left':aud[j]['id'],'right':aud[i]['id'],'evidence':'exhaustive_normalized_trigram_jaccard','jaccard':round(sim,6)})
 finally:db.close()
 components=collections.defaultdict(list)
 for i,a in enumerate(aud):components[du.find(i)].append(i)
 for members in components.values():
  cluster='cluster:'+sha(blob(sorted(aud[i]['id'] for i in members)));leak=any(i<ndev for i in members)
  for i in members:aud[i].update(audit_cluster=cluster,development_overlap=leak,cluster_candidate_members=sum(j>=ndev for j in members),cluster_development_members=sum(j<ndev for j in members))
 outcand=[];used=set()
 for a in sorted(aud[ndev:],key=lambda a:sha(blob([SEED,a['id']]))):
  disposition='eligible_unconsumed_audited_cluster'
  if a['cluster_parse_status']=='unknown':disposition='cluster_unknown'
  elif a['development_overlap']:disposition='development_cluster_overlap'
  elif a['audit_cluster'] in used:disposition='duplicate_global_cluster'
  else:used.add(a['audit_cluster'])
  a={**a,'audit_disposition':disposition,'generator_independence_proven':False,'ready_for_validation':False};outcand.append(a)
 stats={}
 for g in sorted({a.get('feature_group','unknown') for a in outcand}):
  rs=[a for a in outcand if a.get('feature_group','unknown')==g];elig=[a for a in rs if a['audit_disposition']=='eligible_unconsumed_audited_cluster']
  stats[g]={'candidates':len(rs),'eligible_operational_clusters':len(elig),'dispositions':dict(collections.Counter(a['audit_disposition'] for a in rs)),'providers':dict(collections.Counter(a['provider'] for a in elig)),'minimum_30_clusters_met':len(elig)>=30}
 unitstats={}
 for unit in sorted({a.get('support_unit') for a in outcand if a.get('support_unit')}):
  rs=[a for a in outcand if a.get('support_unit')==unit];eligible=[a for a in rs if a['audit_disposition']=='eligible_unconsumed_audited_cluster']
  unitstats[unit]={'matched_candidates':len(rs),'eligible_operational_clusters':len(eligible),'minimum_30_clusters_met':len(eligible)>=30,'providers':dict(collections.Counter(a['provider'] for a in eligible)),'blocked_reasons':dict(collections.Counter(a['audit_disposition'] for a in rs if a not in eligible))}
 protocol={'kind':'metadata-only precompiler provenance and conservative leakage clustering','seed':SEED,'old_manifest':str(old/'manifest.jsonl'),'old_manifest_sha256':sha((old/'manifest.jsonl').read_bytes()),'sampler_sha256':sha(Path(__file__).read_bytes()),'development_roster_complete_declared':development_complete,'additional_development_files':newdevpins,'development_records':ndev,'candidate_records':len(outcand),'support_predicate':predpin,'release_unit_statistics':unitstats,'cluster_similarity':{'method':'exhaustive normalized source structural trigram-set Jaccard within format','threshold':MIN_SIM,'minimum_feature_count':5,'unknowns_not_independent':True},'relations':['exact code/image SHA across all formats','old parsed/lexical family including cross-stratum duplicates','explicit source-provided document/template/generator IDs if present; archive/shard/split is not a family','conservative AST/DOM/language program skeleton','exhaustive candidate-to-development/candidate near-source similarity','transitive union closure; development-connected component entirely excluded','one globally selected representative per component before compiler support filtering'],'limitations':['Operational source/provenance clusters are audited duplicate-isolation units, not a proof of latent generator identity or statistical independence.','No document/template/generator identifier is inferred from archive shard, raw row, provider or unique paper template directory.','A source grammar parse or static feature classifier is not semantic coverage or successful conversion.','No representative global yield inference from this provider-balanced/template-capped cohort; hidden generator dependence remains.','Final support predicates, complete new development roster, compiler/config/QA hashes and controls must freeze before validation.','Metadata audit may inspect source only. No conversion/QA outcomes are consumed.'],'release_gate':{'minimum_audited_unseen_clusters':30,'minimum_full_qualified_rate':0.20,'minimum_incremental_full_qualified_distinct_clusters':5,'positive_control_regression_allowed':False,'negative_control_false_accept_allowed':False,'infrastructure_errors_allowed':False,'cluster_count_not_generator_independence':True,'no_postresult_group_narrowing_or_replacement':True,'maximum_general_fix_with_fresh_holdout':1},'compiler_frozen':False,'validation_started':False,'automatic_batch_launch_authorized_only_after_all_group_gates':True,'old_queue_restart':False,'raw_media_copied_to_local':False,'model_calls':0,'statistics':stats}
 files=[]
 for name,items in [('compiler_validation_development_ids.jsonl',aud[:ndev]),('compiler_validation_cluster_candidates.jsonl',outcand),('compiler_validation_cluster_edges.jsonl',edges),('compiler_validation_candidate_manifest.jsonl',[a for a in outcand if a.get('support_unit') and a['audit_disposition']=='eligible_unconsumed_audited_cluster'])]:
  b=b''.join(blob(x) for x in items);(output/name).write_bytes(b);files.append({'file':name,'sha256':sha(b),'bytes':len(b)})
 b=blob(protocol);(output/'compiler_validation_protocol.json').write_bytes(b);files.append({'file':'compiler_validation_protocol.json','sha256':sha(b),'bytes':len(b)})
 summary={'remote_directory':str(output),'development_records':ndev,'candidate_records':len(outcand),'globally_eligible_operational_clusters':sum(a['audit_disposition']=='eligible_unconsumed_audited_cluster' for a in outcand),'statistics':stats,'files':files,'compiler_frozen':False,'validation_executions':0,'model_calls':0,'development_roster_complete_declared':development_complete,'generator_independence_proven':False,'release_unit_statistics':unitstats,'support_predicate':predpin}
 (output/'compiler_validation_summary.json').write_bytes(blob(summary));print(json.dumps(summary,ensure_ascii=False))
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(R));p.add_argument('--run-id',required=True);p.add_argument('--additional-development-file',action='append',default=[]);p.add_argument('--development-roster-complete',action='store_true');p.add_argument('--predicate-path');a=p.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9_-]+',a.run_id):p.error('bad run id')
 audit(Path(a.root),Path(a.root)/'release/compiler_validation_v1'/a.run_id,a.additional_development_file,a.development_roster_complete,a.predicate_path)
if __name__=='__main__':main()
