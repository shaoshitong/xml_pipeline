"""Install task-private remote runtime over authenticated campus LAN; no Mac payloads."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, tarfile, urllib.request
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--node',required=True);a=p.parse_args()
root=a.root;root.mkdir(parents=True,exist_ok=True)
config=json.loads(sys.stdin.read());config['node']=a.node
configfile=root/'private_config.json';configfile.write_text(json.dumps(config));configfile.chmod(0o600)
request=urllib.request.Request(config['url']+'/runtime',headers={'Authorization':'Bearer '+config['token']})
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
archive=root/'runtime.tar.gz'
with opener.open(request,timeout=120) as response,archive.open('wb') as f:
    expected=response.headers['X-SHA256'];h=hashlib.sha256()
    while True:
        b=response.read(1024**2)
        if not b:break
        f.write(b);h.update(b)
assert h.hexdigest()==expected
with tarfile.open(archive) as t:t.extractall(root,filter='data')
archive.unlink()
packages=root/'runtime/packages'
# Playwright's Python glue and driver are portable; only greenlet's CPython
# extension differs on the Python 3.13 nodes. Wheels/cache stay remote.
if sys.version_info[:2] != (3,12):
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--upgrade','--target',str(packages),'greenlet','--index-url','https://pypi.org/simple'],check=True)
fontconfig=root/'runtime/fonts.conf'
fontconfig.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>'+str(root/'runtime/fonts')+'</dir><cachedir>'+str(root/'runtime/fontcache')+'</cachedir><config></config></fontconfig>')
(root/'runtime/tmp').mkdir(exist_ok=True)
short=Path('/tmp','arxiv-'+str(os.getuid())+'-'+a.node)
if short.is_symlink():assert short.resolve()==(root/'runtime/tmp').resolve()
else:short.symlink_to(root/'runtime/tmp',target_is_directory=True)
env=dict(os.environ,PYTHONPATH=str(packages),FONTCONFIG_FILE=str(fontconfig),TMPDIR=str(short),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
# Verify actual package imports, official JS execution and browser startup.
probe="import fitz,PIL,playwright.sync_api;from playwright.sync_api import sync_playwright;p=sync_playwright().start();b=p.chromium.launch(executable_path="+repr(str(root/'runtime/chrome/chrome'))+",args=['--disable-dev-shm-usage','--disable-gpu']);print(b.version);b.close();p.stop()"
subprocess.run([sys.executable,'-c',probe],env=env,check=True,timeout=90)
receipt=dict(node=a.node,root=str(root),runtime_sha256=expected,python=sys.executable,browser_started=True)
(root/'bootstrap_verified.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
