"""Metadata-only precommit of eligible ranks31-60; no source/QA/registry access."""
import hashlib,json
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v2_locator_fixed';D=R/'release/compiler_validation_v1/cluster_audit_20261101_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
first_path=P/'compiler_validation_selected_manifest.jsonl';protocol_path=P/'compiler_validation_protocol.json';audit_path=P/'compiler_validation_audited_reservoir.jsonl';pool_path=P/'compiler_validation_reservoir.jsonl'
preserved={str(p):sha(p.read_bytes()) for p in (first_path,protocol_path,audit_path,pool_path,P/'compiler_validation_summary.json')}
assert preserved[str(first_path)]=='4193d41c4c3e19dd4888ebc7c5d9c3c0923fc532745a228cc5fc0db3c18e839a'
first=rows(first_path);audit=rows(audit_path);eligible=[r for r in audit if r['audit_disposition']=='eligible_unconsumed_audited_cluster'];dev=rows(D/'compiler_validation_development_ids.jsonl');edges=rows(P/'compiler_validation_cluster_edges.jsonl')
assert len(eligible)==211 and len(first)==30
assert [r['id'] for r in first]==[r['id'] for r in eligible[:30]]
assert eligible==sorted(eligible,key=lambda r:r['reservoir_rank'])
reserve=[{**r,'reserve_order':i+1,'original_eligible_rank':31+i,'reserve_status':'unconsumed_precommitted_single_generic_fix_revalidation_only','ready_for_validation':False} for i,r in enumerate(eligible[30:60])]
assert len(reserve)==30 and len({r['audit_cluster'] for r in reserve})==30
assert not ({r['audit_cluster'] for r in first}&{r['audit_cluster'] for r in reserve})
parent={r['id']:r['id'] for r in dev+audit}
def find(x):
 while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
 return x
def union(x,y):
 x,y=find(x),find(y)
 if x!=y:parent[max(x,y)]=min(x,y)
for e in edges:
 assert e['evidence'].startswith('hard_') or e['evidence']=='typed_DOT_graph_isomorphism'
 union(e['left'],e['right'])
devc={find(r['id']) for r in dev};firstc={find(r['id']) for r in first};reservec={find(r['id']) for r in reserve}
assert len(reservec)==30 and not(reservec&devc) and not(reservec&firstc)
assert all(r['source_hash_verified'] and not r['development_overlap'] and not r['component_near_development_DOT_unknown'] for r in reserve)
reserve_file=P/'compiler_validation_repair_reserve.jsonl';b=b''.join(blob(r) for r in reserve)
with reserve_file.open('xb') as f:f.write(b)
reserve_file.chmod(0o444)
for p,h in preserved.items():assert sha(Path(p).read_bytes())==h
summary={'kind':'unconsumed metadata-only precommit reserve','usage_condition':'Only if first30 validation fails its precommitted gates and one generic repair is frozen, may this sole fresh31-60 cohort be activated. If first30 passes, keep reserve unconsumed. No additional repair validation cohort is authorized by this precommit.','source_audit_directory':str(P),'eligible_clusters':211,'eligible_rank_interval_inclusive':[31,60],'reserve_count':30,'reserve_manifest':str(reserve_file),'reserve_sha256':sha(b),'reserve_bytes':len(b),'first30_manifest_sha256':preserved[str(first_path)],'audit_manifest_sha256':preserved[str(audit_path)],'original_protocol_sha256':preserved[str(protocol_path)],'original_pool_sha256':preserved[str(pool_path)],'proof':{'first30_ids_unchanged':True,'original500_pool_and_protocol_unchanged':True,'fixed_original_ranks31_to60':True,'reserve_unique_hard_DOT_components':30,'reserve_first30_hard_DOT_component_overlap':0,'reserve_6581_development_hard_DOT_component_overlap':0,'development_records':len(dev),'reserve_unknown_or_development_DOT_evidence':0},'registry_reserved_or_written':False,'new_source_or_media_read':False,'new_DOT_parse':False,'validation_executions':0,'outcomes_viewed':False,'model_calls':0,'generator_independence_proven':False,'reserve_id_cluster_metadata':[{'id':r['id'],'audit_cluster':r['audit_cluster'],'reserve_order':r['reserve_order'],'original_eligible_rank':r['original_eligible_rank'],'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256']} for r in reserve]}
p=P/'compiler_validation_repair_reserve_summary.json'
with p.open('xb') as f:f.write(blob(summary))
p.chmod(0o444);print(json.dumps(summary))
