"""Resumable read-only marker scan of a frozen SVG/PNG filename queue.

No pixel decode, conversion, external request or automatic product acceptance.
"""
from pathlib import Path
import collections,datetime,fcntl,json,os,sqlite3,struct,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');BASE=R/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/papers';D=R/'clean/arxiv_research_figures_v1/embedded_XML_image_inventory_v2'
def probe(p):
 ext=p.suffix.lower()
 with p.open('rb') as f:
  if ext=='.svg':
   b=f.read(65536)
   if b'mxfile' in b or b'mxGraphModel' in b:return dict(file=str(p.relative_to(R)),kind='SVG_native_XML_marker')
  elif ext=='.png':
   size=os.fstat(f.fileno()).st_size
   if f.read(8)!=b'\x89PNG\r\n\x1a\n':return None
   for _ in range(10000):
    head=f.read(8)
    if len(head)!=8:return None
    n,kind=struct.unpack('>I4s',head)
    if n>size:return None
    if kind in [b'tEXt',b'zTXt',b'iTXt']:
     prefix=f.read(min(n,128));key=prefix.split(b'\0',1)[0]
     if key.lower() in [b'mxfile',b'mxgraphmodel',b'drawio']:return dict(file=str(p.relative_to(R)),kind='PNG_native_XML_marker',keyword=key.decode(errors='replace'))
     f.seek(n-len(prefix)+4,1)
    else:f.seek(n+4,1)
    if kind==b'IEND':return None
 return None
def publish(c):
 states=dict(c.execute('select status,count(*) from files group by status'));markers=[json.loads(r[0]) for r in c.execute("select details from files where status='marker' order by path")];enumerated=c.execute("select value from meta where key='enumerated'").fetchone();done=bool(enumerated and enumerated[0]=='1')
 result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),directory_walk_complete=done,scan_complete=done and states.get('queued',0)==0 and states.get('pending_io_error',0)==0,states=states,native_XML_markers=len(markers),candidates=markers,scan_scope='SVG first64KiB and PNG text-chunk keywords; frozen filename cohort; only candidates',new_PDF_import_calls=0,new_source_replay_calls=0,new_source_downloads=0,new_model_calls=0,pixel_data_not_decoded=True)
 p=D/'inventory.json';t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');t.write_text(json.dumps(result,indent=2)+'\n');os.replace(t,p);print(json.dumps({k:v for k,v in result.items() if k!='candidates'}),flush=True)
def main():
 D.mkdir(exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 c=sqlite3.connect(D/'files.sqlite');c.execute('pragma journal_mode=WAL');c.execute('create table if not exists files(path text primary key,status text,details text)');c.execute('create table if not exists meta(key text primary key,value text)')
 if c.execute("select value from meta where key='enumerated'").fetchone()!=('1',):
  batch=[]
  for root,dirs,names in os.walk(BASE):
   dirs.sort()
   if '/source' not in root:continue
   for name in sorted(names):
    p=Path(root)/name
    if p.suffix.lower() in ['.png','.svg']:batch.append((str(p.relative_to(R)),'queued','{}'))
    if len(batch)>=5000:c.executemany('insert or ignore into files values(?,?,?)',batch);c.commit();batch=[];publish(c)
  c.executemany('insert or ignore into files values(?,?,?)',batch);c.execute("insert or replace into meta values('enumerated','1')");c.commit();publish(c)
 while True:
  batch=c.execute("select path from files where status='queued' order by path limit 500").fetchall()
  if not batch:break
  for name, in batch:
   try:marker=probe(R/name);status='marker' if marker else 'checked';details=marker or {}
   except OSError as error:status='pending_io_error';details=dict(reason=type(error).__name__+':'+str(error))
   c.execute('update files set status=?,details=? where path=?',(status,json.dumps(details),name))
  c.commit();publish(c)
 publish(c)
if __name__=='__main__':main()
