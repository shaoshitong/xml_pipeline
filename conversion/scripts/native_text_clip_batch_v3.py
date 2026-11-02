"""Repair source rectangular text clipping on font-verified HTML candidates. No autoacceptance."""
import argparse,concurrent.futures,fcntl,json,os,sqlite3,subprocess,time
from pathlib import Path
from native_worker import W,now
from durable_sqlite import begin,commit

def worker(index,limit):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);done=[];log=os.open(W/'native_text_clip_batch_v3_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 while not limit or len(done)<limit:
  row=D.execute("""select j.id,json_extract(j.output_record,'$.code_sha256') from jobs j where j.format='html' and j.state in ('rendered','needs_quality_repair') and json_extract(j.output_record,'$.render.selected_image')='declared_first_page' and json_extract(j.output_record,'$.native_font_validation.output_code_sha256')=json_extract(j.output_record,'$.code_sha256') and json_extract(j.output_record,'$.native_text_clipping') is null and not exists(select 1 from native_text_clip_repairs old where old.id=j.id and old.input_code_sha256=json_extract(j.output_record,'$.code_sha256') and old.state='no_source_text_clips') and not exists(select 1 from native_text_clip_repairs_v3 c where c.id=j.id and c.input_code_sha256=json_extract(j.output_record,'$.code_sha256')) order by j.id limit 1""").fetchone()
  if row is None:
   if limit:break
   time.sleep(20);continue
  id,hash=row;logdir=W/'native_text_clip_dispatch_v3';logdir.mkdir(exist_ok=True);path=logdir/(id+'.'+str(os.getpid())+'.log');start=time.monotonic()
  with (logdir/(id+'.lock')).open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:time.sleep(.25);continue
   if D.execute('select 1 from native_text_clip_repairs_v3 where id=? and input_code_sha256=?',(id,hash)).fetchone():continue
   with path.open('ab') as out:child=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/repair_poster_text_clip_v3.py'),id],stdin=subprocess.DEVNULL,stdout=out,stderr=out);code=child.wait()
  stage=D.execute('select state from native_text_clip_repairs_v3 where id=? and input_code_sha256=?',(id,hash)).fetchone();job=D.execute('select state,worker_pid from jobs where id=?',(id,)).fetchone();event={'at':now(),'id':id,'input_code_sha256':hash,'worker_pid':os.getpid(),'child_pid':child.pid,'exit_code':code,'stage':stage[0] if stage else None,'seconds':time.monotonic()-start,'log':str(path.relative_to(W))};os.write(log,(json.dumps(event)+'\n').encode())
  if job==('native_text_clip_v3_repairing',child.pid):
   os.close(log);return {'worker':index,'processed':len(done),'needs_owned_job_recovery':id,'terminal_child_pid':child.pid}
  if stage and stage[0]!='running' and id not in done:done.append(id)
  if code and not stage:time.sleep(1)
 os.close(log);return {'worker':index,'processed':len(done),'ids':done}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);a=p.parse_args();D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists native_text_clip_repairs_v3 (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');commit(D);D.close();(W/'native_text_clip_batch_v3_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'at':now()}))
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('native_text_clip_batch_v3_smoke_summary.json' if a.limit else 'native_text_clip_batch_v3_summary.json')).write_text(json.dumps({'at':now(),'results':results},indent=2))
