from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts'
def birth(pid):
 try:
  r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
 except FileNotFoundError:return None
D=P/'direct_author_XML_source_replay_v1';D.mkdir(exist_ok=True);path=D/'launch.json';old=json.loads(path.read_text()) if path.exists() else None
if not(old and birth(old['pid'])==old['birth_ticks']):
 with (D/'program.log').open('ab') as f:
  command=[sys.executable,'-u',str(S/'arxiv_direct_author_XML_replay_v1.py'),'--watch']
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
 r=dict(pid=child.pid,birth_ticks=birth(child.pid),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command)
 path.write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
else:print(json.dumps(dict(already_running=True,**old)),flush=True)
# Reload only the report publisher; collection/conversion jobs keep running.
publisher=P/'goal500_progress_v1/launch.json';r=json.loads(publisher.read_text())
if birth(r['pid'])==r['birth_ticks']:
 assert b'arxiv_goal500_progress_v1.py' in Path('/proc',str(r['pid']),'cmdline').read_bytes();os.kill(r['pid'],signal.SIGTERM)
 deadline=time.monotonic()+45
 while birth(r['pid'])==r['birth_ticks'] and time.monotonic()<deadline:time.sleep(.2)
 assert birth(r['pid'])!=r['birth_ticks'],'publisher has not drained; source validation remains running'
subprocess.run([sys.executable,str(S/'launch_arxiv_math_and_publisher_v1.py')],check=True)
