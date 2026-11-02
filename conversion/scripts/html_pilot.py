import base64,hashlib,html,io,json,mimetypes,re,sqlite3,sys,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,pair,native,now
id,record=sqlite3.connect(W/'jobs.sqlite').execute('SELECT id,input_record FROM jobs WHERE format="html" AND category="poster" ORDER BY id LIMIT 1').fetchone();row=json.loads(record);data,code=pair(row);width,height=Image.open(io.BytesIO(data)).size;work=W/'html_pilot'/id;work.mkdir(parents=True,exist_ok=True);assets=(R/row['asset_root']).resolve();blocked=[];served={}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');page=context.new_page()
 def route(req):
  url=urllib.parse.urlparse(req.request.url)
  if url.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
  rel=urllib.parse.unquote(url.path.lstrip('/'))
  if rel=='index.html':req.fulfill(body=code,content_type='text/html');return
  target=(assets/rel).resolve()
  if not target.is_relative_to(assets) or not target.is_file():blocked.append(rel);req.abort();return
  body=target.read_bytes();served[req.request.url]=target;req.fulfill(body=body,content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
 context.route('**/*',route);page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');page.screenshot(path=str(work/'source_html.png'),full_page=False)
 dom=page.evaluate((W/'scripts/html_dom.js').read_text());browser.close()
(work/'dom.json').write_text(json.dumps(dom,ensure_ascii=False)+'\n');assert not blocked,blocked
if dom['unsupported']:(work/'unsupported.json').write_text(json.dumps(dom['unsupported'],ensure_ascii=False,indent=2)+'\n')
root=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device'});diagram=ET.SubElement(root,'diagram',{'id':'poster','name':'Poster'});model=ET.SubElement(diagram,'mxGraphModel',{'page':'1','pageScale':'1','pageWidth':str(width),'pageHeight':str(height)});cells=ET.SubElement(model,'root');ET.SubElement(cells,'mxCell',{'id':'0'});ET.SubElement(cells,'mxCell',{'id':'1','parent':'0'});asset_map=[]
for o in dom['objects']:
 style={'html':'0','strokeColor':'none','fillColor':'none','opacity':str(o['opacity']*100)};value=''
 if o['type']=='rect':
  style.update(fillColor=o['fill']['color'] if o['fill']['opacity'] else 'none',fillOpacity=str(o['fill']['opacity']*100),strokeColor=o['stroke']['color'] if o['bw'] else 'none',strokeWidth=str(o['bw']))
  if o['radius']:style.update(rounded='1',absoluteArcSize='1',arcSize=str(o['radius']*2))
 elif o['type']=='text':
  value=html.escape(o['text']);style.update(html='1',shape='text',align='left',verticalAlign='middle',spacing='0',whiteSpace='nowrap',overflow='visible',fontSize=str(o['fontSize']),fontFamily=o['fontFamily'],fontColor=o['color']['color'],fontStyle=str(int(o['bold'])+2*int(o['italic'])+4*int(o['underline'])))
 elif o['type']=='image':
  assert o['loaded'];src=served[o['src']];blob=src.read_bytes();im=Image.open(io.BytesIO(blob));out=io.BytesIO();im.save(out,format='PNG');uri='data:image/png,'+base64.b64encode(out.getvalue()).decode();style.update(shape='image',image=uri,imageAspect='0',aspect='fixed');asset_map.append({'source':str(src.relative_to(R)),'sha256':hashlib.sha256(blob).hexdigest(),'cell':str(o['id']+1)})
 else:raise ValueError(o['type'])
 cell=ET.SubElement(cells,'mxCell',{'id':str(o['id']+1),'parent':'1','vertex':'1','value':value,'style':';'.join(k+'='+v for k,v in style.items())+';'});ET.SubElement(cell,'mxGeometry',{'x':str(o['x']),'y':str(o['y']),'width':str(o['w']),'height':str(o['h']),'as':'geometry'})
xml=ET.tostring(root,encoding='unicode');(work/'diagram.drawio').write_text(xml)
renderer=W/'rendering/remote_render.py';result=native.native_job(xml,width,height,120,renderer,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
if result['ok']:(work/'image.png').write_bytes(result.pop('png'))
summary={'id':id,'source':row['source'],'objects':len(dom['objects']),'text_objects':sum(o['type']=='text' for o in dom['objects']),'raster_assets':len(asset_map),'unsupported':dom['unsupported'],'blocked':blocked,'source_assets':asset_map,'render':result,'quality_state':'pending_comparison_and_repair','created_at_utc':now(),'directory':str(work)};(work/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(W/'html_pilot.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
