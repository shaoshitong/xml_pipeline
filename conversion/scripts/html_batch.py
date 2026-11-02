"""Offline DOM poster conversion with original asset provenance and explicit limitations."""
import argparse,base64,concurrent.futures,hashlib,html,io,json,mimetypes,os,sqlite3,time,urllib.parse,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_batch import metric

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=60)
def convert(dom,served,width,height):
 root=E.Element('mxfile',{'host':'app.diagrams.net','type':'device'});d=E.SubElement(root,'diagram',{'id':'poster','name':'Poster'});m=E.SubElement(d,'mxGraphModel',{'page':'1','pageScale':'1','pageWidth':str(width),'pageHeight':str(height)});cells=E.SubElement(m,'root');E.SubElement(cells,'mxCell',{'id':'0'});E.SubElement(cells,'mxCell',{'id':'1','parent':'0'});assets=[]
 for o in dom['objects']:
  st={'html':'0','strokeColor':'none','fillColor':'none','opacity':str(o['opacity']*100)};value=''
  if o['type']=='rect':
   st.update(fillColor=o['fill']['color'] if o['fill']['opacity'] else 'none',fillOpacity=str(o['fill']['opacity']*100),strokeColor=o['stroke']['color'] if o['bw'] else 'none',strokeWidth=str(o['bw']))
   if o['radius']:st.update(rounded='1',absoluteArcSize='1',arcSize=str(o['radius']*2))
  elif o['type']=='text':
   value=html.escape(o['text']);st.update(html='1',shape='text',align='left',verticalAlign='middle',spacing='0',whiteSpace='nowrap',overflow='visible',fontSize=str(o['fontSize']),fontFamily=o['fontFamily'],fontColor=o['color']['color'],fontStyle=str(int(o['bold'])+2*int(o['italic'])+4*int(o['underline'])))
  elif o['type']=='image':
   assert o['loaded'],'unloaded image '+o['src']
   if o['src'].startswith('data:'):
    header,encoded=o['src'].split(',',1);blob=base64.b64decode(encoded) if ';base64' in header else urllib.parse.unquote_to_bytes(encoded);source='embedded_original_html_asset'
   else:src=served[o['src']];blob=src.read_bytes();source=str(src.relative_to(R))
   im=Image.open(io.BytesIO(blob));fmt=im.format
   if fmt in ['JPEG','PNG']:encoded=blob;mime='image/jpeg' if fmt=='JPEG' else 'image/png'
   else:out=io.BytesIO();im.save(out,format='PNG');encoded=out.getvalue();mime='image/png'
   st.update(shape='image',image='data:'+mime+','+base64.b64encode(encoded).decode(),imageAspect='0',aspect='fixed');assets.append({'source':source,'source_sha256':hashlib.sha256(blob).hexdigest(),'embedded_sha256':hashlib.sha256(encoded).hexdigest(),'cell':str(o['id']+1)})
  else:raise ValueError('unsupported object '+o['type'])
  c=E.SubElement(cells,'mxCell',{'id':str(o['id']+1),'parent':'1','vertex':'1','value':value,'style':';'.join(k+'='+v for k,v in st.items())+';'});E.SubElement(c,'mxGeometry',{'x':str(o['x']),'y':str(o['y']),'width':str(o['w']),'height':str(o['h']),'as':'geometry'})
 assert any(o['type']=='text' for o in dom['objects']),'no_editable_text_poster_requires_review'
 return E.tostring(root,encoding='unicode'),assets

def worker(index,limit):
 db=connect();n=0;counts={};log=os.open(W/'html_batch_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   db.execute('begin immediate');job=db.execute('select id,input_record,input_manifest from jobs where format="html" and state="queued" order by id limit 1').fetchone()
   if not job:db.commit();break
   id,raw,prepared=job;db.execute('update jobs set state="html_converting",attempts=attempts+1,worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();source=json.loads(raw);inp=json.loads(prepared);record=None;error=None;context=None;start=time.monotonic()
   try:
    data=(R/inp['reference_image']).read_bytes();code=(R/inp['source_code']).read_text();assert hashlib.sha256(data).hexdigest()==source['image_sha256'];assert hashlib.sha256(code.encode()).hexdigest()==source['code_sha256'];im=Image.open(io.BytesIO(data));width,height=im.size;ext=im.format.lower();asset_root=inp.get('asset_root') or source.get('asset_root');assets=(R/asset_root).resolve() if asset_root else None;blocked=[];served={};context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');page=context.new_page();page.set_default_timeout(60000)
    def route(req):
     url=urllib.parse.urlparse(req.request.url)
     if url.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
     rel=urllib.parse.unquote(url.path.lstrip('/'))
     if rel=='index.html':req.fulfill(body=code,content_type='text/html');return
     target=(assets/rel).resolve() if assets else None
     if target is None or not target.is_relative_to(assets) or not target.is_file():blocked.append(rel);req.abort();return
     served[req.request.url]=target;req.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
    context.route('**/*',route);page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
    for attempt in range(3):
     try:source_png=page.screenshot();break
     except Exception:
      if attempt==2:raise
      page.wait_for_timeout(250)
    dom=page.evaluate((W/'scripts/html_dom_v2.js').read_text());xml,asset_map=convert(dom,served,width,height);render=native.native_job(xml,width,height,120,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');dest=R/'clean/drawio_unified'/id[:2]/id;dest.mkdir(parents=True,exist_ok=True);ref=dest/('original_image.'+ext);original=dest/'original_source.html';ref.write_bytes(data);original.write_text(code);(dest/'diagram.drawio').write_text(xml);(dest/'image.png').write_bytes(png);record={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':'html','source_record':source,'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'original_reference':str(ref.relative_to(R)),'original_source_code':str(original.relative_to(R)),'original_asset_root':asset_root,'image_file':str((dest/'image.png').relative_to(R)),'code_file':str((dest/'diagram.drawio').relative_to(R)),'image_sha256':hashlib.sha256(png).hexdigest(),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'format':'drawio','conversion_method':'offline_html_dom_native_shapes_text_original_image_assets_v2','model':None,'vertices':len(dom['objects']),'text_objects':sum(o['type']=='text' for o in dom['objects']),'edges':0,'bound_edges':0,'source_assets':asset_map,'unsupported_features':dom['unsupported'],'blocked_source_resources':blocked,'render':render['native_render'],'metrics':{'original_reference_ssim_512':metric(data,png),'original_source_render_ssim_512':metric(data,source_png),'source_render_vs_drawio_ssim_512':metric(source_png,png)},'quality_state':'pending_text_assets_clipping_and_visual_validation','converted_at_utc':now(),'seconds':time.monotonic()-start};(dest/'conversion.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');state='needs_quality_repair' if dom['unsupported'] or blocked else 'rendered'
    if state=='needs_quality_repair':error='Unsupported CSS/layout or unresolved resources; candidate is not accepted.'
   except Exception as e:state='needs_fallback';error=type(e).__name__+': '+str(e)[:2500]
   finally:
    if context:context.close()
   db.execute('update jobs set state=?,output_record=?,error=?,updated_at=?,worker_pid=NULL where id=?',(state,json.dumps(record,ensure_ascii=False) if record else None,error,now(),id));db.commit();n+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'id':id,'state':state,'error':error,'worker':index,'pid':os.getpid(),'seconds':round(time.monotonic()-start,2)})+'\n').encode())
  browser.close()
 os.close(log);return {'worker':index,'processed':n,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int,default=0);a=p.parse_args();(W/'html_batch_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('html_batch_smoke_summary.json' if a.limit else 'html_batch_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':results,'goal_complete':False},indent=2)+'\n')
