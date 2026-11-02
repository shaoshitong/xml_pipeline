"""Finite second pass: consume first-round terminal failures, repair once, exit.

First-round files are read atomically, never its active SQLite. New late failures
are admitted by the same frozen selector until upstream publishes completion.
"""
import argparse,concurrent.futures,datetime,fcntl,hashlib,json,multiprocessing,os,sqlite3,sys,time,uuid
from pathlib import Path
import fixed_batch_pipeline_v1 as base
from round2_case_v1 import route
R=base.R;W=base.W;FIRST=R/'release/fixed_batch_v1/initial_screen_20261031_1717'
raw=base.raw;atomic=base.atomic;sha=base.sha;now=base.now
def first_status():
 path=FIRST/'summary.json' if (FIRST/'summary.json').exists() else FIRST/'progress.json'
 s=json.loads(path.read_bytes());live=False
 try:
  o=json.loads((FIRST/'owner.json').read_bytes());f=Path('/proc',str(o['pid']),'stat').read_text().rsplit(') ',1)[1].split();live=f[0]!='Z' and int(f[19])==int(o['start_ticks'])
 except (OSError,KeyError,ValueError):pass
 return {**s,'actual_upstream_live':live}
def initialize(run):
 run=Path(run);run.mkdir(parents=True,exist_ok=False);d=sqlite3.connect(run/'status.sqlite')
 d.execute('pragma journal_mode=WAL');d.execute('pragma synchronous=FULL');base.create_schema(d)
 d.execute('alter table samples add column first_result text');d.execute('alter table samples add column initial_actions text')
 for k,v in {'total':0,'full_scope':False,'input_universe':131904,'policy':'bounded_generic_repair_round2_v1','model_calls':0,'finished':False,'upstream_finished':False,'created_at':now(),'first_run':str(FIRST)}.items():base.meta(d,k,v)
 d.commit();d.close()
def discover(run,d,only_ids=()):
 from round2_failure_inventory_v1 import classify
 upstream=first_status();path=FIRST/('failed.jsonl' if upstream.get('finished') else 'inprogress.failed.jsonl')
 order={}
 with (FIRST/'input_order.jsonl').open() as stream:
  for line in stream:
   s=json.loads(line);order[s['id']]=s
 if len(order)!=131904:raise RuntimeError('upstream_input_universe_changed')
 added=0;seen=0;groups={};failure_groups={};h=hashlib.sha256();wanted=set(only_ids)
 with path.open('rb') as stream:
  for line in stream:
   h.update(line);r=json.loads(line);identifier=r['id'];s=order[identifier];seen+=1
   if r.get('status')!='abandoned' or r.get('seq')!=s['seq']:raise RuntimeError('upstream_record_is_not_an_exact_terminal_failure')
   if r.get('case_cleanup_complete') is False:raise RuntimeError('upstream_failure_has_live_or_unverified_child_tree')
   if (r.get('source_code_sha256'),r.get('source_image_sha256'))!=(s['source_code_sha256'],s['source_image_sha256']):raise RuntimeError('upstream_failure_source_identity_mismatch')
   actions=route(r,s['format']);key=','.join(actions) or 'no_generic_fix';groups[key]=groups.get(key,0)+1
   classification='|'.join((s['format'],r.get('phase','unknown'),classify(r)));failure_groups[classification]=failure_groups.get(classification,0)+1
   if not actions or wanted and identifier not in wanted:continue
   source={'id':identifier,'format':s['format'],'category':s['category'],'code_sha256':s['source_code_sha256'],'image_sha256':s['source_image_sha256']}
   n=d.total_changes
   d.execute('insert or ignore into samples(seq,id,source,first_result,initial_actions) values(?,?,?,?,?)',(s['seq'],identifier,json.dumps(source),json.dumps(r,ensure_ascii=False),json.dumps(actions)))
   added+=d.total_changes-n
   if added and added%1000==0:d.commit()
 base.meta(d,'total',d.execute('select count(*) from samples').fetchone()[0]);base.meta(d,'upstream_finished',bool(upstream.get('finished')));d.commit()
 snapshot={'at':now(),'first_failure_records':seen,'first_failed_index_sha256':h.hexdigest(),'new_targets_added':added,'target_total':base.metadata(d)['total'],'action_route_counts':groups,'failure_groups':failure_groups,'upstream_finished':bool(upstream.get('finished')),'upstream_actual_live':upstream['actual_upstream_live'],'selector':'round2_case_v1.route','input_universe':131904,'model_calls':0}
 atomic(run/'target_discovery.json',raw(snapshot));write_targets(run,d);return snapshot
