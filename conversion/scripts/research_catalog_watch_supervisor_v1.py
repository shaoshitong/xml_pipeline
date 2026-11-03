"""Supervise the unchanged v5 catalogue publisher; retry only its lock-busy exit."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,signal,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/research_pairs_catalog';DELEGATE=R/'conversion/scripts/research_catalog_refresh_v5.py'
STOP=False
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def birth(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split()[19])
 except FileNotFoundError:return None
def put(p,v):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def main():
 global STOP
 p=argparse.ArgumentParser();p.add_argument('--run-root',type=Path,required=True);p.add_argument('--interval',type=float,default=60);p.add_argument('--retry-delay',type=float,default=3);a=p.parse_args();root=a.run_root.resolve();assert root.is_relative_to(R/'conversion/research_catalog_watch_supervisor_v1')and a.interval>0 and 0<a.retry_delay<=30;root.mkdir(parents=True,exist_ok=True)
 def stop(signum,frame):
  global STOP
  STOP=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 with(C/'watch_supervisor_v1.lock').open('a+')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);put(root/'owner.json',dict(pid=os.getpid(),birth=birth(os.getpid()),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),delegate_sha256=hashlib.sha256(DELEGATE.read_bytes()).hexdigest()));attempt=0
  while not STOP:
   attempt+=1;out=root/('attempt_'+str(attempt).zfill(6)+'.stdout.log');err=root/('attempt_'+str(attempt).zfill(6)+'.stderr.log');argv=[sys.executable,'-u',str(DELEGATE),'--watch','--interval',str(a.interval)]
   with out.open('ab')as stdout,err.open('ab')as stderr:child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
   launch=dict(pid=child.pid,birth_ticks=birth(child.pid),command=argv,source_sha256=hashlib.sha256(DELEGATE.read_bytes()).hexdigest(),supervisor_pid=os.getpid(),supervisor_birth=birth(os.getpid()),supervisor_root=str(root),attempt=attempt,stdout=str(out),stderr=str(err),startup_success_unproven=True)
   put(root/('attempt_'+str(attempt).zfill(6)+'.launch.json'),launch);put(C/'latest_launch_v5.json',launch);put(root/'state.json',dict(at_utc=now(),stage='delegate_starting',**launch));last_status=None;termination_deadline=None
   while child.poll()is None:
    if STOP and termination_deadline is None:child.terminate();termination_deadline=time.monotonic()+90
    if termination_deadline is not None and time.monotonic()>termination_deadline:child.kill()
    status=C/'watch_status.json'
    if status.exists():
     v=json.loads(status.read_text())
     if v.get('pid')==child.pid and v.get('status')=='running'and v.get('at_utc')!=last_status:
      last_status=v['at_utc'];put(root/'state.json',dict(at_utc=now(),stage='watching',delegate=launch,last_successful_refresh=v))
    time.sleep(.5)
   rc=child.returncode;put(root/('attempt_'+str(attempt).zfill(6)+'.exit.json'),dict(at_utc=now(),returncode=rc,explicit_supervisor_stop=STOP))
   if STOP or rc!=75:
    put(root/'state.json',dict(at_utc=now(),stage='stopped'if STOP or rc==0 else'failed',returncode=rc,explicit_supervisor_stop=STOP));return rc
   put(root/'state.json',dict(at_utc=now(),stage='retrying_publisher_lock_busy',attempt=attempt,returncode=rc,retry_seconds=a.retry_delay))
   deadline=time.monotonic()+a.retry_delay
   while not STOP and time.monotonic()<deadline:time.sleep(.25)
  return 0
if __name__=='__main__':raise SystemExit(main())
