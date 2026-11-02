import hashlib,io,json,os,subprocess,tarfile,urllib.request
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');dest=W/'runtime/tectonic';dest.mkdir(parents=True,exist_ok=True)
req=urllib.request.Request('https://api.github.com/repos/tectonic-typesetting/tectonic/releases/latest',headers={'User-Agent':'img2code-conversion'})
meta=json.load(urllib.request.urlopen(req,timeout=60));assets=[x for x in meta['assets'] if x['name'].endswith('x86_64-unknown-linux-musl.tar.gz')];assert len(assets)==1,[x['name'] for x in meta['assets']];asset=assets[0];data=urllib.request.urlopen(asset['browser_download_url'],timeout=180).read();archive=dest/asset['name'];archive.write_bytes(data)
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
 members=[m for m in tar.getmembers() if m.isfile() and Path(m.name).name=='tectonic'];assert len(members)==1;(dest/'tectonic').write_bytes(tar.extractfile(members[0]).read())
os.chmod(dest/'tectonic',0o755);version=subprocess.check_output([str(dest/'tectonic'),'--version'],text=True).strip();out={'release':meta['tag_name'],'source':asset['browser_download_url'],'archive_sha256':hashlib.sha256(data).hexdigest(),'binary_sha256':hashlib.sha256((dest/'tectonic').read_bytes()).hexdigest(),'version':version};(dest/'provenance.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
