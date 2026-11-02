"""Pinned Mermaid 10 flowchart geometry to real native drawio; all outputs remain pending QA."""
import argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from mermaid_semantic_audit import PARSE
from mermaid_native_v1 import build
from mermaid_geometry_coverage import check
from svg_source_coverage_v2 import audit
from svg_batch import metric
BUNDLE=W/'runtime/mermaid_versions/10.9.1/mermaid.min.js';BUNDLE_SHA='61b335a46df05a7ce1c98378f60e5f3e77a7fb608a1056997e8a649304a936d6'
def sha(b):return hashlib.sha256(b).hexdigest()
def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=120)
def convert(browser,id,source,inp,old,work):
 code=(R/inp['source_code']).read_bytes();ref=(R/inp['reference_image']).read_bytes();assert sha(code)==source['code_sha256'];assert sha(ref)==source['image_sha256'];w,h=Image.open(io.BytesIO(ref)).size;assert max(w,h)<=8192 and w*h<=64000000;options=[];errors=[]
 for font in [None,'Arial']:
  name='default' if font is None else 'arial';ctx=browser.new_context(viewport={'width':800,'height':600},service_workers='block');page=ctx.new_page();blocked=[];page.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page.set_default_timeout(45000)
  try:
   page.set_content('<html><body></body></html>');page.add_script_tag(path=str(BUNDLE));svg=page.evaluate('''async ({code,font})=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,themeVariables:font?{fontFamily:font}:{},flowchart:{htmlLabels:true}});return (await mermaid.render('diagram',code)).svg;}''',{'code':code.decode(),'font':font});ast=page.evaluate(PARSE,code.decode());page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.set_viewport_size({'width':w,'height':h});page.evaluate('''({w,h})=>{let s=document.querySelector('svg');s.style.maxWidth='none';s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('preserveAspectRatio','none');}''',{'w':w,'h':h});page.evaluate('document.fonts.ready');sourcepng=page.screenshot();md=page.evaluate((W/'scripts/mermaid_dom_adapter_v1.js').read_text(),ast);dom=page.evaluate((W/'scripts/svg_dom_mermaid_v1.js').read_text());xml,stats,processed=build(dom,w,h,md);coverage=audit(processed,xml,stats);semantics=check(ast,xml,md);assert coverage['ok'] and semantics['ok'],json.dumps({'coverage':coverage,'semantics':semantics})[:1800];assert not blocked,repr(blocked);stats['source_coverage']=coverage;stats['source_ast_validation']=semantics;stats['source_renderer']={'version':'10.9.1','bundle_sha256':BUNDLE_SHA,'font_override':font};render=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],str({k:v for k,v in render.items() if k!='png'});png=render.pop('png');assert not render['native_render']['content_outside_declared_canvas'],'Actual native content outside original-size canvas';assert Image.open(io.BytesIO(png)).size==(w,h),'Changed rendered canvas';score=metric(ref,png)
   for filename,data in [(name+'.drawio',xml.encode()),(name+'.png',png),(name+'_source.svg',svg.encode()),(name+'_source.png',sourcepng),(name+'_stats.json',json.dumps(stats,ensure_ascii=False,indent=2).encode()),(name+'_ast.json',json.dumps(ast,ensure_ascii=False,indent=2).encode())]:(work/filename).write_bytes(data)
   options.append({'name':name,'font':font,'xml':xml,'png':png,'svg':svg,'sourcepng':sourcepng,'stats':stats,'ast':ast,'render':render['native_render'],'score':score,'source_score':metric(ref,sourcepng),'source_native_score':metric(sourcepng,png)})
  except Exception as e:errors.append({'variant':name,'error':repr(e)})
  finally:ctx.close()
 if not options:raise ValueError(json.dumps(errors))
 best=max(options,key=lambda x:x['score']);prior=old.get('metrics',{}).get('original_reference_ssim_512');summary={'id':id,'chosen':best['name'],'previous_ssim':prior,'candidate_ssim':best['score'],'variants':[{'variant':x['name'],'ssim':x['score'],'source_ssim':x['source_score'],'source_native_ssim':x['source_native_score']} for x in options],'variant_errors':errors};(work/'selection.json').write_text(json.dumps(summary,indent=2))
 if prior is not None and best['score']<prior-.002:raise ValueError('Visual regression: old candidate retained '+json.dumps(summary))
 out=dict(old);out.update(id=id,source_pair_sha256=id,source=source['source'],category=source['category'],format='drawio',source_format='mermaid',source_record=source,source_image_sha256=source['image_sha256'],source_code_sha256=source['code_sha256'],code_sha256=sha(best['xml'].encode()),image_sha256=sha(best['png']),conversion_method='mermaid_10_9_1_source_geometry_native_bound_edges_and_html_text_v1',converted_at_utc=now(),model=None,model_configuration=None,quality_state='pending_independent_original_image_fidelity_and_font_portability_validation',svg_conversion=best['stats'],render=best['render'],variant_selection=summary,source_renderer=best['stats']['source_renderer'],metrics={'original_reference_ssim_512':best['score'],'original_source_render_ssim_512':best['source_score'],'source_render_vs_drawio_ssim_512':best['source_native_score']})
 out['validation_pending']=['Original image layout, typography, shapes and marker fidelity','Font asset portability and final full resource checks','Final source/format/complexity stratified visual QA'];directory=R/'clean/drawio_unified'/id[:2]/id;files={'code_file':('diagram.drawio',best['xml'].encode()),'image_file':('image.png',best['png']),'original_reference':('original_image.'+Image.open(io.BytesIO(ref)).format.lower(),ref),'original_source_code':('original_source.mmd',code),'source_render_svg':('source_render.svg',best['svg'].encode()),'source_render_png':('source_render.png',best['sourcepng']),'source_ast_file':('source_ast.json',json.dumps(best['ast'],ensure_ascii=False,indent=2).encode())}
 for key,(name,data) in files.items():out[key]=str((directory/name).relative_to(R))
 out['source_render_svg_sha256']=sha(best['svg'].encode());out['source_render_png_sha256']=sha(best['sourcepng']);cells=list(E.fromstring(best['xml']).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];out.update(vertices=len(vertices),edges=len(edges),bound_edges=sum(c.get('source') in vertices and c.get('target') in vertices for c in edges));return out,files,summary

