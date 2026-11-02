"""Fixed format pools and source-IR audit only. No conversion, rendering or QA."""
import argparse,collections,hashlib,heapq,importlib.util,json,sqlite3,sys,time
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';FORMATS=('drawio','mermaid','plantuml','svg','html','tikz');SEED='hkust-remaining-types-source-audit-20261101-v1';MAX_POOL=500;MAX_COMPARE=2000000
sys.path.insert(0,str(S))
def raw(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def load(name,p):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def frozen(p,b):
 Path(p).parent.mkdir(parents=True,exist_ok=True)
 with Path(p).open('xb') as f:f.write(b)
 Path(p).chmod(0o444);return {'file':str(p),'sha256':sha(b),'bytes':len(b)}
def rank(fmt,i):return sha(raw([SEED,fmt,i]))
def pool(scope,excluded_ids,excluded_code,excluded_image):
 heaps=collections.defaultdict(list);counts=collections.Counter()
 for r in scope:
  if r['format'] not in FORMATS:continue
  counts[r['format']]+=1
  if r['id'] in excluded_ids or r['source_code_sha256'] in excluded_code or r['source_image_sha256'] in excluded_image:continue
  k=r['format'];v=(-int(rank(k,r['id']),16),r['id'],r);h=heaps[k]
  if len(h)<MAX_POOL:heapq.heappush(h,v)
  elif v>h[0]:heapq.heapreplace(h,v)
 return {f:[x[2] for x in sorted(h,key=lambda x:-x[0])] for f,h in heaps.items()},dict(counts)
class DSU:
 def __init__(self,n):self.p=list(range(n))
 def find(self,x):
  while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=self.p[x]
  return x
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def source(db,u):
 p=R/'conversion/inputs'/u['id'][:2]/u['id']/'source.txt'
 try:b=p.read_bytes()
 except OSError:b=None
 if b is None or sha(b)!=u['source_code_sha256']:
  row=db.execute('select input_manifest from jobs where id=?',(u['id'],)).fetchone()
  if not row or not row[0]:raise ValueError('source_manifest_missing')
  m=json.loads(row[0])
  if m.get('id')!=u['id'] or m.get('code_sha256')!=u['source_code_sha256']:raise ValueError('source_manifest_identity')
  p=R/m['source_code'];b=p.read_bytes()
 if not p.resolve().is_relative_to(R) or len(b)>4*1024*1024 or sha(b)!=u['source_code_sha256']:raise ValueError('source_hash_or_budget')
 return b.decode('utf-8-sig'),str(p.relative_to(R))
def audit_scope(scope_manifest,run_id,development_additions=()):
 start=time.monotonic();out=R/'release/compiler_types_audit_v1'/run_id;out.mkdir(parents=True,exist_ok=False)
 ir=load('types_source_IR',S/'compiler_types_source_ir_v1.py');iso=load('types_isomorphism',S/'compiler_validation_dot_ir_v2.py');old=load('types_old_family',R/'release/round2_heldout_v1/unseen_protocol_20261101_v2/frozen_sampler.py');oldprov=load('types_provenance',S/'compiler_validation_cluster_audit_v1.py');native=load('types_native_language_parser',S/'compiler_native_languages_v1.py')
 from tikz_literal_graph import parse_literal
 class TikzParser:pass
 tikz_parser=TikzParser();tikz_parser.parse_literal=parse_literal
 scope=rows(scope_manifest);universe={r['id']:r for r in scope};dev0=rows(R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl');dev={r['id']:r for r in dev0}
 for p in development_additions:
  for r in rows(p):
   identifier=r['id'];u=universe[identifier];dev.setdefault(identifier,{'id':identifier,'format':u['format'],'code_sha256':u['source_code_sha256'],'image_sha256':u['source_image_sha256'],'cluster_keys':[]})
 reg=sqlite3.connect('file:'+str(R/'release/compiler_v1/validation_registry.sqlite')+'?mode=ro',uri=True);regkeys=set(reg.execute('select kind,value from reservation_keys').fetchall());reg.close()
 dids=set(dev)|{v for k,v in regkeys if k=='id'};dcodes={r['code_sha256'] for r in dev.values()}|{v for k,v in regkeys if k=='code'};dimages={r['image_sha256'] for r in dev.values()}|{v for k,v in regkeys if k=='image'}
 pools,counts=pool(scope,dids,dcodes,dimages);flat=[]
 for f,rr in sorted(pools.items()):flat.extend({'id':r['id'],'seq':r['seq'],'source':{'code_sha256':r['source_code_sha256'],'image_sha256':r['source_image_sha256'],'format':f,'category':r['category']},'source_format':f,'pool_rank':rank(f,r['id'])} for r in rr)
 pins={n:sha((S/n).read_bytes()) for n in ('compiler_types_source_ir_v1.py','compiler_types_unseen_audit_v1.py','test_compiler_types_unseen_audit_v1.py','compiler_validation_dot_ir_v2.py','compiler_native_languages_v1.py','tikz_literal_graph.py','tikz_connectivity.py')}
 method={'seed':SEED,'format_pool_cap':MAX_POOL,'pair_compare_cap_per_unit':MAX_COMPARE,'source_pool_fixed_before_structure_or_provenance_rejections':True,'no_refill':True,'method_pins':pins,'scope_manifest':str(scope_manifest),'scope_sha256':sha(Path(scope_manifest).read_bytes()),'dev_records':len(dev),'actual_IR':'source typed topology/style/hierarchy; exact-isomorphism after invariant filter; no wrapper Jaccard','stable_registry_key':'semantic:'+ir.VERSION+':unit:typed_invariant; invariant collisions excluded unless exact graph isomorphism establishes family','HTML':'DOM+CSS heuristic only; computed layout/assets/fonts/paint unknown; ready=false','TikZ':'literal named graph/closed-basic source inventory only; compilation success not asserted','quality_or_converter_frozen':False,'new_QA_or_conversion':False}
 frozen(out/'compiler_types_method.json',raw(method));frozen(out/'compiler_types_frozen_pool.jsonl',b''.join(raw(r) for r in flat))
 db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=30);records=[];graphs={};unknown_partial=collections.defaultdict(set);source_cache={};metadata_count=0
 def classify(code,fmt):
  if fmt=='drawio':return ir.native(code,old)
  if fmt in ('mermaid','plantuml'):return ir.language(code,fmt,native)
  if fmt=='svg':return ir.svg(code)
  if fmt=='html':return ir.html_ir(code)
  return ir.tikz(code,tikz_parser)
 try:
  work=[('development',universe[i],r) for i,r in dev.items() if i in universe and universe[i]['format'] in FORMATS]+[('candidate',universe[r['id']],r) for r in flat]
  for role,u,prior in work:
   item={'id':u['id'],'role':role,'format':u['format'],'code_sha256':u['source_code_sha256'],'image_sha256':u['source_image_sha256'],'cluster_keys':['id:'+u['id'],'code:'+u['source_code_sha256'],'image:'+u['source_image_sha256']]}
   try:
    row=db.execute('select source,input_record from jobs where id=?',(u['id'],)).fetchone();metadata_count+=1
    if not row:raise ValueError('source_metadata_missing')
    rec=json.loads(row[1])
    if (rec.get('pair_sha256'),rec.get('code_sha256'),rec.get('image_sha256'))!=(u['id'],u['source_code_sha256'],u['source_image_sha256']):raise ValueError('source_metadata_identity')
    item['provider']=row[0];item['provenance_keys']=oldprov.provenance(rec,row[0]);item['cluster_keys']+=item['provenance_keys']
    code,loc=source(db,u);source_cache[u['id']]=(code,loc);item['source_locator']=loc;item['source_hash_verified']=True
    fp=old.fingerprint(code,u['format'])
    if fp.get('template_family'):item['old_stable_family']=fp['template_family'];item['cluster_keys'].append('old_family:'+fp['template_family'])
    if prior.get('cluster_keys'):item['cluster_keys']+= [k for k in prior['cluster_keys'] if k.startswith(('old_family:','document:','provenance:'))]
    if u['format']=='svg' and not (rec.get('render_backend')=='cairosvg' and rec.get('image_provenance')=='rendered_from_source_svg' and rec.get('pairing')=='derived_from_source_svg' and rec.get('source_svg_sha256')==u['source_code_sha256']):raise ValueError('svg_recorded_cairosvg_renderer_provenance_unknown')
    unit,g,evidence=classify(code,u['format']);
    if u['format']=='svg':unit='direct_svg_graphviz_roles_recorded_cairosvg_v1'
    item.update(unit=unit,source_semantic_status='parsed',semantic_evidence=evidence,semantic_invariant=iso.invariant(g));graphs[len(records)]=g
   except Exception as e:
    item.update(source_semantic_status='typed_blocked_or_unknown',reason=str(e)[:250])
    if role=='development' and u['id'] in source_cache:
     key=ir.partial_key(source_cache[u['id']][0],u['format'])
     if key:unknown_partial[u['format']].add(key)
   if role=='candidate':item.update(seq=prior['seq'],source=prior['source'],pool_rank=prior['pool_rank'])
   records.append(item)
  # Frozen structural/provenance blocking, including original stable families.
  du=DSU(len(records));owners={};edges=[]
  for i,r in enumerate(records):
   for k in set(r['cluster_keys']):
    if k in owners:du.union(i,owners[k]);edges.append({'left':records[owners[k]]['id'],'right':r['id'],'evidence':'hard:'+k.split(':',1)[0]})
    else:owners[k]=i
  buckets=collections.defaultdict(list)
  for i in graphs:buckets[(records[i]['unit'],records[i]['semantic_invariant'])].append(i)
  budget=collections.Counter();budget_exceeded=set();collision=set()
  for (unit,sig),members in sorted(buckets.items()):
   representative=members[0]
   for i in members[1:]:
    budget[unit]+=1
    if budget[unit]>MAX_COMPARE:budget_exceeded.add(unit);break
    try:equal=iso.equivalent(graphs[i],graphs[representative])
    except iso.IsoUnknown:equal=False
    if not equal:collision.update(members)
    else:du.union(i,representative);edges.append({'left':records[representative]['id'],'right':records[i]['id'],'evidence':'actual_source_typed_isomorphism'})
  comps=collections.defaultdict(list)
  for i in range(len(records)):comps[du.find(i)].append(i)
  devcomp={du.find(i) for i,r in enumerate(records) if r['role']=='development'};unknowncomp={du.find(i) for i,r in enumerate(records) if r['role']=='candidate' and (i not in graphs or i in collision)};audited=[];unitstats={};selected=[];reserve=[];used=set()
  for i,r in sorted(((i,r) for i,r in enumerate(records) if r['role']=='candidate'),key=lambda p:(p[1]['format'],p[1]['pool_rank'])):
   unit=r.get('unit',r['format']+'_typed_blocked');component=du.find(i);sem='semantic:'+ir.VERSION+':'+unit+':'+r.get('semantic_invariant','unknown')
   registered=any(('hard_cluster',k) in regkeys for k in r['cluster_keys']) or ('hard_cluster',sem) in regkeys
   pk=ir.partial_key(source_cache[r['id']][0],r['format']) if r['id'] in source_cache else None
   near_unknown=bool(pk and pk in unknown_partial[r['format']])
   if unit in budget_exceeded:disp='comparison_budget_exceeded_unit_blocked'
   elif component in devcomp:disp='development_identity_provenance_or_stable_family_overlap'
   elif registered:disp='global_registry_overlap'
   elif i not in graphs:disp='typed_blocked_or_source_unknown'
   elif component in unknowncomp:disp='semantic_equivalence_unknown'
   elif near_unknown:disp='evidence_insufficient_near_unknown_source_structure'
   elif sem in used:disp='duplicate_actual_source_semantic_family'
   else:disp='eligible_operational_cluster';used.add(sem)
   item={**r,'support_unit':unit,'audit_cluster':sem,'cluster_keys':sorted(set(r['cluster_keys']+[sem])),'development_overlap':component in devcomp,'audit_disposition':disp,'ready_for_validation':False,'generator_independence_proven':False};audited.append(item)
  for unit in sorted({r['support_unit'] for r in audited}):
   rr=[r for r in audited if r['support_unit']==unit];ok=[r for r in rr if r['audit_disposition']=='eligible_operational_cluster'];pick=ok[:30] if len(ok)>=30 else [];res=ok[30:60] if len(ok)>=60 else []
   selected.extend({**r,'sample_order_within_unit':i+1} for i,r in enumerate(pick));reserve.extend({**r,'reserve_order':i+1,'eligible_rank':i+31} for i,r in enumerate(res))
   unitstats[unit]={'pool_candidates':len(rr),'eligible_operational_clusters':len(ok),'selected_count':len(pick),'repair_reserve_count':len(res),'minimum30_met':len(ok)>=30,'comparison_budget_exceeded':unit in budget_exceeded,'dispositions':dict(collections.Counter(r['audit_disposition'] for r in rr)),'providers':dict(collections.Counter(r.get('provider','unknown') for r in ok)),'ready':False}
  # Full-scope static inventories: code only, no renderer or prior target metrics.
  inventory=collections.defaultdict(collections.Counter)
  for u in scope:
   fmt=u['format']
   if fmt not in ('drawio','tikz'):continue
   inventory[fmt]['scope']+=1
   try:
    code,loc=source_cache.get(u['id']) or source(db,u)
    if fmt=='drawio':unit,g,ev=ir.native(code,old);inventory[fmt]['intact_editable_native_source_graph']+=1
    else:
     try:
      ev=tikz_parser.parse_literal(code);inventory[fmt]['literal_named_graph_static']+=1
      if all(e['route']=='--' for e in ev['edges']):inventory[fmt]['literal_named_straight_static']+=1
     except ValueError:
      try:ir.closed_basic(code);inventory[fmt]['literal_closedbasic_static']+=1
      except ValueError:inventory[fmt]['not_in_declared_literal_static_subset']+=1
   except Exception:inventory[fmt]['source_missing_invalid_or_budget']+=1
  protocol={**method,'unit_statistics':unitstats,'ready_for_validation':False,'minimum_operational_clusters':30,'repair_reserve_ranks':[31,60],'release_gate':{'minimum_full_qualified_fraction':0.20,'minimum_incremental_fully_qualified_clusters':5,'positive_regressions':0,'negative_false_acceptances':0,'infrastructure_errors':0},'actual_converter_baseline_and_quality_pins_frozen':False,'registry_written':False,'source_compilation_success_claimed':False}
  frozen(out/'compiler_types_protocol.json',raw(protocol))
  files=[]
  for name,rs in [('compiler_types_audited_candidates.jsonl',audited),('compiler_types_selected_manifest.jsonl',selected),('compiler_types_repair_reserve.jsonl',reserve),('compiler_types_development_audit.jsonl',[r for r in records if r['role']=='development']),('compiler_types_cluster_edges.jsonl',edges)]:files.append(frozen(out/name,b''.join(raw(r) for r in rs)))
  for n,h in pins.items():
   if sha((S/n).read_bytes())!=h:raise ValueError('method_pin_changed')
  summary={'run_directory':str(out),'status':'source_metadata_only_pending_converter_QA_freeze','scope_counts':counts,'frozen_pool_counts':{f:len(pools[f]) for f in pools},'development_records':len(dev),'candidate_records':len(flat),'unit_statistics':unitstats,'source_static_inventory':{f:dict(c) for f,c in inventory.items()},'files':files,'method_pins':pins,'comparisons_per_unit':dict(budget),'canonical_jobs_indexed_metadata_queries':metadata_count,'new_conversion_or_QA':False,'new_registry_write':False,'source_compilation_success_claimed':False,'generator_independence_proven':False,'statistical_limits':['Operational source clusters do not prove hidden generator independence.','Fixed capped pools and source support filters do not estimate unbiased population yield.','HTML DOM/CSS and TikZ literal inventories have explicitly unexecuted runtime/layout boundaries.'],'elapsed_seconds':round(time.monotonic()-start,3)}
  frozen(out/'compiler_types_summary.json',raw(summary));print(json.dumps(summary))
 finally:db.close()
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scope-manifest',default=str(R/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl'));p.add_argument('--run-id',required=True);p.add_argument('--development-additions',action='append',default=[]);a=p.parse_args();audit_scope(Path(a.scope_manifest),a.run_id,a.development_additions)
