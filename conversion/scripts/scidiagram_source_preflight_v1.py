"""Source-only original-reference preflight for all 46 priority Sci SVGs."""
from pathlib import Path
import concurrent.futures,collections,datetime,fcntl,hashlib,json,os,sqlite3,sys,time,traceback
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,v):
 tmp=p.with_name(p.name+'.tmp');tmp.write_bytes(raw(v));os.replace(tmp,p)
def observe(request):
 import compiler_scidiagram_source_frontend_v1 as f
 identifier=request['id'];start=time.monotonic();out=dict(id=identifier,normal_conversion_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0)
 try:
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
   db.row_factory=sqlite3.Row;row=db.execute('select*from jobs where id=?',(identifier,)).fetchone();job=dict(row)if row else None
  if job is None:raise ValueError('source_original_not_registered_in_canonical_job_inventory')
  source=json.loads(job['input_record']);seed=dict(id=identifier,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256']);prepared=f.prepare_source(seed,job)
  reference=prepared['sourceproof']['source_reference'];font=prepared['sourceproof']['cairo_browser_physical_font_equivalence'];out.update(status='source_supported'if prepared['ok']else'source_reference_or_font_review',source_work=str(prepared['work']),original_code_sha256=source['code_sha256'],original_image_sha256=source['image_sha256'],source_objects=len(prepared['capture']['dom']['objects']),source_reference_ok=reference['ok'],source_reference_ssim=reference.get('ssim_1024'),source_reference_failures=reference.get('failures'),source_physical_font_ok=font['ok'],resolved_images=len(prepared['sourceproof']['original_panel_resolution']['resolved_images']))
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
   db.row_factory=sqlite3.Row;assert dict(db.execute('select*from jobs where id=?',(identifier,)).fetchone())==job,'canonical_source_row_changed'
 except Exception as e:out.update(status='source_unsupported',reason=str(e)[:3000],error_type=type(e).__name__,traceback=traceback.format_exc()[-4000:])
 out['seconds']=time.monotonic()-start;out['at_utc']=now();return out

def main():
 import compiler_scidiagram_source_frontend_v1 as f
 config=f.configuration();root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=False)
 lock=(root/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);requests=[];index=R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources/index.jsonl'
 for line in index.open():
  row=json.loads(line)
  if row['source']=='yashengsun--SciDiagramRevision'and row['status']=='complex_candidate':requests.append(row)
 assert len(requests)==46 and all(r['source_format']=='svg'for r in requests)
 (root/'source_targets.jsonl').write_bytes(b''.join(json.dumps(row,sort_keys=True).encode()+b'\n'for row in requests));(root/'source_targets.jsonl').chmod(0o444)
 plan=dict(schema='original_provider_SciDiagramRevision_source_preflight_v1',configuration=config,scope=46,producer_sha256=sha(Path(__file__).read_bytes()),source_targets_sha256=sha((root/'source_targets.jsonl').read_bytes()),source_reference_quality_thresholds_changed=False,original_svg_and_provider_png_unchanged=True,new_references_created=False,normal_calls=0,QA_calls=0);(root/'plan.json').write_bytes(raw(plan));(root/'plan.json').chmod(0o444)
 atomic(root/'owner.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19],at_utc=now()));db=sqlite3.connect(root/'status.sqlite');db.execute('create table cases(id text primary key,status text,result text)');db.executemany('insert into cases values(?,?,null)',[(r['id'],'queued')for r in requests]);db.commit();t=time.monotonic()
 def summary(finished=False):
  counts=dict(db.execute('select status,count(*)from cases group by status'));value=dict(at_utc=now(),root=str(root),counts=counts,completed=46-counts.get('queued',0)-counts.get('running',0),scope=46,finished=finished,elapsed_seconds=time.monotonic()-t,normal_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0,goal_complete=False);atomic(root/'summary.json',value);return value
 summary()
 with concurrent.futures.ProcessPoolExecutor(max_workers=4)as pool:
  futures={pool.submit(observe,row):row['id']for row in requests}
  for future in concurrent.futures.as_completed(futures):
   identifier=futures[future]
   try:value=future.result()
   except Exception as e:value=dict(id=identifier,status='observer_error',reason=str(e),normal_conversion_calls=0,candidate_emissions=0,QA_calls=0)
   db.execute('update cases set status=?,result=?where id=?',(value['status'],json.dumps(value),identifier));db.commit();summary()
 assert config==f.configuration();results=[json.loads(r[0])for r in db.execute('select result from cases order by id')];target=root/'source_preflight_results.jsonl';target.write_bytes(b''.join(json.dumps(r,sort_keys=True).encode()+b'\n'for r in results));target.chmod(0o444);value=summary(True);value['results']=dict(file=str(target.relative_to(R)),sha256=sha(target.read_bytes()));value['reasons']=dict(collections.Counter(r.get('reason')or str(r.get('source_reference_failures'))for r in results));atomic(root/'summary.json',value);db.close();lock.close();print(json.dumps(value),flush=True)
if __name__=='__main__':main()
