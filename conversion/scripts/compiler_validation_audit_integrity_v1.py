import json,hashlib,collections
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/cluster_audit_20261101_v1';O=R/'release/round2_heldout_v1/unseen_protocol_20261101_v2'
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
s=json.loads((P/'compiler_validation_summary.json').read_text())
for f in s['files']:assert sha((P/f['file']).read_bytes())==f['sha256']
dev=rows(P/'compiler_validation_development_ids.jsonl');cand=rows(P/'compiler_validation_cluster_candidates.jsonl');selected=rows(P/'compiler_validation_candidate_manifest.jsonl');old=rows(O/'manifest.jsonl');excluded=rows(O/'exclusions.jsonl');oldids={r['id'] for r in excluded};devclusters={r['audit_cluster'] for r in dev};eligible=[r for r in cand if r['audit_disposition']=='eligible_unconsumed_audited_cluster']
assert {r['id'] for r in cand}=={r['id'] for r in old}
assert len({r['audit_cluster'] for r in eligible})==len(eligible)
assert not any(r['audit_cluster'] in devclusters for r in eligible)
assert all(r['source_hash_verified'] for r in eligible)
assert all(r['support_unit'] and r['audit_disposition']=='eligible_unconsumed_audited_cluster' for r in selected)
assert len({r['id'] for r in dev})==len(dev)
a={'metadata_integrity_passed':True,'old_frozen_480_ids_unchanged':True,'globally_one_representative_per_eligible_cluster':True,'eligible_development_cluster_overlap':0,'eligible_source_hashes_verified':True,'development_records':len(dev),'newly_development_ids_not_in_old6577':[{'id':r['id'],'format':r['format'],'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256']} for r in dev if r['id'] not in oldids],'candidate_dispositions':dict(collections.Counter(r['audit_disposition'] for r in cand)),'unknown_candidate_reasons':[{'id':r['id'],'format':r['format'],'reason':r['audit_error']} for r in cand if r['cluster_parse_status']=='unknown'],'support_group_eligible_counts':dict(collections.Counter(r['support_unit'] for r in selected)),'validation_executions':0,'old_queue_restart':False,'generator_independence_proven':False}
(P/'compiler_validation_integrity.json').write_text(json.dumps(a,sort_keys=True)+'\n');print(json.dumps(a))
