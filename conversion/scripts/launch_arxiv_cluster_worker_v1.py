"""Idempotent worker launch after real browser/dependency check; task-only env."""
from pathlib import Path
import argparse,datetime,json,os,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
def birth(pid):
    try:
        r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
    except FileNotFoundError:return None
path=root/'launch.json'
old=json.loads(path.read_text()) if path.exists() else None
if old and birth(old['pid'])==old['birth_ticks']:
    print(json.dumps(dict(already_running=True,**old)));sys.exit()
config=json.loads((root/'private_config.json').read_text());node=config['node']
entry='run_arxiv_cluster_worker_with_lan_source_v1.py' if config.get('source_transport')=='HKUST3_DIRECT_LAN_RELAY' else 'arxiv_cluster_worker_v1.py'
assert entry=='arxiv_cluster_worker_v1.py' or node=='hkust4'
# UNIX domain socket paths are capped near 108 bytes. The data remains on the
# node's remote data disk; only a short, owned symlink lives under /tmp.
short=Path('/tmp','arxiv-'+str(os.getuid())+'-'+node)
if short.is_symlink():assert short.resolve()==(root/'runtime/tmp').resolve()
else:short.symlink_to(root/'runtime/tmp',target_is_directory=True)
env=dict(os.environ,PYTHONPATH=str(root/'runtime/packages'),FONTCONFIG_FILE=str(root/'runtime/fonts.conf'),TMPDIR=str(short),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
probe="import fitz,PIL,playwright.sync_api;from playwright.sync_api import sync_playwright;p=sync_playwright().start();b=p.chromium.launch(executable_path="+repr(str(root/'runtime/chrome/chrome'))+",args=['--disable-dev-shm-usage','--disable-gpu']);print(b.version);b.close();p.stop()"
subprocess.run([sys.executable,'-c',probe],env=env,check=True,timeout=90)
with (root/'program.log').open('ab') as f:
    command=[sys.executable,'-u',str(root/'conversion/scripts'/entry),'--root',str(root),'--config',str(root/'private_config.json')]
    child=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
r=dict(node=node,pid=child.pid,birth_ticks=birth(child.pid),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command,browser_started=True)
path.write_text(json.dumps(r,indent=2));print(json.dumps(r))
