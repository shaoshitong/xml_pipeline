"""Upgrade rotated PDF text to editable native text; preserve prior candidate on failure/regression."""
import argparse,collections,concurrent.futures,hashlib,html,io,json,os,shutil,sqlite3,sys,time,unicodedata,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from pdf_to_native_v2 import source_svg,attach_fonts
from svg_convert_v6 import build
from tikz_connectivity import bind
from svg_batch import metric
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
sha=lambda b:hashlib.sha256(b).hexdigest()
def connection():return sqlite3.connect(W/'jobs.sqlite',timeout=300)
def producer_live():
 for name,script in [('tikz_drawio','tikz_drawio_batch.py'),('tikz_ligature','tikz_ligature_repair.py'),('tikz_render','tikz_render_batch.py'),('tikz_binary_capture','tikz_binary_capture_repair.py')]:
  try:
   o=json.loads((W/(name+'_owner.json')).read_text());p=Path('/proc')/str(o['pid'])/'cmdline'
   if p.exists() and script.encode() in p.read_bytes():return True
  except (OSError,ValueError):pass
 return False

def worker(index,limit):
 D=connection();n=0;events=W/'tikz_rotation_events.jsonl'
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   D.execute('begin immediate');row=D.execute('select id,output_record from jobs where format="tikz" and state in ("rendered","needs_quality_repair") and json_extract(output_record,"$.pdf_conversion.issues") like "%rotated_pdf_text_requires_reconstruction%" and id not in (select id from tikz_rotation_repairs) order by id limit 1').fetchone()
   if not row:
    D.commit()
    if limit or not producer_live():break
    time.sleep(20);continue
   id,raw=row;out=json.loads(raw);D.execute('insert into tikz_rotation_repairs values (?,"running",NULL,?)',(id,now()));D.execute('update jobs set state="tikz_rotation_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));D.commit();started=time.monotonic();published=False;error=None;ctx=None;doc=None;report={'id':id,'time':now()}
   try:
    reference=(R/out['original_reference']).read_bytes();code=(R/out['original_source_code']).read_bytes();pdf=(R/out['source_render_pdf']).read_bytes();assert sha(reference)==out['source_image_sha256'];assert sha(code)==out['source_code_sha256'];assert sha(pdf)==out['source_render_pdf_sha256'];w,h=Image.open(io.BytesIO(reference)).size;work=W/'tikz_rotation'/id;work.mkdir(parents=True,exist_ok=True);doc=pymupdf.open(stream=pdf,filetype='pdf');assert len(doc)==1;svg,fonts,pdfstats=source_svg(doc,doc[0],work);ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False);page=ctx.new_page();page.set_default_timeout(60000);blocked=[];ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',[w,h]);page.evaluate('document.fonts.ready');source_png=None
    for screenshot_attempt in range(3):
     try:source_png=page.screenshot();break
     except Exception:
      if screenshot_attempt==2:raise
      page.wait_for_timeout(250)
    dom=page.evaluate((W/'scripts/svg_dom_pdf_v2.js').read_text());xml,stats=build(dom,w,h);assert stats['native_rotated_text'],'no native rotation';xml=attach_fonts(xml,fonts);xml,connectivity=bind(xml,dom,code.decode());cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];normalize=lambda x:unicodedata.normalize('NFKC',html.unescape(x));assert collections.Counter(normalize(o['text']) for o in dom['objects'] if o['type']=='text')==collections.Counter(normalize(c.get('value')) for c in cells if c.get('value')),'PDF text coverage differs'
    render=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],{k:v for k,v in render.items() if k!='png'};png=render.pop('png');loaded={f['family'] for f in render['native_render'].get('loaded_fonts',[]) if f['status']=='loaded'};assert {o['fontFamily'].strip('"\'') for o in dom['objects'] if o['type']=='text'}<=loaded,'fonts not loaded';score=metric(reference,png);previous=out['metrics']['original_reference_ssim_512'];report.update(previous_reference_ssim=previous,candidate_reference_ssim=score,rotated_text_runs=len(stats['native_rotated_text']));(work/'diagram.drawio').write_text(xml);(work/'image.png').write_bytes(png);(work/'source.svg').write_text(svg)
    if score<previous-.01:raise ValueError('Original-image fidelity diagnostic regressed; prior candidate retained')
    archive=W/'version_archive'/id/'before_tikz_rotation';archive.mkdir(parents=True,exist_ok=True)
    for key in ['code_file','image_file','source_render_svg']:shutil.copy2(R/out[key],archive/Path(out[key]).name)
    (archive/'conversion.json').write_text(raw);dest=(R/out['code_file']).parent;font_records=[]
    for font in fonts.values():
     target=dest/'fonts'/Path(font['file']).name;target.parent.mkdir(exist_ok=True);target.write_bytes(Path(font['file']).read_bytes());assert sha(target.read_bytes())==font['sha256'];font_records.append({**{k:v for k,v in font.items() if k not in ['uri','glyph_advances','file']},'file':str(target.relative_to(R))})
    issues=pdfstats['issues']+stats['issues']+connectivity['issues'];metrics={'original_reference_ssim_512':score,'original_source_render_ssim_512':metric(reference,source_png),'source_render_vs_drawio_ssim_512':metric(source_png,png)}
    if render['native_render']['content_outside_declared_canvas']:issues.append({'reason':'native_content_outside_source_canvas'})
    if min(metrics.values())<.9:issues.append({'reason':'source_or_native_fidelity_below_review_threshold'})
    out.update(conversion_method='sandbox_tikz_pdf_native_unicode_rotated_text_v2',code_sha256=sha(xml.encode()),image_sha256=sha(png),source_render_svg_sha256=sha(svg.encode()),svg_conversion=stats,pdf_conversion=pdfstats,connectivity=connectivity,fonts=font_records,vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),native_text_counter_equal=True,render=render['native_render'],metrics=metrics,unresolved_issues=issues,prior_version_audit=str(archive.relative_to(R)),quality_state='pending_source_semantic_and_visual_validation',converted_at_utc=now());state='needs_quality_repair' if issues or blocked or not connectivity['complete'] else 'rendered'
    D.execute('begin immediate');assert D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==('tikz_rotation_repairing',raw),'ownership changed'
    for key,blob in [('code_file',xml.encode()),('image_file',png),('source_render_svg',svg.encode())]:f=R/out[key];tmp=f.with_suffix(f.suffix+'.rotation.tmp');tmp.write_bytes(blob);tmp.replace(f)
    f=dest/'conversion.json';tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=list)+'\n');tmp.replace(f);published=True;D.execute('update jobs set state=?,output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False,default=list),now(),id));D.execute('update tikz_rotation_repairs set state="published",record=?,updated_at=? where id=?',(json.dumps(report),now(),id));D.commit()
   except Exception as e:
    D.rollback();error=type(e).__name__+': '+str(e)[:2000];D.execute('update jobs set state="needs_quality_repair",error=?,worker_pid=NULL,updated_at=? where id=? and state="tikz_rotation_repairing"',(error,now(),id));D.execute('update tikz_rotation_repairs set state="failed",record=?,updated_at=? where id=?',(json.dumps({**report,'error':error}),now(),id));D.commit()
   finally:
    if doc:doc.close()
    if ctx:ctx.close()
   n+=1;report.update(published=published,error=error,worker=index,seconds=round(time.monotonic()-started,2))
   with events.open('a') as f:f.write(json.dumps(report)+'\n')
  browser.close()
 return {'worker':index,'processed':n}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);parser.add_argument('--limit',type=int,default=0);args=parser.parse_args();D=connection();D.execute('create table if not exists tikz_rotation_repairs (id TEXT PRIMARY KEY,state TEXT,record TEXT,updated_at TEXT)');D.commit();D.close();(W/'tikz_rotation_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':args.workers,'started_at_utc':now(),'limit':args.limit})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(worker,range(args.workers),[args.limit]*args.workers))
 (W/('tikz_rotation_smoke_summary.json' if args.limit else 'tikz_rotation_summary.json')).write_text(json.dumps({'time':now(),'results':results,'goal_complete':False})+'\n')
