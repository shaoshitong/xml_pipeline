"""Recover compiled PDFs whose text-dict embedded binaries broke JSON serialization."""
import multiprocessing,concurrent.futures,hashlib,json,os,sqlite3,sys,time
from pathlib import Path
from native_worker import R,W,now
sys.path.append(str(W/'runtime/python_packages'));import pymupdf

def serializable(value,folder,records):
 if isinstance(value,(bytes,bytearray)):
  data=bytes(value);digest=hashlib.sha256(data).hexdigest();path=folder/(digest+'.bin');path.parent.mkdir(exist_ok=True);path.write_bytes(data);record={'binary_file':str(path.relative_to(R)),'sha256':digest,'bytes':len(data)};records.append(record);return record
 if isinstance(value,dict):return {k:serializable(v,folder,records) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [serializable(v,folder,records) for v in value]
 return value

def producer_live():
 try:
  o=json.loads((W/'tikz_render_owner.json').read_text());p=Path('/proc')/str(o['pid'])/'cmdline';return p.exists() and b'tikz_render_batch.py' in p.read_bytes()
 except (OSError,ValueError):return False

def recover(item):
 id,source_raw,inp_raw,old_error=item;source=json.loads(source_raw);inp=json.loads(inp_raw);directory=W/'tikz_render'/id[:2]/id;pdf=directory/'source.pdf';error=None;record=None
 try:
  assert pdf.exists(),'no existing compiled PDF';assert hashlib.sha256((directory/'source.tex').read_bytes()).hexdigest()==source['code_sha256'];assert hashlib.sha256((R/inp['source_code']).read_bytes()).hexdigest()==source['code_sha256'];captures=[];binary=[]
  with pymupdf.open(pdf) as doc:
   assert len(doc)>0
   for i,page in enumerate(doc):
    svg=directory/f'page{i}.svg';svg.write_text(page.get_svg_image(text_as_path=False));text=page.get_text();paths=page.get_drawings();assert len(text.strip()) or paths or page.get_images(),'blank_page';metadata=serializable(page.get_text('dict'),directory/'pdf_binary_metadata',binary);(directory/f'page{i}_text.json').write_text(json.dumps(metadata,ensure_ascii=False));page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).save(directory/f'page{i}.png');captures.append({'page':i,'width_pt':page.rect.width,'height_pt':page.rect.height,'text_characters':len(text),'drawing_paths':len(paths),'svg_file':str(svg.relative_to(R)),'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),'pdf_render_png':str((directory/f'page{i}.png').relative_to(R))})
   warnings=(directory/'stderr.log').read_text() if (directory/'stderr.log').exists() else ''
   record={'id':id,'source':source['source'],'source_code_sha256':source['code_sha256'],'directory':str(directory.relative_to(R)),'pdf_file':str(pdf.relative_to(R)),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'captures':captures,'pages':len(doc),'compile_returncode':0,'compile_attempts':None,'compile_warnings':[x for x in warnings.splitlines() if 'warning' in x.lower()],'native_drawio_conversion_complete':False,'sandbox':'Existing PDF from original isolated Tectonic compile; this recovery only reads PDF and preserves embedded binary metadata.','captured_at_utc':now(),'recovered_from_error':old_error,'binary_metadata_payloads':binary}
  (directory/'preparation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');state='tikz_source_rendered'
 except Exception as e:state='needs_fallback';error=type(e).__name__+': '+str(e)[:2000]
 return {'id':id,'state':state,'binary_payloads':len(record['binary_metadata_payloads']) if record else 0,'error':error,'record':record}

def publish(d,result):
 id,state,error,record=result['id'],result['state'],result['error'],result['record']
 for attempt in range(8):
  try:
   d.execute('begin immediate');assert d.execute('select state from jobs where id=?',(id,)).fetchone()[0]=='tikz_binary_capture_repairing';d.execute('update jobs set state=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,error,now(),id))
   if record:d.execute('insert or replace into tikz_renders values (?,?,?,?,?)',(id,state,json.dumps(record,ensure_ascii=False),error,now()))
   d.execute('update tikz_binary_capture_repairs set state=?,record=?,updated_at=? where id=?',(state,json.dumps({'binary_metadata_payloads':result['binary_payloads'],'error':error}),now(),id));d.commit();return
  except sqlite3.OperationalError as e:
   d.rollback()
   if 'locked' not in str(e) or attempt==7:raise
   time.sleep(2+attempt)

def main():
 d=sqlite3.connect(W/'jobs.sqlite',timeout=300);d.execute('create table if not exists tikz_binary_capture_repairs (id TEXT PRIMARY KEY,state TEXT,old_error TEXT,record TEXT,updated_at TEXT)');d.commit();(W/'tikz_binary_capture_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':4,'started_at_utc':now()})+'\n')
 while True:
  d.execute('begin immediate');rows=d.execute('select j.id,j.input_record,j.input_manifest,j.error from jobs j join tikz_renders t on t.id=j.id where j.state="needs_fallback" and t.error like "%Object of type bytes is not JSON serializable%" and j.id not in (select id from tikz_binary_capture_repairs where state!="queued") limit 128').fetchall()
  for id,raw,inp,error in rows:d.execute('insert or replace into tikz_binary_capture_repairs values (?,"running",?,NULL,?)',(id,error,now()));d.execute('update jobs set state="tikz_binary_capture_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id))
  d.commit()
  if rows:
   results=[]
   with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
    for result in pool.map(recover,rows):
     publish(d,result);results.append({k:v for k,v in result.items() if k!='record'})
   with (W/'tikz_binary_capture_events.jsonl').open('a') as f:
    for result in results:f.write(json.dumps(result)+'\n')
   print(json.dumps({'time':now(),'processed':len(results),'recovered':sum(x['state']=='tikz_source_rendered' for x in results)}),flush=True)
  if not rows and not producer_live():break
  if not rows:time.sleep(20)
 (W/'tikz_binary_capture_summary.json').write_text(json.dumps({'finished_at_utc':now(),'states':dict(d.execute('select state,count(*) from tikz_binary_capture_repairs group by state'))})+'\n')
if __name__=='__main__':main()
