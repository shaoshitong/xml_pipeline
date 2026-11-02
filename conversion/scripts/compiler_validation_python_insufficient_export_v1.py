import json,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
a=[json.loads(x) for x in (P/'compiler_validation_audited_reservoir.jsonl').read_text().splitlines()]
remaining=[]
for x in a:
 if x['audit_disposition']!='eligible_unconsumed_audited_cluster':continue
 remaining.append({k:x[k] for k in ('id','seq','format','provider','source_locator','code_sha256','image_sha256','support_unit','audit_cluster','reservoir_rank','source_record_sha256','cached_source_artifacts','static_support_evidence')})
assert len(remaining)==11
b=b''.join((json.dumps(x,sort_keys=True,ensure_ascii=False)+'\n').encode() for x in remaining)
p=P/'compiler_validation_insufficient_candidates.jsonl'
with p.open('xb') as f:f.write(b)
p.chmod(0o444)
s=json.loads((P/'compiler_validation_summary.json').read_text());integrity=json.loads((P/'compiler_validation_integrity.json').read_text())
d={'status':'blocked_before_validation_insufficient_audited_clusters','remote_directory':str(P),'matching_unseen_queued_population':11046,'frozen_hash_reservoir':500,'eligible_operational_clusters':11,'minimum_required':30,'validation_selected':0,'candidate_audit_dispositions':{'development_cluster_overlap':489,'eligible_unconsumed_audited_cluster':11},'insufficient_candidates_file':str(p),'insufficient_candidates_file_sha256':sha(b),'candidate_metadata':remaining,'full_artifacts':s['files'],'predicate_pins':s['predicate_pins'],'integrity':integrity,'limitations':['489 development-connected cases indicate conservative structural/provenance cluster overlap, not proof of shared latent generator identity. Overclustering is possible.','The fixed audit rules and candidate pool were not relaxed or refilled after inspecting metadata counts.','No conversion, target render, new QA or model result was consumed; all candidates remain unconsumed.','No ordinary independent-binomial confidence interval or population yield estimate is justified from these operational clusters.'],'elapsed_seconds':s['elapsed_seconds'],'model_calls':0,'validation_executions':0,'batch_started':False,'old_queue_restart':False}
print(json.dumps(d,ensure_ascii=False))
