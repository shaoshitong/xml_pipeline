"""Mac deploy control only: code/config SSH, runtime and payloads stay remote."""
from pathlib import Path
import concurrent.futures as cf,json,shlex,subprocess
S='/backup/shaoshitong/img2code_20261029/conversion/scripts'
config=subprocess.check_output(['ssh','-o','BatchMode=yes','hkust3','cat /backup/shaoshitong/img2code_20261029/conversion/private_arxiv_cluster_v1/broker.json'])
settings={
'hkust1':('/data/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/anaconda3/bin/python'),
'hkust2':('/data/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/anaconda3/bin/python'),
'hkust3':('/backup/shaoshitong/img2code_20261029/conversion/cluster_workers/hkust3','/home/shaoshitong/anaconda3/bin/python'),
'hkust4':('/weka_3/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/miniconda3/bin/python'),
'hkust5':('/mnt/95a003e2-1274-441f-88bf-ca7f5b636032/shaoshitong/arxiv_cluster_direct_v1','/home/shaoshitong/miniconda3/bin/python')}
base=Path(__file__).resolve().parent

def deploy(node,root,python):
    command=shlex.join(['mkdir','-p',root])
    subprocess.run(['ssh','-o','BatchMode=yes',node,command],check=True,capture_output=True)
    subprocess.run(['scp','-q',str(base/'bootstrap_arxiv_cluster_node_v1.py'),node+':'+root+'/bootstrap.py'],check=True,capture_output=True)
    result=subprocess.run(['ssh','-o','BatchMode=yes',node,shlex.join([python,root+'/bootstrap.py','--root',root,'--node',node])],input=config,capture_output=True)
    # Tokens are never logged. Installer output contains package/runtime info.
    print(json.dumps(dict(node=node,returncode=result.returncode,output=result.stdout.decode(errors='replace')[-3500:],error=result.stderr.decode(errors='replace')[-2000:])),flush=True)
    return result.returncode
with cf.ThreadPoolExecutor(max_workers=5) as pool:
    results=list(pool.map(lambda kv:deploy(kv[0],*kv[1]),settings.items()))
raise SystemExit(int(any(results)))
