"""Incremental source-proven native marker/shadow repair; preserve existing typography/alignment."""
import copy,argparse,concurrent.futures,hashlib,io,json,os,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from plantuml_native_v4 import build
from plantuml_fonts import resolve
from svg_convert_v3 import unpack,pack
from svg_batch import metric
from svg_source_coverage_v2 import audit as coverage_audit

def sha(b):return hashlib.sha256(b).hexdigest()
def connect():return sqlite3.connect(W/'jobs.sqlite',timeout=120)
def producers_live():
 for name,script in [('plantuml_repair_v3','plantuml_repair_batch_v3.py'),('plantuml_alignment','plantuml_alignment_batch.py')]:
  try:
   p=json.loads((W/(name+'_owner.json')).read_text())['pid']
   if script.encode() in (Path('/proc')/str(p)/'cmdline').read_bytes():return True
  except (OSError,ValueError):pass
 return False

def repair(browser,out,work):
 oldxml=(R/out['code_file']).read_text();oldpng=(R/out['image_file']).read_bytes();reference=(R/out['original_reference']).read_bytes();svg=(R/out['source_render_svg']).read_bytes()
 for content,key in [(oldxml.encode(),'code_sha256'),(oldpng,'image_sha256'),(reference,'source_image_sha256'),(svg,'source_render_svg_sha256')]:assert sha(content)==out[key],key
 original_code=(R/out['original_source_code']).read_bytes();assert sha(original_code)==out['source_code_sha256']
 w,h=Image.open(io.BytesIO(reference)).size;variant=out['variant_selection']['chosen'];ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False,service_workers='block');blocked=[]
 try:
  ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));p=ctx.new_page();p.set_content('<style>html,body{margin:0;background:white}</style>'+svg.decode());p.evaluate('''({w,h,variant})=>{const s=document.querySelector('svg');if(variant==='scaled'){s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}}''',{'w':w,'h':h,'variant':variant})
  fonts=resolve(p,work);p.evaluate('document.fonts.ready');md=p.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text());dom=p.evaluate((W/'scripts/svg_dom_plantuml_v4.js').read_text());newxml,stats=build(dom,w,h,md);(work/'source_dom.json').write_text(json.dumps(dom));(work/'source_stats.json').write_text(json.dumps(stats));(work/'rebuilt_geometry.drawio').write_text(newxml)
  assert not blocked,'Unexpected external resource';assert md['expectedLinkCount']==len(md['links']),'Unresolved source terminals'
 finally:ctx.close()
 oldroot=E.fromstring(oldxml);cells={c.get('id'):c for c in oldroot.iter('mxCell')};newcells={c.get('id'):c for c in E.fromstring(newxml).iter('mxCell')};rootcells=oldroot.find('.//mxGraphModel/root');align=out.get('native_alignment',{}).get('proof',{});dx,dy=float(align.get('dx',0)),float(align.get('dy',0));changes=[];rejected=[]
 def same_geometry(id):
  a,b=cells.get(id),newcells.get(id)
  if a is None or b is None or a.get('parent')!=b.get('parent'):return False
  ga,gb=a.find('mxGeometry'),b.find('mxGeometry')
  if ga is None or gb is None:return False
  for k in ['x','y','width','height']:
   delta=(dx if k=='x' else dy if k=='y' else 0) if a.get('parent')=='1' else 0
   if abs(float(ga.get(k,0))-float(gb.get(k,0))-delta)>.02:return False
  return True
 for item in stats['native_source_shadows']:
  id=item['object'];a,b=cells.get(id),newcells.get(id)
  if not same_geometry(id) or unpack(a.get('style','')).get('shape')!=unpack(b.get('style','')).get('shape'):rejected.append({'object':id,'reason':'shadow_source_geometry_does_not_match_current_candidate'});continue
  style=unpack(a.get('style',''));newstyle=unpack(b.get('style',''));keys=['shadow','shadowColor','shadowOpacity','shadowOffsetX','shadowOffsetY','shadowBlur']
  if all(style.get(k)==newstyle.get(k) for k in keys):continue
  style.update({k:newstyle[k] for k in keys});a.set('style',pack(style));changes.append({'kind':'shadow',**item})
 for item in stats['handwritten_native_markers']:
  arrow=item['source_arrow_object'];eid=item['native_edge'];a,b=cells.get(eid),newcells.get(eid)
  if arrow not in cells:continue
  if a is None or b is None or a.get('source')!=b.get('source') or a.get('target')!=b.get('target') or not same_geometry(a.get('source')) or not same_geometry(a.get('target')):rejected.append({'object':arrow,'reason':'marker_terminal_geometry_does_not_match_current_candidate'});continue
  side=item['side'];style=unpack(a.get('style',''));newstyle=unpack(b.get('style',''));prefix='exit' if side=='start' else 'entry';keys=[side+'Arrow',side+'Size',side+'Fill',prefix+'X',prefix+'Y',prefix+'Perimeter']
  if style.get(side+'Arrow','none')!='none':rejected.append({'object':arrow,'reason':'current_marker_already_exists'});continue
  style.update({k:newstyle[k] for k in keys});a.set('style',pack(style));rootcells.remove(cells[arrow]);changes.append({'kind':'marker',**item})
 proof={'at':now(),'input_code_sha256':sha(oldxml.encode()),'source_svg_sha256':sha(svg),'preserved_alignment':{'dx':dx,'dy':dy},'source_variant':variant,'changes':changes,'unresolved_mappings':rejected,'source_metadata':md,'font_probe':fonts,'not_acceptance':True}
 if not changes:return None,{**proof,'result':'no_matching_incremental_changes'}
 xml=E.tostring(oldroot,encoding='unicode');removed={x['source_arrow_object'] for x in changes if x['kind']=='marker'};before={c.get('id'):c for c in E.fromstring(oldxml).iter('mxCell')};after={c.get('id'):c for c in oldroot.iter('mxCell')};assert before.keys()-after.keys()==removed;assert not after.keys()-before.keys()
 for id,c in after.items():
  prior=before[id];assert {k:v for k,v in c.attrib.items() if k!='style'}=={k:v for k,v in prior.attrib.items() if k!='style'},id
  assert [E.tostring(x) for x in c]==[E.tostring(x) for x in prior],id
 proof['all_text_parents_terminals_and_remaining_geometry_unchanged']=True
 merged=copy.deepcopy(out['svg_conversion']);added=[{k:v for k,v in x.items() if k!='kind'} for x in changes if x['kind']=='marker'];merged['native_graphviz_arrowheads']=merged.get('native_graphviz_arrowheads',[])+added;merged['counts']['native_arrowheads']=len(merged['native_graphviz_arrowheads']);merged['counts']['vector_shapes']-=len(added);merged['native_source_shadows']=[{k:v for k,v in x.items() if k!='kind'} for x in changes if x['kind']=='shadow'];coverage=coverage_audit(dom,xml,merged);assert coverage['ok'],json.dumps(coverage['errors']);merged['source_coverage_after_style_repair']=coverage;merged['issues'].append({'reason':'native_source_marker_and_shadow_mapping_requires_visual_review','markers_added':len(added),'shadows_added':len(merged['native_source_shadows'])});proof['source_coverage']=coverage
 rendered=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert rendered['ok'],str({k:v for k,v in rendered.items() if k!='png'});png=rendered.pop('png');audit=rendered['native_render'];assert not audit['blocked_resource_requests'];assert Image.open(io.BytesIO(png)).size==(w,h),'Native output size changed: '+repr(Image.open(io.BytesIO(png)).size)+' vs '+repr((w,h))
 before_score=metric(reference,oldpng);score=metric(reference,png);proof.update(before_ssim=before_score,after_ssim=score,render=audit)
 (work/'candidate.drawio').write_text(xml);(work/'candidate.png').write_bytes(png);(work/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));(work/'before.drawio').write_text(oldxml);(work/'before.png').write_bytes(oldpng);(work/'before.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 if score<before_score-.002:return None,{**proof,'result':'visual_regression_old_candidate_retained'}
 if audit['content_outside_declared_canvas'] and not out.get('render',{}).get('content_outside_declared_canvas'):return None,{**proof,'result':'new_content_outside_canvas_old_candidate_retained'}
 updated=dict(out);updated['svg_conversion']=merged;updated.update(conversion_method=out['conversion_method']+'_source_markers_shadows_v4',native_style_repair=proof,code_sha256=sha(xml.encode()),image_sha256=sha(png),render=audit,quality_state='pending_independent_source_semantics_and_visual_validation',converted_at_utc=now());updated['metrics']=dict(out['metrics']);updated['metrics'].update(original_reference_ssim_512=score,source_render_vs_drawio_ssim_512=None);updated['vertices']=sum(c.get('vertex')=='1' for c in after.values());updated['prior_version_audit']=str(work.relative_to(R));return (updated,xml,png),{**proof,'result':'published'}

def worker(index,limit,ids):
 db=connect();n=0;log=os.open(W/'plantuml_style_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or n<limit:
   db.execute('begin immediate');sql="select id,state,output_record from jobs j where format='plantuml' and state in ('rendered','needs_quality_repair') and json_extract(output_record,'$.conversion_method') like 'plantuml_pinned_%' and json_extract(output_record,'$.conversion_method') not like '%_source_markers_shadows_v4' and not exists(select 1 from plantuml_style_repairs s where s.id=j.id and s.source_hash=json_extract(j.output_record,'$.code_sha256'))";params=[]
   if ids:sql+=' and id in ('+','.join('?' for _ in ids)+')';params=ids
   else:sql+=" and exists(select 1 from plantuml_geometry_repairs_v3 s where s.id=j.id and s.state in ('published','failed'))"
   row=db.execute(sql+' order by id limit 1',params).fetchone()
   if not row:
    db.commit()
    if limit or ids or not producers_live():break
    time.sleep(15);continue
   id,beforestate,raw=row;out=json.loads(raw);sourcehash=out['code_sha256'];db.execute('insert into plantuml_style_repairs values (?,?,"running",NULL,?)',(id,sourcehash,now()));db.execute('update jobs set state="plantuml_style_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();work=W/'plantuml_style_repair'/id/sourcehash[:16];work.mkdir(parents=True,exist_ok=True);published=False;error=None;start=time.monotonic();summary={'id':id}
   try:
    result,report=repair(browser,out,work);summary.update(report)
    if result:
     updated,xml,png=result;db.execute('begin immediate');assert db.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==('plantuml_style_repairing',raw),'Ownership changed'
     for key,data in [('code_file',xml.encode()),('image_file',png)]:q=R/out[key];tmp=q.with_suffix(q.suffix+'.style.tmp');tmp.write_bytes(data);tmp.replace(q)
     (R/out['code_file']).parent.joinpath('conversion.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n');out=updated;published=True
   except Exception as e:db.rollback();error=repr(e);summary.update(result='failed',error=error)
   db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',('needs_quality_repair' if published else beforestate,json.dumps(out,ensure_ascii=False) if published else raw,error,now(),id));db.execute('update plantuml_style_repairs set state=?,record=?,updated_at=? where id=? and source_hash=?',(summary['result'],json.dumps(summary),now(),id,sourcehash));db.commit();n+=1;os.write(log,(json.dumps({**summary,'pid':os.getpid(),'worker':index,'seconds':time.monotonic()-start})+'\n').encode());print(json.dumps({k:summary.get(k) for k in ['id','result','before_ssim','after_ssim','error']}),flush=True)
  browser.close()
 os.close(log);return {'worker':index,'processed':n}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();db=connect();db.execute('create table if not exists plantuml_style_repairs (id TEXT,source_hash TEXT,state TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,source_hash))');db.commit();db.close();(W/'plantuml_style_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'ids':a.ids,'started_at_utc':now()}))
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[a.ids]*a.workers))
 (W/('plantuml_style_smoke_summary.json' if a.limit or a.ids else 'plantuml_style_summary.json')).write_text(json.dumps({'at':now(),'results':results,'goal_complete':False},indent=2))
