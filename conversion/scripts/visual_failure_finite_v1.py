"""Finite four-spawn, read-only canonical visual-failure evidence collection.

Only this run's immutable manifest, per-ID state and retained evidence change.
No canonical writer, acceptance, queue claim, model API or watch loop exists.
The outer per-case process tree has one total 360-second deadline, including
collector admission/preflight and its own isolated QA subprocess.
"""
import argparse
import concurrent.futures as futures
import datetime
import fcntl
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import sys
import time
import uuid

ROOT=Path('/backup/shaoshitong/img2code_20261029')
BASE=Path('conversion/prototype/visual_failure_certificate_v1')
POLICY='finite_1730_readonly_visual_failure_evidence_four_spawn_v1'
COLLECTOR_SHA='6b57c6077c167ea731f1fbea4b9b6e0240c6264cdce95d8c386c7df644fdce4c'
GUARD_SHA='fd33e9d73933547d5a23939f091387c0da02ad40a2ff41545d16f122ef3c059a'
REPORT_SHA='28d0316c290ec551d6ffb9851c6dcb32f2d1a608af2b62c9845e89d963288d34'
SOURCE_MANIFEST_SHA='3c0d0190181def37d4180db9f8aa9e772e5117e9825d9e89069797dff863e06e'
EXPECTED={'python':1358,'svg':356,'tikz':6,'drawio':1,'html':9}
LOADED_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EVENTS=None


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def require(ok,why):
 if not ok:raise ValueError(why)
def birth(pid=None):
 try:
  pid=pid or os.getpid();v=Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split()
  return {'pid':pid,'start_ticks':int(v[19]),'ppid':int(v[1]),'state':v[0]}
 except (OSError,ValueError,IndexError):return None

def write(path,value,immutable=False):
 path=Path(path);raw=canonical(value);path.parent.mkdir(parents=True,exist_ok=True)
 if immutable:
  with path.open('xb') as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
 else:
  temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
  with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,path)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return {'file':str(path),'sha256':sha(raw),'bytes':len(raw)}

def disk(root):
 logical=allocated=count=0
 for parent,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=[d for d in dirs if not Path(parent,d).is_symlink()]
  for name in files:
   try:s=Path(parent,name).lstat();logical+=s.st_size;allocated+=getattr(s,'st_blocks',0)*512;count+=1
   except FileNotFoundError:pass
 usage=shutil.disk_usage(root)
 return {'logical_bytes_retained':logical,'allocated_bytes_retained':allocated,'files_retained':count,'filesystem_free_bytes':usage.free}

def manifest_items(source):
 require(source['full_scope']==131904,'wrong_full_scope')
 items=[x for x in source['items'] if x['logical_visual_route_class']=='current_visual_catalog_routes_terminal_or_inapplicable']
 counts={}
 for x in items:counts[x['source_format']]=counts.get(x['source_format'],0)+1
 require(counts==EXPECTED and len(items)==len({x['id'] for x in items})==1730,'fixed_1730_manifest_mismatch')
 return sorted(items,key=lambda x:({'python':0,'svg':1,'tikz':2,'drawio':3,'html':4}[x['source_format']],x['id']))

def init_worker(events):
 global EVENTS
 EVENTS=events;EVENTS.put({'kind':'worker_ready','at':now(),'worker':birth(),'command':Path('/proc/self/cmdline').read_bytes().decode(errors='replace').split('\0')})

