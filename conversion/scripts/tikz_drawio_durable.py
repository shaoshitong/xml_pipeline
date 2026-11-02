"""Consume compiled TikZ PDF into native vector/text XML, preserve all evidence, never auto-accept."""
import argparse,collections,concurrent.futures,hashlib,html,io,json,os,shutil,sqlite3,sys,time,unicodedata,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
from pdf_to_native import source_svg,attach_fonts
from svg_convert_v2 import build
from tikz_connectivity import bind
from svg_batch import metric
from durable_sqlite import begin,commit

READY_STATE="tikz_source_rendered"

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=2)
def producer_live():
 try:
  owner=json.loads((W/'tikz_render_owner.json').read_text());p=Path('/proc')/str(owner['pid'])/'cmdline';return p.exists() and b'tikz_render_batch.py' in p.read_bytes()
 except (OSError,ValueError):return False

def worker(index,limit,selected):
 db=connect();done=0;counts={};log=os.open(W/'tikz_durable_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or done<limit:
   sql='select j.id,j.input_record,j.input_manifest,r.record from jobs j join tikz_renders r on r.id=j.id where j.state=?';args=[READY_STATE]
   if selected:sql+=' and j.id in ('+','.join('?' for _ in selected)+')';args+=selected
   job=db.execute(sql+' order by j.id limit 1',args).fetchone()
   if not job:
    db.commit()
    if limit or selected or not producer_live():break
    time.sleep(15);continue
   id,raw,prepared,execution_raw=job;begin(db)
   current=db.execute('select state,input_record,input_manifest,output_record from jobs where id=?',(id,)).fetchone()
   if current[:3]!=(READY_STATE,raw,prepared):db.rollback();continue
   old_output=current[3];db.execute('update jobs set state="tikz_converting",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(db);source=json.loads(raw);inp=json.loads(prepared);execution=json.loads(execution_raw);started=time.monotonic();record=None;error=None;ctx=None;doc=None;publish=False
   try:
    assert execution['pages']==1,'multiple_pdf_pages_require_source_correspondence_review: '+str(execution['pages'])
    pdf=(R/execution['pdf_file']).read_bytes();assert hashlib.sha256(pdf).hexdigest()==execution['pdf_sha256'];code=(R/inp['source_code']).read_bytes();data=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];assert hashlib.sha256(data).hexdigest()==source['image_sha256'];im=Image.open(io.BytesIO(data));width,height=im.size;ext=im.format.lower();blocked=[];work=W/'tikz_native'/id[:2]/id;work.mkdir(parents=True,exist_ok=True);doc=pymupdf.open(stream=pdf,filetype='pdf');svg,fonts,pdfstats=source_svg(doc,doc[0],work);(work/'reconstructed_source.svg').write_text(svg)
    ctx=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=ctx.new_page();page.set_default_timeout(60000);ctx.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');source_png=page.screenshot();(work/'source_render.png').write_bytes(source_png);dom=page.evaluate((W/'scripts/svg_dom_pdf.js').read_text());xml,stats=build(dom,width,height);xml=attach_fonts(xml,fonts);xml,connectivity=bind(xml,dom,code.decode());cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];assert vertices,'no_editable_objects';assert stats['counts'].get('text',0) or stats['counts'].get('vector_shapes',0),'raster_only_not_allowed';normalize=lambda s:unicodedata.normalize('NFKC',html.unescape(s));text_equal=collections.Counter(normalize(o['text']) for o in dom['objects'] if o['type']=='text')==collections.Counter(normalize(c.get('value')) for c in cells if c.get('value'));assert text_equal,'native_text_counter_differs_from_pdf_svg'
    render=native.native_job(xml,width,height,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');loaded={f['family'] for f in render['native_render'].get('loaded_fonts',[]) if f['status']=='loaded'};used_fonts={o['fontFamily'].strip('"\'') for o in dom['objects'] if o['type']=='text'};assert used_fonts<=loaded,'embedded fonts not loaded: '+str(used_fonts-loaded)
    dest=R/'clean/drawio_unified'/id[:2]/id;dest.mkdir(parents=True,exist_ok=True);ref=dest/('original_image.'+ext);orig=dest/'original_source.tex';ref.write_bytes(data);orig.write_bytes(code);(dest/'source_render.pdf').write_bytes(pdf);(dest/'source_render.svg').write_text(svg);font_records=[]
    for f in fonts.values():
     fp=Path(f['file']);target=dest/'fonts'/fp.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(fp,target);assert hashlib.sha256(target.read_bytes()).hexdigest()==f['sha256'];font_records.append({**{k:v for k,v in f.items() if k not in ['uri','glyph_advances','file']},'file':str(target.relative_to(R))})
    record={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':'tikz','source_record':source,'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'original_reference':str(ref.relative_to(R)),'original_source_code':str(orig.relative_to(R)),'source_render_pdf':str((dest/'source_render.pdf').relative_to(R)),'source_render_pdf_sha256':execution['pdf_sha256'],'source_render_svg':str((dest/'source_render.svg').relative_to(R)),'source_render_svg_sha256':hashlib.sha256(svg.encode()).hexdigest(),'image_file':str((dest/'image.png').relative_to(R)),'code_file':str((dest/'diagram.drawio').relative_to(R)),'image_sha256':hashlib.sha256(png).hexdigest(),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'format':'drawio','conversion_method':'sandbox_tikz_pdf_to_native_vectors_unicode_embedded_fonts_and_source_connections_v1','model':None,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'pdf_conversion':pdfstats,'svg_conversion':stats,'connectivity':connectivity,'fonts':font_records,'native_text_counter_equal':text_equal,'blocked_source_resources':blocked,'render':render['native_render'],'metrics':{'original_reference_ssim_512':metric(data,png),'original_source_render_ssim_512':metric(data,source_png),'source_render_vs_drawio_ssim_512':metric(source_png,png)},'execution_audit':str((R/execution['directory']/'preparation.json').relative_to(R)),'compile_warnings':execution['compile_warnings'],'quality_state':'pending_source_semantic_and_visual_validation','converted_at_utc':now(),'seconds':time.monotonic()-started}
    checkpoint=W/'tikz_durable_publication'/id;checkpoint.mkdir(parents=True,exist_ok=True);(checkpoint/'candidate.drawio').write_text(xml);(checkpoint/'candidate.png').write_bytes(png);(checkpoint/'before_record.json').write_text(old_output or 'null');issues=pdfstats['issues']+stats['issues']+connectivity['issues'];issues+=([{'reason':'native_content_outside_source_canvas'}] if record['render']['content_outside_declared_canvas'] else []);issues+=([{'reason':'source_or_native_fidelity_below_review_threshold'}] if min(record['metrics'].values())<.9 else []);record['unresolved_issues']=issues;(checkpoint/'candidate_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,default=lambda x:list(x))+'\n');publish=True;state='needs_quality_repair' if issues or blocked or not connectivity['complete'] or record['bound_edges']!=len(edges) else 'rendered'
    if state=='needs_quality_repair':error='Unresolved PDF/TikZ features or connector/arrow fidelity; inspect conversion record.'
   except Exception as e:state='needs_fallback';error=type(e).__name__+': '+str(e)[:2400]
   finally:
    if doc:
     try:doc.close()
     except Exception:pass
    if ctx:
     try:ctx.close()
     except Exception:pass
   new_raw=json.dumps(record,ensure_ascii=False,default=lambda x:list(x)) if publish else old_output;metrics_raw=json.dumps({'seconds':time.monotonic()-started,'record_exists':publish});retry_count=begin(db)
   assert db.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('tikz_converting',os.getpid(),old_output),'Job ownership changed'
   if publish:
    for key,filename in [('code_file','candidate.drawio'),('image_file','candidate.png')]:
     destfile=R/record[key];tmp=destfile.with_suffix(destfile.suffix+'.tdurable.tmp');shutil.copyfile(checkpoint/filename,tmp);tmp.replace(destfile)
    meta=(R/record['code_file']).parent/'conversion.json';tmp=meta.with_suffix('.tdurable.tmp');tmp.write_text(new_raw+'\n');tmp.replace(meta)
   db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,new_raw,error,now(),id));db.execute('insert or replace into tikz_native_results values (?,?,?,?,?)',(id,state,error,now(),metrics_raw));commit(db)
   if publish:(checkpoint/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':record['code_sha256'],'image_sha256':record['image_sha256'],'writer_retry_count':retry_count}))
   done+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'id':id,'state':state,'error':error,'worker':index,'pid':os.getpid(),'seconds':round(time.monotonic()-started,2)})+'\n').encode())
  browser.close()
 os.close(log);return {'worker':index,'processed':done,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids-file');a=p.parse_args();selected=json.loads(Path(a.ids_file).read_text()) if a.ids_file else [];db=connect();db.execute('create table if not exists tikz_native_results (id TEXT PRIMARY KEY,state TEXT,error TEXT,updated_at TEXT,metrics TEXT)');db.commit();db.close();owner={'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'selected':len(selected),'started_at_utc':now()};(W/'tikz_durable_owner.json').write_text(json.dumps(owner)+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:result=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[selected]*a.workers))
 (W/('tikz_durable_smoke_summary.json' if a.limit or selected else 'tikz_durable_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':result,'goal_complete':False},indent=2)+'\n')
