"""Durable parallel source-only admission; never emit a candidate or run QA."""
from pathlib import Path
import argparse,concurrent.futures,datetime,hashlib,json,os,signal,sqlite3,subprocess,sys,time,traceback
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def raw(x):return(json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,value):
 tmp=p.with_name(p.name+'.tmp');tmp.write_bytes(raw(value));os.replace(tmp,p)
def leaf_alpha_source_supported(obj,dom):
 st=obj.get('style',{});css=obj.get('sceneComputedCss',{});refs=obj.get('sceneAncestry',[]);anc=dom['sceneMetadata']['ancestors']
 return obj.get('type')=='shape'and obj.get('tag')in('rect','circle','ellipse','polygon')and st.get('fill')!='none'and st.get('stroke')=='none'and not obj.get('sceneUseContexts')and not obj.get('sceneMarkerContexts')and bool(refs)and all(float(anc[r]['opacity'])==1 for r in refs[:-1])and 0<float(st.get('opacity',1))<1 and abs(float(anc[refs[-1]]['opacity'])-float(st['opacity']))<1e-8 and css.get('mixBlendMode')=='normal'and css.get('isolation')=='auto'and all(css.get(k)=='none'for k in('filter','clipPath','maskImage'))
def case(identifier,work):
 import compiler_svg_scene_frontend_v22 as f
 import compiler_svg_general_guard_v18 as core
 out=dict(id=identifier,at_utc=now(),normal_conversion_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0);t=time.monotonic();job=None
 try:
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
   db.row_factory=sqlite3.Row;job=dict(db.execute('select*from jobs where id=?',(identifier,)).fetchone())
  original=json.loads(job['input_record']);out.update(source_code_sha256=original['code_sha256'],source_image_sha256=original['image_sha256']);prepared=f.prepare_source(job);out['source_observation_work']=str(prepared['work']);out['source_reference_and_physical_font_reproduced']=prepared['ok']
  if not prepared['ok']:raise ValueError('source_reference_or_physical_font_mismatch')
  dom=prepared['capture']['dom'];features=core.source_features(dom,prepared['size']);allowed={o['id']for o in dom['objects']if leaf_alpha_source_supported(o,dom)}
  failures=[v for v in features['failures']if not(v.get('reason')=='source_element_or_ancestor_opacity_requires_compositing_frontend'and v.get('id')in allowed)]
  out.update(status='unsupported'if failures else'admitted',source_feature_failures=failures,objects=len(dom['objects']),source_bindings=len(features['binding']['bindings']),marker_instances=len(features['binding']['markers']),single_fill_leaf_alpha_source_cases=sorted(allowed),source_only_semantic_admission=True,candidate_quality_not_predicted_or_claimed=True,reason=failures[0]['reason']if failures else'source_semantic_admission_passed')
 except Exception as e:
  reason=str(e);source_rejection=reason.startswith(('source_','actual_source_','general_svg_','unsupported_','unregistered_reference_','use_'))
  out.update(status='unsupported'if source_rejection else'error',reason=reason[:3000],error_type=type(e).__name__,traceback=traceback.format_exc()[-6000:])
 finally:
  if job is not None:
   with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
    db.row_factory=sqlite3.Row;current=dict(db.execute('select*from jobs where id=?',(identifier,)).fetchone())
   if current!=job:out.update(status='error',reason='infrastructure_canonical_source_row_changed_during_observation')
  out['elapsed_seconds']=time.monotonic()-t;out['finished_at']=now();atomic(work/'result.json',out)
 return out

