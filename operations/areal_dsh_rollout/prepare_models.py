#!/usr/bin/env python3
"""Stream official model files through existing SSH routes without local weights."""
import concurrent.futures
import argparse
import json
import shlex
import subprocess
import time

BASE = "/data/user/mou176/experiments/drawio-areal-dsh-20261118"
LAB = ["ssh", "-S", "/tmp/drawio-lab3-20261118.sock", "-oBatchMode=yes", "hkust3"]
HPC = ["ssh", "-S", "/home/shaoshitong/.cache/drawio-hpc3-20261118/control.sock",
       "-oBatchMode=yes", "mou176@hpc3login.hpc.hkust-gz.edu.cn"]

RECEIVER = r'''
import hashlib,json,pathlib,sys,time
info=json.loads(sys.argv[1]); p=pathlib.Path(info['path']); p.parent.mkdir(parents=True,exist_ok=True)
part=p.with_name(p.name+'.partial'); expected=info['size']; offset=info['offset']
if part.exists() and part.stat().st_size!=offset: raise RuntimeError('Partial changed')
h=hashlib.sha256() if info.get('lfs') else hashlib.sha1(('blob '+str(expected)+'\0').encode())
if offset:
 with part.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
count=offset
with part.open('ab' if offset else 'wb') as f:
 while True:
  b=sys.stdin.buffer.read(8*1024*1024)
  if not b: break
  count+=len(b)
  if count>expected: raise RuntimeError('Source returned excess bytes')
  f.write(b);h.update(b)
if count!=expected: raise RuntimeError('Incomplete '+str(count)+'/'+str(expected))
actual=h.hexdigest()
if actual!=info['hash']:
 part.unlink()
 raise RuntimeError('Hash mismatch '+actual)
part.replace(p)
print(json.dumps({'file':p.name,'bytes':count,'verified_hash':actual}),flush=True)
'''

VERIFIER = r'''
import hashlib,json,pathlib,struct,sys,time
p=pathlib.Path(sys.argv[1]);m=json.loads((p/'source-manifest.json').read_text());files=[]
for x in m['files']:
 q=p/x['rfilename'];n=q.stat().st_size
 if n!=x['size']:raise RuntimeError('Wrong size: '+q.name)
 expected=x.get('lfs',{}).get('sha256',x['blobId'])
 h=hashlib.sha256() if x.get('lfs') else hashlib.sha1(('blob '+str(n)+'\0').encode())
 with q.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 if h.hexdigest()!=expected:raise RuntimeError('Wrong hash: '+q.name)
 files.append(dict(name=q.name,bytes=n,algorithm='sha256' if x.get('lfs') else 'git-blob-sha1',hash=h.hexdigest()))
index=json.loads((p/'model.safetensors.index.json').read_text());observed={}
for shard in sorted(set(index['weight_map'].values())):
 with (p/shard).open('rb') as f:
  n=struct.unpack('<Q',f.read(8))[0];header=json.loads(f.read(n))
 for key in header:
  if key!='__metadata__':observed[key]=shard
if observed!=index['weight_map']:raise RuntimeError('Tensor index/header mismatch')
config=json.loads((p/'config.json').read_text())
receipt=dict(model=m['id'],source_revision=m['revision'],verified_at=time.time(),files=files,
             tensor_count=len(observed),model_type=config['model_type'],vision_config_present='vision_config' in config)
(p/'verification-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))
'''


def command(route, text, timeout=60):
    args = LAB + [shlex.join(HPC + [text])] if route is HPC else route + [text]
    return subprocess.check_output(args, text=True, timeout=timeout)


def remote_python(route, source, argument=None, timeout=60):
    cmd = "python3 -c " + shlex.quote(source)
    if argument is not None:
        cmd += " " + shlex.quote(json.dumps(argument))
    return command(route, cmd, timeout)


def metadata(model):
    code = """import json,subprocess,sys
m=sys.argv[1];u='https://hf-mirror.com/api/models/Qwen/'+m+'?blobs=true'
s=json.loads(subprocess.check_output(['curl','--noproxy','*','-fsSL','--connect-timeout','8','--max-time','30',u]))
mu='https://modelscope.cn/api/v1/models/Qwen/'+m+'/repo/files?Revision=master&Recursive=true'
ms=json.loads(subprocess.check_output(['curl','--noproxy','*','-fsSL','--connect-timeout','8','--max-time','30',mu]))
mf={x['Path']:x for x in ms['Data']['Files']}
files=[x for x in s['siblings'] if x['rfilename'].endswith(('.json','.jinja','.txt','.safetensors')) or x['rfilename']=='LICENSE']
for x in files:
 if x.get('lfs'):
  y=mf[x['rfilename']]
  if y['Sha256']!=x['lfs']['sha256'] or y['Size']!=x['size']:raise RuntimeError('Mirror file hash/size disagreement')
  x['download_url']='https://modelscope.cn/models/Qwen/'+m+'/resolve/master/'+x['rfilename']
print(json.dumps({'id':s['id'],'revision':s['sha'],'files':files}))
"""
    return json.loads(command(LAB, "python3 -c " + shlex.quote(code) + " " + shlex.quote(model)))


