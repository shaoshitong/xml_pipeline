import json,sqlite3,hashlib,io
from pathlib import Path
from PIL import Image
from native_worker import R,W,native,now
from durable_sqlite import begin,commit
D=sqlite3.connect(W/'jobs.sqlite',timeout=2);base=W/'recovery_audit';base.mkdir(exist_ok=True);selected=json.loads((W/'active_worker_pid_audit.json').read_text())['dead'];results=[]
for item in selected:
 id=item['id'];report={'id':id,'at':now()}
 try:
  state,raw,pid,input_raw=D.execute('select state,output_record,worker_pid,input_record from jobs where id=?',(id,)).fetchone();assert state==item['state'] and pid==item['pid'];proc=Path('/proc')/str(pid)/'cmdline';assert not proc.exists() or not proc.read_bytes(),'Worker still live';source=json.loads(input_raw);meta=R/'clean/drawio_unified'/id[:2]/id/'conversion.json';out=json.loads(meta.read_text());assert out['id']==id and out['source_image_sha256']==source['image_sha256'] and out['source_code_sha256']==source['code_sha256'];checks=[]
  for pathkey,hashkey in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_svg','source_render_svg_sha256')]:
   if out.get(pathkey):
    path=R/out[pathkey];assert path.resolve().is_relative_to(R/'clean');assert hashlib.sha256(path.read_bytes()).hexdigest()==out[hashkey],pathkey;checks.append(pathkey)
  for group in ['fonts','source_assets']:
   for asset in out.get(group,[]):
    path=R/asset['file'];assert path.resolve().is_relative_to(R/'clean');assert hashlib.sha256(path.read_bytes()).hexdigest()==asset.get('embedded_sha256',asset.get('sha256')),group
    if asset.get('original_file'):assert hashlib.sha256((R/asset['original_file']).read_bytes()).hexdigest()==asset['original_sha256']
  xml=(R/out['code_file']).read_text();png=(R/out['image_file']).read_bytes();w,h=Image.open(R/out['original_reference']).size;fresh=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];assert fresh['png']==png,'Fresh actual native PNG differs';report.update(payloads_verified=checks,fresh_native_png_identical=True,old_worker_pid=pid,old_state=state,recovered_state='needs_quality_repair',accepted=False)
  (base/(id+'.before.json')).write_text(json.dumps({'state':state,'record':json.loads(raw) if raw else None,'worker_pid':pid},indent=2));(base/(id+'.verified.json')).write_text(json.dumps(report,indent=2));out['publication_recovery']={'at':now(),'proof':str((base/(id+'.verified.json')).relative_to(R))};out['quality_state']='pending_source_and_visual_validation_after_verified_publication_recovery';newraw=json.dumps(out,ensure_ascii=False)
  begin(D);assert D.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()==(state,raw,pid);assert not proc.exists() or not proc.read_bytes();tmp=meta.with_suffix('.recovery.tmp');tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2));tmp.replace(meta);D.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=NULL,error=?,updated_at=? where id=?',(newraw,'Recovered persisted native candidate after original worker terminated on SQLite lock; source/visual validation still required.',now(),id))
  if state=='svg_v6_repairing':D.execute('update svg_v6_repairs set state="published",record=?,updated_at=? where id=?',(json.dumps(report),now(),id))
  elif state=='tikz_converting':
   D.execute('insert or replace into tikz_native_results values (?,?,?,?,?)',(id,'needs_quality_repair','Verified publication recovered after lock failure',now(),json.dumps(report)));D.execute('update tikz_ligature_repairs set finished_at=? where id=?',(now(),id))
  commit(D);report['recovered']=True
 except Exception as e:D.rollback();report.update(recovered=False,error=repr(e))
 results.append(report);print(json.dumps(report),flush=True)
(base/'summary.json').write_text(json.dumps({'at':now(),'results':results},indent=2));assert all(r.get('recovered') for r in results)
