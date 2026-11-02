"""Preserve exact native pixels while bundling each observed physical font face."""
import argparse,concurrent.futures,hashlib,json,os,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from portable_native_fonts_v2 import capture,embed,ready_page
from fontmix_validation import verify_graph,verify_fonts,zero_lineboxes
from durable_sqlite import begin,commit
sha=lambda b:hashlib.sha256(b).hexdigest()

def canonical(xml,changed):
 root=E.fromstring(xml);root.find('.//mxGraphModel').attrib.pop('extFonts',None);parents={c:p for p in root.iter() for c in p}
 for c in root.iter('mxCell'):
  cid=c.get('id') or parents[c].get('id')
  if cid in changed:c.set('style',';'.join(x for x in c.get('style','').split(';') if x and x.split('=',1)[0] not in ['fontFamily','fontStyle','fontSource'])+';')
 return E.canonicalize(E.tostring(root,encoding='unicode'))

def worker(index,limit,ids):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);done=0;log=os.open(W/'native_font_embedding_v2_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser)
  while not limit or done<limit:
   sql="""select j.id,j.state,j.output_record from jobs j where j.state in ('rendered','needs_quality_repair') and j.format in ('mermaid','plantuml','svg','python','html') and j.output_record is not null and coalesce(json_extract(j.output_record,'$.native_font_validation.output_code_sha256'),'')!=json_extract(j.output_record,'$.code_sha256') and exists(select 1 from native_font_embeddings prior where prior.id=j.id and prior.input_code_sha256=json_extract(j.output_record,'$.code_sha256') and prior.state='pending_separate_font_repair' and prior.record like '%mixed_or_missing_physical_font%') and not exists(select 1 from native_font_embeddings_v2 f where f.id=j.id and f.input_code_sha256=json_extract(j.output_record,'$.code_sha256'))""";args=[]
   if ids:sql+=' and j.id in ('+','.join('?' for _ in ids)+')';args=ids
   row=D.execute(sql+' order by j.id limit 1',args).fetchone()
   if row is None:
    if limit or ids:break
    time.sleep(20);continue
   id,before,raw=row;old=json.loads(raw);oldhash=old['code_sha256'];begin(D)
   if D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()!=(before,raw) or D.execute('select 1 from native_font_embeddings_v2 where id=? and input_code_sha256=?',(id,oldhash)).fetchone():D.rollback();continue
   D.execute('insert into native_font_embeddings_v2 values (?,?,"running",NULL,?)',(id,oldhash,now()));D.execute('update jobs set state="font_embedding_v2_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(D);report={'id':id,'input_code_sha256':oldhash,'at':now()};out=None;work=W/'native_font_embedding_v2'/id/oldhash;work.mkdir(parents=True,exist_ok=True);start=time.monotonic()
   try:
    xml=(R/old['code_file']).read_text();png=(R/old['image_file']).read_bytes();assert sha(xml.encode())==oldhash and sha(png)==old['image_sha256'];(work/'before.drawio').write_text(xml);(work/'before_record.json').write_text(raw);model=E.fromstring(xml).find('.//mxGraphModel');assert not model.get('extFonts') and 'fontSource=' not in xml,'Existing custom font payload requires separate asset verification';observed=capture(page,xml);(work/'observed_fonts.json').write_text(json.dumps(observed,indent=2));new,fonts,details=embed(xml,observed,work/'fonts',page);(work/'font_details.json').write_text(json.dumps(details,indent=2));assert not details['issues'],str(details['issues'])[:1600];assert details['mixed_text_cells'] and details['changes'],'No mixed-font text to repair';changed={x['cell'] for x in details['changes']};w,h=Image.open(R/old['image_file']).size;attempts=[];selected=None
    for variant,candidate in [('inherited',new),('zero',zero_lineboxes(new,details))]:
     attempt={'variant':variant}
     try:
      verify_graph(xml,candidate,details);fresh=native.native_job(candidate,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'],str({k:v for k,v in fresh.items() if k!='png'});(work/(variant+'.drawio')).write_text(candidate);(work/(variant+'_render.json')).write_text(json.dumps(fresh['native_render'],indent=2));verify_fonts(observed,fresh['native_render'],details);attempt['font_glyph_counts_preserved']=True;assert fresh['png']==png,'Embedded-font candidate changes native PNG pixels';attempt['ok']=True;selected=variant;new=candidate
     except Exception as e:attempt.update(ok=False,error=repr(e))
     attempts.append(attempt);(work/'attempts.json').write_text(json.dumps(attempts,indent=2))
     if selected:break
    assert selected,'No pixel-identical mixed-font candidate: '+str(attempts)
    details={k:v for k,v in details.items() if k!='grapheme_probes'};report['selected_linebox_variant']=selected
    records=[];fontroot=R/'clean/font_assets';fontroot.mkdir(exist_ok=True)
    for f in fonts.values():
     src=Path(f['file']);dest=fontroot/src.name
     if not dest.exists():tmp=dest.with_suffix(dest.suffix+'.'+str(os.getpid())+'.tmp');shutil.copyfile(src,tmp);tmp.replace(dest)
     assert sha(dest.read_bytes())==f['sha256'];orig=Path(f['original_file']);originaldest=fontroot/(f['original_sha256']+orig.suffix.lower())
     if not originaldest.exists():tmp=originaldest.with_suffix(originaldest.suffix+'.'+str(os.getpid())+'.tmp');shutil.copyfile(orig,tmp);tmp.replace(originaldest)
     assert sha(originaldest.read_bytes())==f['original_sha256'];records.append({**{k:v for k,v in f.items() if k not in ['uri','file','original_file']},'file':str(dest.relative_to(R)),'original_file':str(originaldest.relative_to(R)),'source_system_font_path':str(orig)})
    proof={'ok':True,'output_code_sha256':sha(new.encode()),'actual_custom_font_text_cells':len(changed),'font_files':len(records),'physical_faces_preserved':True,'native_pixels_unchanged':True,'graph_changes_limited_to_font_styles_and_verified_editable_spans':True,'physical_font_glyph_counts_preserved':True,'editable_text_exact':True,'method':'physical_font_runs_with_exact_native_pixels_v2','font_details':details,'audit':str((work/'report.json').relative_to(R))};out={**old,'code_sha256':sha(new.encode()),'render':fresh['native_render'],'native_embedded_fonts':records,'native_font_validation':proof};out['validation_pending']=[x.replace('Font asset portability and final full resource checks','Final full resource checks') for x in old.get('validation_pending',[])];report.update(published=True,font_files=len(records),text_cells=len(changed),native_pixels_unchanged=True,accepted=False);(work/'before.drawio').write_text(xml);(work/'before_record.json').write_text(raw);(work/'candidate.drawio').write_text(new);(work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(work/'observed_fonts.json').write_text(json.dumps(observed,indent=2))
   except Exception as e:out=None;report.update(published=False,error=repr(e),accepted=False)
   (work/'report.json').write_text(json.dumps(report,indent=2));newraw=json.dumps(out,ensure_ascii=False) if out else raw;begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('font_embedding_v2_repairing',os.getpid(),raw),'Job ownership changed'
   if out:
    path=R/out['code_file'];tmp=path.with_suffix('.font.tmp');shutil.copyfile(work/'candidate.drawio',tmp);tmp.replace(path);meta=path.parent/'conversion.json';tmp=meta.with_suffix('.font.tmp');tmp.write_text(newraw+'\n');tmp.replace(meta)
   D.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',(before,newraw,now(),id));D.execute('update native_font_embeddings_v2 set state=?,record=?,updated_at=? where id=? and input_code_sha256=?',('published' if out else 'pending_separate_font_repair',json.dumps(report),now(),id,oldhash));commit(D)
   if out:(work/'committed.json').write_text(json.dumps({'at':now(),'output_code_sha256':out['code_sha256'],'image_sha256':out['image_sha256']}))
   os.write(log,(json.dumps({**report,'seconds':time.monotonic()-start,'worker_pid':os.getpid()})+'\n').encode());done+=1
  browser.close()
 os.close(log);return {'worker':index,'processed':done}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists native_font_embeddings_v2 (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');commit(D);D.close();(W/'native_font_embedding_v2_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'ids':a.ids,'at':now()}));
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[a.ids]*a.workers))
 (W/('native_font_embedding_v2_smoke_summary.json' if a.limit or a.ids else 'native_font_embedding_v2_summary.json')).write_text(json.dumps({'at':now(),'results':results},indent=2))
