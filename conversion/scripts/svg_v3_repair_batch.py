"""Upgrade completed Graphviz candidates; preserve prior versions, never auto-accept."""
import argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v3 import build
from svg_source_coverage import audit
from svg_batch import metric

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=60)
def producers_live():
 for name,script in [('svg_batch_v2','svg_batch_v2.py'),('python_drawio','python_drawio_batch.py')]:
  try:
   owner=json.loads((W/(name+'_owner.json')).read_text());proc=Path('/proc')/str(owner['pid'])/'cmdline'
   if proc.exists() and script.encode() in proc.read_bytes():return True
  except (OSError,ValueError):pass
 return False

def worker(index,limit):
 db=connect();n=0;counts={};log=os.open(W/'svg_v3_repair_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   db.execute('begin immediate');row=db.execute('''select id,state,output_record from jobs where state in ('rendered','needs_quality_repair') and format in ('svg','python') and json_extract(output_record,'$.svg_conversion.counts.node_groups')>0 and json_extract(output_record,'$.conversion_method') in ('svg_element_native_stencils_editable_text_and_connectors_v2','sandbox_python_to_svg_to_native_drawio_v2') and id not in (select id from svg_v3_repairs) order by id limit 1''').fetchone()
   if not row:
    db.commit()
    if limit or not producers_live():break
    time.sleep(15);continue
   id,beforestate,raw=row;out=json.loads(raw);db.execute('insert into svg_v3_repairs values (?,"running",NULL,?)',(id,now()));db.execute('update jobs set state="svg_v3_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();start=time.monotonic();ctx=None;error=None;publish=False;report={'id':id,'started_at_utc':now()}
   try:
    svgfile=out.get('source_render_svg') or out['original_source_code'];svg=(R/svgfile).read_text();data=(R/out['original_reference']).read_bytes();assert hashlib.sha256(data).hexdigest()==out['source_image_sha256'];im=Image.open(io.BytesIO(data));w,h=im.size;blocked=[];ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False,service_workers='block');page=ctx.new_page();page.set_default_timeout(60000);ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[w,h]);page.evaluate('document.fonts.ready');dom=page.evaluate((W/'scripts/svg_dom.js').read_text());xml,stats=build(dom,w,h);coverage=audit(dom,xml,stats);stats['source_coverage']=coverage;stats['issues'].extend(coverage['errors']);render=native.native_job(xml,w,h,90,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not render['ok']:raise ValueError(json.dumps({k:v for k,v in render.items() if k!='png'}))
    png=render.pop('png');score=metric(data,png);previous_score=out['metrics']['original_reference_ssim_512'];report.update(previous_reference_ssim=previous_score,candidate_reference_ssim=score,native_arrowheads=stats['counts']['native_arrowheads'],edge_child_labels=stats['edge_child_labels'])
    archive=W/'version_archive'/id/'before_svg_v3';archive.mkdir(parents=True,exist_ok=True)
    for key in ['code_file','image_file']:
     src=R/out[key];shutil.copy2(src,archive/src.name)
    (archive/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    if score<previous_score-.01:
     (archive/'rejected_v3.drawio').write_text(xml);(archive/'rejected_v3.png').write_bytes(png);raise ValueError('Native arrow/label upgrade materially worsened diagnostic similarity; prior candidate retained')
    cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];out.update(conversion_method='svg_element_native_graphviz_arrows_and_edge_labels_v3' if out['source_format']=='svg' else 'sandbox_python_to_svg_to_native_drawio_v3',svg_conversion=stats,vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),code_sha256=hashlib.sha256(xml.encode()).hexdigest(),image_sha256=hashlib.sha256(png).hexdigest(),render=render['native_render'],converted_at_utc=now(),quality_state='pending_independent_source_semantics_and_visual_validation',prior_version_audit=str(archive.relative_to(R)));out['metrics']['original_reference_ssim_512']=score;out['metrics'].pop('source_render_vs_drawio_ssim_512',None);out['metrics']['source_render_vs_drawio_ssim_512']=None
    # Native XML+PNG are always regenerated together. The archived prior pair stays intact.
    (R/out['code_file']).write_text(xml);(R/out['image_file']).write_bytes(png);(R/out['code_file']).parent.joinpath('conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');publish=True;state='needs_quality_repair' if stats['issues'] or blocked or out['bound_edges']!=len(edges) else 'rendered';report.update(state=state,published=True,issues=len(stats['issues']))
   except Exception as e:state='needs_quality_repair';error=type(e).__name__+': '+str(e)[:2000];report.update(state=state,published=False,error=error)
   finally:
    if ctx:ctx.close()
   db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False) if publish else raw,error,now(),id));db.execute('update svg_v3_repairs set state=?,record=?,updated_at=? where id=?',('published' if publish else 'failed',json.dumps(report),now(),id));db.commit();n+=1;counts[state]=counts.get(state,0)+1;os.write(log,(json.dumps({**report,'worker':index,'pid':os.getpid(),'seconds':round(time.monotonic()-start,2)})+'\n').encode())
  browser.close()
 os.close(log);return {'worker':index,'processed':n,'counts':counts}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);a=p.parse_args();db=connect();db.execute('create table if not exists svg_v3_repairs (id TEXT PRIMARY KEY,state TEXT,record TEXT,updated_at TEXT)');db.commit();db.close();(W/'svg_v3_repair_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('svg_v3_repair_smoke_summary.json' if a.limit else 'svg_v3_repair_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'results':results,'goal_complete':False},indent=2)+'\n')