def offset(info):
    code = """import hashlib,json,pathlib,sys
x=json.loads(sys.argv[1]);p=pathlib.Path(x['path']);q=p.with_name(p.name+'.partial')
if p.exists() and p.stat().st_size==x['size']:
 h=hashlib.sha256() if x['lfs'] else hashlib.sha1(('blob '+str(x['size'])+'\\0').encode())
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 if h.hexdigest()==x['hash']:print(-1);sys.exit()
if q.exists() and q.stat().st_size>x['size']:q.unlink()
print(q.stat().st_size if q.exists() else 0)
"""
    return int(remote_python(HPC, code, info, timeout=180).strip())


def transfer(model, revision, entry):
    name = entry['rfilename']
    info = dict(path=BASE+'/models/'+model+'/'+name, size=entry['size'],
                lfs=bool(entry.get('lfs')), hash=entry.get('lfs',{}).get('sha256',entry['blobId']))
    for attempt in range(3):
        info['offset'] = offset(info)
        if info['offset'] == -1:
            return {'file':name,'bytes':info['size'],'reused':True}
        url = entry.get('download_url','https://hf-mirror.com/Qwen/'+model+'/resolve/'+revision+'/'+name)
        curl = ['curl','--noproxy','*','-fsSL','--retry','0',
                '--connect-timeout','10','--speed-time','45','--speed-limit','1024']
        if info['offset']:
            curl += ['--range',str(info['offset'])+'-']
        cmd = 'python3 -c '+shlex.quote(RECEIVER)+' '+shlex.quote(json.dumps(info))
        pipeline = 'set -o pipefail\n'+shlex.join(curl+[url])+' | '+shlex.join(HPC+[cmd])
        result = subprocess.run(LAB+['bash -lc '+shlex.quote(pipeline)],capture_output=True,text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(json.dumps({'retry':attempt+1,'file':name,'error':result.stderr[-1400:]}),flush=True)
    raise RuntimeError('Transfer failed: '+model+'/'+name)


def progress(model, total):
    code = """import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);fs=list(p.glob('*'))
print(json.dumps({'model':p.name,'bytes':sum(x.stat().st_size for x in fs if x.is_file() and x.name!='source-manifest.json'),'files':{x.name:x.stat().st_size for x in fs if x.is_file() and (x.suffix=='.partial' or x.suffix=='.safetensors')}}))
"""
    data=json.loads(command(HPC,'python3 -c '+shlex.quote(code)+' '+shlex.quote(BASE+'/models/'+model)))
    data['expected_bytes']=total
    data['observed_at']=time.time()
    print(json.dumps(data),flush=True)


def verify(model):
    return command(HPC,'python3 -c '+shlex.quote(VERIFIER)+' '+shlex.quote(BASE+'/models/'+model),timeout=360)


def prepare(model, workers=2):
    meta=metadata(model)
    total=sum(x['size'] for x in meta['files'])
    print(json.dumps({'start':model,'revision':meta['revision'],'expected_bytes':total}),flush=True)
    remote_python(HPC,"import json,pathlib,sys;x=json.loads(sys.argv[1]);p=pathlib.Path(x['path']);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x['manifest'],indent=2))",
                  {'path':BASE+'/models/'+model+'/source-manifest.json','manifest':meta})
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(transfer,model,meta['revision'],x):x for x in sorted(meta['files'],key=lambda x:x['size'])}
        pending=set(futures)
        while pending:
            done,pending=concurrent.futures.wait(pending,timeout=20,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                print(json.dumps(future.result()),flush=True)
            if pending:
                progress(model,total)
    print(verify(model),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',choices=('Qwen3.5-4B','Qwen3.5-9B'),default=['Qwen3.5-4B','Qwen3.5-9B'])
    parser.add_argument('--workers',type=int,choices=(1,2,4),default=2)
    options=parser.parse_args()
    for model_name in options.models:
        prepare(model_name,options.workers)
