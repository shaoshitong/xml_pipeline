import hashlib,json,shutil,sqlite3
from pathlib import Path
from native_worker import R,W,now
from sandbox_runner import run,PYTHON

def main():
 db=sqlite3.connect(W/'jobs.sqlite');rows=[]
 for source in ('MiliLab--Omni-I2C','allenai--CoSyn-400K'):rows.extend(db.execute('select id,input_record,input_manifest from jobs where format="python" and source=? order by id limit 3',(source,)).fetchall())
 results=[]
 for id,raw,prepared in rows:
  inp=json.loads(prepared);source=json.loads(raw);directory=W/'python_pilot'/id;directory.mkdir(parents=True,exist_ok=True);code=(R/inp['source_code']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];(directory/'source.py').write_bytes(code);shutil.copy2(W/'scripts/python_capture.py',directory/'capture.py');extra=[]
  if inp.get('source_data'):shutil.copy2(R/inp['source_data'],directory/'data.json')
  for p in (W/'runtime/graphviz',W/'runtime/python_packages'):
   if p.exists():extra.append((p,p))
  try:
   r=run(directory,[PYTHON,'-I','/work/capture.py'],timeout=150,extra_ro=extra);(directory/'stdout.log').write_text(r.stdout);(directory/'stderr.log').write_text(r.stderr);result={'id':id,'source':source['source'],'directory':str(directory),'returncode':r.returncode,'execution':json.loads((directory/'execution.json').read_text()) if (directory/'execution.json').exists() else None,'stderr_tail':r.stderr[-2000:]}
  except Exception as e:result={'id':id,'error':str(e)}
  results.append(result);print(json.dumps(result),flush=True)
 (W/'python_pilot.json').write_text(json.dumps({'finished_at_utc':now(),'results':results},indent=2)+'\n')
if __name__=='__main__':main()
