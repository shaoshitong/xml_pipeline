import argparse,concurrent.futures,hashlib,json,os,shutil,sqlite3,time
from pathlib import Path
from native_worker import R,W,now
from sandbox_runner import run,PYTHON

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=60)
def worker(index,limit):
 db=connect();n=0;counts={};log=os.open(W/'python_render_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 while not limit or n<limit:
  db.execute('begin immediate');item=db.execute('select id,input_record,input_manifest from jobs where route="python" and state="queued" order by id limit 1').fetchone()
  if not item:db.commit();break
  id,raw,prepared=item;db.execute('update jobs set state="python_rendering",attempts=attempts+1,worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();source=json.loads(raw);inp=json.loads(prepared);directory=W/'python_render'/id[:2]/id;directory.mkdir(parents=True,exist_ok=True);began=time.monotonic();error=None;result=None
  try:
   code=(R/inp['source_code']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];(directory/'source.py').write_bytes(code);shutil.copy2(W/'scripts/python_capture.py',directory/'capture.py')
   if inp.get('source_data'):
    data=(R/inp['source_data']).read_bytes();assert hashlib.sha256(data).hexdigest()==inp['source_data_sha256'];(directory/'data.json').write_bytes(data)
   if inp.get('panel_assets'):raise ValueError('Asset-bearing Python requires asset manifest support')
   extra=[(p,p) for p in [W/'runtime/graphviz',W/'runtime/python_packages'] if p.exists()];r=run(directory,[PYTHON,'-I','/work/capture.py'],timeout=150,extra_ro=extra);(directory/'stdout.log').write_text(r.stdout);(directory/'stderr.log').write_text(r.stderr);meta=json.loads((directory/'execution.json').read_text()) if (directory/'execution.json').exists() else {'ok':False,'error':r.stderr[-2500:]};assert r.returncode==0 and meta['ok'],json.dumps(meta)
   captures=[]
   for c in meta['captures']:
    p=directory/c['svg'];assert p.is_file() and p.stat().st_size>100;captures.append({**c,'svg_file':str(p.relative_to(R)),'svg_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
   result={'id':id,'source':source['source'],'source_code_sha256':source['code_sha256'],'input_manifest':inp,'directory':str(directory.relative_to(R)),'captures':captures,'figures':len(captures),'execution':meta,'sandbox':'bwrap --unshare-all; explicit read-only runtimes; network/host private paths inaccessible; per-case writable work directory; CPU/memory/file limits','source_data_provided':bool(inp.get('source_data')),'native_drawio_conversion_complete':False,'captured_at_utc':now()};state='python_source_rendered';(directory/'preparation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  except Exception as e:state='needs_fallback';error=type(e).__name__+': '+str(e)[:2500]
  db.execute('insert or replace into python_renders values (?,?,?,?,?)',(id,state,json.dumps(result,ensure_ascii=False) if result else None,error,now()));db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(state,error,now(),id));db.commit();n+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'id':id,'worker':index,'pid':os.getpid(),'state':state,'error':error,'seconds':round(time.monotonic()-began,2)})+'\n').encode())
 os.close(log);return {'worker':index,'processed':n,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int,default=0);args=p.parse_args();assert (W/'runtime/graphviz/bin/dot').exists();assert json.loads((W/'aux_data_preparation.json').read_text())['ok'];db=connect();db.execute('create table if not exists python_renders (id TEXT PRIMARY KEY,state TEXT,record TEXT,error TEXT,updated_at TEXT)');db.commit();db.close();(W/'python_render_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':args.workers,'limit_per_worker':args.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(worker,range(args.workers),[args.limit]*args.workers))
 (W/('python_render_smoke_summary.json' if args.limit else 'python_render_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':results,'goal_complete':False},indent=2)+'\n')
