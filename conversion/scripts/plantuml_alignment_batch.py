"""Bounded native-geometry registration after semantic conversion; no raster wrapping or auto-acceptance."""
import argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time
from pathlib import Path
import numpy as np
from PIL import Image
from skimage.registration import phase_cross_correlation
from native_worker import R,W,native,now
from native_translation import translate
from svg_batch import metric

def dbconn():return sqlite3.connect(W/'jobs.sqlite',timeout=120)
def producers_live():
 for name,script in [('plantuml_repair','plantuml_repair_batch.py'),('plantuml_repair_v3','plantuml_repair_batch_v3.py')]:
  try:
   owner=json.loads((W/(name+'_owner.json')).read_text());p=Path('/proc')/str(owner['pid'])/'cmdline'
   if p.exists() and script.encode() in p.read_bytes():return True
  except (OSError,ValueError):pass
 return False

def repair(out,work):
 xml=(R/out['code_file']).read_text();png=(R/out['image_file']).read_bytes();ref=(R/out['original_reference']).read_bytes();assert hashlib.sha256(xml.encode()).hexdigest()==out['code_sha256'];assert hashlib.sha256(png).hexdigest()==out['image_sha256'];assert hashlib.sha256(ref).hexdigest()==out['source_image_sha256'];a=np.array(Image.open(io.BytesIO(ref)).convert('RGB'));b=np.array(Image.open(io.BytesIO(png)).convert('RGB'));score=metric(ref,png);summary={'before_ssim':score,'variants':[],'source_code_sha256':out['code_sha256']}
 if a.shape!=b.shape:summary['result']='different_canvas_requires_other_repair';return None,summary
 shift,err,_=phase_cross_correlation(a.mean(axis=2),b.mean(axis=2),upsample_factor=10);summary['phase_shift_yx']=shift.tolist();best=None;w,h=a.shape[1],a.shape[0]
 candidates=list(dict.fromkeys([(round(float(shift[1])*2)/2,round(float(shift[0])*2)/2),(round(float(shift[1])),round(float(shift[0])))]))
 for n,(dx,dy) in enumerate(candidates):
  if max(abs(dx),abs(dy))>8 or (dx==0 and dy==0):continue
  moved,proof=translate(xml,dx,dy);render=native.native_job(moved,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
  if not render['ok']:summary['variants'].append({'dx':dx,'dy':dy,'error':str({k:v for k,v in render.items() if k!='png'})});continue
  audit=render['native_render']
  if audit['content_outside_declared_canvas'] or audit['blocked_resource_requests'] or Image.open(io.BytesIO(render['png'])).size!=(w,h):summary['variants'].append({'dx':dx,'dy':dy,'error':'Clipping, changed canvas or blocked resources'});continue
  value=metric(ref,render['png']);entry={'dx':dx,'dy':dy,'ssim':value,'proof':proof};summary['variants'].append(entry);(work/(str(n)+'.drawio')).write_text(moved);(work/(str(n)+'.png')).write_bytes(render['png'])
  if value>score+.001 and (best is None or value>best['score']):best={'xml':moved,'png':render['png'],'score':value,'render':audit,'proof':proof}
 if not best:summary['result']='no_safe_improvement';return None,summary
 archive=work/'before';archive.mkdir(exist_ok=True);(archive/'diagram.drawio').write_text(xml);(archive/'image.png').write_bytes(png);(archive/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));updated=dict(out);updated['metrics']=dict(out['metrics']);updated['metrics'].update(original_reference_ssim_512=best['score'],source_render_vs_drawio_ssim_512=None)
 if out.get('source_render_png'):updated['metrics']['java_source_render_vs_drawio_ssim_512']=metric((R/out['source_render_png']).read_bytes(),best['png'])
 updated.update(code_sha256=hashlib.sha256(best['xml'].encode()).hexdigest(),image_sha256=hashlib.sha256(best['png']).hexdigest(),conversion_method=out['conversion_method']+'_bounded_alignment_v1',render=best['render'],native_alignment={'at':now(),'proof':best['proof'],'previous_method':out['conversion_method'],'previous_code_sha256':out['code_sha256'],'diagnostic_before':score,'diagnostic_after':best['score'],'archive':str(archive.relative_to(R)),'not_acceptance':True},quality_state='pending_independent_source_semantics_and_visual_validation',converted_at_utc=now())
 summary.update(result='published',after_ssim=best['score'],proof=best['proof']);return (updated,best['xml'],best['png']),summary

