import json,hashlib,io,math,xml.etree.ElementTree as E
from PIL import Image,ImageOps,ImageDraw
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from plantuml_native import build
from svg_source_coverage_v2 import audit
from svg_batch import metric
base=W/'plantuml_source_probe';results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for r in json.loads((W/'text_fidelity_selection.json').read_text()):
  if r['format']!='plantuml':continue
  work=base/r['id'];svg=(work/'source.svg').read_text();reference=(R/r['reference']).read_bytes();w,h=Image.open(io.BytesIO(reference)).size
  for variant in ['natural_original','natural_dejavu']:
   row={'id':r['id'],'variant':variant,'previous_native_ssim':r['score']};ctx=None
   try:
    ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False,service_workers='block');page=ctx.new_page();page.set_default_timeout(30000);page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg)
    page.evaluate('([w,h])=>{let s=document.querySelector("svg"),bg=s.querySelector(":scope > g > rect");if(bg && +bg.getAttribute("x")===0 && +bg.getAttribute("y")===0){bg.setAttribute("width",w);bg.setAttribute("height",h);}}',[w,h])
    if variant=='natural_dejavu':page.evaluate('()=>{for(const t of document.querySelectorAll("text")){let f=t.getAttribute("font-family");if(f==="sans-serif"||f==="\'Consolas\'")t.setAttribute("font-family","DejaVu Sans");}}')
    page.evaluate('document.fonts.ready');sourcepng=page.screenshot();metadata=page.evaluate((W/'scripts/plantuml_dom_adapter.js').read_text());dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());xml,stats=build(dom,w,h,metadata);coverage=audit(dom,xml,stats);stats['source_coverage']=coverage;stats['issues']+=coverage['errors'];render=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');(work/(variant+'.drawio')).write_text(xml);(work/(variant+'.png')).write_bytes(png);(work/(variant+'_source.png')).write_bytes(sourcepng);(work/(variant+'_dom.json')).write_text(json.dumps(dom));(work/(variant+'_stats.json')).write_text(json.dumps(stats,indent=2));row.update(ssim=metric(reference,png),source_svg_ssim=metric(reference,sourcepng),source_svg_vs_native_ssim=metric(sourcepng,png),counts=stats['counts'],issues=stats['issues'],coverage=coverage,metadata=metadata,render=render['native_render'])
   except Exception as e:row['error']=repr(e)
   finally:
    if ctx:ctx.close()
   results.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ['metadata','render','issues']}),flush=True)
 browser.close()
(base/'natural_probe_report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
canvas=Image.new('RGB',(1800,1800),'#eeeeee');draw=ImageDraw.Draw(canvas)
for i,r in enumerate([r for r in json.loads((W/'text_fidelity_selection.json').read_text()) if r['format']=='plantuml']):
 for j,(label,path) in enumerate([('original',R/r['reference']),('native',base/r['id']/'natural_dejavu.png'),('source PNG',base/r['id']/'source.png')]):
  if not path.exists():continue
  im=Image.open(path).convert('RGB');im=ImageOps.contain(im,(580,555));canvas.paste(im,(j*600+(600-im.width)//2,i*600+35));draw.text((j*600+8,i*600+8),r['id'][:10]+' '+label,fill='black')
canvas.save(base/'natural_probe_contact.jpg',quality=90)