def write_targets(run,d):
 target=run/'targets.jsonl';tmp=target.with_suffix('.tmp');h=hashlib.sha256();count=0
 with tmp.open('wb') as f:
  for seq,identifier,source,actions in d.execute('select seq,id,source,initial_actions from samples order by seq'):
   line=raw({'seq':seq,'id':identifier,'source':json.loads(source),'actions':json.loads(actions)});f.write(line);h.update(line);count+=1
  f.flush();os.fsync(f.fileno())
 tmp.replace(target);atomic(run/'targets_status.json',raw({'at':now(),'unique_targets':count,'sha256':h.hexdigest(),'first_round_finished':base.metadata(d).get('upstream_finished'),'future_first_failures_admitted_until_upstream_finished':True}))
def implementation():
 p=base.pins()
 names=['round2_pipeline_v1.py','round2_case_v1.py','round2_html_repair_v1.py','round2_source_repair_v1.py','round2_canvas_repair_v1.py','round2_font_repair_v1.py','round2_font_canvas_registration_v1.py','round2_failure_inventory_v1.py']
 optional=[]
 for n in names+optional:
  path=W/'scripts'/n
  if n in names or path.exists():p[str(path)]=sha(path.read_bytes())
 handoff=W/'round2_source_repair_v1_handoff.json'
 if handoff.exists():
  for path,h in json.loads(handoff.read_bytes()).get('pins',{}).items():
   if sha(Path(path).read_bytes())!=h:raise RuntimeError('source_adapter_dependency_changed:'+path)
   p[path]=h
 for path in [W/'scripts/native_padding_proof.py',W/'scripts/portable_native_fonts.py',W/'scripts/native_source_font_profile_v4.py',W/'rendering_canvas_padding_proof/remote_render.py',W/'rendering_fonts/remote_render.py']:
  p[str(path)]=sha(path.read_bytes())
 import round2_font_canvas_registration_v1 as registration
 p.update(registration.configuration()['pins'])
 return p
def execute(task):
 from initial_conversion_process_v1 import run
 work=Path(task['work']);work.mkdir(parents=True,exist_ok=False);atomic(work/'request.json',raw(task))
 env={k:os.environ[k] for k in ['PATH','HOME','LANG','LC_ALL','TMPDIR','XDG_CACHE_HOME'] if k in os.environ};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=str(R/'env')+':'+str(W/'scripts'),PYTHONDONTWRITEBYTECODE='1')
 isolation=run([sys.executable,'-B',str(W/'scripts/round2_case_v1.py'),str(work/'request.json')],work,task['case_timeout_seconds'],env);atomic(work/'isolation.json',raw(isolation))
 result={'id':task['id'],'seq':task['seq'],'source_code_sha256':task['source']['code_sha256'],'source_image_sha256':task['source']['image_sha256'],'model_calls':0,'round':2,'evidence_directory':str(work.relative_to(R)),'case_cleanup_complete':isolation.get('cleanup_complete') is True}
 if not isolation.get('cleanup_complete'):return {**result,'status':'abandoned','reason':'round2_cleanup_failed','infrastructure_failure':True}
 if isolation.get('deadline_exceeded'):return {**result,'status':'abandoned','reason':'round2_whole_case_timeout','timeout_seconds':task['case_timeout_seconds']}
 if not isolation.get('ok') or not (work/'result.json').exists():return {**result,'status':'abandoned','reason':'round2_process_failed'}
 r=json.loads((work/'result.json').read_bytes())
 if any(r.get(k)!=result[k] for k in ['id','seq','source_code_sha256','source_image_sha256']):raise RuntimeError('round2_result_identity_mismatch')
 return {**r,**result}
def export(run,d,final=False):
 out=base.export(run,final);out.update(round=2,first_run=str(FIRST),input_universe=131904,upstream_finished=base.metadata(d).get('upstream_finished'),historical_qualified_baseline=2544,second_round_qualified_are_disjoint_from_first_round_qualified=True)
 atomic(run/('summary.json' if final else 'progress.json'),raw(out));return out
def merge_final(run):
 first=FIRST/'qualified.jsonl';second=run/'qualified.jsonl';seen=set();counts={};target=run/'merged_qualified.jsonl';temp=target.with_suffix('.tmp');h=hashlib.sha256()
 with temp.open('wb') as f:
  for label,path in [('first_round_qualified',first),('second_round_new_qualified',second)]:
   n=0
   for line in path.open('rb'):
    r=json.loads(line)
    if r['id'] in seen:raise RuntimeError('qualified_id_overlap_between_rounds')
    seen.add(r['id']);f.write(line);h.update(line);n+=1
   counts[label]=n
  f.flush();os.fsync(f.fileno())
 temp.replace(target);r={**counts,'combined_unique_qualified':len(seen),'sha256':h.hexdigest(),'file':str(target.relative_to(R)),'historical_old_qualified_baseline':2544,'at':now()};atomic(run/'incremental_summary.json',raw(r));return r
