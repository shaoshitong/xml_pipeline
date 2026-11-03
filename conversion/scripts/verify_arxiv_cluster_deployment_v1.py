"""Mac read-only deployment/source verification; no downloads or state restarts."""
from pathlib import Path
import concurrent.futures as cf,datetime,hashlib,json,shlex,subprocess
here=Path(__file__).resolve()
repo=here.parents[2] if here.parent.name=='scripts' and here.parent.parent.name=='conversion' else here.parents[1]/'xml_pipeline'
R='/backup/shaoshitong/img2code_20261029'
settings={
'hkust1':('/data/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/anaconda3/bin/python'),
'hkust2':('/data/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/anaconda3/bin/python'),
'hkust3':(R+'/conversion/cluster_workers/hkust3','/home/shaoshitong/anaconda3/bin/python'),
'hkust4':('/weka_3/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/miniconda3/bin/python'),
'hkust5':('/mnt/95a003e2-1274-441f-88bf-ca7f5b636032/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/miniconda3/bin/python')}
entry='conversion/scripts/arxiv_cluster_worker_v1.py';expected=hashlib.sha256((repo/entry).read_bytes()).hexdigest()
relay_entry='conversion/scripts/run_arxiv_cluster_worker_with_lan_source_v1.py';relay_hash=hashlib.sha256((repo/relay_entry).read_bytes()).hexdigest()
oldhelper=subprocess.check_output(['git','-C',str(repo),'show','4583f49:conversion/scripts/arxiv_oai_direct_pipeline_v1.py']);oldhash=hashlib.sha256(oldhelper).hexdigest()
def remote(node,python,code):
 a=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',node,shlex.join([python,'-'])],input=code.encode(),capture_output=True,timeout=90)
 if a.returncode:raise RuntimeError(node+':'+a.stderr.decode(errors='replace')[-700:])
 return json.loads(a.stdout)
def worker(item):
 node,(root,python)=item
 code="""from pathlib import Path
import datetime,hashlib,json
root=Path(ROOT);r=json.loads((root/'launch.json').read_text());p=Path('/proc',str(r['pid']));stat=(p/'stat').read_text().rsplit(')',1)[1].split();assert stat[0]!='Z' and stat[19]==r['birth_ticks'];config=json.loads((root/'private_config.json').read_text());mode=config.get('source_transport','DIRECT');entrypoint='run_arxiv_cluster_worker_with_lan_source_v1.py' if mode=='HKUST3_DIRECT_LAN_RELAY' else 'arxiv_cluster_worker_v1.py';assert str(root/'conversion/scripts'/entrypoint).encode() in (p/'cmdline').read_bytes();assert mode!='HKUST3_DIRECT_LAN_RELAY' or (NODE=='hkust4' and hashlib.sha256((root/'conversion/scripts'/entrypoint).read_bytes()).hexdigest()==EXPECTED_RELAY)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entry=sha(root/'conversion/scripts/arxiv_cluster_worker_v1.py');helper=sha(root/'conversion/scripts/arxiv_oai_direct_pipeline_v1.py');assert entry==EXPECTED_ENTRY and helper==EXPECTED_HELPER
log=(root/'program.log').read_text(errors='replace');marker='"pid": '+str(r['pid']);start=log.rfind(marker);tail=log[start:] if start>=0 else log[-100000:];assert 'Exception in thread native-' not in tail
print(json.dumps(dict(node=NODE,pid=r['pid'],birth_ticks=stat[19],process_alive_verified=True,task_threads=len(list((p/'task').iterdir())),worker_entry_sha256=entry,direct_worker_helper_sha256=helper,source_transport=mode,entrypoint=entrypoint,worker_helper_Git_revision='4583f49',status=json.loads((root/'status.json').read_text()))))
"""
 code='ROOT='+repr(root)+'\nNODE='+repr(node)+'\nEXPECTED_ENTRY='+repr(expected)+'\nEXPECTED_HELPER='+repr(oldhash)+'\nEXPECTED_RELAY='+repr(relay_hash)+'\n'+code
 return remote(node,python,code)
with cf.ThreadPoolExecutor(max_workers=5) as pool:nodes=list(pool.map(worker,settings.items()))
names=subprocess.check_output(['git','-C',str(repo),'diff','--name-only','df52a9f','HEAD','--','conversion/scripts'],text=True).splitlines()
expected_sources={name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in names if (repo/name).is_file()}
code="""from pathlib import Path
import datetime,hashlib,json
R=Path(ROOT);rows=[]
for name,expected in EXPECTED.items():
 p=R/name;actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==expected,name
 rows.append(dict(file=name,sha256=actual,bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns))
P=R/'clean/arxiv_research_figures_v1'
print(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=rows,goal=json.loads((P/'goal500_progress_v1/current.json').read_text()),cluster=json.loads((P/'cluster_direct_v1/progress.json').read_text()),math=json.loads((P/'math_source_replay_v1/summary.json').read_text()),metadata=json.loads((P/'oai_direct_pipeline_v1/latest_metadata.json').read_text()))))
"""
code='ROOT='+repr(R)+'\nEXPECTED='+repr(expected_sources)+'\n'+code
central=remote('hkust3','/home/shaoshitong/anaconda3/bin/python',code)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),nodes=nodes,central=central,baseline_rows=3759,goal_complete=False)
out=Path.cwd()/'outputs/cluster_deployment_verified_latest.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
p=repo/'REMOTE_SOURCE_MANIFEST.json';manifest=json.loads(p.read_text());rows={r['file']:r for r in manifest['files']};rows.update({r['file']:r for r in central['files']});manifest['files']=[rows[k] for k in sorted(rows)];manifest['at_utc']=central['at_utc'];p.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(nodes_verified=[n['node'] for n in nodes],source_files_verified=len(central['files']),accepted_new=central['goal']['accepted_new_pairs']['rows'],unified_rows=central['goal']['unified_pairs']['rows'],actual_cluster_bytes=central['cluster']['source_bytes_actually_received'],cluster_jobs=central['cluster']['jobs'],math_verified=central['math']['source_replay_verified'],output=str(out))))
