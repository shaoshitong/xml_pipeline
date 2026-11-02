import json,sqlite3
from playwright.sync_api import sync_playwright
from native_worker import R,W
pfile=W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js';print('bundle',pfile.exists());d=sqlite3.connect(W/'jobs.sqlite');id,prep=d.execute('select id,input_manifest from jobs where format="mermaid" order by id limit 1').fetchone();code=(R/json.loads(prep)['source_code']).read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html><body></body></html>');page.add_script_tag(path=str(pfile));page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:false}})");r=page.evaluate('''async code=>{let d=await mermaid.mermaidAPI.getDiagramFromText(code);let vertices=d.db.getVertices?.(),edges=d.db.getEdges?.();return {type:d.type,dbkeys:Object.keys(d.db),vertices:vertices instanceof Map?[...vertices.entries()]:vertices,edges};}''',code);print(json.dumps(r,ensure_ascii=False));b.close()
(W/'mermaid_reference_probe.json').write_text(json.dumps({'id':id,'result':r},ensure_ascii=False,indent=2)+'\n')
