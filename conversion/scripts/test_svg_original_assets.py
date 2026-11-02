import collections,hashlib,io,json,sqlite3
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_original_assets import resolve
from svg_convert_v6 import build
from svg_source_coverage_v2 import audit
from harness_context_v3 import hydrate
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');reports=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for prefix in ['0186e98e','03337e9d']:
  id,raw,inp,prev=D.execute('select id,input_record,input_manifest,output_record from jobs where id like ?',(prefix+'%',)).fetchone();source=json.loads(raw);out=json.loads(prev);work=W/'svg_asset_native_tests'/id;work.mkdir(parents=True,exist_ok=True);svg,uses,ctx=resolve(source,json.loads(inp),out,work);assert uses;w,h=ctx['width'],ctx['height'];page=b.new_page(viewport={'width':w,'height':h});page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',[w,h]);page.evaluate('document.fonts.ready');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');source_png=page.screenshot();dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());xml,stats=build(dom,w,h);coverage=audit(dom,xml,stats);assert coverage['ok'];_,native_assets=hydrate(xml,ctx);expected=collections.Counter(x['asset_id'] for x in uses);actual=collections.Counter(x['asset_id'] for x in native_assets);assert expected==actual,(expected,actual);render=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];png=render.pop('png');(work/'source.svg').write_text(svg);(work/'source.png').write_bytes(source_png);(work/'diagram.drawio').write_text(xml);(work/'image.png').write_bytes(png);report={'id':id,'source_images':len(uses),'native_images':len(native_assets),'image_bytes_and_multiplicity_exact':True,'source_coverage':coverage,'original_native_ssim':metric(ctx['reference'],png),'source_native_ssim':metric(source_png,png),'previous_original_ssim':out['metrics']['original_reference_ssim_512'],'accepted':False};reports.append(report);(work/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));page.close()
 b.close()
(W/'svg_asset_native_tests/report.json').write_text(json.dumps({'time':now(),'ok':True,'results':reports},indent=2))
