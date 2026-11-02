from native_label_paint_order import inspect_order,pixel_audit
from PIL import Image
"""Revision-keyed source affine repair; publish improved candidates, never auto-accept."""
import argparse,json,sqlite3,hashlib,os,shutil,time,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from durable_sqlite import begin,commit
from mermaid_reference_fit_v3 import convert_variant
from promote_source_payloads import materialize_sources
from harness_source_provenance import resolve
from harness_context_v4 import structure
from mermaid_native_v2 import check_backgrounds
sha=lambda b:hashlib.sha256(b).hexdigest()
METHOD='mermaid_10_9_1_source_global_reference_fit_label_paint_order_v8'

def publish_record(old,best,work):
 report=json.loads((best/'report.json').read_text());xml=(best/'candidate.drawio').read_text();png=(best/'candidate.png').read_bytes();struct=structure(xml,{})
 assert struct['ok'] and not struct['source_asset_image_cells'] and struct['edges']==struct['bound_edges']
 assert not old.get('source_assets') and not old.get('used_assets'),'Original assets need separate preservation proof'
 keep=['id','source_pair_sha256','source','category','source_format','source_record','source_image_sha256','source_code_sha256','original_reference','original_source_code','image_file','code_file','format','original_asset_root','original_vector_assets','source_assets','used_assets']
 out=materialize_sources({k:old[k] for k in keep if k in old});dest=(R/old['code_file']).parent/'source_fit_v8'/old['code_sha256'];dest.mkdir(parents=True,exist_ok=True);files={}
 for name in ['source_fit.svg','source_fit.png','source_dom.json','source_ast.json','source_geometry.json','source_stats.json','anchor_fit.json','optimization.json']:
  data=(best/name).read_bytes();p=dest/name
  if p.exists():assert p.read_bytes()==data,'Versioned source already differs'
  else:p.write_bytes(data)
  files[name]={'file':str(p.relative_to(R)),'sha256':sha(data)}
 fonts=json.loads((best/'fonts.json').read_text())
 for f in fonts.values():
  for key,hkey,prefix in [('file','sha256','native_'),('original_file','original_sha256','original_')]:
   source=Path(f[key]);data=source.read_bytes();assert sha(data)==f[hkey];target=R/'clean/font_assets'/(prefix+f[hkey]+source.suffix)
   if target.exists():assert target.read_bytes()==data
   else:target.write_bytes(data)
   f[key]=str(target.relative_to(R))
 out.update(code_sha256=sha(xml.encode()),image_sha256=sha(png),conversion_method=METHOD,model=None,model_configuration=None,converted_at_utc=now(),previous_candidate_archive=str((work/'baseline').relative_to(R)),vertices=struct['vertices'],edges=struct['edges'],bound_edges=struct['bound_edges'],source_editability=report['geometry'],source_coverage=report['source_object_coverage'],svg_conversion=json.loads((best/'source_stats.json').read_text()),native_embedded_fonts=list(fonts.values()),native_font_validation={'method':'actual_physical_font_embedding_and_identical_native_pixels','output_code_sha256':sha(xml.encode()),'native_pixels_unchanged':True,'audit':str((best/'report.json').relative_to(R))},native_source_geometry_repair={'method':'whole_source_affine_from_original_fill_boundaries','files':files,'audit':str((best/'report.json').relative_to(R))},source_render_svg=files['source_fit.svg']['file'],source_render_svg_sha256=files['source_fit.svg']['sha256'],source_render_png=files['source_fit.png']['file'],source_render_png_sha256=files['source_fit.png']['sha256'],source_renderer={'version':report['source_renderer_version'],'bundle_sha256':report['bundle_sha256'],'font_override':report['font_override']},render={k:v for k,v in json.loads((best/'native_render.json').read_text()).items() if k!='actual_text_positions'},metrics={'original_reference_ssim_512':report['native_reference_ssim'],'source_render_vs_drawio_ssim_512':report['source_native_ssim'],'original_source_render_ssim_512':report['source_reference_ssim']},quality_state='source_global_fit_native_checked_pending_visual_acceptance',validation_pending=['Independent original-reference visual review; no SSIM-only acceptance','Source physical typography and marker contour fidelity'])
 (work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));return out

