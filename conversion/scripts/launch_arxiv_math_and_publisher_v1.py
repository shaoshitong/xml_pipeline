from pathlib import Path
import datetime,json,os,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts'
def birth(pid):
 try:
  r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
 except FileNotFoundError:return None
for name,script,args in [('math_source_replay_v1','arxiv_math_source_repair_v1.py',[]),('goal500_progress_v1','arxiv_goal500_progress_v1.py',['--watch'])]:
 D=P/name;D.mkdir(exist_ok=True);path=D/'launch.json';old=json.loads(path.read_text()) if path.exists() else None
 if old and birth(old['pid'])==old['birth_ticks']:
  print(json.dumps(dict(already_running=True,**old)));continue
 with (D/'program.log').open('ab') as f:
  command=[sys.executable,'-u',str(S/script),*args]
  p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
 record=dict(pid=p.pid,birth_ticks=birth(p.pid),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command)
 path.write_text(json.dumps(record,indent=2));print(json.dumps(record))
