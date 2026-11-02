"""Upgrade completed Graphviz candidates; preserve prior versions, never auto-accept."""
import base64,collections,argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v6 import build
from svg_original_assets import resolve as resolve_assets
from harness_context_v3 import hydrate
from svg_source_coverage_v2 import audit
from svg_batch import metric
from durable_sqlite import begin,commit

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=2)
def producers_live():
 for name,script in [('svg_batch_v2','svg_batch_v2.py'),('python_drawio','python_drawio_batch.py'),('svg_v3_repair','svg_v3_repair_batch.py')]:
  try:
   owner=json.loads((W/(name+'_owner.json')).read_text());proc=Path('/proc')/str(owner['pid'])/'cmdline'
   if proc.exists() and script.encode() in proc.read_bytes():return True
  except (OSError,ValueError):pass
 return False

def worker(index,limit):
 db=connect();n=0;counts={};log=os.open(W/'svg_v7_repair_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   row=db.execute('''select id,state,output_record,input_record,input_manifest from jobs where state in ('rendered','needs_quality_repair') and format='svg' and json_extract(output_record,'$.conversion_method') like 'svg_element_native%' and (json_extract(output_record,'$.svg_conversion.issues') like '%text_transform%' or json_array_length(json_extract(input_manifest,'$.panel_assets'))>0) and id not in (select id from svg_v6_repairs) order by id limit 1''').fetchone()
   if not row:
    db.commit()
    if limit or not producers_live():break
    time.sleep(15);continue
   id,beforestate,raw,input_raw,prepared_raw=row;begin(db)
   if db.execute('select state,output_record from jobs where id=?',(id,)).fetchone()!=(beforestate,raw) or db.execute('select 1 from svg_v6_repairs where id=?',(id,)).fetchone():db.rollback();continue
   out=json.loads(raw);db.execute('insert into svg_v6_repairs values (?,"running",NULL,?)',(id,now()));db.execute('update jobs set state="svg_v6_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(db);start=time.monotonic();ctx=None;error=None;publish=False;report={'id':id,'started_at_utc':now()}
   try:
    work=W/'svg_v6_repair'/id;work.mkdir(parents=True,exist_ok=True);svg,asset_uses,asset_ctx=resolve_assets(json.loads(input_raw),json.loads(prepared_raw),out,work);data=(R/out['original_reference']).read_bytes();assert hashlib.sha256(data).hexdigest()==out['source_image_sha256'];im=Image.open(io.BytesIO(data));w,h=im.size;blocked=[];ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False,service_workers='block');page=ctx.new_page();page.set_default_timeout(60000);ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[w,h]);page.evaluate('document.fonts.ready');dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());xml,stats=build(dom,w,h);_,verified_images=hydrate(xml,asset_ctx);expected_images=collections.Counter(hashlib.sha256(base64.b64decode(o['href'].split(',',1)[1])).hexdigest() for o in dom['objects'] if o['type']=='image');assert expected_images==collections.Counter(a['sha256'] for a in verified_images),'native raster image hashes or multiplicity differ from visible SVG';coverage=audit(dom,xml,stats);stats['source_coverage']=coverage;stats['issues'].extend(coverage['errors']);render=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');score=metric(data,png);previous_score=out['metrics']['original_reference_ssim_512'];report.update(previous_reference_ssim=previous_score,candidate_reference_ssim=score,native_arrowheads=stats['counts']['native_arrowheads'],edge_child_labels=stats['edge_child_labels'],native_rotated_text=len(stats['native_rotated_text']),original_asset_uses=len(asset_uses))
    archive=W/'version_archive'/id/'before_svg_v6';archive.mkdir(parents=True,exist_ok=True)
    for key in ['code_file','image_file']:
     src=R/out[key];shutil.copy2(src,archive/src.name)
    (archive/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    if score<previous_score-.01:
     (archive/'rejected_v6.drawio').write_text(xml);(archive/'rejected_v6.png').write_bytes(png);raise ValueError('Native arrow/label upgrade materially worsened diagnostic similarity; prior candidate retained')
    cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];out.update(conversion_method='svg_element_native_rotated_text_and_verified_original_assets_v6',svg_conversion=stats,vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),code_sha256=hashlib.sha256(xml.encode()).hexdigest(),image_sha256=hashlib.sha256(png).hexdigest(),render=render['native_render'],converted_at_utc=now(),quality_state='pending_independent_source_semantics_and_visual_validation',prior_version_audit=str(archive.relative_to(R)));out['metrics']['original_reference_ssim_512']=score;out['metrics'].pop('source_render_vs_drawio_ssim_512',None);out['metrics']['source_render_vs_drawio_ssim_512']=None
    asset_records=[]
    for asset in asset_ctx['assets'].values():
     folder=(R/out['code_file']).parent/'source_assets';folder.mkdir(exist_ok=True);imagepath=folder/Path(asset['file']).name;originalpath=folder/Path(asset['original_file']).name;imagepath.write_bytes(asset['bytes']);originalpath.write_bytes(asset['original_bytes']);asset_records.append({**{k:v for k,v in asset.items() if k not in ['bytes','original_bytes','file','original_file']},'file':str(imagepath.relative_to(R)),'original_file':str(originalpath.relative_to(R))})
    out['source_assets']=asset_records;out['verified_original_asset_uses']=asset_uses;out['native_raster_hash_coverage']={'ok':True,'count':len(verified_images)}
    # Native XML+PNG are always regenerated together. The archived prior pair stays intact.
    checkpoint=W/'svg_v7_publication'/id;checkpoint.mkdir(parents=True,exist_ok=True);(checkpoint/'candidate.drawio').write_text(xml);(checkpoint/'candidate.png').write_bytes(png);(checkpoint/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(checkpoint/'before_record.json').write_text(raw);publish=True;state='needs_quality_repair' if stats['issues'] or blocked or out['bound_edges']!=len(edges) else 'rendered';report.update(state=state,published=True,issues=len(stats['issues']))
   except Exception as e:state='needs_quality_repair';error=type(e).__name__+': '+str(e)[:2000];report.update(state=state,published=False,error=error)
   finally:
    if ctx:
     try:ctx.close()
     except Exception as cleanup_error:report['context_cleanup_error']=repr(cleanup_error)
   new_raw=json.dumps(out,ensure_ascii=False) if publish else raw;report_raw=json.dumps(report);retry_count=begin(db)
   assert db.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('svg_v6_repairing',os.getpid(),raw),'Job ownership changed during conversion'
   if publish:
    for key,filename in [('code_file','candidate.drawio'),('image_file','candidate.png')]:
     dest=R/out[key];temp=dest.with_suffix(dest.suffix+'.svg7.tmp');shutil.copyfile(checkpoint/filename,temp);temp.replace(dest)
    dest=(R/out['code_file']).parent/'conversion.json';temp=dest.with_suffix('.svg7.tmp');temp.write_text(new_raw+'\n');temp.replace(dest)
   db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,new_raw,error,now(),id));db.execute('update svg_v6_repairs set state=?,record=?,updated_at=? where id=?',('published' if publish else 'failed',report_raw,now(),id));commit(db)
   if publish:(checkpoint/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256'],'writer_retry_count':retry_count}))
   n+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({**report,'worker':index,'pid':os.getpid(),'seconds':round(time.monotonic()-start,2)})+'\n').encode())
  browser.close()
 os.close(log);return {'worker':index,'processed':n,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);a=p.parse_args();db=connect();db.execute('create table if not exists svg_v6_repairs (id TEXT PRIMARY KEY,state TEXT,record TEXT,updated_at TEXT)');db.commit();db.close();(W/'svg_v7_repair_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('svg_v7_repair_smoke_summary.json' if a.limit else 'svg_v7_repair_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':results,'goal_complete':False},indent=2)+'\n')
