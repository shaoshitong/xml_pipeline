"""Explicitly authorized single candidate publication, with original-pair audit."""
import hashlib,json,sqlite3,subprocess,uuid
from pathlib import Path
import tikz_execution_candidate_batch_v1 as b
ID='6a09ccf14db3f3ac3d016e3eff21daed7c468f7e9a7ea1a5fef3a853f6fe36a6'
policy,files=b.implementation();db=sqlite3.connect('file:'+str(b.W/'jobs.sqlite')+'?mode=ro',uri=True);selection=b.select_candidate(db,policy,uuid.uuid4().hex,publish=True,ids=[ID])
if selection is None:
 out={'at':b.now(),'id':ID,'published':False,'accepted':0,'skipped_busy_or_ineligible':True};db.close();b.atomic(b.W/'tikz_execution_candidate_v1_publish_smoke.json',(json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out));raise SystemExit(0)
prior=b.snapshot(db,ID);old=json.loads(prior[1]);original={k:(b.R/old[k]).read_bytes() for k in ('code_file','image_file','original_source_code','original_reference')};meta=(b.R/old['code_file']).parent/'conversion.json';old_meta=meta.read_bytes();models={t:db.execute('select * from '+t+' where id=?',(ID,)).fetchone() for t in b.MODEL_TABLES if b.exists(db,t)};db.close()
run=subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(b.W/'scripts/tikz_execution_candidate_batch_v1.py'),'--workers','1','--limit','1','--publish','--id',ID],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900);b.atomic(b.W/'tikz_execution_candidate_v1_publish_smoke.stdout',run.stdout.encode());b.atomic(b.W/'tikz_execution_candidate_v1_publish_smoke.stderr',run.stderr.encode());print(run.stdout,flush=True);assert run.returncode==0,run.stderr[-2500:]
db=sqlite3.connect('file:'+str(b.W/'jobs.sqlite')+'?mode=ro',uri=True);current=b.snapshot(db,ID);new=json.loads(current[1]);models_after={t:db.execute('select * from '+t+' where id=?',(ID,)).fetchone() for t in models};db.close();assert current[0]=='needs_quality_repair' and new['conversion_method']==b.METHOD and new['quality_state']=='pending_automatic_quality_v3_recheck';assert current[2] is None;assert current[5:]==prior[5:];assert meta.read_bytes()==old_meta
for key,blob in original.items():assert (b.R/old[key]).read_bytes()==blob
for key in ('id','source_pair_sha256','source_code_sha256','source_image_sha256'):assert new[key]==old[key]
assert new.get('previous_candidate_archive')==old.get('previous_candidate_archive')
archive=b.R/new['execution_prior_pair_archive'];assert archive.resolve().is_relative_to(b.R/'clean');assert json.loads((archive/'conversion.json').read_text())==old;assert (archive/'diagram.drawio').read_bytes()==original['code_file'] and (archive/'image.png').read_bytes()==original['image_file']
for table,previous in models.items():
 if previous is not None:
  after=models_after[table];assert after[0]==previous[0] and after[1]=='held_for_quality_v3' and after[2]==previous[2] and after[3] is None
record_file=(b.R/new['code_file']).parent/'conversion.json';assert json.loads(record_file.read_text())==new;out={'at':b.now(),'id':ID,'published':True,'accepted':0,'policy':policy,'job_state':current[0],'quality_state':new['quality_state'],'candidate_record_file':str(record_file),'code_sha256':new['code_sha256'],'image_sha256':new['image_sha256'],'source_and_native_prior_payloads_unchanged':True,'old_metadata_pointer_unchanged':True,'complete_prior_pair_archive_verified':True,'legacy_harness_archive_locator_preserved':True,'model_running_calls_untouched_and_idle_attempt_history_preserved':True,'input_record_manifest_attempts_route_format_source_category_unchanged':True};b.atomic(b.W/'tikz_execution_candidate_v1_publish_smoke.json',(json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out),flush=True)
