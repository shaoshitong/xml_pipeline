"""Read-only canonical claim diagnostics; a stale PID is not an active owner.

Never clears or changes the authoritative row. Existing live/unknown owners
are per-target deferrals. Only absent, zombie or birth-after-claim processes
prove the historical claim is stale; the full raw job snapshot remains exact.
"""
from pathlib import Path
import datetime,hashlib,json,os
from initial_conversion_process_v1 import identity
W=Path('/backup/shaoshitong/img2code_20261029/conversion')
POLICY='canonical_claim_actual_proc_birth_entrypoint_readonly_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def diagnose(job,proc=Path('/proc'),observe=identity):
 pid=job.get('worker_pid');report={'policy':POLICY,'claimed_worker_pid':pid,'canonical_state':job.get('state'),'canonical_updated_at':job.get('updated_at'),'canonical_fields_changed':False}
 def finish(status,allowed,reason,**extra):return {**report,'status':status,'conversion_allowed':allowed,'defer_only_this_sample':not allowed,'reason':reason,**extra}
 if pid is None:return finish('unclaimed',True,'canonical_worker_pid_is_null')
 if isinstance(pid,bool)or not isinstance(pid,int)or pid<=0:return finish('uncertain',False,'malformed_nonnull_canonical_worker_pid')
 root=Path(proc)/str(pid)
 current=observe(pid)
 if current is None:
  if not root.exists():return finish('stale_dead',True,'claimed_proc_is_absent')
  return finish('uncertain',False,'claimed_proc_exists_but_birth_unreadable')
 if current.get('state')in ('Z','X'):return finish('stale_dead',True,'claimed_process_is_terminal',actual_process=current)
 entry={}
 try:
  argv=(root/'cmdline').read_bytes().split(b'\0');entry['argv_sha256']=sha(b'\0'.join(argv));entry['executable_name']=Path(os.fsdecode(argv[0])).name if argv and argv[0]else None
  scripts=[]
  for token in argv[1:]:
   if not token or token.startswith(b'-'):continue
   q=Path(os.fsdecode(token))
   if q.is_absolute()and q.suffix in ('.py','.js','.sh'):
    q=q.resolve()
    if q.is_relative_to(W.resolve()):scripts.append({'file':str(q),'sha256':sha(q.read_bytes())})
  entry['owned_entrypoint_scripts']=scripts
 except(OSError,ValueError):entry['entrypoint_observation']='unreadable'
 after=observe(pid)
 if after is None:
  if not root.exists():return finish('stale_dead',True,'claimed_proc_disappeared_during_observation',first_process=current,entrypoint=entry)
  return finish('uncertain',False,'claimed_proc_birth_became_unreadable',first_process=current,entrypoint=entry)
 if after.get('start_ticks')!=current.get('start_ticks'):return finish('uncertain',False,'pid_birth_changed_during_observation',first_process=current,last_process=after,entrypoint=entry)
 actual={**after,'entrypoint':entry}
 try:
  boot=next(int(line.split()[1])for line in(Path(proc)/'stat').read_text().splitlines()if line.startswith('btime '))
  actual['start_utc_seconds']=boot+after['start_ticks']/os.sysconf('SC_CLK_TCK')
  update=datetime.datetime.fromisoformat(job['updated_at'].replace('Z','+00:00'))
  if update.tzinfo is None:raise ValueError('claim_timestamp_has_no_timezone')
  actual['claim_updated_utc_seconds']=update.timestamp()
  # btime has 1-second resolution; require >1s to prove numerical PID reuse.
  if actual['start_utc_seconds']>update.timestamp()+1:
   return finish('stale_pid_reused',True,'actual_process_born_after_historical_claim',actual_process=actual)
 except(OSError,ValueError,TypeError,KeyError,StopIteration):actual['claim_birth_comparison']='unavailable'
 return finish('live_or_uncertain_owner',False,'nonnull_claim_has_actual_live_process_without_proven_reuse',actual_process=actual)
def require_available(job):
 report=diagnose(job)
 if not report['conversion_allowed']:raise ValueError('deferred_canonical_live_or_uncertain_worker_claim')
 return report
