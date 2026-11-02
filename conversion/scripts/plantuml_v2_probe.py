import json,sqlite3,io,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import W,R,native,now
from plantuml_native import build
from svg_source_coverage_v2 import audit
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');selected=[]
for id, in D.execute("select id from plantuml_geometry_repairs where state='failed' order by id"):
 f=W/'plantuml_geometry_repair'/id/'source.svg'
 if f.exists() and E.parse(f).getroot().get('data-diagram-type')=='STATE':selected.append(id)
 if len(selected)>=6:break
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for id in selected:
  row={'id':id};ctx=None;d=W/'plantuml_v2_probe'/id;d.mkdir(parents=True,exist_ok=True)
  try:
   inp,old=D.execute('select input_manifest,output_record from jobs where id=?',(id,)).fetchone();inp=json.loads(inp);old=json.loads(old);ref=(R/inp['reference_image']).read_bytes();w,h=Image.open(io.BytesIO(ref)).size;svg=(W/'plantuml_geometry_repair'/id/'source.svg').read_text();ctx=b.new_context(viewport={'width':w,'height':h},java_script_enabled=False);page=ctx.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.evaluate('document.fonts.ready');md=page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text());dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());xml,stats=build(dom,w,h,md);coverage=audit(dom,xml,stats);(d/'metadata.json').write_text(json.dumps(md,indent=2));(d/'dom.json').write_text(json.dumps(dom));(d/'stats.json').write_text(json.dumps(stats,indent=2));(d/'diagram.drawio').write_text(xml);row.update(groups=len(md['groups']),links=len(md['links']),expected_links=md['expectedLinkCount'],issues=md['issues'],coverage=coverage)
   assert coverage['ok'] and len(md['links'])==md['expectedLinkCount'],'unresolved source links';result=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert result['ok'],str({k:v for k,v in result.items() if k!='png'});(d/'image.png').write_bytes(result['png']);row.update(previous_ssim=old['metrics']['original_reference_ssim_512'],ssim=metric(ref,result['png']),native_markers=stats['counts']['native_arrowheads'])
  except Exception as e:row['error']=repr(e)
  finally:
   if ctx:ctx.close()
  results.append(row);print(json.dumps(row),flush=True)
 b.close()
(W/'plantuml_v2_probe/report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
