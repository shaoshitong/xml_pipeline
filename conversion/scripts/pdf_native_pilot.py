import hashlib,io,json,sqlite3,sys
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
from pdf_to_native import source_svg,attach_fonts
from svg_convert_v2 import build
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for item in json.loads((W/'tikz_pilot.json').read_text())['results']:
  id=item['id'];work=W/'pdf_native_pilot'/id;work.mkdir(parents=True,exist_ok=True);ctx=None;result={'id':id,'source':item['source'],'started_at_utc':now()}
  try:
   inp=json.loads(D.execute('select input_manifest from jobs where id=?',(id,)).fetchone()[0]);data=(R/inp['reference_image']).read_bytes();w,h=Image.open(io.BytesIO(data)).size;doc=pymupdf.open(Path(item['directory'])/'source.pdf');svg,fonts,source=source_svg(doc,doc[0],work);(work/'reconstructed_source.svg').write_text(svg);ctx=b.new_context(viewport={'width':w,'height':h},java_script_enabled=False,service_workers='block');blocked=[];ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page=ctx.new_page();page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[w,h]);page.evaluate('document.fonts.ready');screenshot=page.screenshot();(work/'reconstructed_source.png').write_bytes(screenshot);dom=page.evaluate((W/'scripts/svg_dom.js').read_text());xml,stats=build(dom,w,h);xml=attach_fonts(xml,fonts);(work/'diagram.drawio').write_text(xml);render=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],{k:v for k,v in render.items() if k!='png'};png=render.pop('png');(work/'image.png').write_bytes(png);font_report=[{k:v for k,v in f.items() if k not in ['uri','glyph_advances']} for f in fonts.values()];result.update(state='candidate_needs_connectivity_and_quality_repair',source=source,font_report=font_report,conversion=stats,blocked=blocked,render=render['native_render'],metrics={'original_vs_drawio':metric(data,png),'original_vs_reconstructed_svg':metric(data,screenshot),'drawio_vs_reconstructed_svg':metric(screenshot,png)})
  except Exception as e:result.update(state='error',error=type(e).__name__+': '+str(e)[:3000])
  finally:
   if ctx:ctx.close()
  (work/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:list(x))+'\n');results.append(result);print(json.dumps({k:v for k,v in result.items() if k not in ['font_report','conversion','render','source']},default=lambda x:list(x)),flush=True)
 b.close()
(W/'pdf_native_pilot.json').write_text(json.dumps({'finished_at_utc':now(),'results':results,'accepted':False},ensure_ascii=False,indent=2,default=lambda x:list(x))+'\n')
