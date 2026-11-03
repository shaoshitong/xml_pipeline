from pathlib import Path
import datetime,json,os,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/cluster_direct_v1/source_relay_v1';D.mkdir(exist_ok=True)
def birth(pid):
 try:
  s=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return s[19] if s[0]!='Z' else None
 except FileNotFoundError:return None
p=D/'launch.json'
if p.exists():
 old=json.loads(p.read_text())
 if birth(old['pid'])==old['birth_ticks']:print(json.dumps(dict(already_running=True,**old)));raise SystemExit()
with (D/'program.log').open('ab') as log:
 child=subprocess.Popen([sys.executable,'-u',str(R/'conversion/scripts/arxiv_lan_source_relay_v1.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
r=dict(pid=child.pid,birth_ticks=birth(child.pid),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='HKUST3_DIRECT source transport for campus-only HKUST4');p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