def worker(index,limit,ids):
 db=dbconn();n=0;log=os.open(W/'plantuml_alignment_events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
 while not limit or n<limit:
  db.execute('begin immediate');sql="select id,state,output_record from jobs j where format='plantuml' and state in ('rendered','needs_quality_repair') and json_extract(output_record,'$.conversion_method') in ('plantuml_pinned_2025_7_source_svg_native_geometry_v1','plantuml_pinned_2025_7_source_svg_native_geometry_v2','plantuml_pinned_2025_7_source_svg_native_geometry_and_physical_fonts_v3') and not exists(select 1 from plantuml_alignment_repairs a where a.id=j.id and a.source_hash=json_extract(j.output_record,'$.code_sha256'))";params=[]
  if ids:sql+=' and id in ('+','.join('?' for _ in ids)+')';params=ids
  else:sql+=" and exists(select 1 from plantuml_geometry_repairs_v3 p where p.id=j.id and p.state in ('published','failed'))"
  row=db.execute(sql+' order by id limit 1',params).fetchone()
  if not row:
   db.commit()
   if limit or ids or not producers_live():break
   time.sleep(15);continue
  id,before,raw=row;out=json.loads(raw);source_hash=out['code_sha256'];db.execute('insert into plantuml_alignment_repairs values (?, ?,"running",NULL,?)',(id,source_hash,now()));db.execute('update jobs set state="plantuml_alignment_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));db.commit();start=time.monotonic();work=W/'plantuml_alignment'/id/source_hash[:16];work.mkdir(parents=True,exist_ok=True);record={'id':id,'started_at':now()};published=False;error=None
  try:
   result,summary=repair(out,work);record.update(summary)
   if result:
    updated,xml,png=result
    db.execute('begin immediate');current=db.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert current==('plantuml_alignment_repairing',raw),'Job ownership changed'
    for key,data in [('code_file',xml.encode()),('image_file',png)]:p=R/out[key];tmp=p.with_suffix(p.suffix+'.alignment.tmp');tmp.write_bytes(data);tmp.replace(p)
    (R/out['code_file']).parent.joinpath('conversion.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n');out=updated;published=True
  except Exception as e:error=repr(e);record.update(result='failed',error=error);db.rollback()
  db.execute('update jobs set state=?,output_record=?,error=?,worker_pid=NULL,updated_at=? where id=?',('needs_quality_repair' if published else before,json.dumps(out,ensure_ascii=False) if published else raw,error,now(),id));db.execute('update plantuml_alignment_repairs set state=?,record=?,updated_at=? where id=? and source_hash=?',(record['result'],json.dumps(record),now(),id,source_hash));db.commit();n+=1;os.write(log,(json.dumps({**record,'worker':index,'pid':os.getpid(),'seconds':time.monotonic()-start})+'\n').encode())
 os.close(log);return {'worker':index,'processed':n}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();db=dbconn();db.execute('create table if not exists plantuml_alignment_repairs (id TEXT,source_hash TEXT,state TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,source_hash))');db.commit();db.close();(W/'plantuml_alignment_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'ids':a.ids,'started_at_utc':now()}))
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[a.ids]*a.workers))
 (W/('plantuml_alignment_smoke_summary.json' if a.limit or a.ids else 'plantuml_alignment_summary.json')).write_text(json.dumps({'at':now(),'results':results,'goal_complete':False},indent=2))
