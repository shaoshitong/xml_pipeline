import json,sqlite3
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from portable_native_fonts_v2 import ready_page,capture,embed
from fontmix_validation import verify_graph,verify_fonts,zero_lineboxes
from fontmix_native_stack import native_stack_variant
B=W/'font_native_stack_tests';B.mkdir(exist_ok=True);D=sqlite3.connect(W/'jobs.sqlite');cases=[]
for prefix in ['00133b4c9','0025a787','00415df','00446bcd','00483236','004a3126']:
 row=D.execute('select j.id,j.output_record from jobs j where j.id like ?',(prefix+'%',)).fetchone()
 if row:
  id,raw=row;out=json.loads(raw);xml=(R/out['code_file']).read_text()
  if 'extFonts=' not in xml:cases.append((id,xml,R/out['image_file']))
p=W/'font_portability_probe_v2/fixture';cases.append(('fixture',(p/'before.drawio').read_text(),p/'before.png'))
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser)
 for id,xml,image in cases:
  path=B/id;path.mkdir(exist_ok=True);result={'id':id}
  try:
   obs=capture(page,xml);candidate,fonts,details=embed(xml,obs,path/'fonts',page);assert not details['issues'],details['issues'];new,nd=native_stack_variant(xml,zero_lineboxes(candidate,details),details,fonts);(path/'before.drawio').write_text(xml);(path/'candidate.drawio').write_text(new);(path/'details.json').write_text(json.dumps(nd,indent=2));(path/'observations.json').write_text(json.dumps(obs,indent=2));verify_graph(xml,new,nd);w,h=Image.open(image).size;out=native.native_job(new,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert out['ok'];(path/'candidate.png').write_bytes(out['png']);(path/'render.json').write_text(json.dumps(out['native_render'],indent=2));verify_fonts(obs,out['native_render'],nd);result.update(physical_font_glyph_counts_preserved=True,pixel_identical=out['png']==image.read_bytes(),text_cells=len(nd['changes']),stack_cells=len(nd['native_stack_cells']),unresolved_precedence=[c['cell'] for c in nd['changes'] if c.get('native_stack_unresolved')]);assert result['pixel_identical'];result['ok']=True
  except Exception as e:result.update(ok=False,error=repr(e)[:1600])
  results.append(result);(path/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 browser.close()
(B/'test_report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