def run_batch(run,workers=12,timeout=900,preflight=False,selected_ids=()):
 run=Path(run).resolve();lock=(run/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 d=sqlite3.connect(run/'status.sqlite',timeout=30);d.execute('pragma synchronous=FULL')
 if d.execute('select count(*) from samples where status="running"').fetchone()[0]:d.close();lock.close();raise RuntimeError('explicit_previous_tree_cleanup_required_before_resume')
 p=implementation();owner={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]),'at':now(),'workers':workers,'case_timeout_seconds':timeout,'pins':p,'round':2,'watch':False,'finite_upstream_follow':not preflight}
 atomic(run/'owner.json',raw(owner))
 if not (run/'control.json').exists():atomic(run/'control.json',raw({'stop_dispatch':False}))
 active={};fatal=None;completed=0;last_discover=time.monotonic();last_export=0
 try:
  with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
   while True:
    base.ensure_pins(p);stopped=json.loads((run/'control.json').read_bytes()).get('stop_dispatch') is True
    if not stopped and not fatal:
     restriction=' and id in ('+','.join('?' for _ in selected_ids)+')' if selected_ids else ''
     for seq in [r[0] for r in d.execute('select seq from samples where status="queued"'+restriction+' order by seq limit ?',(*selected_ids,max(0,workers-len(active))))]:
      task=base.claim(d,seq);first,actions=d.execute('select first_result,initial_actions from samples where seq=?',(seq,)).fetchone();task.update(first_result=json.loads(first),initial_actions=json.loads(actions),pins=p,work=str(W/'round2_fixed_v1'/run.name/(str(seq).zfill(6)+'_'+task['id'])),case_timeout_seconds=timeout);active[pool.submit(execute,task)]=task
    if active:
     done,_=concurrent.futures.wait(active,timeout=5,return_when=concurrent.futures.FIRST_COMPLETED)
     for future in done:
      task=active.pop(future)
      try:r=future.result()
      except Exception as e:r={'id':task['id'],'seq':task['seq'],'source_code_sha256':task['source']['code_sha256'],'source_image_sha256':task['source']['image_sha256'],'status':'abandoned','reason':'round2_supervisor_failure','detail':repr(e),'infrastructure_failure':True,'model_calls':0}
      base.finish(d,task['seq'],r);completed+=1
      if r.get('infrastructure_failure'):fatal=r
      if completed%20==0:print(json.dumps({'at':now(),'completed_this_start':completed,'seq':task['seq'],'status':r['status']}),flush=True)
    restriction=' and id in ('+','.join('?' for _ in selected_ids)+')' if selected_ids else ''
    queued=d.execute('select count(*) from samples where status="queued"'+restriction,tuple(selected_ids)).fetchone()[0]
    if time.monotonic()-last_export>=60:export(run,d);last_export=time.monotonic()
    if fatal or stopped:
     if not active:break
    elif not active and not queued:
     if preflight:break
     upstream=first_status()
     if upstream.get('finished'):
      discovery=discover(run,d)
      if discovery['new_targets_added']==0:break
     elif not upstream['actual_upstream_live']:fatal={'reason':'upstream_stopped_before_completion','at':now()};break
     else:
      if time.monotonic()-last_discover>=120:discover(run,d);last_discover=time.monotonic()
      time.sleep(2)
    elif not preflight and time.monotonic()-last_discover>=300:discover(run,d);last_discover=time.monotonic()
  if fatal:atomic(run/'infrastructure_stop.json',raw(fatal))
  if not preflight and not fatal and not stopped and base.metadata(d).get('upstream_finished') and d.execute('select count(*) from samples where status not in ("qualified","abandoned")').fetchone()[0]==0:
   audit=base.final_asset_audit(d);atomic(run/'final_asset_audit.json',raw(audit));out=export(run,d,True);out['incremental_summary']=merge_final(run);base.meta(d,'finished',True);d.commit();atomic(run/'summary.json',raw(out));return out
  return export(run,d)
 finally:d.close();lock.close()
def cli():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['create','run','status']);p.add_argument('--run-id',required=True);p.add_argument('--workers',type=int,default=12);p.add_argument('--case-timeout',type=float,default=900);p.add_argument('--preflight',action='store_true');p.add_argument('--id',dest='ids',action='append',default=[]);a=p.parse_args()
 if not all(c.isalnum() or c in '-_' for c in a.run_id) or not 1<=a.workers<=16 or not 60<=a.case_timeout<=1800:p.error('invalid run ID/workers/timeout')
 run=R/'release/round2_fixed_v1'/a.run_id
 if a.action=='create':initialize(run);d=sqlite3.connect(run/'status.sqlite');out=discover(run,d,a.ids);d.close()
 elif a.action=='run':out=run_batch(run,a.workers,a.case_timeout,a.preflight,a.ids)
 else:out=base.status(run)
 print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':cli()
