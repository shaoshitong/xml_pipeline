import collections,hashlib,json
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v1';D=R/'release/compiler_validation_v1/cluster_audit_20261101_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
s=json.loads((P/'compiler_validation_summary.json').read_text());p=json.loads((P/'compiler_validation_protocol.json').read_text())
for f in s['files']:assert sha((P/f['file']).read_bytes())==f['sha256']
dev=rows(D/'compiler_validation_development_ids.jsonl');dids={r['id'] for r in dev};codes={r['code_sha256'] for r in dev};images={r['image_sha256'] for r in dev};dclusters={r['audit_cluster'] for r in dev}
reservoir=rows(P/'compiler_validation_reservoir.jsonl');audited=rows(P/'compiler_validation_audited_reservoir.jsonl');sel=rows(P/'compiler_validation_selected_manifest.jsonl');population=rows(P/'compiler_validation_matching_population.jsonl');edges=rows(P/'compiler_validation_cluster_edges.jsonl')
assert len(reservoir)<=500
assert [r['id'] for r in reservoir]==[r['id'] for r in sorted(reservoir,key=lambda r:r['reservoir_rank'])]
assert set(r['id'] for r in reservoir)==set(r['id'] for r in audited)
assert not any(r['id'] in dids or r['source']['code_sha256'] in codes or r['source']['image_sha256'] in images for r in reservoir)
assert len({r['audit_cluster'] for r in sel})==len(sel)
assert all(r['audit_disposition']=='eligible_unconsumed_audited_cluster' and r['source_hash_verified'] and not r['development_overlap'] for r in sel)
assert all(r['support_unit']=='python_graphviz_cached_source_v1' for r in sel)
assert len(sel)==0 or len(sel)==30
for r in sel:
 assert sha((R/r['source_locator']).read_bytes())==r['source']['code_sha256']
 ev=r['static_support_evidence'];arts=r['cached_source_artifacts']
 assert sha((R/arts['source_render_dot']).read_bytes())==ev['source_dot_sha256']
 assert sha((R/arts['source_render_svg']).read_bytes())==ev['source_svg_sha256']
 assert sha((R/arts['execution_audit']).read_bytes())==ev['execution_audit_sha256']
expected=sorted(population,key=lambda r:sha((json.dumps(['hkust-compiler-population-holdout-20261101-v1','population_reservoir',r['unit'],r['id']],sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()))[:500]
assert [r['id'] for r in expected]==[r['id'] for r in reservoir]
valid=sorted([r for r in audited if r['audit_disposition']=='eligible_unconsumed_audited_cluster'],key=lambda r:r['reservoir_rank'])
assert [r['id'] for r in sel]==[r['id'] for r in valid[:30]] if len(valid)>=30 else len(sel)==0
probe=[r['id'] for r in dev if r['id'].startswith('002e')]
out={'metadata_integrity_passed':True,'queued_matching_population':len(population),'fixed_hash_reservoir_ids_reproduced':True,'reservoir_count':len(reservoir),'selected_count':len(sel),'unique_selected_clusters':len({r['audit_cluster'] for r in sel}),'all_selected_source_and_cached_payload_hashes_verified':True,'exact_development_overlap':0,'development_roster':len(dev),'root_probe_prefix_002e_in_development_roster':probe,'no_postaudit_reservoir_refill':True,'first30_ranked_valid_clusters_reproduced':True,'validation_executions':0,'model_calls':0,'old_queue_restart':False,'generator_independence_proven':False,'statistics':s['statistics'],'predicate_pins':s['predicate_pins'],'selected_manifest_sha256':sha((P/'compiler_validation_selected_manifest.jsonl').read_bytes()),'protocol_sha256':sha((P/'compiler_validation_protocol.json').read_bytes())}
(P/'compiler_validation_integrity.json').write_text(json.dumps(out,sort_keys=True)+'\n');print(json.dumps(out))
