import io,json,sqlite3,xml.etree.ElementTree as ET,zipfile,hashlib
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,pair,native,normalize,now
z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war');bundles=W/'runtime/drawio_bundles';plant=[i.filename for i in z.infolist() if 'plantuml' in i.filename and i.filename.endswith('.min.js')];print(json.dumps({'plantuml_bundles':plant}),flush=True)
for name in plant:(bundles/Path(name).name).write_bytes(z.read(name))
db=sqlite3.connect(W/'jobs.sqlite');items=[db.execute('SELECT id,input_record FROM jobs WHERE format=? ORDER BY id LIMIT 1',(fmt,)).fetchone() for fmt in ('mermaid','plantuml')];results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=browser.new_page();page.route('**/*',lambda route:route.abort());page.set_content('<html><body></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
 for filename in ['drawio-elk.min.js','drawio-mermaid.min.js']+[Path(x).name for x in plant]:page.add_script_tag(path=str(bundles/filename))
 print(json.dumps({'api':page.evaluate('({mermaid:typeof mxMermaidToDrawio,plantuml:typeof mxPlantUmlToDrawio})')}),flush=True)
 for id,record in items:
  row=json.loads(record);data,code=pair(row);width,height=Image.open(io.BytesIO(data)).size;d=W/'text_diagram_pilot'/id;d.mkdir(parents=True,exist_ok=True)
  try:
   xml=page.evaluate("args=>{const converter=args[0]==='mermaid'?mxMermaidToDrawio:mxPlantUmlToDrawio;return converter.parseText(args[1],{securityLevel:'strict',startOnLoad:false,maxTextSize:2000000});}",[row['format'],code]);assert xml
   xml,_,model=normalize(xml);cells=list(model.iter('mxCell'));assert any(c.get('vertex')=='1' for c in cells),'converter skipped all statements';(d/'diagram.drawio').write_text(xml)
   result=native.native_job(xml,width,height,90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
   if result['ok']:(d/'image.png').write_bytes(result.pop('png'))
   info={'id':id,'format':row['format'],'vertices':sum(c.get('vertex')=='1' for c in cells),'edges':sum(c.get('edge')=='1' for c in cells),'bound_edges':sum(c.get('edge')=='1' and bool(c.get('source')) and bool(c.get('target')) for c in cells),'render':result,'quality_state':'pending_source_coverage_and_visual_comparison','directory':str(d),'conversion_method':'official_drawio_native_'+row['format']}
  except Exception as e:info={'id':id,'format':row['format'],'error':type(e).__name__+': '+str(e)[:2000]}
  results.append(info);(d/'summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n');print(json.dumps(info,ensure_ascii=False),flush=True)
 browser.close()
(W/'text_diagram_pilot.json').write_text(json.dumps({'created_at_utc':now(),'results':results},ensure_ascii=False,indent=2)+'\n')
