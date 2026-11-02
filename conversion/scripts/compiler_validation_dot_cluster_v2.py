"""One finite re-audit of the unchanged500 using actual cached-DOT semantics.
No Python source execution, layout, renderer, target conversion or QA outcome.
"""
import collections,hashlib,importlib.util,json,os,sqlite3,subprocess,time
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');V1=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v1';DEV=R/'release/compiler_validation_v1/cluster_audit_20261101_v1';OUT=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v2';S=R/'conversion/scripts';DOT=R/'conversion/runtime/graphviz/bin/dot'
MAX_ISO_COMPARISONS=2000000
HARD_PREFIXES=('id:','code:','image:','document:','provenance:','skeleton:','old_family:')
def raw(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def frozen(p,b):
 with Path(p).open('xb') as f:f.write(b)
 Path(p).chmod(0o444);return {'file':Path(p).name,'sha256':sha(b),'bytes':len(b)}
class DSU:
 def __init__(self,n):self.p=list(range(n))
 def find(self,x):
  while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=self.p[x]
  return x
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def evidence_disposition(component_development,own_dot_unknown,component_unknown,near_dev_unknown,duplicate):
 if component_development:return 'development_cluster_overlap'
 if own_dot_unknown:return 'DOT_parse_or_identity_unknown'
 if component_unknown:return 'component_DOT_audit_unknown'
 if near_dev_unknown:return 'audit_insufficient_near_development_DOT_unknown'
 if duplicate:return 'duplicate_global_DOT_or_hard_cluster'
 return 'eligible_unconsumed_audited_cluster'
def hard_keys(r):
 k=[v for v in r.get('cluster_keys',[]) if v.startswith(HARD_PREFIXES)]
 return sorted(set(k+['id:'+r['id'],'code:'+r['code_sha256'],'image:'+r['image_sha256']]+r.get('provenance_keys',[])))
def graph_identity(record,expected,candidate=False):
 if (record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(expected['id'],expected['code_sha256'],expected['image_sha256']):raise ValueError('cached_record_identity_mismatch')
 locator=record.get('source_render_dot')
 if not isinstance(locator,str) or Path(locator).is_absolute():raise ValueError('cached_DOT_missing')
 p=(R/locator).resolve(strict=True)
 if not p.is_relative_to(R/'clean'):raise ValueError('cached_DOT_not_in_clean')
 b=p.read_bytes()
 if len(b)>4*1024*1024:raise ValueError('cached_DOT_budget')
 audit_path=(R/record['execution_audit']).resolve(strict=True)
 if not audit_path.is_relative_to(R):raise ValueError('capture_audit_outside_root')
 ab=audit_path.read_bytes();audit=json.loads(ab)
 if (audit.get('id'),audit.get('source_code_sha256'))!=(expected['id'],expected['code_sha256']):raise ValueError('capture_original_identity_mismatch')
 captures=audit.get('captures',[])
 if not audit.get('execution',{}).get('ok') or len(captures)!=1 or captures[0].get('engine')!='graphviz':raise ValueError('capture_not_single_graphviz')
 capture=(R/str(Path(audit['directory'])/captures[0]['dot'])).resolve(strict=True)
 if not capture.is_relative_to(R) or capture.read_bytes()!=b:raise ValueError('capture_DOT_identity_mismatch')
 if record.get('source_data_sha256') and audit.get('input_manifest',{}).get('source_data_sha256')!=record['source_data_sha256']:raise ValueError('capture_source_data_identity_mismatch')
 if candidate:
  ev=expected['static_support_evidence']
  if (sha(b),sha(ab))!=(ev['source_dot_sha256'],ev['execution_audit_sha256']):raise ValueError('candidate_changed_from_frozen_reservoir')
  code=(R/expected['source_locator']).resolve(strict=True)
  if not code.is_relative_to(R) or sha(code.read_bytes())!=expected['code_sha256']:raise ValueError('original_source_code_changed')
 return b,{'source_dot_sha256':sha(b),'execution_audit_sha256':sha(ab),'source_data_sha256':record.get('source_data_sha256'),'source_locator':str(p.relative_to(R))}
def parse_dot(b,out,ir,cache):
 h=sha(b)
 if h in cache:return cache[h]
 proc=subprocess.run([str(DOT),'-Tdot_json'],input=b,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
 if proc.returncode:raise ValueError('dot_json_parse_failed:'+proc.stderr.decode(errors='replace')[:150])
 if len(proc.stdout)>16*1024*1024:raise ValueError('dot_json_budget')
 document=json.loads(proc.stdout);f=out/'dot_json'/(h+'.json');f.parent.mkdir(exist_ok=True);frozen(f,proc.stdout)
 g=ir.typed_graph(document);value=(g,{'dot_json_sha256':sha(proc.stdout),'typed_invariant':ir.invariant(g),'typed_nodes':g.number_of_nodes(),'typed_relations':g.number_of_edges(),'source_graph_nodes':len(document.get('objects',[]))-int(document.get('_subgraph_cnt',0)),'source_graph_edges':len(document.get('edges',[])),'source_subgraphs':int(document.get('_subgraph_cnt',0))})
 cache[h]=value;return value

def main():
 start=time.monotonic();OUT.mkdir(parents=True,exist_ok=False)
 ir=load('compiler_validation_dot_ir_frozen_v2',S/'compiler_validation_dot_ir_v2.py')
 oldsummary=json.loads((V1/'compiler_validation_summary.json').read_text());oldprotocol=json.loads((V1/'compiler_validation_protocol.json').read_text())
 for f in oldsummary['files']:
  if sha((V1/f['file']).read_bytes())!=f['sha256']:raise ValueError('v1_audit_changed')
 devsum=json.loads((DEV/'compiler_validation_summary.json').read_text())
 for f in devsum['files']:
  if sha((DEV/f['file']).read_bytes())!=f['sha256']:raise ValueError('development_roster_changed')
 dev=rows(DEV/'compiler_validation_development_ids.jsonl');reservoir=rows(V1/'compiler_validation_reservoir.jsonl');oldaud={r['id']:r for r in rows(V1/'compiler_validation_audited_reservoir.jsonl')}
 if len(reservoir)!=500 or len({r['id'] for r in reservoir})!=500:raise ValueError('frozen500_identity_mismatch')
 candidates=[{**r,**{k:oldaud[r['id']][k] for k in ('format','code_sha256','image_sha256','cluster_keys')}} for r in reservoir]
 if len(dev)!=6581:raise ValueError('development_roster_mismatch')
 records=dev+candidates;ndev=len(dev);index={r['id']:i for i,r in enumerate(records)};du=DSU(len(records));edges=[];keyowner={}
 pins={'driver':sha(Path(__file__).read_bytes()),'typed_IR':sha((S/'compiler_validation_dot_ir_v2.py').read_bytes()),'IR_tests':sha((S/'compiler_validation_dot_ir_test_v2.py').read_bytes()),'driver_tests':sha((S/'compiler_validation_dot_cluster_test_v2.py').read_bytes()),'dot_parser':sha(DOT.read_bytes())}
 method={'version':'compiler_validation_DOT_semantics_v2','old_reservoir':str(V1/'compiler_validation_reservoir.jsonl'),'old_reservoir_sha256':sha((V1/'compiler_validation_reservoir.jsonl').read_bytes()),'old500_IDs_and_order_unchanged':True,'development_records':ndev,'method_pins':pins,'hard_relations':['exact original ID/code/image','explicit document/template/generator provenance','same old Python skeleton or old family'],'Python_near_relation':'Not a union evidence by itself. DOT typed semantic equivalence is required; near dev with unknown/missing DOT makes candidate audit-insufficient.','DOT_relation':'Pinned dot -Tdot_json syntax-only parse; ID/text-normalized typed graph with topology/direction/multiplicity/ports/shapes/styles/fonts/dimensions/graph config/cluster memberships; WL invariant is only candidate filter followed by exact typed graph isomorphism.','DOT_equivalence':'Ignore text and arbitrary IDs; same typed graph is hard-isolated, even with different wrapper. No approximate DOT threshold is introduced.','unknown_policy':'Candidate parse/identity unknown and any unresolved equivalent bucket excluded; candidate with Python-near dev whose DOT cannot be audited is evidence-insufficient.','caps':{'candidate_pool':500,'max_iso_comparisons':MAX_ISO_COMPARISONS,'per_isomorphism_seconds':ir.MAX_ISO_SECONDS,'per_dot_parse_seconds':20},'new_target_QA_seen':False,'method_fixed_before_full_audit':True}
 frozen(OUT/'compiler_validation_method_frozen.json',raw(method))
 for i,r in enumerate(records):
  for k in hard_keys(r):
   if k in keyowner:du.union(i,keyowner[k]);edges.append({'left':records[keyowner[k]]['id'],'right':r['id'],'evidence':'hard_'+k.split(':',1)[0]})
   else:keyowner[k]=i
 near_dev=collections.defaultdict(set)
 for e in rows(V1/'compiler_validation_cluster_edges.jsonl'):
  if e['evidence']!='exhaustive_normalized_trigram_jaccard':continue
  l,r=index[e['left']],index[e['right']]
  if l<ndev<=r:near_dev[r].add(l)
  elif r<ndev<=l:near_dev[l].add(r)
 db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=30);graphs={};dotmeta={};unknown=set();cache={}
 try:
  for i,r in enumerate(records):
   if r.get('format')!='python':continue
   try:
    row=db.execute('select output_record from jobs where id=?',(r['id'],)).fetchone()
    if not row or not row[0]:raise ValueError('existing_source_capture_record_missing')
    if i>=ndev and sha(row[0].encode())!=r['source_record_sha256']:raise ValueError('candidate_source_record_changed')
    record=json.loads(row[0]);b,identity=graph_identity(record,r,i>=ndev);g,info=parse_dot(b,OUT,ir,cache);graphs[i]=g;dotmeta[i]={'id':r['id'],'role':'development' if i<ndev else 'candidate','status':'parsed_bound_DOT',**identity,**info}
   except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as e:
    unknown.add(i);dotmeta[i]={'id':r['id'],'role':'development' if i<ndev else 'candidate','status':'DOT_audit_unknown','reason':str(e)[:200]}
 finally:db.close()
 buckets=collections.defaultdict(list)
 for i in graphs:buckets[dotmeta[i]['typed_invariant']].append(i)
 iso_count=0;budget_exceeded=False;equivalence_unknown=set();same_dot_links=0
 for signature,members in sorted(buckets.items()):
  reps=[]
  for i in members:
   match=False
   for j in reps:
    iso_count+=1
    if iso_count>MAX_ISO_COMPARISONS:budget_exceeded=True;break
    try:equal=ir.equivalent(graphs[i],graphs[j])
    except ir.IsoUnknown:equivalence_unknown.update(members);equal=False
    if equal:
     du.union(i,j);same_dot_links+=1;edges.append({'left':records[j]['id'],'right':records[i]['id'],'evidence':'typed_DOT_graph_isomorphism','typed_invariant':signature});match=True;break
   if budget_exceeded:break
   if not match:reps.append(i)
  if budget_exceeded:break
 near_unknown_indices={i for i in range(ndev,len(records)) if near_dev[i]&unknown}
 components=collections.defaultdict(list)
 for i in range(len(records)):components[du.find(i)].append(i)
 compinfo={}
 for root,members in components.items():compinfo[root]={'cluster':'dotv2:'+sha(raw(sorted(records[i]['id'] for i in members))),'development_overlap':any(i<ndev for i in members),'uncertain':any(i in equivalence_unknown or (i>=ndev and i in unknown) for i in members),'near_unknown':any(i in near_unknown_indices for i in members)}
 used=set();audited=[];eligible=[];reason_counts=collections.Counter();near_unknown_cases=0
 for offset,r in enumerate(candidates):
  i=ndev+offset;c=compinfo[du.find(i)];missing=near_dev[i]&unknown;near_unknown_cases+=bool(missing)
  disposition='audit_budget_exceeded' if budget_exceeded else evidence_disposition(c['development_overlap'],i in unknown,c['uncertain'],c['near_unknown'],c['cluster'] in used)
  if disposition=='eligible_unconsumed_audited_cluster':used.add(c['cluster'])
  item={**r,'audit_cluster':c['cluster'],'development_overlap':c['development_overlap'],'source_hash_verified':i not in unknown,'DOT_audit':dotmeta.get(i),'audit_disposition':disposition,'component_near_development_DOT_unknown':c['near_unknown'],'near_development_DOT_unknown_count':len(missing),'near_development_DOT_unknown_ids':[records[j]['id'] for j in sorted(missing)],'generator_independence_proven':False,'ready_for_validation':False}
  audited.append(item);reason_counts[disposition]+=1
  if disposition=='eligible_unconsumed_audited_cluster':eligible.append(item)
 selected=[{**r,'sample_order_within_unit':i+1} for i,r in enumerate(eligible[:30])] if len(eligible)>=30 and not budget_exceeded else []
 if pins['driver']!=sha(Path(__file__).read_bytes()) or pins['typed_IR']!=sha((S/'compiler_validation_dot_ir_v2.py').read_bytes()):raise ValueError('method_changed_during_audit')
 files=[]
 for name,rs in [('compiler_validation_audited_reservoir.jsonl',audited),('compiler_validation_selected_manifest.jsonl',selected),('compiler_validation_DOT_audit.jsonl',[dotmeta[i] for i in sorted(dotmeta)]),('compiler_validation_cluster_edges.jsonl',edges)]:files.append(frozen(OUT/name,b''.join(raw(r) for r in rs)))
 files.append(frozen(OUT/'compiler_validation_reservoir.jsonl',(V1/'compiler_validation_reservoir.jsonl').read_bytes()))
 stats={'python_graphviz_cached_source_v1':{'matching_queued_population':11046,'population_providers':{'allenai--CoSyn-400K':11046},'frozen_reservoir':500,'eligible_operational_clusters':len(eligible),'selected_validation_clusters':len(selected),'minimum_30_met':len(eligible)>=30,'dispositions':dict(reason_counts),'selected_providers':dict(collections.Counter(r['provider'] for r in selected))}}
 auditstats={'development_python':sum(r.get('format')=='python' for r in dev),'development_DOT_parsed':sum(i<ndev for i in graphs),'development_DOT_unknown':sum(i<ndev for i in unknown),'candidate_DOT_parsed':sum(i>=ndev for i in graphs),'candidate_DOT_unknown':sum(i>=ndev for i in unknown),'candidate_near_unknown_development':near_unknown_cases,'typed_DOT_equivalence_links':same_dot_links,'typed_isomorphism_comparisons':iso_count,'typed_equivalence_unknown_records':len(equivalence_unknown),'Python_wrapper_near_alone_union_links':0}
 protocol={**{k:v for k,v in oldprotocol.items() if not k.startswith('audit_')},'method':'compiler_input_DOT_semantic_cluster_v2','method_frozen_before_audit':str(OUT/'compiler_validation_method_frozen.json'),'method_pins':pins,'prior_v1_audit_preserved':str(V1),'old500_IDs_and_order_unchanged':True,'reservoir_refilled':False,'statistics':stats,'audit_statistics':auditstats,'audit_budget_exceeded':budget_exceeded,'audit_budget_exceeded_blocks_all_groups':budget_exceeded,'audit_max_typed_isomorphism_comparisons':MAX_ISO_COMPARISONS,'audit_typed_isomorphism_comparisons':iso_count,'legacy_wrapper_near_threshold_for_unknown_checks':0.85,'release_gate':oldprotocol['release_gate'],'predicate_pins':oldprotocol['predicate_pins'],'compiler_config_qa_not_yet_frozen':True,'validation_executions':0,'outcomes_viewed':False,'generator_independence_proven':False,'limitations':['Operational actual-DOT input equivalence is not latent generator independence; unknown shared generators remain possible.','The500 reservoir was provider-balanced/input-capped after one static source scan; no unbiased population yield estimate or ordinary independent-binomial confidence claim.','Hard original code/image/provenance/Python exact skeleton/old-family exclusions remain even when DOT differs.','DOT attribute/default/alias normalization is declared in frozen typed_IR source; unknown semantic parsing/identity blocks evidence.','Python near similarity alone is not a DOT input family. Missing dev DOT behind a near relation is explicitly insufficient evidence.','This is a metadata audit-object correction before outcomes, not a conversion gain.'],'elapsed_seconds':round(time.monotonic()-start,3)}
 files.append(frozen(OUT/'compiler_validation_protocol.json',raw(protocol)));files.append({'file':'compiler_validation_method_frozen.json','sha256':sha((OUT/'compiler_validation_method_frozen.json').read_bytes()),'bytes':(OUT/'compiler_validation_method_frozen.json').stat().st_size})
 summary={'remote_directory':str(OUT),'status':'metadata_candidates_frozen_pending_compiler_QA_seal' if selected else 'blocked_insufficient_audited_clusters','statistics':stats,'audit_statistics':auditstats,'files':files,'selected_total':len(selected),'reservoir_total':500,'validation_executions':0,'outcomes_viewed':False,'audit_budget_exceeded':budget_exceeded,'predicate_pins':protocol['predicate_pins'],'method_pins':pins,'old500_IDs_and_order_unchanged':True,'generator_independence_proven':False,'elapsed_seconds':protocol['elapsed_seconds']}
 frozen(OUT/'compiler_validation_summary.json',raw(summary));print(json.dumps(summary))
if __name__=='__main__':main()
