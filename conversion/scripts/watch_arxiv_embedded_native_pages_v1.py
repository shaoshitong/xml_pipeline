"""Deterministic remote compiler watch; no model calls or repeated failed cases."""
from pathlib import Path
import datetime,fcntl,hashlib,json,os,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion/dpsk_svg_png_compiler_20261103';JOB=W/'results/embedded_XML_page_compiler_v1';D=R/'clean/arxiv_research_figures_v1/embedded_native_page_watch_v1';ENTRY=W/'scripts/run_embedded_xml_page_compiler_v1.py'
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(v):
 p=D/'status.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
def main():
 D.mkdir(exist_ok=True);owner=(D/'watch.lock').open('a');fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB);launch=dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],at_utc=now(),CPU_host='HKUST3');(D/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
 while True:
  lock=(JOB/'program.lock').open('a')
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:
   lock.close();put(dict(at_utc=now(),state='existing_compiler_owns_queue',no_duplicate_batch_started=True,CPU_host='HKUST3'));time.sleep(60);continue
  lock.close();cmd=[sys.executable,str(ENTRY),'batch','--workers','8','--replay-workers','2']
  with (D/'batch.log').open('ab') as log:
   p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);state=dict(at_utc=now(),state='processing_cumulative_inventory',batch_pid=p.pid,batch_birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(')',1)[1].split()[19],CPU_host='HKUST3',model_calls=0,new_PDF_import_calls=0);put(state);exitcode=p.wait()
  if exitcode:
   tail=(D/'batch.log').read_text(errors='replace')[-2500:]
   if 'BlockingIOError' in tail:put(dict(at_utc=now(),state='compiler_lock_race_waiting',exit_code=exitcode));time.sleep(60);continue
   put(dict(at_utc=now(),state='compiler_error_requires_repair',exit_code=exitcode,log=str(D/'batch.log'),CPU_host='HKUST3'));raise SystemExit(exitcode)
  snapshot=json.loads((JOB/'status.json').read_text());put(dict(at_utc=now(),state='pass_completed_waiting_new_sources',exit_code=0,verified_page_candidates=snapshot['verified_page_candidates'],page_states=snapshot['page_states'],CPU_host='HKUST3',model_calls=0,new_PDF_import_calls=0));time.sleep(120)
if __name__=='__main__':main()
