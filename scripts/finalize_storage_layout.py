from pathlib import Path
import datetime,hashlib,json,os,shutil
R=Path('/backup/shaoshitong/img2code_20261029');M=R/'reports/storage_migration'
read=lambda p:json.loads(p.read_text());audit=read(M/'content_audit.json');record=read(M/'record_audit.json');cleanup=read(M/'cleanup.json');summary=read(R/'release/summary.json')
assert audit['ok'] and record['ok'] and cleanup['ok'] and audit['checked_pairs']==784171
manifest=R/'release/manifest.jsonl';h=hashlib.sha256(manifest.read_bytes()).hexdigest();assert h==summary['sha256']==record['manifest_sha256']==audit['input_manifest_sha256']['unified']
empty=[]
for base,dirs,files in os.walk(R/'clean',followlinks=False):
 if not dirs and not files:empty.append(base)
assert not empty,empty
assert not (R/'derived').exists()
for x in cleanup['deleted']:assert not (R/x['path']).exists(),x['path']
finished=datetime.datetime.now(datetime.timezone.utc).isoformat();summary.update(status='complete',storage_updated_at_utc=finished)
(R/'release/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
acceptance={'ok':True,'finished_at_utc':finished,'total_pairs':784171,'manifest_sha256':h,'records_unchanged_except_paths':record['ok'],'external_active_paths':0,'missing_active_paths':0,'full_content_checked_pairs':audit['checked_pairs'],'full_content_errors':audit['errors'],'clean_empty_directories':0,'top_level_derived_exists':False,'authorized_cleanup_complete':True,'audit_reports':['reports/storage_migration/record_audit.json','reports/storage_migration/content_audit.json','reports/storage_migration/cleanup.json'],'historical_semantic_quality_limits_unchanged':True}
(R/'release/acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
complete={'status':'complete','finished_at_utc':finished,'root':str(R),'manifest':str(manifest),'manifest_sha256':h,'total_pairs':784171,'payload_root':str(R/'clean'),'acceptance':'release/acceptance.json','storage_layout_version':2}
(R/'release/complete.json').write_text(json.dumps(complete,indent=2)+'\n')
old=R/'collection_done.json'
if old.exists():shutil.copy2(old,M/'before/collection_done.json')
old.write_text(json.dumps(complete,indent=2)+'\n')
print(json.dumps({'summary':summary,'acceptance':acceptance,'cleanup':{'deleted_allocated_file_bytes':cleanup['deleted_allocated_file_bytes'],'deleted_paths':[x['path'] for x in cleanup['deleted']],'empty_clean_directories_removed':len(cleanup['empty_clean_directories'])}},ensure_ascii=False))
