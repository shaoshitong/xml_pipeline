import hashlib,json,os,re,subprocess,urllib.request
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');D=W/'runtime/graphviz_deb';D.mkdir(parents=True,exist_ok=True);cache=D/'packages';cache.mkdir(exist_ok=True)
packages=['graphviz','libgvc6','libcdt5','libcgraph6','libpathplan4','libgvpr2','liblab-gamut1','libann0','libgts-0.7-5','libgd3','libxpm4','libxaw7','libltdl7','libwebp6','libjpeg-turbo8']
packages=[p for p in packages if subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}',p],text=True,capture_output=True).stdout.strip()!='installed']
r=subprocess.run(['apt-get','--print-uris','download']+packages,text=True,capture_output=True,timeout=60);assert r.returncode==0,r.stderr;results=[]
for line in r.stdout.splitlines():
 if not line.startswith("'"):continue
 parts=line.split();url=parts[0].strip("'").replace('http://','https://',1);filename=parts[1];expected=int(parts[2]);data=urllib.request.urlopen(url,timeout=120).read();assert len(data)==expected
 if len(parts)>3 and ':' in parts[3]:alg,digest=parts[3].split(':',1);assert hashlib.new(alg.lower(),data).hexdigest()==digest
 p=cache/filename;p.write_bytes(data);subprocess.run(['dpkg-deb','-x',str(p),str(D)],check=True);results.append({'name':filename,'url':url,'sha256':hashlib.sha256(data).hexdigest()});print(json.dumps(results[-1]),flush=True)
lib=D/'usr/lib/x86_64-linux-gnu';env=dict(os.environ,LD_LIBRARY_PATH=str(lib),GVBINDIR=str(lib/'graphviz'));binary=D/'usr/bin/dot';cfg=subprocess.run([str(binary),'-c'],env=env,text=True,capture_output=True);version=subprocess.run([str(binary),'-V'],env=env,text=True,capture_output=True);report={'packages':results,'configure_returncode':cfg.returncode,'configure_stderr':cfg.stderr,'version':version.stderr,'version_returncode':version.returncode};(D/'provenance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
