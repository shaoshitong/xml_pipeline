"""Continue native XML marker discovery from newly completed source papers.

Seeds the complete frozen v2 ledger, never re-probes its paths, and scans each
later completed source paper once. Header markers remain candidates, not pairs.
"""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,sqlite3,time,uuid
from inventory_arxiv_embedded_XML_images_v2 import probe
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';F=P/'embedded_XML_image_inventory_v2';D=P/'embedded_XML_image_inventory_incremental_v3';BASE=P/'recent_ai_source_expansion_v2/papers'
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(path,obj):
 t=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');t.write_text(json.dumps(obj,indent=2)+'\n');os.replace(t,path)
def schema(c):
 c.execute('pragma journal_mode=WAL');c.execute('create table if not exists files(path text primary key,status text,details text,origin text)');c.execute('create table if not exists papers(id text primary key,status text,finished_utc text,details text)');c.execute('create table if not exists meta(key text primary key,value text)');c.commit()
def scan_source(c,paper,root,probe_fn=probe):
 prior=c.execute('select status from papers where id=?',(paper,)).fetchone()
 if prior and prior[0] in ('covered_by_frozen_v2','scanned'):return 0
 if not root.is_dir():return None
 added=0
 def walk_error(error):raise error
 for folder,dirs,names in os.walk(root,followlinks=False,onerror=walk_error):
  dirs.sort()
  for name in sorted(names):
   p=Path(folder)/name
   if p.suffix.lower() not in ('.svg','.png'):continue
   key=str(p)
   if c.execute('select 1 from files where path=?',(key,)).fetchone():continue
   if not p.resolve().is_relative_to(root.resolve()):raise ValueError('source_image_path_escapes_paper')
   marker=probe_fn(p)
   c.execute('insert into files values(?,?,?,?)',(key,'marker' if marker else 'checked',json.dumps(marker or {}),'incremental_v3'));added+=1
 c.execute('insert or replace into papers values(?,?,?,?)',(paper,'scanned',now(),json.dumps(dict(new_headers=added))));c.commit();return added

def seed(c):
 if c.execute("select value from meta where key='seeded'").fetchone():return
 frozen=json.loads((F/'inventory.json').read_text());launch=json.loads((F/'launch.json').read_text())
 assert frozen['scan_complete'] and frozen['directory_walk_complete'] and set(frozen['states'])<={'checked','marker'}
 c.execute('attach database ? as frozen',((F/'files.sqlite').as_uri()+'?mode=ro',))
 c.execute("insert or ignore into files select ?||path,status,details,'frozen_v2' from frozen.files",(str(R)+'/',))
 c.execute("insert or replace into meta values('frozen_cutoff',?)",(launch['at_utc'],));c.execute("insert or replace into meta values('frozen_inventory_SHA256',?)",(hashlib.sha256((F/'inventory.json').read_bytes()).hexdigest(),));c.execute("insert or replace into meta values('seeded','1')");c.commit();c.execute('detach database frozen')
def publish(c):
 states=dict(c.execute('select status,count(*) from files group by status'));candidates=[json.loads(x) for x, in c.execute("select details from files where status='marker' order by path")]
 out=dict(at_utc=now(),directory_walk_complete=True,scan_complete=c.execute("select count(*) from papers where status in ('queued','pending_io_error')").fetchone()[0]==0,completed_source_cohort_only=True,continuous_incremental=True,states=states,native_XML_markers=len(candidates),candidates=candidates,paper_states=dict(c.execute('select status,count(*) from papers group by status')),new_header_reads=c.execute("select count(*) from files where origin='incremental_v3'").fetchone()[0],scan_scope='v2 frozen headers plus once-per-completed-paper incremental SVG/PNG headers',not_parsed_or_accepted=True,new_PDF_import_calls=0,new_source_downloads=0,new_model_calls=0,pixel_data_not_decoded=True)
 put(D/'inventory.json',out);print(json.dumps({k:v for k,v in out.items() if k!='candidates'}),flush=True)
def iteration(c):
 cutoff=c.execute("select value from meta where key='frozen_cutoff'").fetchone()[0]
 frozen_papers={Path(x).relative_to(BASE).parts[0] for x, in c.execute("select path from files where origin='frozen_v2'")}
 with sqlite3.connect((P/'recent_ai_source_expansion_v2/once.sqlite').as_uri()+'?mode=ro',uri=True) as source:
  rows=source.execute("select id,json_extract(record,'$.finished_at_utc') from papers where status='source_completed' order by id").fetchall()
 c.executemany('insert or ignore into papers values(?,?,?,?)',[(paper,'queued',finished,'{}') for paper,finished in rows]);c.commit()
 for i,(paper,finished) in enumerate(rows):
  previous=c.execute('select status from papers where id=?',(paper,)).fetchone()
  if previous and previous[0] in ('scanned','covered_by_frozen_v2'):continue
  try:
   if previous and previous[0]=='queued' and finished and datetime.datetime.fromisoformat(finished)<=datetime.datetime.fromisoformat(cutoff) and paper in frozen_papers:
    c.execute('insert or replace into papers values(?,?,?,?)',(paper,'covered_by_frozen_v2',finished,'{}'));c.commit()
   else:
    result=scan_source(c,paper,BASE/paper/'source')
    if result is None:raise FileNotFoundError('completed_source_directory_missing')
  except (OSError,ValueError) as error:
   c.rollback();c.execute('insert or replace into papers values(?,?,?,?)',(paper,'pending_io_error',now(),json.dumps(dict(reason=type(error).__name__+':'+str(error)))));c.commit()
  if i%100==0:publish(c)
 publish(c)
def main(watch):
 D.mkdir(exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 put(D/'launch.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],at_utc=now()))
 c=sqlite3.connect((D/'files.sqlite').as_uri(),timeout=60,uri=True);schema(c);seed(c)
 while True:
  iteration(c)
  if not watch:break
  time.sleep(120)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');main(p.parse_args().watch)
