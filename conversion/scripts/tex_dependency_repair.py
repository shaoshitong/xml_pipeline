"""Resolve missing official bundle files, requeue only proven dependency failures."""
import hashlib,json,re,sqlite3,time
from pathlib import Path
from native_worker import W,now
from tectonic_compile import fetch,missing_files
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);D.execute('create table if not exists tikz_dependency_repairs (id TEXT,error_sha256 TEXT,record TEXT,updated_at TEXT,primary key(id,error_sha256))');D.commit();(W/'tex_dependency_owner.json').write_text(json.dumps({'pid':__import__('os').getpid(),'started_at_utc':now()})+'\n')
def live():
 try:
  o=json.loads((W/'tikz_render_owner.json').read_text());p=Path('/proc')/str(o['pid'])/'cmdline';return p.exists() and b'tikz_render_batch.py' in p.read_bytes()
 except (OSError,ValueError):return False
while True:
 changed=0
 for id,error in D.execute('select id,error from jobs where format="tikz" and state="needs_fallback"').fetchall():
  text=error or '';h=hashlib.sha256(text.encode()).hexdigest()
  if D.execute('select 1 from tikz_dependency_repairs where id=? and error_sha256=?',(id,h)).fetchone():continue
  names=set(missing_files(text))
  for lib in re.findall(r"did not find the pgf library '([A-Za-z0-9_.-]+)'",text):names.add('pgflibrary'+lib+'.code.tex')
  for lib in re.findall(r"did not find the pgfplots library '([A-Za-z0-9_.-]+)'",text):names.add('pgfplotslibrary'+lib+'.code.tex')
  if not names:continue
  result=[]
  for name in sorted(names):
   try:result.append(fetch(name))
   except Exception as exc:result.append({'name':name,'ok':False,'error':str(exc)[:500]})
  requeue=any(r['ok'] for r in result)
  D.execute('begin immediate');D.execute('insert or ignore into tikz_dependency_repairs values (?,?,?,?)',(id,h,json.dumps({'files':result,'requeued':requeue}),now()))
  if requeue:changed+=D.execute('update jobs set state="queued",error=NULL,updated_at=? where id=? and state="needs_fallback" and error=?',(now(),id,error)).rowcount
  D.commit();print(json.dumps({'time':now(),'id':id,'dependencies':[r['name'] for r in result],'requeued':requeue}),flush=True)
 if not live():break
 time.sleep(20)
(W/'tex_dependency_summary.json').write_text(json.dumps({'finished_at_utc':now(),'repair_records':D.execute('select count(*) from tikz_dependency_repairs').fetchone()[0],'goal_complete':False})+'\n')
