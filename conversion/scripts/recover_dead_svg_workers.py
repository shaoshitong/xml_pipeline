import json,sqlite3
from pathlib import Path
from PIL import Image
from native_worker import R,W,native,now,sha
from durable_sqlite import begin,commit

def live(pid):
 p=Path('/proc')/str(pid)/'cmdline';return p.exists() and bool(p.read_bytes())
owner=json.loads((W/'svg_batch_v2_owner.json').read_text());assert not live(owner['pid']),'Original SVG coordinator still live'
D=sqlite3.connect(W/'jobs.sqlite',timeout=2);rows=D.execute('select id,state,worker_pid,output_record,input_record from jobs where state="svg_converting" and route="svg_v2"').fetchall();B=W/'svg_worker_recovery_20261031';B.mkdir(exist_ok=True);results=[]
for id,state,pid,raw,source_raw in rows:
 if live(pid):continue
 source=json.loads(source_raw);base=B/id;base.mkdir(exist_ok=True);before={'state':state,'worker_pid':pid,'output_record':json.loads(raw) if raw else None};(base/'before.json').write_text(json.dumps(before,indent=2));meta=R/'clean/drawio_unified'/id[:2]/id/'conversion.json';recovered=None;error=None
 try:
  body=meta.read_text();(base/'before_conversion.json').write_text(body);out=json.loads(body);assert out['id']==id and out['source_code_sha256']==source['code_sha256'] and out['source_image_sha256']==source['image_sha256']
  for k,hk in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:
   p=R/out[k];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==out[hk]
  w,h=Image.open(R/out['original_reference']).size;fresh=native.native_job((R/out['code_file']).read_text(),w,h,120,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==(R/out['image_file']).read_bytes(),'Actual rerender differs'
  out['publication_recovery']={'at':now(),'previous_worker_pid':pid,'audit':str((base/'result.json').relative_to(R))};out['quality_state']='pending_source_and_visual_validation_after_verified_publication_recovery';recovered=out
 except Exception as e:error=repr(e)
 begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==(state,pid,raw);assert not live(pid)
 if recovered:
  temp=meta.with_suffix('.recovered.tmp');temp.write_text(json.dumps(recovered,ensure_ascii=False,indent=2));temp.replace(meta);D.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=NULL,error=?,updated_at=? where id=?',(json.dumps(recovered,ensure_ascii=False),'Recovered verified candidate after confirmed SQLite-lock worker termination; quality review pending',now(),id));action='recovered_verified_pair'
 else:
  D.execute('update jobs set state="queued",worker_pid=NULL,error=?,updated_at=? where id=?',('Requeued after confirmed worker termination; existing files preserved; recovery validation: '+str(error),now(),id));action='requeued_preserving_existing_files'
 commit(D);result={'id':id,'previous_pid':pid,'action':action,'recovery_error':error,'accepted':False,'at':now()};(base/'result.json').write_text(json.dumps(result,indent=2));results.append(result);print(json.dumps(result),flush=True)
out={'at':now(),'original_coordinator_confirmed_terminal':True,'results':results,'goal_complete':False};(B/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
