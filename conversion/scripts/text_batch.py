"""Resumable official Mermaid/PlantUML conversion; rendering is not acceptance."""
import argparse,concurrent.futures,hashlib,io,json,os,sqlite3,time,traceback,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from skimage.metrics import structural_similarity
from native_worker import R,W,native,normalize,now
from promote_source_payloads import materialize_sources

def connect():
 d=sqlite3.connect(W/'jobs.sqlite',timeout=60);d.execute('PRAGMA busy_timeout=60000');return d

def worker(index,limit):
 db=connect();done=0;counts={};pid=os.getpid();bundle=W/'runtime/drawio_bundles';log=os.open(W/'text_batch_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);context=browser.new_context(service_workers='block');context.set_offline(True);page=context.new_page();page.set_default_timeout(60000);page.route('**/*',lambda r:r.abort());page.set_content('<html><body></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
  for filename in ['drawio-elk.min.js','drawio-mermaid.min.js']+sorted(x.name for x in bundle.glob('*plantuml*.min.js')):page.add_script_tag(path=str(bundle/filename))
  while not limit or done<limit:
   db.execute('BEGIN IMMEDIATE');job=db.execute('SELECT id,input_record,input_manifest FROM jobs WHERE state="queued" AND route IN ("mermaid","plantuml") AND input_manifest IS NOT NULL ORDER BY id LIMIT 1').fetchone()
   if not job:db.commit();break
   id,raw,prepared=job;db.execute('UPDATE jobs SET state="converting",attempts=attempts+1,worker_pid=?,updated_at=? WHERE id=?',(pid,now(),id));db.commit();source=json.loads(raw);inp=json.loads(prepared);began=time.monotonic();directory=R/'clean/drawio_unified'/id[:2]/id;out=None;error=None
   try:
    code=(R/inp['source_code']).read_text();data=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code.encode()).hexdigest()==source['code_sha256'];assert hashlib.sha256(data).hexdigest()==source['image_sha256']
    xml=page.evaluate("args=>{const c=args[0]==='mermaid'?mxMermaidToDrawio:mxPlantUmlToDrawio;return c.parseText(args[1],{securityLevel:'strict',startOnLoad:false,maxTextSize:2000000});}",[source['format'],code]);assert isinstance(xml,str) and xml,'native_converter_no_output'
    xml,pages,model=normalize(xml);cells=list(model.iter('mxCell'));parents={child:parent for parent in model.iter() for child in parent};cid=lambda c:c.get('id') or parents.get(c,ET.Element('none')).get('id');ids=[cid(c) for c in cells];vertices={cid(c) for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];assert vertices,'native_converter_no_editable_vertices';assert all(ids) and len(ids)==len(set(ids)),'duplicate_or_missing_cell_ids'
    result=native.native_job(xml,inp['width'],inp['height'],90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not result['ok']:raise ValueError(json.dumps({k:v for k,v in result.items() if k!='png'}))
    png=result.pop('png');image=Image.open(io.BytesIO(data)).convert('RGBA');background=Image.new('RGBA',image.size,'white');background.alpha_composite(image);ref=background.convert('RGB');prediction=Image.open(io.BytesIO(png)).convert('RGB');score=float(structural_similarity(np.array(ref.resize((512,512))),np.array(prediction.resize((512,512))),channel_axis=2,data_range=255));bound=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges)
    out={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':source['format'],'source_record':source,'original_reference':inp['reference_image'],'original_source_code':inp['source_code'],'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'image_file':str((directory/'image.png').relative_to(R)),'code_file':str((directory/'diagram.drawio').relative_to(R)),'image_sha256':hashlib.sha256(png).hexdigest(),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'format':'drawio','conversion_method':'official_drawio_native_'+source['format'],'vertices':len(vertices),'edges':len(edges),'bound_edges':bound,'render':result['native_render'],'metrics':{'original_reference_ssim_512':score},'quality_state':'pending_source_coverage_and_fidelity','validation_pending':['independent source-statement/node/edge/text coverage','original-image fidelity and text/layout checks','stratified visual review'],'model':None,'model_configuration':None,'converted_at_utc':now(),'seconds':time.monotonic()-began}
    out=materialize_sources(out)
    directory.mkdir(parents=True,exist_ok=True);(directory/'diagram.drawio').write_text(xml);(directory/'image.png').write_bytes(png);(directory/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');state='rendered'
   except Exception as exc:state='needs_fallback';error=type(exc).__name__+': '+str(exc)[:1800]
   db.execute('UPDATE jobs SET state=?,updated_at=?,output_record=?,error=?,worker_pid=NULL WHERE id=?',(state,now(),json.dumps(out,ensure_ascii=False) if out else None,error,id));db.commit();done+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({'time':now(),'worker':index,'pid':pid,'id':id,'state':state,'error':error,'seconds':round(time.monotonic()-began,2)})+'\n').encode())
  browser.close()
 os.close(log);db.close();return {'worker':index,'processed':done,'states':counts}

def main(args):
 prepared=json.loads((W/'input_preparation.json').read_text());assert prepared['ok'] and prepared['prepared_total']==131904
 db=connect();columns={x[1] for x in db.execute('PRAGMA table_info(jobs)')}
 if 'worker_pid' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN worker_pid INTEGER')
 db.execute('CREATE INDEX IF NOT EXISTS job_state_route_idx ON jobs(state,route,id)');db.commit();db.close();(W/'text_batch_owner.json').write_text(json.dumps({'pid':os.getpid(),'started_at_utc':now(),'workers':args.workers,'limit_per_worker':args.limit})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(worker,range(args.workers),[args.limit]*args.workers))
 result={'finished_at_utc':now(),'workers':results,'goal_complete':False,'note':'Every generated result remains pending semantic/fidelity validation; unsupported or failed examples retained as needs_fallback.'};(W/'text_batch_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int,default=0);main(p.parse_args())
