import json,sqlite3
from playwright.sync_api import sync_playwright
from native_worker import R,W,native
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
 for filename in ['drawio-elk.min.js','drawio-mermaid.min.js']:page.add_script_tag(path=str(W/'runtime/drawio_bundles'/filename))
 print(page.evaluate('JSON.stringify({exports:Object.keys(mxMermaidToDrawio),globals:Object.keys(window).filter(k=>/mermaid/i.test(k)),functions:Object.entries(mxMermaidToDrawio).filter(([k,v])=>typeof v==="function").map(([k,v])=>[k,String(v).slice(0,600)])})'));b.close()
d=sqlite3.connect(W/'jobs.sqlite');x=d.execute('select output_record from jobs where format="mermaid" and output_record is not null order by id limit 1').fetchone();r=json.loads(x[0]);print((R/r['code_file']).read_text()[:7000])
