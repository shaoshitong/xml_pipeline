"""Finite metadata/source-only candidate prefilter, capped reservoirs and audit.
No source execution, conversions, renderer, QA outcome or model call.
"""
import argparse,ast,collections,hashlib,heapq,importlib.util,json,sqlite3,re,time
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
SEED='hkust-compiler-population-holdout-20261101-v1'
MAX_CANDIDATES_PER_UNIT=500
MAX_NEAR_COMPARISONS=2000000
MIN_SIM=.85
def blob(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def frozen(p,b):
 with Path(p).open('xb') as f:f.write(b);f.flush()
 Path(p).chmod(0o444)
 return {'file':Path(p).name,'sha256':sha(b),'bytes':len(b)}
def keep(heaps,unit,row):
 score=int(sha(blob([SEED,'population_reservoir',unit,row['id']])),16);h=heaps[unit];item=(-score,row['id'],row)
 if len(h)<MAX_CANDIDATES_PER_UNIT:heapq.heappush(h,item)
 elif item>h[0]:heapq.heapreplace(h,item)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(R));ap.add_argument('--run-id',required=True);ap.add_argument('--native-predicate');ap.add_argument('--scene-predicate');ap.add_argument('--formats',default='mermaid,plantuml');ap.add_argument('--development-audit',default='cluster_audit_20261101_v1');a=ap.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9_-]+',a.run_id):ap.error('invalid run id')
 root=Path(a.root).resolve();out=root/'release/compiler_validation_v1'/a.run_id;out.mkdir(parents=True,exist_ok=False)
 auditpath=root/'conversion/scripts/compiler_validation_cluster_audit_v1.py';mod=load('compiler_validation_frozen_auditor',auditpath);native=load('compiler_validation_native_support',a.native_predicate) if a.native_predicate else None
 scene=load('compiler_validation_scene_support',a.scene_predicate) if a.scene_predicate else None
 formats=set(a.formats.split(','))
 if not formats or formats-{'mermaid','plantuml','python'}:ap.error('bad formats')
 if formats&{'mermaid','plantuml'} and native is None:ap.error('native predicate required for language groups')
 if 'python' in formats and scene is None:ap.error('scene predicate required for Python group')
 oldmod=load('compiler_validation_old_structure',root/'release/round2_heldout_v1/unseen_protocol_20261101_v2/frozen_sampler.py')
 devdir=root/'release/compiler_validation_v1'/a.development_audit;devsummary=json.loads((devdir/'compiler_validation_summary.json').read_text())
 for f in devsummary['files']:
  if sha((devdir/f['file']).read_bytes())!=f['sha256']:raise ValueError('development_audit_changed')
 dev=rows(devdir/'compiler_validation_development_ids.jsonl');dev_ids={r['id'] for r in dev};dev_code={r['code_sha256'] for r in dev};dev_image={r['image_sha256'] for r in dev}
 ledger=root/'release/round2_fixed_v1/repair_pass_20261101_0627';control=json.loads((ledger/'control.json').read_text())
 if control.get('stop_dispatch') is not True:raise ValueError('old_round_not_paused')
 db=sqlite3.connect('file:'+str(root/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 status=sqlite3.connect('file:'+str(ledger/'status.sqlite')+'?mode=ro',uri=True,timeout=30)
 q=status.execute('select seq,id,source from samples where attempts=0 and status="queued" order by seq').fetchall()
 if status.execute('select count(*) from samples where status="running"').fetchone()[0]:raise ValueError('old_round_inflight')
 status.close();heaps=collections.defaultdict(list);count=collections.Counter();population=[];providerstats=collections.defaultdict(collections.Counter);start=time.monotonic()
 predicatepins={'audit':{'path':str(auditpath),'sha256':sha(auditpath.read_bytes())},'reservoir':{'path':str(Path(__file__)),'sha256':sha(Path(__file__).read_bytes())}}
 if native:predicatepins['native']={'path':a.native_predicate,'sha256':sha(Path(a.native_predicate).read_bytes())}
 if scene:
  tree=ast.parse(Path(a.scene_predicate).read_text());func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='static_support')
  predicatepins['scene']={'path':a.scene_predicate,'sha256':sha(Path(a.scene_predicate).read_bytes()),'static_support_ast_sha256':sha(ast.dump(func,include_attributes=False).encode()),'call':'static_support(record)'}
 try:
  for seq,identifier,s in q:
   source=json.loads(s);fmt=source['format'];count['queued_total']+=1
   if fmt not in formats:continue
   count['examined_format:'+fmt]+=1
   if identifier in dev_ids or source['code_sha256'] in dev_code or source['image_sha256'] in dev_image:count['exact_development_overlap:'+fmt]+=1;continue
   row={'id':identifier,'seq':seq,'source':source};supported=False;unit=None
   try:
    if fmt in ('mermaid','plantuml'):
     code,loc=mod.source(root,db,identifier,source['code_sha256']);spt=native.support_predicate(code,fmt);supported=spt['supported'];unit=spt['unit'];row['source_locator']=loc
     if not supported:count['unsupported_by_predicate:'+fmt]+=1
    else:
     old=db.execute('select output_record from jobs where id=?',(identifier,)).fetchone()
     if not old or not old[0]:count['no_prior_source_artifact_record:python']+=1;continue
     record=json.loads(old[0])
     if (record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(identifier,source['code_sha256'],source['image_sha256']):raise ValueError('cached_source_record_identity_mismatch')
     row['source_record_sha256']=sha(old[0].encode())
     spt=scene.static_support(record);supported=spt.get('supported',spt.get('ok',False));unit=spt.get('unit') or spt.get('group')
     if not supported:count['unsupported_by_predicate:python']+=1
     row['static_support_evidence']=spt
     row['cached_source_artifacts']={k:record.get(k) for k in ('source_render_dot','source_render_svg','source_render_svg_sha256','source_render_execution_audit','execution_audit') if record.get(k)}
    if supported:
     if not unit:raise ValueError('supported_predicate_missing_unit')
     src,rec=db.execute('select source,input_record from jobs where id=?',(identifier,)).fetchone();rec=json.loads(rec)
     row.update(provider=src,support_unit=unit,provenance_keys=mod.provenance(rec,src));count['matching_population:'+unit]+=1;providerstats[unit][src]+=1;keep(heaps,unit,row)
     population.append({'id':identifier,'seq':seq,'unit':unit,'code_sha256':source['code_sha256'],'image_sha256':source['image_sha256'],'provider':src})
   except Exception as e:
    count['metadata_or_source_error:'+fmt]+=1
    # A source/metadata failure is excluded from support, never marked converted.
  predicate_unchanged=all(sha(Path(v['path']).read_bytes())==v['sha256'] for v in predicatepins.values())
  if not predicate_unchanged:raise ValueError('predicate_or_auditor_changed_during_metadata_scan')
  frozen(out/'compiler_validation_matching_population.jsonl',b''.join(blob(r) for r in population))
  candidates=[]
  for unit,h in sorted(heaps.items()):
   for score,i,r in sorted(h,key=lambda t:-t[0]):candidates.append({**r,'reservoir_rank':sha(blob([SEED,'population_reservoir',unit,i]))})
  frozen(out/'compiler_validation_reservoir.jsonl',b''.join(blob(r) for r in candidates))
  # No reservoir refill after cluster exclusions. Raw source is read only on HKUST.
  allrows=[];features=[];du=mod.DSU(len(dev)+len(candidates));keys={};edges=[];ndev=len(dev)
  for idx,r in enumerate(dev+candidates):
   isdev=idx<ndev;fmt=r['format'] if isdev else r['source']['format'];codehash=r['code_sha256'] if isdev else r['source']['code_sha256'];imagehash=r['image_sha256'] if isdev else r['source']['image_sha256']
   item={**r,'format':fmt,'code_sha256':codehash,'image_sha256':imagehash,'role':'development' if isdev else 'unconsumed_reservoir'}
   klist=['code:'+codehash,'image:'+imagehash]+item.get('provenance_keys',[])
   if isdev:klist+=r.get('cluster_keys',[])
   try:
    code,loc=mod.source(root,db,r['id'],codehash,r.get('source_locator'));sk=mod.tree_skeleton(code,fmt,oldmod);fs=mod.shingles(mod.tokens(sk))
    item.update(source_locator=loc,source_hash_verified=True,program_skeleton_sha256=sha(sk.encode()),cluster_parse_status='audited_operational_structure');klist.append('skeleton:'+fmt+':'+sha(sk.encode()))
    fp=oldmod.fingerprint(code,fmt)
    if fp.get('template_family'):klist.append('old_family:'+fp['template_family'])
   except Exception as e:item.update(source_hash_verified=False,cluster_parse_status='unknown',audit_error=str(e)[:200]);fs=frozenset()
   item['cluster_keys']=sorted(set(klist));allrows.append(item);features.append(fs)
   for k in item['cluster_keys']:
    if k in keys:du.union(idx,keys[k]);edges.append({'left':allrows[keys[k]]['id'],'right':r['id'],'evidence':k.split(':',1)[0]})
    else:keys[k]=idx
  comparisons=0;exceeded=False
  for i in range(ndev,len(allrows)):
   aa=features[i]
   if len(aa)<5:continue
   for j in range(i):
    bb=features[j]
    if allrows[i]['format']!=allrows[j]['format'] or len(bb)<5:continue
    if min(len(aa),len(bb))/max(len(aa),len(bb))<MIN_SIM:continue
    comparisons+=1
    if comparisons>MAX_NEAR_COMPARISONS:exceeded=True;break
    inter=len(aa&bb);sim=inter/(len(aa)+len(bb)-inter)
    if sim>=MIN_SIM:du.union(i,j);edges.append({'left':allrows[j]['id'],'right':allrows[i]['id'],'evidence':'exhaustive_normalized_trigram_jaccard','jaccard':round(sim,6)})
   if exceeded:break
  components=collections.defaultdict(list)
  for i in range(len(allrows)):components[du.find(i)].append(i)
  for members in components.values():
   cl='cluster:'+sha(blob(sorted({allrows[i]['id'] for i in members})));devleak=any(i<ndev for i in members)
   for i in members:allrows[i].update(audit_cluster=cl,development_overlap=devleak,cluster_candidate_members=sum(j>=ndev for j in members),cluster_development_members=sum(j<ndev for j in members))
  seen=set();audited=[];selected=[];stats={}
  for row in sorted(allrows[ndev:],key=lambda r:r['reservoir_rank']):
   if exceeded:disposition='audit_budget_exceeded_no_release'
   elif row['cluster_parse_status']=='unknown':disposition='cluster_unknown'
   elif row['development_overlap']:disposition='development_cluster_overlap'
   elif row['audit_cluster'] in seen:disposition='duplicate_global_cluster'
   else:disposition='eligible_unconsumed_audited_cluster';seen.add(row['audit_cluster'])
   audited.append({**row,'audit_disposition':disposition,'generator_independence_proven':False})
  declared_units=({'mermaid_flowchart_native_v1'} if 'mermaid' in formats else set())|({'plantuml_component_native_v1'} if 'plantuml' in formats else set())|({'python_graphviz_cached_source_v1'} if 'python' in formats else set())
  for unit in sorted(declared_units|set(heaps)):
   eligible=[r for r in audited if r['support_unit']==unit and r['audit_disposition']=='eligible_unconsumed_audited_cluster'];group=[r for r in audited if r['support_unit']==unit]
   chosen=eligible[:30] if len(eligible)>=30 else []
   for r in chosen:selected.append({**r,'sample_order_within_unit':len([x for x in selected if x['support_unit']==unit])+1,'ready_for_validation':False})
   stats[unit]={'matching_queued_population':count['matching_population:'+unit],'population_providers':dict(providerstats[unit]),'frozen_reservoir':len(group),'eligible_operational_clusters':len(eligible),'selected_validation_clusters':len(chosen),'minimum_30_met':len(eligible)>=30,'dispositions':dict(collections.Counter(r['audit_disposition'] for r in group)),'selected_providers':dict(collections.Counter(r['provider'] for r in chosen))}
  if not all(sha(Path(v['path']).read_bytes())==v['sha256'] for v in predicatepins.values()):raise ValueError('predicate_or_auditor_changed_before_freeze')
  files=[]
  for name,rr in [('compiler_validation_audited_reservoir.jsonl',audited),('compiler_validation_selected_manifest.jsonl',selected),('compiler_validation_cluster_edges.jsonl',edges)]:files.append(frozen(out/name,b''.join(blob(r) for r in rr)))
  for name in ('compiler_validation_matching_population.jsonl','compiler_validation_reservoir.jsonl'):files.append({'file':name,'sha256':sha((out/name).read_bytes()),'bytes':(out/name).stat().st_size})
  protocol={'seed':SEED,'method':'single fixed-hash bottom500/unit matching source capability, followed by unchanged conservative audit; never refill after audit exclusions','max_reservoir_per_unit':MAX_CANDIDATES_PER_UNIT,'source_queued_snapshot':str(ledger/'status.sqlite'),'queued_snapshot_count':len(q),'formats_examined':sorted(formats),'development_roster_records':ndev,'development_manifest_sha256':sha((devdir/'compiler_validation_development_ids.jsonl').read_bytes()),'predicate_pins':predicatepins,'native_predicate_only_static':True,'scene_predicate_only_static':True,'audit_jaccard_threshold':MIN_SIM,'audit_near_comparisons':comparisons,'audit_max_near_comparisons':MAX_NEAR_COMPARISONS,'audit_budget_exceeded_blocks_all_groups':exceeded,'statistics':stats,'release_gate':{'min_audited_unseen_clusters':30,'min_full_qualified_fraction':.20,'min_C_minus_B_new_fully_qualified_clusters':5,'positive_control_regressions':0,'negative_false_accepts':0,'infrastructure_errors':0},'compiler_config_qa_not_yet_frozen':True,'validation_executions':0,'outcomes_viewed':False,'generator_independence_proven':False,'limitations':['Operational source/provenance clusters are not proof of latent generator identity or independent-binomial sampling.','Provider/archive/split/row is not treated as generator identity.','No random reservoir resampling or failure replacement is allowed.','Static source/cached-artifact eligibility is not conversion, fidelity, reference reproduction or semantic completeness.','Only this frozen queued snapshot is represented; no whole-release yield claim.'],'elapsed_seconds':round(time.monotonic()-start,3)}
  files.append(frozen(out/'compiler_validation_protocol.json',blob(protocol)))
  summary={'remote_directory':str(out),'counters':dict(count),'statistics':stats,'files':files,'selected_total':len(selected),'reservoir_total':len(candidates),'validation_executions':0,'outcomes_viewed':False,'near_comparisons':comparisons,'audit_budget_exceeded':exceeded,'predicate_pins':predicatepins,'elapsed_seconds':protocol['elapsed_seconds']}
  frozen(out/'compiler_validation_summary.json',blob(summary));print(json.dumps(summary,ensure_ascii=False))
 finally:db.close()
if __name__=='__main__':main()
