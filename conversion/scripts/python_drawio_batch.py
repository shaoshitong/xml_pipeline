"""Consume sandbox-prepared Python SVGs; preserve originals, never auto-accept."""
import argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v2 import build
from svg_batch import metric

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=60)
def producer_live():
 try:
  owner=json.loads((W/'python_render_owner.json').read_text());p=Path('/proc')/str(owner['pid'])/'cmdline';return p.exists() and b'python_render_batch.py' in p.read_bytes()
 except (OSError,ValueError):return False

def worker(index,limit):
 db=connect();done=0;counts={};log=os.open(W/'python_drawio_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or done<limit:
   db.execute('begin immediate');job=db.execute('select j.id,j.input_record,j.input_manifest,r.record from jobs j join python_renders r on r.id=j.id where j.state="python_source_rendered" order by j.id limit 1').fetchone()
   if not job:
    db.commit()
    if limit or not producer_live():break
    time.sleep(15);continue
   id,raw,prepared,execution_raw=job;db.execute('update jobs set state="python_converting",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();source=json.loads(raw);inp=json.loads(prepared);execution=json.loads(execution_raw);started=time.monotonic();record=None;error=None;ctx=None
   try:
    assert execution['figures']==1,'multiple_captured_figures_require_source_correspondence_review: '+str(execution['figures'])
    cap=execution['captures'][0];svgpath=R/cap['svg_file'];svgbytes=svgpath.read_bytes();assert hashlib.sha256(svgbytes).hexdigest()==cap['svg_sha256'];code=(R/inp['source_code']).read_bytes();data=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];assert hashlib.sha256(data).hexdigest()==source['image_sha256'];im=Image.open(io.BytesIO(data));width,height=im.size;ext=im.format.lower();blocked=[]
    ctx=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=ctx.new_page();page.set_default_timeout(60000);ctx.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svgbytes.decode());page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready')
    for attempt in range(3):
     try:source_png=page.screenshot();break
     except Exception:
      if attempt==2:raise
      page.wait_for_timeout(250)
    dom=page.evaluate((W/'scripts/svg_dom.js').read_text());xml,stats=build(dom,width,height);cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];assert vertices,'no_editable_objects';assert stats['counts'].get('text',0) or stats['counts'].get('vector_shapes',0),'raster_only_not_allowed';render=native.native_job(xml,width,height,90,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');dest=R/'clean/drawio_unified'/id[:2]/id;dest.mkdir(parents=True,exist_ok=True);ref=dest/('original_image.'+ext);orig=dest/'original_source.py';svgdest=dest/'source_render.svg';ref.write_bytes(data);orig.write_bytes(code);svgdest.write_bytes(svgbytes)
    record={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':'python','source_record':source,'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'original_reference':str(ref.relative_to(R)),'original_source_code':str(orig.relative_to(R)),'source_render_svg':str(svgdest.relative_to(R)),'source_render_svg_sha256':cap['svg_sha256'],'image_file':str((dest/'image.png').relative_to(R)),'code_file':str((dest/'diagram.drawio').relative_to(R)),'image_sha256':hashlib.sha256(png).hexdigest(),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'format':'drawio','conversion_method':'sandbox_python_to_svg_to_native_drawio_v2','model':None,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'svg_conversion':stats,'blocked_source_resources':blocked,'render':render['native_render'],'metrics':{'original_reference_ssim_512':metric(data,png),'original_source_render_ssim_512':metric(data,source_png),'source_render_vs_drawio_ssim_512':metric(source_png,png)},'execution_audit':str((R/execution['directory']/'preparation.json').relative_to(R)),'execution_success':execution['execution']['ok'],'capture_count':execution['figures'],'quality_state':'pending_source_semantic_and_visual_validation','converted_at_utc':now(),'seconds':time.monotonic()-started}
    if inp.get('source_data'):
     aux=(R/inp['source_data']).read_bytes();assert hashlib.sha256(aux).hexdigest()==inp['source_data_sha256'];(dest/'original_data.json').write_bytes(aux);record.update(original_source_data=str((dest/'original_data.json').relative_to(R)),source_data_sha256=inp['source_data_sha256'],source_data_locator=inp['source_data_locator'])
    if cap.get('dot'):
     dot=svgpath.parent/cap['dot'];assert dot.is_file();(dest/'source_render.dot').write_bytes(dot.read_bytes());record['source_render_dot']=str((dest/'source_render.dot').relative_to(R))
    (dest/'diagram.drawio').write_text(xml);(dest/'image.png').write_bytes(png);(dest/'conversion.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');state='needs_quality_repair' if stats['issues'] or blocked or record['bound_edges']!=len(edges) else 'rendered'
    if state=='needs_quality_repair':error='Unresolved SVG features, connector editing semantics or blocked resources; inspect conversion record.'
   except Exception as e:state='needs_fallback';error=type(e).__name__+': '+str(e)[:2400]
   finally:
    if ctx:ctx.close()
   db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,json.dumps(record,ensure_ascii=False) if record else None,error,now(),id));db.commit();done+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'id':id,'state':state,'error':error,'worker':index,'pid':os.getpid(),'seconds':round(time.monotonic()-started,2)})+'\n').encode())
  browser.close()
 os.close(log);return {'worker':index,'processed':done,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int,default=0);a=p.parse_args();(W/'python_drawio_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:result=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('python_drawio_smoke_summary.json' if a.limit else 'python_drawio_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':result,'goal_complete':False},indent=2)+'\n')
