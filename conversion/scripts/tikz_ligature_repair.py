"""Retry only normalizable multi-Unicode ligatures; do not disturb the live main consumer."""
import concurrent.futures,json,os,sqlite3,time,unicodedata
from pathlib import Path
import tikz_drawio_batch as batch
from pdf_fonts import LIGATURES
from native_worker import W,now
batch.READY_STATE='tikz_ligature_retry'
def main_live():
 try:
  o=json.loads((W/'tikz_drawio_owner.json').read_text());p=Path('/proc')/str(o['pid'])/'cmdline';return p.exists() and b'tikz_drawio_batch.py' in p.read_bytes()
 except (OSError,ValueError):return False

def main():
 D=sqlite3.connect(W/'jobs.sqlite',timeout=60);D.execute('create table if not exists tikz_ligature_repairs (id TEXT PRIMARY KEY,old_error TEXT,queued_at TEXT,finished_at TEXT)');D.commit();(W/'tikz_ligature_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':2,'started_at_utc':now()})+'\n');events=W/'tikz_ligature_repair_events.jsonl'
 while True:
  D.execute('begin immediate');rows=D.execute('select j.id,j.error from jobs j left join tikz_ligature_repairs r on r.id=j.id where j.format="tikz" and j.state="needs_fallback" and j.error like ? and r.id is null',("%unresolved multi-Unicode glyph mapping%",)).fetchall();selected=[]
  for id,error in rows:
   # Only known ligature spellings; other Unicode ambiguity stays unresolved.
   import ast
   try:raw=ast.literal_eval(error.split('glyph mapping ',1)[1])
   except (ValueError,SyntaxError):continue
   if unicodedata.normalize('NFKC',raw) not in LIGATURES:continue
   D.execute('insert into tikz_ligature_repairs values (?,?,?,NULL)',(id,error,now()));D.execute('update jobs set state="tikz_ligature_retry",error=NULL,updated_at=? where id=?',(now(),id));selected.append(id)
  D.commit()
  if selected:
   with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:results=list(pool.map(batch.worker,range(2),[0]*2,[selected]*2))
   D.executemany('update tikz_ligature_repairs set finished_at=? where id=?',[(now(),id) for id in selected]);D.commit()
   with events.open('a') as f:f.write(json.dumps({'time':now(),'ids':selected,'results':results})+'\n')
   print(json.dumps({'processed':len(selected),'results':results}),flush=True)
  if not main_live():break
  time.sleep(20)
if __name__=='__main__':main()
