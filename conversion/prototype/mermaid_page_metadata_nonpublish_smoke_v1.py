"""Two real current records; read-only jobs/outcomes/queues, remote artifacts only."""
import sys,json,sqlite3,hashlib,datetime
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path[:0]=[str(W/'prototype'),str(W/'scripts')]
from mermaid_page_metadata_candidate_v1 import generate,canonical
sha=lambda b:hashlib.sha256(b).hexdigest();db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);audit_path=W/'mermaid_canvas_metadata_audit_v1.json';audit=json.loads(audit_path.read_text());owner=(W/'auto_quality_owner.json').read_bytes();results=[];base=W/'prototype/mermaid_page_metadata_v1_smoke';base.mkdir(exist_ok=True)
def snapshot(id):
 names=[r[1] for r in db.execute('pragma table_info(jobs)')];row=db.execute('select * from jobs where id=?',(id,)).fetchone();return dict(zip(names,row))
def guard(id):
 for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
  if not db.execute('select 1 from sqlite_master where name=?',(table,)).fetchone():continue
  cols={r[1] for r in db.execute('pragma table_info('+table+')')};extra=' or worker_pid is not NULL' if 'worker_pid' in cols else '';assert not db.execute('select 1 from '+table+" where id=? and (state='running'"+extra+')',(id,)).fetchone(),'model owned'
for receipt in audit['records']:
 if len(results)>=2:break
 id=receipt['id'];job=snapshot(id)
 if job['worker_pid'] is not None or job['state'] not in ('rendered','needs_quality_repair','harness_review_pending'):continue
 old=json.loads(job['output_record']);original=json.loads(job['input_record']);outcome=db.execute('select * from processing_outcomes_v2 where id=?',(id,)).fetchone()
 if not outcome or outcome[5]!='pending' or old['code_sha256']!=receipt['code_sha256'] or old['image_sha256']!=receipt['image_sha256']:continue
 guard(id);work=base/id/(old['code_sha256']+'_'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S%f'));work.parent.mkdir(exist_ok=True);out,proof=generate(old,original,work,R);assert snapshot(id)==job,'job changed during nonpublish smoke';assert db.execute('select * from processing_outcomes_v2 where id=?',(id,)).fetchone()==outcome,'outcome changed';guard(id);assert (W/'auto_quality_owner.json').read_bytes()==owner,'QA owner changed';item={'id':id,'job_snapshot_sha256':sha(canonical(job)),'outcome_snapshot_sha256':sha(canonical(outcome)),'qa_owner_sha256':sha(owner),'audit_sha256':sha(audit_path.read_bytes()),'work':str(work),'candidate_checks_passed':proof['candidate_checks_passed'],'state':proof['state'],'error':proof.get('error'),'published':False,'accepted':False,'stored_equals_fresh':proof.get('old_stored_png_equals_fresh'),'all_custom':proof.get('all_current_fonts_custom'),'original_gate_before':proof.get('original_quality_before',{}).get('ok'),'original_gate_after':proof.get('original_quality_after',{}).get('ok'),'AST_before':proof.get('source_before',{}).get('ok'),'AST_after':proof.get('source_after',{}).get('ok'),'output_code_sha256':proof.get('output_code_sha256'),'output_image_sha256':proof.get('output_image_sha256')};results.append(item);print(json.dumps(item),flush=True)
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'audit_scope':len(audit['records']),'real_cases':results,'whole_pairs_accepted':0,'published':0,'model_calls':0,'production_mutated':False,'scope':'Two finite proof cases, not a claim that all 953 metadata candidates satisfy every current gate.'};path=base/'report.json';path.write_bytes(canonical(result));print(json.dumps({'report':str(path),'results':results}),flush=True)
