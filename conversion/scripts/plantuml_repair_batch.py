"""Rebuild PlantUML native candidates from pinned source renderer geometry; never auto-accept."""
import argparse,concurrent.futures,hashlib,io,json,os,re,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from plantuml_runtime import run as source_render,JAR_SHA
from plantuml_native import build
from svg_source_coverage_v2 import audit
from svg_batch import metric

def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=120)
def live():
 try:
  own=json.loads((W/'text_batch_owner.json').read_text());return b'text_batch.py' in (Path('/proc')/str(own['pid'])/'cmdline').read_bytes()
 except (OSError,ValueError):return False

def convert(browser,id,source,inp,old,work):
 code=(R/inp['source_code']).read_bytes();reference=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];assert hashlib.sha256(reference).hexdigest()==source['image_sha256'];image=Image.open(io.BytesIO(reference));w,h=image.size;metadata=str(image.info.get('plantuml',''));versions=re.findall(r'PlantUML version ([^\s(]+)',metadata)
 if versions and set(versions)!={'1.2025.7'}:raise ValueError('Different original renderer version requires separate runtime: '+repr(versions))
 if max(w,h)>8192 or w*h>64000000:raise ValueError('Reference canvas exceeds current renderer limits')
 svg=source_render(work,code,'svg');E.fromstring(svg);source_png=source_render(work,code,'png');(work/'source.svg').write_bytes(svg);(work/'source.png').write_bytes(source_png);options=[];errors=[]
 for variant in ['scaled','natural']:
  ctx=None
  try:
   ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False,service_workers='block');blocked=[];ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page=ctx.new_page();page.set_default_timeout(45000);page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode())
   page.evaluate('''({w,h,variant})=>{let s=document.querySelector('svg');if(variant==='scaled'){s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}else{let bg=s.querySelector(':scope > g > rect');if(bg && +bg.getAttribute('x')===0 && +bg.getAttribute('y')===0){bg.setAttribute('width',w);bg.setAttribute('height',h);}}for(const t of s.querySelectorAll('text')){let f=t.getAttribute('font-family');if(f==='sans-serif'||f==="'Consolas'")t.setAttribute('font-family','DejaVu Sans');}}''',{'w':w,'h':h,'variant':variant});page.evaluate('document.fonts.ready');source_svg_png=None
   for attempt in range(3):
    try:source_svg_png=page.screenshot();break
    except Exception:
     if attempt==2:raise
     page.wait_for_timeout(250)
   md=page.evaluate((W/'scripts/plantuml_dom_adapter.js').read_text());dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());assert md['groups'],'diagram has no supported engine entity groups; requires other conversion route';xml,stats=build(dom,w,h,md);coverage=audit(dom,xml,stats);stats['source_coverage']=coverage;stats['issues']+=coverage['errors']
   if not coverage['ok'] or md['expectedLinkCount']!=len(md['links']):raise ValueError('Incomplete native source graph coverage: '+json.dumps(coverage['errors']+md['issues'])[:1500])
   if blocked:raise ValueError('Source SVG external resources blocked: '+repr(blocked)[:500])
   result=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
   if not result['ok']:raise ValueError(json.dumps({k:v for k,v in result.items() if k!='png'}))
   png=result.pop('png');score=metric(reference,png);(work/(variant+'.drawio')).write_text(xml);(work/(variant+'.png')).write_bytes(png);(work/(variant+'_stats.json')).write_text(json.dumps(stats,indent=2));(work/(variant+'_source.png')).write_bytes(source_svg_png);options.append({'variant':variant,'xml':xml,'png':png,'stats':stats,'render':result['native_render'],'score':score,'source_svg_vs_native_ssim':metric(source_svg_png,png)})
  except Exception as e:errors.append({'variant':variant,'error':repr(e)})
  finally:
   if ctx:ctx.close()
 if not options:raise ValueError(json.dumps(errors))
 chosen=max(options,key=lambda x:x['score']);previous=(old or {}).get('metrics',{}).get('original_reference_ssim_512');summary={'id':id,'previous_ssim':previous,'candidate_ssim':chosen['score'],'chosen':chosen['variant'],'variants':[{'variant':o['variant'],'ssim':o['score'],'source_svg_vs_native_ssim':o['source_svg_vs_native_ssim']} for o in options],'variant_errors':errors,'source_png_vs_reference_ssim':metric(reference,source_png)};(work/'selection.json').write_text(json.dumps(summary,indent=2))
 if previous is not None and chosen['score']<previous-.01:raise ValueError('Original-image similarity regression; previous candidate retained: '+json.dumps(summary))
 directory=R/'clean/drawio_unified'/id[:2]/id;directory.mkdir(parents=True,exist_ok=True);archive=W/'version_archive'/id/'before_plantuml_source_geometry';archive.mkdir(parents=True,exist_ok=True)
 if old:
  for key in ['code_file','image_file']:
   if old.get(key) and (R/old[key]).exists():shutil.copy2(R/old[key],archive/Path(old[key]).name)
  (archive/'conversion.json').write_text(json.dumps(old,indent=2))
 files={'code_file':('diagram.drawio',chosen['xml'].encode()),'image_file':('image.png',chosen['png']),'original_reference':('original_image.'+image.format.lower(),reference),'original_source_code':('original_source.puml',code),'source_render_svg':('source_render.svg',svg),'source_render_png':('source_render.png',source_png)};out=dict(old or {});out.update(id=id,source_pair_sha256=id,source=source['source'],category=source['category'],source_format='plantuml',source_record=source,source_image_sha256=source['image_sha256'],source_code_sha256=source['code_sha256'],format='drawio',conversion_method='plantuml_pinned_2025_7_source_svg_native_geometry_v1',model=None,converted_at_utc=now(),quality_state='pending_independent_source_semantics_and_visual_validation',svg_conversion=chosen['stats'],render=chosen['render'],prior_version_audit=str(archive.relative_to(R)),plantuml_runtime={'version':'1.2025.7','jar_sha256':JAR_SHA,'original_metadata_versions':versions,'network_disabled':True,'security_profile':'SANDBOX','font_mapping':{'sans-serif':'DejaVu Sans',"'Consolas'":'DejaVu Sans'},'font_mapping_evidence':'conversion/plantuml_source_probe/java_physical_font_resolution.json'},variant_selection=summary)
 for key,(name,data) in files.items():(directory/name).write_bytes(data);out[key]=str((directory/name).relative_to(R))
 out['code_sha256']=hashlib.sha256(chosen['xml'].encode()).hexdigest();out['image_sha256']=hashlib.sha256(chosen['png']).hexdigest();out['source_render_svg_sha256']=hashlib.sha256(svg).hexdigest();out['source_render_png_sha256']=hashlib.sha256(source_png).hexdigest();cells=list(E.fromstring(chosen['xml']).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];out.update(vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),metrics={'original_reference_ssim_512':chosen['score'],'original_source_render_ssim_512':summary['source_png_vs_reference_ssim'],'source_render_vs_drawio_ssim_512':chosen['source_svg_vs_native_ssim']});(directory/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');return out,summary

def worker(index,limit,ids):
 db=connect();n=0;log=os.open(W/'plantuml_repair_events.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o644)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   db.execute('begin immediate');sql="select id,state,output_record,input_record,input_manifest from jobs where format='plantuml' and state in ('rendered','needs_quality_repair','needs_fallback') and input_manifest is not null and id not in (select id from plantuml_geometry_repairs)";params=[]
   if ids:sql+=' and id in ('+','.join('?' for x in ids)+')';params=ids
   row=db.execute(sql+' order by id limit 1',params).fetchone()
   if not row:
    db.commit()
    if limit or ids or not live():break
    time.sleep(15);continue
   id,beforestate,raw,source,inp=row;db.execute('insert into plantuml_geometry_repairs values (?,"running",NULL,?)',(id,now()));db.execute('update jobs set state="plantuml_geometry_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();began=time.monotonic();out=None;error=None;report={'id':id,'started_at_utc':now()};work=W/'plantuml_geometry_repair'/id;work.mkdir(parents=True,exist_ok=True)
   try:out,summary=convert(b,id,json.loads(source),json.loads(inp),json.loads(raw) if raw else None,work);report.update(summary,published=True,state='needs_quality_repair');state='needs_quality_repair'
   except Exception as e:error=type(e).__name__+': '+str(e)[:3000];state=beforestate;report.update(error=error,published=False,state=state)
   db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False) if out else raw,error,now(),id));db.execute('update plantuml_geometry_repairs set state=?,record=?,updated_at=? where id=?',('published' if out else 'failed',json.dumps(report),now(),id));db.commit();n+=1;os.write(log,(json.dumps({**report,'worker':index,'pid':os.getpid(),'seconds':time.monotonic()-began})+'\n').encode())
  b.close()
 os.close(log);return {'worker':index,'processed':n}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();db=connect();db.execute('create table if not exists plantuml_geometry_repairs (id TEXT PRIMARY KEY,state TEXT,record TEXT,updated_at TEXT)');db.commit();db.close();(W/'plantuml_repair_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'ids':a.ids,'started_at_utc':now()})+'\n')
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[a.ids]*a.workers))
 (W/('plantuml_repair_smoke_summary.json' if a.limit or a.ids else 'plantuml_repair_summary.json')).write_text(json.dumps({'at':now(),'results':results,'goal_complete':False},indent=2))
