from pathlib import Path
import json,os,signal,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'oai_direct_pipeline_v1';S=R/'conversion/scripts'
def birth(pid):
 try:
  r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
 except FileNotFoundError:return None
r=json.loads((D/'launch.json').read_text())
if birth(r['pid'])==r['birth_ticks']:
 assert b'arxiv_oai_direct_pipeline_v1.py' in Path('/proc',str(r['pid']),'cmdline').read_bytes()
 env=Path('/proc',str(r['pid']),'environ').read_bytes();assert b'ARXIV_CLUSTER_CONFIG=' in env
 os.kill(r['pid'],signal.SIGTERM)
 while birth(r['pid'])==r['birth_ticks']:time.sleep(2)
subprocess.run([sys.executable,str(S/'launch_arxiv_oai_direct_v1.py')],env=dict(os.environ,ARXIV_CLUSTER_CONFIG=str(R/'conversion/private_arxiv_cluster_v1/broker.json')),check=True)
