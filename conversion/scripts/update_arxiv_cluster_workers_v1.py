"""Publish code then restart only verified idle task workers, preserve busy workers."""
from pathlib import Path
import concurrent.futures as cf,json,shlex,subprocess
settings={
'hkust1':('/data/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/anaconda3/bin/python'),
'hkust2':('/data/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/anaconda3/bin/python'),
'hkust3':('/backup/shaoshitong/img2code_20261029/conversion/cluster_workers/hkust3','/home/shaoshitong/anaconda3/bin/python'),
'hkust4':('/weka_3/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/miniconda3/bin/python'),
'hkust5':('/mnt/95a003e2-1274-441f-88bf-ca7f5b636032/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/miniconda3/bin/python')}
base=Path(__file__).resolve().parent

def update(node,root,python):
    names=['restart_arxiv_idle_cluster_worker_v1.py','arxiv_cluster_worker_v1.py','arxiv_oai_direct_pipeline_v1.py']
    subprocess.run(['scp','-q',*[str(base/n) for n in names],node+':'+root+'/conversion/scripts/'],check=True,capture_output=True)
    result=subprocess.run(['ssh','-o','BatchMode=yes',node,shlex.join([python,root+'/conversion/scripts/restart_arxiv_idle_cluster_worker_v1.py','--root',root])],capture_output=True)
    print(json.dumps(dict(node=node,returncode=result.returncode,output=result.stdout.decode(errors='replace')[-2500:],error=result.stderr.decode(errors='replace')[-1500:])),flush=True)
with cf.ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(lambda kv:update(kv[0],*kv[1]),settings.items()))