def execute(root,workers,timeout):
 import compiler_svg_general_guard_v18 as core
 cfg=json.loads((root/'configuration.json').read_bytes());assert cfg==core.configuration();assert sha(Path(__file__).read_bytes())==json.loads((root/'plan.json').read_bytes())['producer_sha256'];db=sqlite3.connect(root/'status.sqlite');db.execute('pragma journal_mode=WAL');db.row_factory=sqlite3.Row
 # Resume only after the previous owner is demonstrably gone; never supersede
 # live work or infer death from a stale timestamp.
 owner_path=root/'owner.json'
 if owner_path.exists():
  owner=json.loads(owner_path.read_bytes());p=Path('/proc',str(owner['pid']),'stat')
  if p.exists()and p.read_text().rsplit(') ',1)[1].split()[19]==str(owner['birth_ticks']):raise RuntimeError('existing_audit_owner_live_no_duplicate')
 owner=dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19],at_utc=now());atomic(owner_path,owner)
 db.execute("update sources set status='queued' where status='running'");db.commit();start=time.monotonic();attempted_before=db.execute("select count(*)from sources where status!='queued'").fetchone()[0]
 def summary(finished=False):
  counts=dict(db.execute('select status,count(*)from sources group by status'));value=dict(at_utc=now(),root=str(root),counts=counts,total=sum(counts.values()),completed=sum(counts.get(k,0)for k in('admitted','unsupported','error')),finished=finished,source_core_configuration_sha256=sha(raw(cfg)),normal_conversion_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0,goal_complete=False,elapsed_seconds=time.monotonic()-start);atomic(root/'summary.json',value);return value
 def observe(row):
  work=root/'cases'/row['id'];work.mkdir(parents=True,exist_ok=True);log=(work/('attempt_'+str(row['attempts']+1)+'.log')).open('wb');command=[sys.executable,str(Path(__file__).resolve()),'case','--id',row['id'],'--work',str(work)]
  process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
  try:process.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   if process.poll()is None:os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:
    if process.poll()is None:os.killpg(process.pid,signal.SIGKILL)
    process.wait()
   return dict(id=row['id'],status='error',reason='infrastructure_source_observation_timeout',normal_conversion_calls=0,candidate_emissions=0,QA_calls=0,elapsed_seconds=timeout)
  finally:log.close()
  result=work/'result.json'
  if process.returncode or not result.exists():return dict(id=row['id'],status='error',reason='infrastructure_source_observer_process_exit',exit_code=process.returncode)
  value=json.loads(result.read_bytes());assert value['id']==row['id']and value['candidate_emissions']==0 and value['normal_conversion_calls']==0
  assert(value.get('source_code_sha256'),value.get('source_image_sha256'))==(row['source_code_sha256'],row['source_image_sha256']);return value
 summary();queue=iter(db.execute("select*from sources where status='queued' order by seq").fetchall());futures={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
  def dispatch():
   while len(futures)<workers:
    row=next(queue,None)
    if row is None:return
    db.execute("update sources set status='running',attempts=attempts+1,started_at=? where id=?",(now(),row['id']));db.commit();futures[pool.submit(observe,row)]=row['id']
  dispatch();summary()
  while futures:
   done,_=concurrent.futures.wait(futures,timeout=5,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    identifier=futures.pop(future)
    try:value=future.result()
    except Exception as e:value=dict(id=identifier,status='error',reason='infrastructure_admission_controller_exception:'+str(e))
    db.execute('update sources set status=?,finished_at=?,result=? where id=?',(value['status'],now(),json.dumps(value),identifier));db.commit()
   dispatch();summary()
 assert cfg==core.configuration();assert sha(Path(__file__).read_bytes())==json.loads((root/'plan.json').read_bytes())['producer_sha256'];final=summary(True)
 for status in('admitted','unsupported','error'):
  rows=[json.loads(r[0])for r in db.execute('select result from sources where status=?order by seq',(status,))];target=root/(status+'.jsonl');target.write_bytes(b''.join(json.dumps(row,sort_keys=True).encode()+b'\n'for row in rows));target.chmod(0o444)
 final['files']={name:dict(file=str((root/name).relative_to(R)),sha256=sha((root/name).read_bytes()))for name in['admitted.jsonl','unsupported.jsonl','error.jsonl']};atomic(root/'summary.json',final);db.close();return final

def create(root,pool):
 import compiler_svg_general_guard_v18 as core
 root.mkdir(parents=True,exist_ok=False);source=pool/'supported_population.jsonl';rows=[json.loads(x)for x in source.read_bytes().splitlines()if x];cfg=core.configuration();(root/'configuration.json').write_bytes(raw(cfg));(root/'configuration.json').chmod(0o444);(root/'input.jsonl').write_bytes(source.read_bytes());(root/'input.jsonl').chmod(0o444)
 plan=dict(source_pool=str(pool),input_sha256=sha(source.read_bytes()),targets=len(rows),configuration=cfg,producer_sha256=sha(Path(__file__).read_bytes()),policy='All source-only Cairo/reference/font, source DOM/use and semantic/marker/compositing admission checks precede future unseen selection. No candidate is emitted, no candidate quality is inspected, source-family seals and every rejected original remain retained. This is not a qualification or a change to quality thresholds.',normal_calls=0,candidate_emissions=0,QA_calls=0)
 (root/'plan.json').write_bytes(raw(plan));(root/'plan.json').chmod(0o444);db=sqlite3.connect(root/'status.sqlite');db.execute('create table sources(seq integer primary key,id text unique,source_code_sha256 text,source_image_sha256 text,status text,attempts integer,started_at text,finished_at text,result text)');db.executemany('insert into sources values(?,?,?,?,?,0,null,null,null)',[(i,r['id'],r['source']['code_sha256'],r['source']['image_sha256'],'queued')for i,r in enumerate(rows)]);db.commit();db.close();return dict(root=str(root),targets=len(rows))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=('create','run','case'));parser.add_argument('--work',type=Path,required=True);parser.add_argument('--source-pool',type=Path);parser.add_argument('--id');parser.add_argument('--workers',type=int,default=12);parser.add_argument('--timeout',type=int,default=120);a=parser.parse_args();assert a.work.resolve().is_relative_to(R/'conversion/source_resolved_geometry_admission_v1');assert 1<=a.workers<=12
 value=create(a.work,a.source_pool)if a.action=='create'else execute(a.work,a.workers,a.timeout)if a.action=='run'else case(a.id,a.work);print(json.dumps(value),flush=True)
