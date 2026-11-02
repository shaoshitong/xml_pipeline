"""Revision-keyed VEE delta discovery; serialized repair with durable ownership checks."""
import argparse,hashlib,json,os,sqlite3,subprocess,time
from PIL import Image
from native_worker import R,W,now
from durable_sqlite import begin,commit
from source_vee_incremental import patch,NoVeeDelta

def main(limit):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists source_vee_scan (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');commit(D);count=0;(W/'source_vee_batch_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':1,'limit':limit,'at':now()}))
 while not limit or count<limit:
  row=D.execute("""select id,state,output_record from jobs j where format in ('python','svg') and state in ('rendered','needs_quality_repair') and json_extract(output_record,'$.native_source_font_repair.source_after_dom_file') is not null and json_extract(output_record,'$.native_font_validation.output_code_sha256')=json_extract(output_record,'$.code_sha256') and json_extract(output_record,'$.native_source_marker_repair') is null and not exists(select 1 from source_vee_scan s where s.id=j.id and s.input_code_sha256=json_extract(j.output_record,'$.code_sha256')) order by id limit 1""").fetchone()
  if not row:
   if limit:break
   time.sleep(30);continue
  id,state,raw=row;r=json.loads(raw);h=r['code_sha256'];report={'id':id,'input_code_sha256':h,'at':now()};stage='validation_error'
  try:
   domfile=R/r['native_source_font_repair']['source_after_dom_file'];assert hashlib.sha256(domfile.read_bytes()).hexdigest()==r['native_source_font_repair']['source_after_dom_sha256'];dom=json.loads(domfile.read_text());xml=(R/r['code_file']).read_text();assert hashlib.sha256(xml.encode()).hexdigest()==h;w,he=Image.open(R/r['original_reference']).size;new,proof=patch(xml,dom,w,he);report['source_confirmed_additional_markers']=len(proof['markers']);stage='eligible'
  except NoVeeDelta as e:stage='no_additional_vee';report['reason']=str(e)
  except Exception as e:report['error']=repr(e)
  if stage=='eligible':
   # Only dispatch a still-idle exact revision. The child claims again under transaction.
   current=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()
   if current!=(state,raw):time.sleep(.5);continue
   folder=W/'source_vee_dispatch';folder.mkdir(exist_ok=True);log=folder/(id+'.'+h+'.log')
   with log.open('ab') as f:child=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/repair_source_vee_incremental.py'),id],stdin=subprocess.DEVNULL,stdout=f,stderr=f);code=child.wait()
   owned=D.execute('select state,worker_pid from jobs where id=?',(id,)).fetchone();assert owned!=('source_vee_repairing',child.pid),'Terminal child left owned job; recovery required'
   result=D.execute('select state,record from source_vee_repairs where id=? and input_code_sha256=?',(id,h)).fetchone()
   if not result:time.sleep(1);continue
   stage=result[0];report.update(repair_result=json.loads(result[1]),child_pid=child.pid,exit_code=code,log=str(log.relative_to(R)))
  begin(D);D.execute('insert or ignore into source_vee_scan values (?,?,?,?,?)',(id,h,stage,json.dumps(report),now()));commit(D);count+=1
  with (W/'source_vee_batch_events.jsonl').open('a') as f:f.write(json.dumps({'id':id,'input_code_sha256':h,'stage':stage,'at':now()})+'\n')
 print(json.dumps({'at':now(),'scanned':count,'states':D.execute('select state,count(*) from source_vee_scan group by state').fetchall()}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);a=p.parse_args();main(a.limit)
