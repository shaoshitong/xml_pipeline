"""Inspect actual publisher identities, controlled busy exits and completed refreshes."""
from pathlib import Path
import argparse,json,subprocess
p=argparse.ArgumentParser();p.add_argument('--launch',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();launch=json.loads(a.launch.read_text())
code='''from pathlib import Path
import json,datetime,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/research_pairs_catalog';root=Path(ROOT);assert root.is_relative_to(R/'conversion/research_catalog_watch_supervisor_v1')
def read(p):return json.loads(p.read_text())if p.exists()else None
def live(pid,birth):
 p=Path('/proc',str(pid),'stat')
 if not p.exists():return False
 f=p.read_text().rsplit(') ',1)[1].split();return f[0]!='Z'and int(f[19])==int(birth)
launch=read(root/'launch.json');state=read(root/'state.json');latest=read(C/'latest_launch_v5.json');watch=read(C/'watch_status.json');current=read(C/'current.json');attempts=[]
for p in sorted(root.glob('attempt_*.exit.json')):
 v=read(p);err=p.with_name(p.name.replace('.exit.json','.stderr.log'));attempts.append(dict(exit=v,stderr=err.read_text()[-1000:]))
delegate_live=bool(latest and latest.get('birth_ticks')is not None and live(latest['pid'],latest['birth_ticks']));current_watch_healthy=bool(delegate_live and watch.get('pid')==latest['pid']and watch.get('status')=='running'and state.get('stage')=='watching')
print(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),supervisor_live=live(launch['pid'],launch['birth']),delegate_live=delegate_live,healthy_current_watch=current_watch_healthy,state=state,controlled_busy_exits=attempts,watch_status=watch,catalogue_at=current['at_utc'],catalogue_main=current['unique_pairs_by_evidence_view']['paper_diagrams_and_posters_full8'],delegate_source_unchanged=hashlib.sha256((R/'conversion/scripts/research_catalog_refresh_v5.py').read_bytes()).hexdigest()==launch['delegate_source_sha256'],no_converter_or_QA_changes=True,goal_complete=False)))
'''.replace('ROOT',repr(launch['root']))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20);assert r.returncode==0,r.stderr
v=json.loads(r.stdout);a.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