def worker(index,limit,ids):
 assert sha(BUNDLE.read_bytes())==BUNDLE_SHA;db=connect();n=0;log=os.open(W/'mermaid_geometry_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   db.execute('begin immediate');sql="select id,state,input_record,input_manifest,output_record from jobs where format='mermaid' and state in ('rendered','needs_quality_repair','needs_fallback') and input_manifest is not null and id not in(select id from mermaid_geometry_repairs)";params=[]
   if ids:sql+=' and id in ('+','.join('?' for _ in ids)+')';params=ids
   row=db.execute(sql+' order by id limit 1',params).fetchone()
   if not row:db.commit();break
   id,before,source,inp,raw=row;db.execute('insert into mermaid_geometry_repairs values (?,"running",NULL,?)',(id,now()));db.execute('update jobs set state="mermaid_geometry_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();out=None;error=None;summary={'id':id};work=W/'mermaid_geometry_repair'/id;work.mkdir(parents=True,exist_ok=True);start=time.monotonic()
   try:
    old=json.loads(raw) if raw else {};candidate,files,details=convert(browser,id,json.loads(source),json.loads(inp),old,work);summary.update(details);archive=work/'before';archive.mkdir(exist_ok=True)
    for key in ['code_file','image_file']:
     if old.get(key) and (R/old[key]).is_file():shutil.copy2(R/old[key],archive/Path(old[key]).name)
    (archive/'conversion.json').write_text(json.dumps(old,ensure_ascii=False,indent=2));candidate['prior_version_audit']=str(archive.relative_to(R));db.execute('begin immediate');assert db.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==('mermaid_geometry_repairing',raw),'Ownership changed';directory=R/'clean/drawio_unified'/id[:2]/id;directory.mkdir(parents=True,exist_ok=True)
    for key,(name,data) in files.items():q=directory/name;tmp=q.with_suffix(q.suffix+'.mgeom.tmp');tmp.write_bytes(data);tmp.replace(q)
    (directory/'conversion.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n');out=candidate;summary['published']=True
   except Exception as e:db.rollback();error=repr(e);summary.update(error=error,published=False)
   state='needs_quality_repair' if out else before;db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False) if out else raw,error,now(),id));db.execute('update mermaid_geometry_repairs set state=?,record=?,updated_at=? where id=?',('published' if out else 'failed',json.dumps(summary),now(),id));db.commit();os.write(log,(json.dumps({**summary,'pid':os.getpid(),'worker':index,'seconds':time.monotonic()-start})+'\n').encode());print(json.dumps(summary),flush=True);n+=1
  browser.close()
 os.close(log);return {'worker':index,'processed':n}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();db=connect();db.execute('create table if not exists mermaid_geometry_repairs (id TEXT PRIMARY KEY,state TEXT,record TEXT,updated_at TEXT)');db.commit();db.close();(W/'mermaid_geometry_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'ids':a.ids,'started_at_utc':now()}))
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[a.ids]*a.workers))
 (W/('mermaid_geometry_smoke_summary.json' if a.limit or a.ids else 'mermaid_geometry_summary.json')).write_text(json.dumps({'at':now(),'results':results,'goal_complete':False},indent=2))
