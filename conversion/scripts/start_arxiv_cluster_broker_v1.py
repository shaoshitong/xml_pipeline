from pathlib import Path
import datetime,json,os,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'cluster_direct_v1';S=R/'conversion/scripts'
sys.path.insert(0,str(S));import arxiv_cluster_broker_v1 as broker
broker.init()
def birth(pid):
    try:
        v=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return v[19] if v[0]!='Z' else None
    except FileNotFoundError:return None
path=D/'broker_launch.json'
old=json.loads(path.read_text()) if path.exists() else None
if old and birth(old['pid'])==old['birth_ticks']:
    print(json.dumps(dict(already_running=True,**old)));sys.exit()
with (D/'broker.log').open('ab') as log:
    p=subprocess.Popen([sys.executable,'-u',str(S/'arxiv_cluster_broker_v1.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
r=dict(pid=p.pid,birth_ticks=birth(p.pid),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());path.write_text(json.dumps(r,indent=2));print(json.dumps(r))
