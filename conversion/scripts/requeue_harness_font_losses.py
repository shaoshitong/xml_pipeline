import hashlib,json,sqlite3,sys
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');R=W.parent;sys.path.insert(0,str(W/'scripts'))
from native_worker import now
from durable_sqlite import begin,commit
sha=lambda b:hashlib.sha256(b).hexdigest()
D=sqlite3.connect(W/'jobs.sqlite',timeout=2);inventory=json.loads((W/'harness_v3_font_loss_inventory.json').read_text());results=[]
for row in inventory['cases']:
 if not row['missing_prior_fonts']:continue
 id=row['id'];state,raw=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()
 if state!='harness_review_pending':results.append({'id':id,'skipped_state':state});continue
 r=json.loads(raw);assert r['previous_candidate_archive']==row['archive'];previous=json.loads((R/row['archive']/'conversion.json').read_text());assert previous['source_code_sha256']==r['source_code_sha256'] and previous['source_image_sha256']==r['source_image_sha256'];assert sha((R/r['code_file']).read_bytes())==r['code_sha256'] and sha((R/r['image_file']).read_bytes())==r['image_sha256']
 for f in previous['native_embedded_fonts']:assert (R/f['file']).resolve().is_relative_to(R/'clean') and sha((R/f['file']).read_bytes())==f['sha256']
 B=W/'harness_v3_font_recovery'/id;B.mkdir(parents=True,exist_ok=True);(B/'before_record.json').write_text(raw);q=D.execute('select * from harness_queue_v3 where id=?',(id,)).fetchone();(B/'before_queue.json').write_text(json.dumps(q));r['source_font_recovery_archive']=row['archive'];r['font_portability_regression']={'at':now(),'missing_prior_font_aliases':row['missing_prior_fonts'],'critic_pass_invalidated':True,'reason':'V3 compact/hydrate omitted native_embedded_fonts; re-evaluate with verified font registry and independent source editability gates.','audit':str(B.relative_to(R))};r['quality_state']='needs_font_resource_and_independent_editability_repair';new=json.dumps(r,ensure_ascii=False)
 begin(D)
 if D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()!=(state,raw):D.rollback();results.append({'id':id,'skipped_changed':True});continue
 assert D.execute('select state from harness_queue_v3 where id=?',(id,)).fetchone()==('attempt_finished',)
 p=(R/r['code_file']).parent/'conversion.json';temp=p.with_suffix('.fontreview.tmp');temp.write_text(new+'\n');temp.replace(p);D.execute('update jobs set state="needs_quality_repair",output_record=?,updated_at=? where id=?',(new,now(),id));D.execute('update harness_queue_v3 set state="held_for_font_v4",priority=-1,worker_pid=NULL,error=? where id=?',('Prior native font registry lost; v4 re-evaluation required',id));commit(D);(B/'requeued.json').write_text(json.dumps({'id':id,'at':now(),'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256']}));results.append({'id':id,'requeued':True,'code_sha256_unchanged':r['code_sha256'],'image_sha256_unchanged':r['image_sha256']})
out={'at':now(),'results':results};(W/'harness_v3_font_recovery_requeue.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
