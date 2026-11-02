"""Read-only viewport/source-identity preflight over all 953 audit IDs."""
import sys,json,sqlite3,collections,hashlib,datetime
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path[:0]=[str(W/'prototype'),str(W/'scripts')]
from mermaid_page_metadata_candidate_v1 import viewport_facts,canonical
from mermaid_page_metadata_batch_v1 import context
sha=lambda b:hashlib.sha256(b).hexdigest();db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);audit_file=W/'mermaid_canvas_metadata_audit_v1.json';audit_raw=audit_file.read_bytes();audit=json.loads(audit_raw);owner=(W/'auto_quality_owner.json').read_bytes();rows=[]
for item in audit['records']:
 id=item['id'];result={'id':id,'audit_code_sha256':item['code_sha256'],'audit_image_sha256':item['image_sha256']}
 try:
  job,outcome,q,old,source=context(db,id);assert (old['code_sha256'],old['image_sha256'],old['source_image_sha256'])==(item['code_sha256'],item['image_sha256'],item['source_image_sha256']),'audit_current_hash_changed';data,size,facts=viewport_facts(R,old,source);after=context(db,id);assert after[0]==job and after[1]==outcome and after[2]==q,'changed_during_read_only_preflight';result.update(state='viewport_identity_preflight_pass',code_sha256=old['code_sha256'],image_sha256=old['image_sha256'],source_code_sha256=old['source_code_sha256'],source_image_sha256=old['source_image_sha256'],job_snapshot_sha256=sha(canonical(job)),outcome_snapshot_sha256=sha(canonical(outcome)),queue_snapshots_sha256=sha(canonical(q)),viewport=size)
 except Exception as error:result.update(state='deferred_or_stale',reason=str(error))
 rows.append(result)
assert audit_file.read_bytes()==audit_raw and (W/'auto_quality_owner.json').read_bytes()==owner,'scope_or_policy_changed';report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_audit_count':len(audit['records']),'input_audit_sha256':sha(audit_raw),'active_qa_owner_sha256':sha(owner),'groups':dict(collections.Counter(r['state'] for r in rows)),'deferred_reasons':dict(collections.Counter(r['reason'] for r in rows if 'reason' in r)),'records':rows,'scope':'Entire 953-ID audit viewport/source/current identity preflight only. This does not run official AST or fresh native equivalence for all records and is not whole-pair qualification.','production_changes':0,'model_calls':0};folder=W/'prototype/mermaid_page_metadata_v1_smoke';folder.mkdir(exist_ok=True);path=folder/'cohort_preflight.json';path.write_bytes(canonical(report));print(json.dumps({k:v for k,v in report.items() if k!='records'}|{'report':str(path)}),flush=True)
