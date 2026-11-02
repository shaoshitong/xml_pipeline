"""Durable normal-frontend call claims; orchestration/QA never reset source core."""
import hashlib,json,os,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';ROOT=W/'drawio_author_source_once_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def core(compiler):return sha(Path(compiler.__file__).read_bytes())
def claim(identifier,source,compiler,request):
 key=core(compiler);directory=ROOT/key;directory.mkdir(parents=True,exist_ok=True);path=directory/(identifier+'.json')
 value={'schema':'normal_author_native_source_frontend_call_claim_v1','id':identifier,'source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],'frontend_file':str(Path(compiler.__file__).resolve()),'frontend_sha256':key,'frontend_configuration_policy':compiler.configuration()['policy'],'claimed_before_frontend':True,'nonce':uuid.uuid4().hex,'pid':os.getpid(),'request':str(Path(request).resolve()),'ambiguous_interruption_is_not_reexecuted':True,'model_calls':0}
 try:
  with path.open('xb') as f:f.write(json.dumps(value,sort_keys=True).encode());f.flush();os.fsync(f.fileno())
 except FileExistsError:
  prior=json.loads(path.read_bytes())
  if any(prior[k]!=value[k]for k in ('id','source_code_sha256','source_image_sha256','frontend_sha256')):raise RuntimeError('infrastructure_once_claim_identity_conflict')
  raise ValueError('deferred_same_frozen_source_frontend_already_claimed')
 fd=os.open(directory,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
 try:os.fsync(fd)
 finally:os.close(fd)
 return {'file':str(path.relative_to(R)),'sha256':sha(path.read_bytes()),'normal_frontend_claimed_once':True}
def claims(compiler):
 rows=[]
 for p in sorted((ROOT/core(compiler)).glob('*.json')):
  value=json.loads(p.read_bytes())
  if value['frontend_sha256']!=core(compiler):raise RuntimeError('infrastructure_once_claim_core_changed')
  rows.append(value|{'claim_file':str(p),'claim_sha256':sha(p.read_bytes())})
 return rows
