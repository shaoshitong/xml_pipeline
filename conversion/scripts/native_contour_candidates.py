import json,sqlite3,hashlib,io,os,time,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,normalize,now,pair
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);items=[]
for id,raw,prep in D.execute('select id,output_record,input_manifest from jobs where route="native" and state="rendered"'):
 out=json.loads(raw)
 if out.get('metrics',{}).get('exact_reference_pixels') and out['bound_edges']!=out['edges']:items.append((id,out,json.loads(prep)))
base=W/'native_contour_repair';base.mkdir(exist_ok=True);(W/'native_contour_owner.json').write_text(json.dumps({'pid':os.getpid(),'started':now(),'selected':len(items)}));results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);pg=b.new_page();pg.route('**/*',lambda r:r.abort());pg.set_content('<html></html>');pg.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');pg.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));js=(W/'scripts/bind_native_contours_v2.js').read_text()
 for id,out,inp in items:
  rec={'id':id,'at':now()};t=time.monotonic()
  try:
   xml=(R/out['code_file']).read_text();assert hashlib.sha256(xml.encode()).hexdigest()==out['code_sha256'];prop=pg.evaluate(js,xml);rec.update(changes=prop['changes'],unresolved=prop['unresolved'],moves=prop['moves'])
   if not prop['changes']:rec['state']='no_unique_rendered_contour'
   else:
    assert all(abs(m['dx']-17)<.05 and abs(m['dy']-11)<.05 for m in prop['moves']),'Actual endpoint movement mismatch'
    candidate,_,model=normalize(prop['xml']);model.attrib.update(E.fromstring(xml).find('.//mxGraphModel').attrib);root=E.Element('mxfile',{'host':'app.diagrams.net','type':'device'});E.SubElement(root,'diagram',{'id':'page-1','name':'Page-1'}).append(model);candidate=E.tostring(root,encoding='unicode')
    data,source=pair(out['source_record']);ref=Image.open(io.BytesIO(data)).convert('RGBA');white=Image.new('RGBA',ref.size,'white');white.alpha_composite(ref);ref=white.convert('RGB');render=native.native_job(candidate,inp['width'],inp['height'],90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],str({k:v for k,v in render.items() if k!='png'});png=render.pop('png');pred=Image.open(io.BytesIO(png)).convert('RGB');exact=ref.size==pred.size and bool(np.array_equal(ref,pred));parents={c:p for p in model.iter() for c in p};cid=lambda c:c.get('id') or parents.get(c,E.Element('none')).get('id');cells=list(model.iter('mxCell'));vertices={cid(c) for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];bound=sum(c.get('source') in vertices and c.get('target') in vertices for c in edges);rec.update(exact_reference_pixels=exact,bound_edges=bound,edges=len(edges),source_hashes_verified=True,code_sha256=hashlib.sha256(candidate.encode()).hexdigest(),image_sha256=hashlib.sha256(png).hexdigest(),render=render['native_render'],previous_code_sha256=out['code_sha256'],state='pixel_exact_fully_bound' if exact and bound==len(edges) else 'pixel_exact_partial' if exact else 'rejected_pixel_change')
    directory=base/id;directory.mkdir(exist_ok=True);(directory/'candidate.drawio').write_text(candidate);(directory/'candidate.png').write_bytes(png);(directory/'before_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(directory/'before.drawio').write_text(xml)
  except Exception as e:rec.update(state='error',error=repr(e))
  rec['seconds']=time.monotonic()-t;results.append(rec)
  if (base/id).exists():(base/id/'audit.json').write_text(json.dumps(rec,indent=2))
  with (base/'events.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
  print(json.dumps({'id':id,'state':rec['state'],'changes':len(rec.get('changes',[])),'seconds':rec['seconds'],'error':rec.get('error')}),flush=True)
 b.close()
(W/'native_contour_summary.json').write_text(json.dumps({'finished':now(),'selected':len(items),'results':results},indent=2))
