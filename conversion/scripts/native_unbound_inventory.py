import json,sqlite3,collections
from playwright.sync_api import sync_playwright
from native_worker import R,W,native
script=r'''xml=>{document.body.innerHTML='<div id="g" style="width:8192px;height:8192px;position:relative"></div>';const g=new Graph(document.getElementById('g'));const d=mxUtils.parseXml(xml);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();const states=Object.values(g.model.cells).map(c=>g.view.getState(c)).filter(Boolean),nodes=states.filter(s=>s.cell.vertex&&s.width>3&&s.height>3&&s.style.shape!=='text'&&s.style.shape!=='line'&&s.style.strokeColor!=='none'&&s.style.opacity!==0),missing=[];for(const e of states.filter(s=>s.cell.edge)){for(const source of [true,false]){if(g.model.getTerminal(e.cell,source))continue;let p=source?e.absolutePoints?.[0]:e.absolutePoints?.at(-1);if(!p)continue;const choices=nodes.map(s=>({id:s.cell.id,shape:s.style.shape,rotation:s.style.rotation,style:s.cell.style,box:[s.x,s.y,s.width,s.height],distance:Math.hypot(Math.max(s.x-p.x,0,p.x-s.x-s.width),Math.max(s.y-p.y,0,p.y-s.y-s.height))})).sort((a,b)=>a.distance-b.distance).slice(0,3);missing.push({edge:e.cell.id,source,point:{x:p.x,y:p.y},choices});}}g.destroy();return missing;}'''
d=sqlite3.connect(W/'jobs.sqlite');rows=[]
for id,raw in d.execute('select id,output_record from jobs where route="native" and state="rendered"'):
 r=json.loads(raw)
 if r.get('metrics',{}).get('exact_reference_pixels') and r['edges']!=r['bound_edges']:rows.append((id,r))
out=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);pg=b.new_page();pg.route('**/*',lambda r:r.abort());pg.set_content('<html></html>');pg.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');pg.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
 for id,r in rows[:50]:
  try:out.append({'id':id,'edges':r['edges'],'bound':r['bound_edges'],'missing':pg.evaluate(script,(R/r['code_file']).read_text())})
  except Exception as e:out.append({'id':id,'error':str(e)[:400]})
 b.close()
(W/'native_unbound_inventory.json').write_text(json.dumps(out,indent=2));print(json.dumps({'selected':len(out),'results':out},indent=2))
