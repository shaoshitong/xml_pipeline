import argparse,hashlib,io,json,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert import build

def metrics(data,png):
 a=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',a.size,'white');bg.alpha_composite(a);a=bg.convert('RGB');b=Image.open(io.BytesIO(png)).convert('RGB');return {'ssim_512':float(structural_similarity(np.array(a.resize((512,512))),np.array(b.resize((512,512))),channel_axis=2,data_range=255)),'exact_pixels':a.size==b.size and bool(np.array_equal(a,b))}
def main():
 db=sqlite3.connect(W/'jobs.sqlite');selected=[]
 for source, in db.execute('select distinct source from jobs where format="svg" order by source'):
  selected.extend(db.execute('select id,input_record,input_manifest from jobs where format="svg" and source=? order by id limit 1',(source,)).fetchall())
 results=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  for id,raw,prepared in selected:
   inp=json.loads(prepared);source=json.loads(raw);code=(R/inp['source_code']).read_text();data=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code.encode()).hexdigest()==source['code_sha256'];assert hashlib.sha256(data).hexdigest()==source['image_sha256'];width,height=Image.open(io.BytesIO(data)).size;out=W/'svg_pilot'/id;out.mkdir(parents=True,exist_ok=True);blocked=[];began=time.monotonic();result={'id':id,'source':source['source'],'directory':str(out),'created_at_utc':now()}
   context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=context.new_page();context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code)
   try:
    page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');png=page.screenshot();(out/'source_svg.png').write_bytes(png);dom=page.evaluate((W/'scripts/svg_dom.js').read_text());(out/'dom.json').write_text(json.dumps(dom,ensure_ascii=False));xml,stats=build(dom,width,height);(out/'diagram.drawio').write_text(xml);result.update(stats=stats,blocked=blocked,source_vs_reference=metrics(data,png));render=native.native_job(xml,width,height,90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if render['ok']:
     pred=render.pop('png');(out/'image.png').write_bytes(pred);result.update(converted_vs_reference=metrics(data,pred),converted_vs_source=metrics(png,pred))
    result['render']=render
   except Exception as exc:result['error']=str(exc)
   context.close();result['seconds']=round(time.monotonic()-began,2);(out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');results.append(result);print(json.dumps(result),flush=True)
  browser.close()
 (W/'svg_pilot.json').write_text(json.dumps({'created_at_utc':now(),'results':results},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
