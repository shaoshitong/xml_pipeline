import collections,hashlib,json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v2_locator_fixed';V1=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v1';D=R/'release/compiler_validation_v1/cluster_audit_20261101_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
s=json.loads((P/'compiler_validation_summary.json').read_text());protocol=json.loads((P/'compiler_validation_protocol.json').read_text())
for f in s['files']:assert sha((P/f['file']).read_bytes())==f['sha256']
assert (P/'compiler_validation_reservoir.jsonl').read_bytes()==(V1/'compiler_validation_reservoir.jsonl').read_bytes()
dev=rows(D/'compiler_validation_development_ids.jsonl');reservoir=rows(P/'compiler_validation_reservoir.jsonl');audited=rows(P/'compiler_validation_audited_reservoir.jsonl');selected=rows(P/'compiler_validation_selected_manifest.jsonl');dot={r['id']:r for r in rows(P/'compiler_validation_DOT_audit.jsonl')};edges=rows(P/'compiler_validation_cluster_edges.jsonl')
assert [r['id'] for r in reservoir]==[r['id'] for r in audited]
assert len(selected)==30 and len({r['audit_cluster'] for r in selected})==30
assert [r['id'] for r in selected]==[r['id'] for r in audited if r['audit_disposition']=='eligible_unconsumed_audited_cluster'][:30]
parent={r['id']:r['id'] for r in dev+audited}
def find(x):
 while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
 return x
def union(a,b):
 a,b=find(a),find(b)
 if a!=b:parent[max(a,b)]=min(a,b)
for e in edges:
 assert e['evidence'].startswith('hard_') or e['evidence']=='typed_DOT_graph_isomorphism'
 union(e['left'],e['right'])
devcomponents={find(r['id']) for r in dev};dids={r['id'] for r in dev};codes={r['code_sha256'] for r in dev};images={r['image_sha256'] for r in dev}
assert not any(find(r['id']) in devcomponents for r in selected)
assert len({find(r['id']) for r in selected})==30
assert all(r['source_hash_verified'] and not r['development_overlap'] and not r['component_near_development_DOT_unknown'] for r in selected)
assert not any(r['id'] in dids or r['code_sha256'] in codes or r['image_sha256'] in images for r in selected)
near_unknown=collections.defaultdict(set)
for e in rows(V1/'compiler_validation_cluster_edges.jsonl'):
 if e['evidence']!='exhaustive_normalized_trigram_jaccard':continue
 a,b=e['left'],e['right']
 if a in dids and dot.get(a,{}).get('status')=='DOT_audit_unknown':near_unknown[b].add(a)
 if b in dids and dot.get(b,{}).get('status')=='DOT_audit_unknown':near_unknown[a].add(b)
assert not any(near_unknown[r['id']] for r in selected)
db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True)
for r in selected:
 assert sha((R/r['source_locator']).read_bytes())==r['code_sha256']
 row=db.execute('select output_record from jobs where id=?',(r['id'],)).fetchone()[0];assert sha(row.encode())==r['source_record_sha256'];record=json.loads(row);ev=r['static_support_evidence']
 assert sha((R/record['source_render_dot']).read_bytes())==ev['source_dot_sha256']==dot[r['id']]['source_dot_sha256']
 assert sha((R/record['source_render_svg']).read_bytes())==ev['source_svg_sha256']
 assert sha((R/record['execution_audit']).read_bytes())==ev['execution_audit_sha256']
 assert sha((P/'dot_json'/(ev['source_dot_sha256']+'.json')).read_bytes())==dot[r['id']]['dot_json_sha256']
assert not s['audit_budget_exceeded']
result={'metadata_integrity_passed':True,'old500_IDs_and_order_unchanged':True,'old_reservoir_bytes_unchanged':True,'first30_ranked_eligible_clusters_reproduced':True,'unique_selected_operational_clusters':30,'selected_development_components_overlap':0,'selected_unknown_DOT_or_near_unknown_development':0,'all_selected_source_record_DOT_SVG_capture_and_parser_JSON_hashes_verified':True,'edges_only_hard_or_typed_DOT_isomorphism':True,'Python_near_alone_union_links':0,'validation_executions':0,'new_QA_outcomes_seen':False,'generator_independence_proven':False,'selected_manifest_sha256':sha((P/'compiler_validation_selected_manifest.jsonl').read_bytes()),'protocol_sha256':sha((P/'compiler_validation_protocol.json').read_bytes()),'selected_metadata':[{'id':r['id'],'seq':r['seq'],'source':r['source'],'provider':r['provider'],'source_locator':r['source_locator'],'audit_cluster':r['audit_cluster'],'source_record_sha256':r['source_record_sha256'],'source_dot_sha256':r['static_support_evidence']['source_dot_sha256'],'typed_invariant':r['DOT_audit']['typed_invariant']} for r in selected]}
(P/'compiler_validation_integrity.json').write_text(json.dumps(result,sort_keys=True)+'\n');print(json.dumps(result))