def run_one(task):
 from initial_conversion_process_v1 import run as run_process,identity,same_birth
 root=Path(task['root']);run=Path(task['run']);identifier=task['id'];work=run/'cases'/identifier
 EVENTS.put({'kind':'case_started','at':now(),'id':identifier,'worker':birth()})
 try:
  manifest_raw=Path(task['manifest_file']).read_bytes();require(sha(manifest_raw)==task['manifest_sha256'],'immutable_manifest_changed');manifest=json.loads(manifest_raw)
  require(sha((run/'implementation/visual_failure_finite_v1.py').read_bytes())==manifest['implementation']['supervisor'],'immutable_supervisor_snapshot_changed')
  import initial_conversion_process_v1 as process_module
  require(sha(Path(process_module.__file__).read_bytes())==manifest['implementation']['process'],'immutable_process_helper_changed')
  execution=run_process([sys.executable,str(run/'implementation/visual_failure_finite_v1.py'),'--case',str(work/'request.json')],work/'outer_process',360,
                        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  result_file=work/'case_result.json'
  if execution.get('ok') and result_file.is_file():
   raw=result_file.read_bytes();result=json.loads(raw);result['case_result_sha256']=sha(raw)
  else:
   result={'id':identifier,'effective_proposal':False,'state':'pending_case_deadline_or_runtime','reason':'outer360s deadline/runtime; partial assets retained','report':None}
  live=[]
  for record in execution.get('tracked_processes',[]):
   if same_birth(record,identity(record['pid'])):live.append({k:record[k] for k in ('pid','start_ticks')})
  result.update(worker=birth(),outer_execution=execution,matching_live_owned_births=live,
                fatal=not execution.get('cleanup_complete',False) or bool(live) or (execution.get('returncode') not in (0,None) and not execution.get('deadline_exceeded')),retained=disk(work),finished_at=now())
  return result
 except BaseException as error:
  return {'id':identifier,'effective_proposal':False,'state':'pending_supervisor_runtime_error','reason':repr(error),'worker':birth(),'fatal':True,'finished_at':now(),'retained':disk(work)}

def effective_decision(report,clip):
 effective=report.get('proposal') is True and clip.get('complete') is True
 reason=report.get('reason') if report.get('proposal') is not True or clip.get('complete') is True else 'clip_dependency_closure_not_complete'
 return effective,reason

def case(request_path):
 request=json.loads(Path(request_path).read_bytes());root=Path(request['root']);run=Path(request['run']);identifier=request['id'];work=Path(request_path).parent
 require(request['deadline_seconds']==360 and request['policy']==POLICY,'unknown_case_policy')
 manifest_raw=Path(request['manifest_file']).read_bytes();require(sha(manifest_raw)==request['manifest_sha256'],'case_manifest_changed');manifest=json.loads(manifest_raw)
 require(identifier in {x['id'] for x in manifest['items']},'case_not_in_fixed_manifest')
 require(sha(Path(__file__).read_bytes())==manifest['implementation']['supervisor'],'supervisor_pin_changed')
 scripts=root/'conversion/scripts';sys.path.insert(0,str(scripts))
 for name,key in [('visual_failure_certificate_v1.py','collector'),('visual_failure_route_guard_v1.py','guard'),('visual_failure_clip_evidence_v1.py','clip_evidence'),('initial_conversion_process_v1.py','process')]:
  require(sha((scripts/name).read_bytes())==manifest['implementation'][key],'immutable_case_dependency_changed:'+name)
 import visual_failure_certificate_v1 as collector
 import visual_failure_clip_evidence_v1 as clip_evidence
 config=collector.configuration(root);db=sqlite3.connect('file:'+str(root/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=0);db.execute('pragma query_only=on')
 try:report=collector.prepare(db,identifier,config,timeout=360,work=work/'collector_attempt')
 finally:db.close()
 clip=clip_evidence.inspect(report,root,work/'collector_attempt')
 effective,reason=effective_decision(report,clip)
 result={'id':identifier,'effective_proposal':effective,'raw_collector_proposal':report.get('proposal') is True,
         'state':'fresh_visual_failure_evidence_proposal' if effective else 'pending_evidence_or_admission',
         'reason':reason,
         'deferred_reason':report.get('deferred_reason'),'report':str(work/'collector_attempt/report.json'),
         'report_file_sha256':sha((work/'collector_attempt/report.json').read_bytes()),'certificate_sha256':report.get('certificate_sha256'),
         'clip_dependency_evidence':clip,'inner_cleanup_complete':report.get('execution',{}).get('cleanup_complete'),
         'accepted':False,'terminal_publication_authorized':False,'model_api_calls':0,'canonical_mutations':0}
 write(work/'case_result.json',result,immutable=True);return 0

def apply_event(event,states,workers):
 if event['kind']=='worker_ready':workers[str(event['worker']['pid'])]=event;return
 if event['kind']=='case_started':
  item=states[event['id']]
  if item['state'] in ('scheduled','running'):
   item.update(state='running',started_at=event['at'],worker=event['worker'])

def collect(root,run_id):
 require(sha(Path(__file__).read_bytes())==LOADED_SHA,'supervisor_source_changed_after_import')
 root=Path(root).resolve();scripts=root/'conversion/scripts';sys.path.insert(0,str(scripts))
 require(sha((scripts/'visual_failure_certificate_v1.py').read_bytes())==COLLECTOR_SHA and sha((scripts/'visual_failure_route_guard_v1.py').read_bytes())==GUARD_SHA,'frozen_collector_or_guard_changed')
 import visual_failure_certificate_v1 as collector
 config=collector.configuration(root)
 source=root/'conversion/prototype/visual_only_scope_ro_v1/visual_only_current_manifest_v2.json';raw=source.read_bytes();require(sha(raw)==SOURCE_MANIFEST_SHA,'frozen4382_manifest_changed');items=manifest_items(json.loads(raw))
 run=root/BASE/'finite_runs'/run_id;run.mkdir(parents=True,exist_ok=False)
 lock=(root/BASE/'finite_supervisor_v1.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 implementation={'supervisor':LOADED_SHA,'collector':COLLECTOR_SHA,'guard':GUARD_SHA,
                 'clip_evidence':sha((scripts/'visual_failure_clip_evidence_v1.py').read_bytes()),
                 'process':sha((scripts/'initial_conversion_process_v1.py').read_bytes())}
 require(implementation['process']=='45d6097a9349c9ce0ff6b2de7384900445fe75aaa1ff8a3c5e48c743d216b736','frozen_process_helper_changed')
 manifest={'schema':POLICY,'created_at':now(),'full_scope':131904,'count':1730,'format_counts':EXPECTED,'items':items,
           'source_manifest_sha256':SOURCE_MANIFEST_SHA,'source_report_sha256':REPORT_SHA,'implementation':implementation,
           'workers':4,'case_total_deadline_seconds':360,'api_calls':0,'canonical_writer':False,'watch':False}
 entry=write(run/'manifest.json',manifest,immutable=True)
 impldir=run/'implementation';impldir.mkdir()
 for name in ('visual_failure_finite_v1.py','visual_failure_certificate_v1.py','visual_failure_route_guard_v1.py','visual_failure_clip_evidence_v1.py'):
  content=(scripts/name).read_bytes();p=impldir/name
  with p.open('xb') as stream:stream.write(content);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
 states={};tasks=[]
 for ordinal,item in enumerate(items):
  identifier=item['id'];work=run/'cases'/identifier;work.mkdir(parents=True)
  state={'id':identifier,'ordinal':ordinal,'source_format':item['source_format'],'state':'queued','attempts_this_run':0,'effective_proposal':False};states[identifier]=state;write(work/'state.json',state)
  task={'policy':POLICY,'root':str(root),'run':str(run),'id':identifier,'manifest_file':entry['file'],'manifest_sha256':entry['sha256'],'deadline_seconds':360}
  write(work/'request.json',task,immutable=True);tasks.append(task)
 owner={'policy':POLICY,'created_at':now(),'owner':birth(),'run':str(run),'run_id':run_id,'manifest':entry,'implementation':implementation,
        'workers':4,'case_total_deadline_seconds':360,'model_api_calls':0,'canonical_writer':False,'watch':False}
 write(run/'owner.json',owner,immutable=True)
 write(root/BASE/'finite_supervisor_v1_owner.json',owner)
 events=mp.get_context('spawn').Queue();workers={};done=0;cursor=0;drain=None;active={};started=time.monotonic();last_progress=0
 log=(run/'events.jsonl').open('a',buffering=1)
 def emit(event):log.write(json.dumps(event,ensure_ascii=False)+'\n');log.flush()
 def progress(final=False):
  counts={}
  for value in states.values():counts[value['state']]=counts.get(value['state'],0)+1
  value={'at':now(),'owner':birth(),'run_id':run_id,'manifest_sha256':entry['sha256'],'expected':1730,'covered_state_records':len(states),
         'counts':counts,'attempted_unique':sum(x['attempts_this_run'] for x in states.values()),'finished':done,
         'effective_proposals':sum(x.get('effective_proposal',False) for x in states.values()),'workers':workers,'active_ids':sorted(t['id'] for t in active.values()),
         'drain_reason':drain,'final':final,'seconds':round(time.monotonic()-started,3),'retained':disk(run),'canonical_mutations':0,'model_api_calls':0,'writer_called':False}
  write(run/'progress.json',value);print(json.dumps({k:value[k] for k in ('at','run_id','counts','finished','effective_proposals','drain_reason','final','retained')},ensure_ascii=False),flush=True)
 with futures.ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(events,)) as pool:
  progress()
  while cursor<len(tasks) or active:
   while not drain and cursor<len(tasks) and len(active)<4:
    task=tasks[cursor];cursor+=1;state=states[task['id']];require(state['attempts_this_run']==0,'same_run_second_attempt_forbidden');state.update(state='scheduled',attempts_this_run=1,scheduled_at=now());write(run/'cases'/task['id']/'state.json',state)
    try:active[pool.submit(run_one,task)]=task
    except BaseException as error:
     state.update(state='pending_not_started_pool_failure',reason=repr(error));write(run/'cases'/task['id']/'state.json',state);drain=repr(error);break
   while True:
    try:event=events.get_nowait();apply_event(event,states,workers);emit(event)
    except queue.Empty:break
   completed=[future for future in active if future.done()]
   for future in completed:
    task=active.pop(future)
    try:result=future.result()
    except BaseException as error:result={'id':task['id'],'effective_proposal':False,'state':'pending_worker_error','reason':repr(error),'fatal':True,'finished_at':now()}
    state=states[task['id']];state.update(result);done+=1;write(run/'cases'/task['id']/'state.json',state);emit({'kind':'case_finished','at':now(),'id':task['id'],'state':state['state'],'effective_proposal':state['effective_proposal'],'fatal':state.get('fatal',False)})
    if state.get('fatal'):drain='Owned subtree/worker failure; stop new cases: '+str(state.get('reason'))
   if time.monotonic()-last_progress>=20 or completed:
    progress();last_progress=time.monotonic()
   if drain and not active:break
   time.sleep(.1)
 if drain:
  for task in tasks[cursor:]:
   state=states[task['id']];state.update(state='pending_not_started_due_drain',reason=drain);write(run/'cases'/task['id']/'state.json',state)
 while True:
  try:event=events.get_nowait();apply_event(event,states,workers);emit(event)
  except queue.Empty:break
 progress(final=True);log.close();events.close();events.join_thread()
 write(run/'coverage_final.json',{'at':now(),'manifest_sha256':entry['sha256'],'records':list(states.values()),'unique_ids':len(states),'all_attempts_at_most_one':all(x['attempts_this_run']<=1 for x in states.values()),'canonical_mutations':0,'model_api_calls':0},immutable=True)
 return 2 if drain else 0

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--run-id');p.add_argument('--case',type=Path);a=p.parse_args(argv)
 if a.case:return case(a.case)
 require(a.run_id and len(a.run_id)==32 and all(c in '0123456789abcdef' for c in a.run_id),'explicit_fresh_run_uuid_required')
 return collect(a.root,a.run_id)

if __name__=='__main__':sys.exit(main())
