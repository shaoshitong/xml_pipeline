"""Compile every TikZ source in isolation, preserving all pages and errors."""
import argparse,concurrent.futures,hashlib,json,os,sqlite3,sys,time
from pathlib import Path
from native_worker import R,W,now
from tectonic_compile import compile_case
sys.path.append(str(W/'runtime/python_packages'))
import pymupdf

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=60)
def worker(index,limit):
 db=connect();n=0;counts={};log=os.open(W/'tikz_render_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644);runtime=W/'runtime/tectonic';cache=runtime/'cache'
 while not limit or n<limit:
  db.execute('begin immediate');item=db.execute('select id,input_record,input_manifest from jobs where format="tikz" and state="queued" order by id limit 1').fetchone()
  if not item:db.commit();break
  id,raw,prepared=item;db.execute('update jobs set state="tikz_rendering",attempts=attempts+1,worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();source=json.loads(raw);inp=json.loads(prepared);directory=W/'tikz_render'/id[:2]/id;directory.mkdir(parents=True,exist_ok=True);began=time.monotonic();error=None;result=None
  try:
   code=(R/inp['source_code']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];(directory/'source.tex').write_bytes(code)
   if inp.get('panel_assets'):raise ValueError('Asset-bearing TeX requires explicit sandbox asset mapping')
   r,attempts=compile_case(directory);(directory/'stdout.log').write_text(r.stdout);(directory/'stderr.log').write_text(r.stderr);pdf=directory/'source.pdf';assert r.returncode==0 and pdf.exists(),'tectonic failed: '+r.stderr[-2200:];doc=pymupdf.open(pdf);assert len(doc)>0,'empty_pdf';captures=[]
   for i,page in enumerate(doc):
    svg=directory/f'page{i}.svg';svg.write_text(page.get_svg_image(text_as_path=False));text=page.get_text();paths=page.get_drawings();assert len(text.strip()) or len(paths),'blank_page';(directory/f'page{i}_text.json').write_text(json.dumps(page.get_text('dict'),ensure_ascii=False));page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).save(directory/f'page{i}.png');captures.append({'page':i,'width_pt':page.rect.width,'height_pt':page.rect.height,'text_characters':len(text),'drawing_paths':len(paths),'svg_file':str(svg.relative_to(R)),'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),'pdf_render_png':str((directory/f'page{i}.png').relative_to(R))})
   result={'id':id,'source':source['source'],'source_code_sha256':source['code_sha256'],'directory':str(directory.relative_to(R)),'pdf_file':str(pdf.relative_to(R)),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'captures':captures,'pages':len(doc),'compile_returncode':r.returncode,'compile_attempts':attempts,'compile_warnings':[line for line in r.stderr.splitlines() if 'warning' in line.lower()],'native_drawio_conversion_complete':False,'sandbox':'bwrap --unshare-all; no network; cached packages only; no host private paths; explicit read-only runtime; writable case directory; resource limits','captured_at_utc':now()};doc.close();state='tikz_source_rendered';(directory/'preparation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  except Exception as e:state='needs_fallback';error=type(e).__name__+': '+str(e)[:2500]
  db.execute('insert or replace into tikz_renders values (?,?,?,?,?)',(id,state,json.dumps(result,ensure_ascii=False) if result else None,error,now()));db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(state,error,now(),id));db.commit();n+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'id':id,'worker':index,'pid':os.getpid(),'state':state,'error':error,'seconds':round(time.monotonic()-began,2)})+'\n').encode())
 os.close(log);return {'worker':index,'processed':n,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int,default=0);args=p.parse_args();db=connect();db.execute('create table if not exists tikz_renders (id TEXT PRIMARY KEY,state TEXT,record TEXT,error TEXT,updated_at TEXT)');db.commit();db.close();(W/'tikz_render_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':args.workers,'limit_per_worker':args.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(worker,range(args.workers),[args.limit]*args.workers))
 (W/('tikz_render_smoke_summary.json' if args.limit else 'tikz_render_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':results,'goal_complete':False},indent=2)+'\n')
