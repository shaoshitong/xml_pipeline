"""Consume one reviewed finite capture manifest; no models or new capture retries."""
from pathlib import Path
import fcntl,hashlib,json,os,sqlite3,sys,time,uuid,signal
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import svg_program_terminal_outcomes_v1 as writer
import negative_terminal_receipt_reader_v3 as reader
SCOPE=W/'prototype/svg_failure_closure_v1/scans/ef29a9be462a4bf090779cbf0c9500f7';EXPECTED_MANIFEST='06e9abd6b9402cf4df8983caabb7d4f1af4b735ff2a8f4e68e75348ebe77f421';WRITER_SHA='f892477e6d7069c844e63f353e75798d1ced0b807e4a97f793b64a5857175c8a';READER_SHA='2cfe22ab23ba04dccb8940e6782582a1ace9c0e6e8c1d495adfdcdab165f486c';DRAIN=False

def atomic(path,value):
 p=Path(path);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(writer.canonical(value));tmp.replace(p)

def birth(pid):
 try:
  s=(Path('/proc')/str(pid)/'stat').read_text();return int(s[s.rindex(')')+2:].split()[19])
 except (OSError,ValueError,IndexError):return None

def stop(*_):
 global DRAIN;DRAIN=True

def main():
 global DRAIN
 signal.signal(signal.SIGUSR1,stop);lock=(W/'svg_program_terminal_finite_cohort_v1.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert writer.sha(Path(writer.__file__).read_bytes())==WRITER_SHA and writer.sha(Path(reader.__file__).read_bytes())==READER_SHA
 raw=(SCOPE/'manifest.json').read_bytes();assert writer.sha(raw)==EXPECTED_MANIFEST;manifest=json.loads(raw);ids=manifest['selected_ids'];assert len(ids)==len(set(ids))==2129 and manifest['limit']==0 and manifest['scope_inputs']==131904
 smoke=json.loads((W/'svg_negative_writer_real_private2.json').read_text());assert smoke['ok'] and smoke['canonical_outcome_updates']==0 and smoke['writer_sha256']==WRITER_SHA and smoke['reader_sha256']==READER_SHA and len(smoke['results'])==2
 review=W/'svg_current_program_negative_writer_final_review_v2.json';assert writer.sha(review.read_bytes())=='7f15577ee592634999a46552f0761ab3096e096473aac1f18629de69b7cef180'
 launch=json.loads((W/'svg_failure_closure_scan_v1_full_launch_receipt.json').read_text());capture_pid=launch['pid'];assert capture_pid==499425
 runid=uuid.uuid4().hex;run=W/'svg_program_terminal_outcomes_v1/runs'/runid;run.mkdir(parents=True,exist_ok=False);control=W/'svg_program_terminal_finite_cohort_v1_control.json';atomic(control,{'drain':False,'purpose':'Finite reviewed2129 source-failure cohort only; source/candidates/model history unchanged'})
 owner={'at':writer.now(),'pid':os.getpid(),'pid_start_ticks':birth(os.getpid()),'run_id':runid,'run':str(run),'scope':str(SCOPE),'selected':2129,'writer_sha256':WRITER_SHA,'reader_sha256':READER_SHA,'manifest_sha256':EXPECTED_MANIFEST,'publish':True,'model_calls':0,'accepted':False,'max_capture_wait_seconds':7200};atomic(W/'svg_program_terminal_finite_cohort_v1_owner.json',owner);atomic(run/'manifest.json',{**owner,'selected_ids':ids})
 config=writer.configuration(R);db=sqlite3.connect(W/'jobs.sqlite',timeout=0);results=[];counts={};started=time.monotonic();status='running';error=None
 try:
  for identifier in ids:
   if DRAIN or json.loads(control.read_text()).get('drain') is True:status='drained';break
   writer.collector.ensure_pins(config['closure'])
   folder=SCOPE/identifier;isolation=folder/'capture_isolation.json'
   while not isolation.exists():
    if DRAIN or json.loads(control.read_text()).get('drain') is True:status='drained';break
    if time.monotonic()-started>7200:status='capture_wait_budget_exhausted';break
    process=Path('/proc')/str(capture_pid)/'cmdline'
    if not process.exists():break
    actual=[x.decode() for x in process.read_bytes().split(bytes([0])) if x];assert actual==launch['command'],'Capture PID was reused; no restart'
    time.sleep(1)
   if status!='running':break
   if not isolation.exists():result={'id':identifier,'state':'pending_missing_completed_capture','applied':False,'accepted':False}
   else:
    isolated=json.loads(isolation.read_text());certificate=folder/'evidence/report.json'
    if not isolated.get('ok') or not isolated.get('cleanup_complete') or isolated.get('deadline_exceeded') or not certificate.exists():result={'id':identifier,'state':'pending_capture_resource_or_incomplete_subtree','applied':False,'accepted':False}
    else:
     plan=json.loads(certificate.read_bytes())
     if not plan.get('proposal'):result={'id':identifier,'state':'pending_source_or_available_repair','deferred_reasons':plan.get('deferred_reasons',[]),'applied':False,'accepted':False}
     else:result=writer.apply(db,plan,config,publish=True)
   if result.get('applied'):
    row=db.execute('select id,category,format,source_code_hash,source_image_hash,reason,record from processing_outcomes_v2 where id=? and status=?',(identifier,'abandoned')).fetchone();assert row is not None;verified=reader.validate_outcome(row,R);assert verified['receipt_verified'] and verified['decision']==result['decision'] and verified['commit_nonce']==result['commit_nonce'];result['strict_receipt_postcommit_verified']=True
   results.append(result);counts[result['state']]=counts.get(result['state'],0)+1
   with (run/'results.jsonl').open('ab') as stream:stream.write(writer.canonical(result).rstrip(b'\n')+b'\n');stream.flush();os.fsync(stream.fileno())
   atomic(W/'svg_program_terminal_finite_cohort_v1_runtime.json',{**owner,'at':writer.now(),'status':status,'completed':len(results),'counts':counts,'last_id':identifier,'goal_complete':False})
   print(json.dumps({'id':identifier,'state':result['state'],'completed':len(results),'selected':2129,'applied':result.get('applied',False)}),flush=True)
   if result['state']=='commit_outcome_unknown':status='unknown_commit_requires_nonce_audit';break
 except BaseException as exc:
  if db.in_transaction:db.rollback()
  error=repr(exc);status='failed_closed';raise
 finally:
  db.close();report={**owner,'at':writer.now(),'status':'complete' if len(results)==len(ids) and error is None else status,'completed':len(results),'counts':counts,'error':error,'records_file':str(run/'results.jsonl'),'all_selected_examined':len(results)==len(ids),'goal_complete':False};atomic(run/'summary.json',report);atomic(W/'svg_program_terminal_finite_cohort_v1_runtime.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