def main(limit,ids):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists mermaid_reference_fit_repairs_v8 (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');commit(D)
 (W/'mermaid_reference_fit_v8_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':1,'at':now(),'limit':limit,'ids':ids}));count=0
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  while not limit or count<limit:
   begin(D);sql="""select j.id,j.state,j.output_record from jobs j where j.format='mermaid' and j.state in ('rendered','needs_quality_repair','harness_review_pending') and json_extract(j.output_record,'$.code_sha256') is not null and coalesce(json_extract(j.output_record,'$.conversion_method'),'')!=? and not exists(select 1 from mermaid_reference_fit_repairs_v8 f where f.id=j.id and f.input_code_sha256=json_extract(j.output_record,'$.code_sha256'))""";params=[METHOD]
   if ids:sql+=' and j.id in ('+','.join('?' for _ in ids)+')';params+=ids
   row=D.execute(sql+' order by case when j.source="allenai--CoSyn-400K" then 0 else 1 end,j.id limit 1',params).fetchone()
   if not row:
    commit(D)
    if limit or ids:break
    time.sleep(30);continue
   id,state,raw=row;old=json.loads(raw);oldhash=old['code_sha256'];D.execute('insert into mermaid_reference_fit_repairs_v8 values (?,?,"running",NULL,?)',(id,oldhash,now()));D.execute('update jobs set state="mermaid_reference_fit_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(D)
   work=W/'harness_sessions'/('reference_fit_v8_'+id+'_'+oldhash[:16]);work.mkdir(parents=True,exist_ok=True);base=work/'baseline';base.mkdir(exist_ok=True);(base/'conversion.json').write_text(raw);report={'id':id,'at':now(),'input_code_sha256':oldhash,'published':False,'accepted':False,'variants':[]};out=None;best=None
   try:
    assert not resolve(old)[0].get('native_source_font_repair'),'Existing source-font mapping requires incremental repair'
    for key,hkey,name in [('code_file','code_sha256','diagram.drawio'),('image_file','image_sha256','image.png')]:
     data=(R/old[key]).read_bytes();assert sha(data)==old[hkey];(base/name).write_bytes(data)
    candidates=[]
    for name,font in [('default',None),('arial','Arial')]:
     folder=work/name
     try:
      result=convert_variant(browser,old,folder,font);report['variants'].append({'name':name,'score':result['native_reference_ssim'],'source_score':result['source_reference_ssim'],'moves':result['actual_endpoint_moves']});candidates.append((result['source_reference_ssim'],result['native_reference_ssim'],folder))
     except Exception as e:
      (work/(name+'_error.txt')).write_text(traceback.format_exc());report['variants'].append({'name':name,'error':repr(e)})
    assert candidates,'No supported source calibration; prior candidate retained'
    source_score,score,best=max(candidates,key=lambda x:(x[0],x[1]));report['variant_selection']='Highest complete original-source-render similarity; native similarity is checked separately, so native marker/layout errors cannot select the wrong source font';prior=old.get('metrics',{}).get('original_reference_ssim_512');newreport=json.loads((best/'report.json').read_text());newbg=newreport['native_html_backgrounds']['source_backgrounds'];oldbindings=old.get('svg_conversion',{}).get('native_html_label_backgrounds',[]);oldbgvalid=False
    try:oldbgvalid=len(oldbindings)==newbg and check_backgrounds((base/'diagram.drawio').read_text(),oldbindings)['ok']
    except AssertionError:pass
    oldpaint=None
    if newbg>0 and oldbgvalid:
     oldorder=inspect_order(browser,(base/'diagram.drawio').read_text(),oldbindings);w,h=Image.open(R/old['original_reference']).size;oldpaint=pixel_audit((base/'diagram.drawio').read_text(),oldorder['boxes'],w,h)
    background_improved=newbg>0 and (not oldbgvalid or not oldpaint['ok']);report['previous_background_pixel_audit']=oldpaint;report['source_background_fidelity_improved']=background_improved
    prior_source=old.get('metrics',{}).get('original_source_render_ssim_512');source_improved=prior_source is not None and source_score>prior_source+.01 and score>=prior-.003;report['source_render_fidelity_improved']=source_improved
    assert prior is not None and (score>prior+.003 or (background_improved and score>=prior) or source_improved),'No source-backed or material diagnostic improvement; prior candidate retained'
    out=publish_record(old,best,work);report.update(published=True,prior_ssim=prior,candidate_ssim=score,chosen_variant=best.name,output_code_sha256=out['code_sha256'],output_image_sha256=out['image_sha256'],work=str(work.relative_to(R)))
   except Exception as e:out=None;report.update(error=repr(e),published=False);(work/'error.txt').write_text(traceback.format_exc())
   (work/'report.json').write_text(json.dumps(report,indent=2));begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('mermaid_reference_fit_repairing',os.getpid(),raw),'Ownership changed'
   if out:
    assert sha((R/old['code_file']).read_bytes())==oldhash and sha((R/old['image_file']).read_bytes())==old['image_sha256']
    q=D.execute('select state from harness_queue_v3 where id=?',(id,)).fetchone();assert not q or q[0]!='running'
    for src,dst in [(best/'candidate.drawio',R/out['code_file']),(best/'candidate.png',R/out['image_file']),(work/'candidate_record.json',(R/out['code_file']).parent/'conversion.json')]:
     tmp=dst.with_suffix(dst.suffix+'.referencefit.tmp');shutil.copyfile(src,tmp);tmp.replace(dst)
    if q and q[0]=='attempt_finished':D.execute('update harness_queue_v3 set state="held_for_source_v5",error=NULL,worker_pid=NULL where id=?',(id,));report['queued_new_deterministic_revision_for_harness']=True
   D.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',('needs_quality_repair' if out else state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));D.execute('update mermaid_reference_fit_repairs_v8 set state=?,record=?,updated_at=? where id=? and input_code_sha256=?',('published' if out else 'retained_prior_candidate',json.dumps(report),now(),id,oldhash));commit(D);count+=1
   (work/'report.json').write_text(json.dumps(report,indent=2))
   if out:(work/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256']}))
   print(json.dumps(report),flush=True)
  browser.close()
 print(json.dumps({'at':now(),'processed':count,'states':dict(D.execute('select state,count(*) from mermaid_reference_fit_repairs_v8 group by state'))}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();main(a.limit,a.ids)
