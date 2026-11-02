from pathlib import Path
import sys,json,uuid,io
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
if '--child'in sys.argv:
 from playwright.sync_api import sync_playwright
 from html_source_whitespace_capture_v8 import screenshot
 from PIL import Image
 import numpy as np
 rows=[]
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=browser.new_page(viewport=dict(width=256,height=256))
  for owner,marker,child in [('hidden','visible','visible'),('hidden','hidden','visible'),('visible','hidden','visible'),('hidden','',''),('collapse','visible','visible')]:
   svg=f'<style>body{{margin:0;background:white}}</style><svg width="256" height="256" xmlns="http://www.w3.org/2000/svg"><defs><marker id="m" refX="10" refY="5" markerWidth="10" markerHeight="10" orient="auto" style="visibility:{marker}"><path style="visibility:{child}" d="M0 0 L10 5 L0 10Z"/></marker></defs><path visibility="{owner}" d="M10 30 L80 30" fill="none" stroke="black" marker-end="url(#m)"/></svg>';page.set_content(svg);a=np.asarray(Image.open(io.BytesIO(screenshot(page))).convert('RGB'));rows.append(dict(owner=owner,marker=marker,child=child,paint_pixels=int(np.any(a<245,axis=2).sum())))
  browser.close()
 print(json.dumps(rows))
else:
 import initial_conversion_process_v1 as bounded
 d=W/'svg_visibility_marker_probe_bound_v1'/uuid.uuid4().hex;result=bounded.run([sys.executable,'-B',__file__,'--child'],d,60);print(json.dumps(dict(work=str(d),process=result)))
