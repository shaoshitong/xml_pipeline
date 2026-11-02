"""Single-worker supervisor for the frozen finite execution candidate producer.

The validated producer accepts only positive finite limits. This independent
supervisor invokes it serially, one item by default, and waits when drained.
SIGUSR1/SIGTERM/SIGINT or control JSON {"drain":true} stop after the active
item; the supervisor never kills its child, another worker, or a model call.
"""
import argparse,fcntl,json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
import tikz_execution_candidate_batch_v1 as batch

DRAIN=False


def request_drain(*_):
 global DRAIN
 DRAIN=True


def child_command(limit,publish):
 if limit<1 or limit>1000:raise ValueError('Finite child limit must be 1..1000')
 return [sys.executable,'-u',str(batch.W/'scripts/tikz_execution_candidate_batch_v1.py'),'--workers','1','--limit',str(limit)]+(['--publish'] if publish else [])


def event(**values):print(json.dumps({'at':batch.now(),**values}),flush=True)


def active_others():
 found=[]
 for path in Path('/proc').iterdir():
  if not path.name.isdigit() or int(path.name)==os.getpid():continue
  try:args=[p.decode(errors='replace') for p in (path/'cmdline').read_bytes().split(b'\0') if p]
  except OSError:continue
  if any(Path(p).name in ('tikz_execution_candidate_batch_v1.py','tikz_execution_candidate_watch_v1.py') for p in args):found.append({'pid':int(path.name),'args':args})
 return found


def main(args):
 if args.workers!=1 or not 1<=args.batch_size<=1000 or args.limit<0 or not 1<=args.idle_seconds<=300:raise ValueError('One worker, finite child batch 1..1000 and nonnegative total limit required')
 for sig in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):signal.signal(sig,request_drain)
 lock=(batch.W/'tikz_execution_candidate_watch_v1.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 other=active_others()
 if other:raise RuntimeError('Existing candidate producer/supervisor must finish first: '+json.dumps(other))
 policy,files=batch.implementation();batch.require_bounded_smoke(policy,args.publish,1,args.batch_size)
 owner={'pid':os.getpid(),'started_at':batch.now(),'watch_id':uuid.uuid4().hex,'policy':policy,'implementation':files,'workers':1,'batch_size':args.batch_size,'limit':args.limit,'publish':args.publish,'accepted':0};batch.atomic(batch.W/'tikz_execution_candidate_watch_v1_owner.json',(json.dumps(owner,indent=2)+'\n').encode());counts={};processed=0;batches=0;idle=False
 event(stage='watch_started',**{k:v for k,v in owner.items() if k!='implementation'})
 while not DRAIN and (not args.limit or processed<args.limit):
  control=batch.W/'tikz_execution_candidate_watch_v1_control.json'
  if control.exists() and json.loads(control.read_text()).get('drain'):break
  batch.ensure_implementation(policy,files);batch.require_bounded_smoke(policy,args.publish,1,args.batch_size)
  limit=min(args.batch_size,args.limit-processed) if args.limit else args.batch_size;command=child_command(limit,args.publish);before=None
  summary_file=batch.W/'tikz_execution_candidate_v1_summary.json'
  if summary_file.exists():before=json.loads(summary_file.read_text()).get('run_id')
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL);runtime={**owner,'at':batch.now(),'stage':'processing','child_pid':child.pid,'child_command':command,'processed':processed,'batches':batches,'counts':counts,'accepted':0};batch.atomic(batch.W/'tikz_execution_candidate_watch_v1_runtime.json',(json.dumps(runtime,indent=2)+'\n').encode())
  code=child.wait()
  if code:raise RuntimeError('Finite frozen candidate producer failed; supervisor stops without retrying a process loop: '+str(code))
  summary=json.loads(summary_file.read_text())
  if summary.get('policy')!=policy or summary.get('run_id')==before or summary.get('accepted')!=0:raise RuntimeError('Finite producer summary is stale or has unexpected policy/acceptance')
  handled=sum(w['processed'] for w in summary['workers']);processed+=handled;batches+=1
  for worker in summary['workers']:
   for state,n in worker['counts'].items():counts[state]=counts.get(state,0)+n
  stage='processing' if handled else 'idle';runtime={**owner,'at':batch.now(),'stage':stage,'child_pid':None,'processed':processed,'batches':batches,'counts':counts,'last_child_summary':summary,'accepted':0};batch.atomic(batch.W/'tikz_execution_candidate_watch_v1_runtime.json',(json.dumps(runtime,indent=2)+'\n').encode())
  if handled:event(stage='finite_batch_finished',processed_this_batch=handled,processed=processed,batches=batches,counts=counts,accepted=0)
  elif not idle:event(stage='waiting_for_new_idle_source_revisions',processed=processed,counts=counts,accepted=0)
  idle=not handled
  if not handled:
   deadline=time.monotonic()+args.idle_seconds
   while not DRAIN and time.monotonic()<deadline:time.sleep(max(0,min(1,deadline-time.monotonic())))
 result={**owner,'at':batch.now(),'stage':'drained','processed':processed,'batches':batches,'counts':counts,'accepted':0};batch.atomic(batch.W/'tikz_execution_candidate_watch_v1_runtime.json',(json.dumps(result,indent=2)+'\n').encode());event(stage='watch_drained',processed=processed,batches=batches,counts=counts,accepted=0)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=1);parser.add_argument('--limit',type=int,default=0);parser.add_argument('--batch-size',type=int,default=1);parser.add_argument('--idle-seconds',type=int,default=30);parser.add_argument('--publish',action='store_true');args=parser.parse_args()
 try:main(args)
 except Exception as error:
  event(stage='watch_stopped_error',error=repr(error),accepted=0);raise
