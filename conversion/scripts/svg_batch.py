import argparse,concurrent.futures,hashlib,io,json,os,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from skimage.metrics import structural_similarity
from native_worker import R,W,native,now
from svg_convert import build

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=60)
def metric(data,png):
 a=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',a.size,'white');bg.alpha_composite(a);a=bg.convert('RGB');b=Image.open(io.BytesIO(png)).convert('RGB');return float(structural_similarity(np.array(a.resize((512,512))),np.array(b.resize((512,512))),channel_axis=2,data_range=255))
def worker(index,limit):
 db=connect();counts={};done=0;log=os.open(W/'svg_batch_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or done<limit:
   db.execute('BEGIN IMMEDIATE');job=db.execute('SELECT id,input_record,input_manifest FROM jobs WHERE state="queued" AND route="svg" AND input_manifest IS NOT NULL ORDER BY id LIMIT 1').fetchone()
   if not job:db.commit();break
   id,raw,prepared=job;db.execute('UPDATE jobs SET state="svg_converting",attempts=attempts+1,worker_pid=?,updated_at=? WHERE id=?',(os.getpid(),now(),id));db.commit();source=json.loads(raw);inp=json.loads(prepared);began=time.monotonic();record=None;error=None;context=None
   try:
    code=(R/inp['source_code']).read_text();data=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code.encode()).hexdigest()==source['code_sha256'];assert hashlib.sha256(data).hexdigest()==source['image_sha256'];width,height=Image.open(io.BytesIO(data)).size;blocked=[]
    context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=context.new_page();page.set_default_timeout(60000);context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code);page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');source_png=None
    for screenshot_attempt in range(3):
     try:source_png=page.screenshot();break
     except Exception:
      if screenshot_attempt==2:raise
      page.wait_for_timeout(250)
    dom=page.evaluate((W/'scripts/svg_dom.js').read_text());xml,stats=build(dom,width,height);tree=E.fromstring(xml);cells=list(tree.iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];assert vertices,'no_editable_objects'
    if stats['counts'].get('text',0)==0 and stats['counts'].get('vector_shapes',0)==0:raise ValueError('raster_only_svg_not_allowed')
    render=native.native_job(xml,width,height,90,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');directory=R/'clean/drawio_unified'/id[:2]/id;ext=Image.open(io.BytesIO(data)).format.lower();original_image=directory/('original_image.'+ext);original_code=directory/'original_source.svg';record={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':'svg','source_record':source,'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'original_reference':str(original_image.relative_to(R)),'original_source_code':str(original_code.relative_to(R)),'image_file':str((directory/'image.png').relative_to(R)),'code_file':str((directory/'diagram.drawio').relative_to(R)),'image_sha256':hashlib.sha256(png).hexdigest(),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'format':'drawio','conversion_method':'svg_element_native_stencils_editable_text_and_connectors_v1','model':None,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'svg_conversion':stats,'blocked_source_resources':blocked,'render':render['native_render'],'metrics':{'original_reference_ssim_512':metric(data,png),'original_source_render_ssim_512':metric(data,source_png),'source_render_vs_drawio_ssim_512':metric(source_png,png)},'quality_state':'pending_source_semantic_and_visual_validation','converted_at_utc':now(),'seconds':time.monotonic()-began}
    directory.mkdir(parents=True,exist_ok=True);original_image.write_bytes(data);original_code.write_text(code);(directory/'diagram.drawio').write_text(xml);(directory/'image.png').write_bytes(png);(directory/'conversion.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');state='needs_quality_repair' if stats['issues'] or blocked or record['bound_edges']!=len(edges) else 'rendered'
    if state=='needs_quality_repair':error='SVG features or inferred connector semantics require review/repair; see svg_conversion.issues.'
   except Exception as exc:state='needs_fallback';error=type(exc).__name__+': '+str(exc)[:2000]
   finally:
    if context:context.close()
   db.execute('UPDATE jobs SET state=?,updated_at=?,output_record=?,error=?,worker_pid=NULL WHERE id=?',(state,now(),json.dumps(record,ensure_ascii=False) if record else None,error,id));db.commit();done+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'pid':os.getpid(),'worker':index,'id':id,'state':state,'error':error,'seconds':round(time.monotonic()-began,2)})+'\n').encode())
  browser.close()
 os.close(log);return {'worker':index,'processed':done,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int,default=0);a=p.parse_args();(W/'svg_batch_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('svg_batch_smoke_summary.json' if a.limit else 'svg_batch_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':results,'goal_complete':False},indent=2)+'\n')
