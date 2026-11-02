"""Repair the current explicit-source graph cohort with full revision ownership and audits."""
import argparse,concurrent.futures,hashlib,json,os,shutil,signal,sqlite3,subprocess,time,xml.etree.ElementTree as E
from native_worker import R,W,now
from durable_sqlite import begin,commit
from native_page_padding_batch import source_render
from harness_source_provenance import validate_source_record
from svg_batch import metric
sha=lambda b:hashlib.sha256(b).hexdigest()
STATE='tikz_literal_repairing'

def execute(script,args,work,timeout=420):
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts'/script),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),start_new_session=True)
 try:out,err=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGKILL);p.communicate();raise
 work.mkdir(parents=True,exist_ok=True);(work/(script+'.stdout')).write_bytes(out);(work/(script+'.stderr')).write_bytes(err)
 assert p.returncode==0,err.decode(errors='replace')[-1800:]

def repair(id,raw):
 old=json.loads(raw);digest=old['code_sha256'];work=W/'tikz_literal_binding_pilot'/id/digest;validate_source_record(old)
 execute('pilot_tikz_literal_binding.py',[id],work)
 report=json.loads((work/'report.json').read_text());assert report['input_code_sha256']==digest and report['binding']['complete'],json.dumps(report['binding']['issues'])
 assert report.get('render_ok') and report['after_ssim']>=report['before_ssim']-.02,'Material raster fidelity regression requires a separate repair'
 execute('verify_tikz_literal_binding.py',[id,digest],work)
 verification=json.loads((work/'verification.json').read_text());assert verification['ok'] and verification['output_code_sha256']==report['output_code_sha256']
 info=json.loads((work/'render.json').read_text());usage=[f for row in info['actual_platform_font_usage'] for f in row['fonts'] if f['glyphCount']];assert usage and all(f['isCustomFont'] for f in usage),'Native text fell back to an unembedded font'
 w,h=info['canvas'];source_attempts=[]
 for i in range(3):
  try:sourcepng=source_render(old,w,h,work);source_attempts.append({'attempt':i+1,'ok':True});break
  except Exception as exc:
   source_attempts.append({'attempt':i+1,'error':repr(exc)})
   if 'Page.captureScreenshot' not in str(exc) or i==2:raise
 (work/'source_capture_attempts.json').write_text(json.dumps(source_attempts,indent=2)+'\n')
 xml=(work/'candidate.drawio').read_bytes();png=(work/'candidate.png').read_bytes();assert sha(xml)==report['output_code_sha256'] and sha(png)==report['output_image_sha256'];reference=(R/old['original_reference']).read_bytes();archive=W/'harness_sessions'/('literal_binding_'+id+'_'+digest)/'baseline';archive.mkdir(parents=True,exist_ok=True);(archive/'conversion.json').write_text(raw);shutil.copyfile(work/'baseline.drawio',archive/'diagram.drawio');shutil.copyfile(R/old['image_file'],archive/'image.png');assert sha((archive/'diagram.drawio').read_bytes())==digest and sha((archive/'image.png').read_bytes())==old['image_sha256']
 cells=list(E.fromstring(xml).iter('mxCell'));issues=[x for x in old.get('unresolved_issues',[]) if x.get('reason')!='tikz_source_connectivity_unresolved']+report['binding']['issues']
 out={**old,'code_sha256':sha(xml),'image_sha256':sha(png),'conversion_method':'source_named_tikz_nodes_and_native_bound_paths_v1','connectivity':report['binding'],'vertices':sum(c.get('vertex')=='1' for c in cells),'edges':report['source_edges'],'bound_edges':report['source_edges'],'render':info,'metrics':{**old.get('metrics',{}),'original_reference_ssim_512':report['after_ssim'],'original_source_render_ssim_512':metric(reference,sourcepng),'source_render_vs_drawio_ssim_512':metric(sourcepng,png)},'previous_candidate_archive':str(archive.relative_to(R)),'native_binding_validation':str((work/'verification.json').relative_to(R)),'unresolved_issues':issues,'quality_state':'pending_source_graph_arrow_fidelity_and_independent_visual_acceptance','converted_at_utc':now()}
 (work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');summary={'id':id,'at':now(),'input_hash':digest,'code_sha256':sha(xml),'image_sha256':sha(png),'source_nodes':report['source_nodes'],'bound_edges':report['source_edges'],'endpoint_moves':len(verification['native_moves']['moves']),'source_ssim_before':report['before_ssim'],'source_ssim_after':report['after_ssim'],'work':str(work.relative_to(R)),'accepted':False};return work,out,summary

def worker(index,limit):
 d=sqlite3.connect(W/'jobs.sqlite',timeout=2);n=0;counts={}
 while not limit or n<limit:
  row=d.execute('''select j.id,j.state,j.output_record from jobs j join tikz_literal_candidates c on c.id=j.id where j.state in ('rendered','needs_quality_repair') and j.worker_pid is NULL and coalesce(json_extract(j.output_record,'$.edges'),0)=0 and json_extract(j.output_record,'$.native_page_padding') is NULL and json_extract(j.output_record,'$.native_canvas_contract') is NULL and not exists(select 1 from tikz_literal_repairs t where t.id=j.id and t.input_hash=json_extract(j.output_record,'$.code_sha256')) order by c.reference_ssim desc,j.id limit 1''').fetchone()
  if not row:
   if limit:break
   time.sleep(30);continue
  id,state,raw=row;digest=json.loads(raw)['code_sha256'];begin(d)
  if d.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()!=(state,raw,None) or d.execute('select 1 from tikz_literal_repairs where id=? and input_hash=?',(id,digest)).fetchone():d.rollback();continue
  d.execute('insert into tikz_literal_repairs values (?,?,"running",NULL,?)',(id,digest,now()));d.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,os.getpid(),now(),id));commit(d);out=None
  try:work,out,record=repair(id,raw)
  except Exception as exc:record={'id':id,'at':now(),'input_hash':digest,'error':repr(exc),'previous_candidate_retained':True,'accepted':False}
  begin(d);assert d.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()==(STATE,raw,os.getpid()),'Repair ownership changed'
  stage='published' if out else 'retained_prior_candidate'
  if out:
   for a,b in [(work/'candidate.drawio',R/out['code_file']),(work/'candidate.png',R/out['image_file']),(work/'candidate_record.json',(R/out['code_file']).parent/'conversion.json')]:
    tmp=b.with_suffix(b.suffix+'.literal.tmp');shutil.copyfile(a,tmp);tmp.replace(b)
  d.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',('needs_quality_repair' if out else state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));d.execute('update tikz_literal_repairs set state=?,record=?,updated_at=? where id=? and input_hash=?',(stage,json.dumps(record),now(),id,digest));commit(d);n+=1;counts[stage]=counts.get(stage,0)+1;print(json.dumps({'at':now(),'id':id,'worker':index,'stage':stage,'bound_edges':record.get('bound_edges'),'error':record.get('error')}),flush=True)
 return {'worker':index,'processed':n,'counts':counts}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);a=p.parse_args()
 for name in ('tikz_literal_parser_tests.json','tikz_literal_binding_guard_tests.json'):assert json.loads((W/name).read_text())['ok']
 inventory=json.loads((W/'tikz_literal_inventory.json').read_text());d=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(d);d.execute('create table if not exists tikz_literal_candidates(id TEXT PRIMARY KEY,reference_ssim REAL)');d.execute('create table if not exists tikz_literal_repairs(id TEXT,input_hash TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_hash))');d.executemany('insert or replace into tikz_literal_candidates values (?,?)',[(x['id'],x['reference_ssim'] or 0) for x in inventory['candidates']]);commit(d);d.close();(W/'tikz_literal_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'at':now(),'seeded_candidates':len(inventory['candidates'])}))
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 (W/('tikz_literal_smoke_summary.json' if a.limit else 'tikz_literal_summary.json')).write_text(json.dumps({'at':now(),'results':results,'goal_complete':False},indent=2)+'\n')
