import hashlib,io,json,shutil,sqlite3,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v3 import build
from svg_pilot import metrics
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);report=json.loads((W/'python_pilot.json').read_text());results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for item in report['results']:
  if not item.get('execution',{}).get('ok') or item['execution']['figures']!=1:continue
  id=item['id'];raw,prep,state=D.execute('select input_record,input_manifest,state from jobs where id=?',(id,)).fetchone()
  if state=='accepted':continue
  source=json.loads(raw);inp=json.loads(prep);work=W/'code_svg_v3_pilot'/id;work.mkdir(parents=True,exist_ok=True);result={'id':id,'source':source['source'],'created_at_utc':now()};D.execute('update jobs set state="python_converting",attempts=attempts+1,updated_at=? where id=? and state!="accepted"',(now(),id));D.commit()
  try:
   svgpath=Path(item['directory'])/item['execution']['captures'][0]['svg'];code=svgpath.read_text();data=(R/inp['reference_image']).read_bytes();width,height=Image.open(io.BytesIO(data)).size;blocked=[];context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=context.new_page();context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');sourcepng=None
   for screenshot_attempt in range(3):
    try:sourcepng=page.screenshot();break
    except Exception:
     if screenshot_attempt==2:raise
     page.wait_for_timeout(250)
   (work/'source_render.png').write_bytes(sourcepng);dom=page.evaluate((W/'scripts/svg_dom.js').read_text());xml,stats=build(dom,width,height);context.close();r=native.native_job(xml,width,height,90,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'],r;png=r.pop('png');dest=R/'clean/drawio_unified'/id[:2]/id;dest.mkdir(parents=True,exist_ok=True);(dest/'diagram.drawio').write_text(xml);(dest/'image.png').write_bytes(png);(dest/'original_source.py').write_bytes((R/inp['source_code']).read_bytes());shutil.copy2(R/inp['reference_image'],dest/'original_image.bin');shutil.copy2(svgpath,dest/'source_render.svg');tree=E.fromstring(xml);cells=list(tree.iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];out={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':'python','source_record':source,'format':'drawio','conversion_method':'sandbox_python_graphviz_or_matplotlib_to_svg_to_native_drawio_v3','source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'original_reference':str((dest/'original_image.bin').relative_to(R)),'original_source_code':str((dest/'original_source.py').relative_to(R)),'source_render_svg':str((dest/'source_render.svg').relative_to(R)),'code_file':str((dest/'diagram.drawio').relative_to(R)),'image_file':str((dest/'image.png').relative_to(R)),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'image_sha256':hashlib.sha256(png).hexdigest(),'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'svg_conversion':stats,'execution':item,'blocked_resources':blocked,'render':r['native_render'],'metrics':{'original_reference_ssim_512':metrics(data,png)['ssim_512'],'source_render_vs_reference_ssim_512':metrics(data,sourcepng)['ssim_512'],'drawio_vs_source_render_ssim_512':metrics(sourcepng,png)['ssim_512']},'quality_state':'pending_semantics_and_visual_review','model':None,'converted_at_utc':now()}
   if inp.get('source_data'):shutil.copy2(R/inp['source_data'],dest/'original_data.json');out.update(original_source_data=str((dest/'original_data.json').relative_to(R)),source_data_sha256=inp['source_data_sha256'],source_data_locator=inp['source_data_locator'])
   (dest/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');state='needs_quality_repair' if stats['issues'] or out['bound_edges']!=out['edges'] else 'rendered';D.execute('update jobs set state=?,output_record=?,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False),now(),id));result.update(state=state,metrics=out['metrics'],counts=stats['counts'],issues=len(stats['issues']))
  except Exception as e:result.update(state='needs_fallback',error=str(e)[:2000]);D.execute('update jobs set state="needs_fallback",error=?,updated_at=? where id=?',(result['error'],now(),id))
  D.commit();results.append(result);print(json.dumps(result),flush=True)
 browser.close()
(W/'code_svg_v3_pilot.json').write_text(json.dumps({'finished_at_utc':now(),'results':results},indent=2)+'\n')
