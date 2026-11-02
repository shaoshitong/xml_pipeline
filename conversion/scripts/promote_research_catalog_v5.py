"""Promote a fully verified catalogue and replace only its obsolete publisher."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def checked_pointer(root):
 p=json.loads((root/'current.json').read_bytes())
 for k in ['index','summary','validation']:assert sha((R/p[k]['file']).read_bytes())==p[k]['sha256']
 return p

def main():
 import research_catalog_refresh_v5 as publisher
 stage=R/'clean/research_pairs_catalog_v5_staging';canonical=R/'clean/research_pairs_catalog'
 candidate=checked_pointer(stage);assert candidate['publisher']=='research_catalog_refresh_v5'and candidate['publisher_source_sha256']==sha((S/'research_catalog_refresh_v5.py').read_bytes())
 summary=json.loads((R/candidate['summary']['file']).read_bytes());vector=[r for r in summary['input_manifests']if r['id'].startswith('scientific_chart_vector_')];assert len(vector)==3 and sum(r['rows']for r in vector)==1875
 assert summary['new_conversions']==summary['new_QA']==summary['external_models']==0
 root=R/'conversion/research_catalog_v5_promotion'/uuid.uuid4().hex;root.mkdir(parents=True)
 old=json.loads((canonical/'latest_launch_v3.json').read_bytes());stat=Path('/proc',str(old['pid']),'stat');was_live=stat.exists()and stat.read_text().rsplit(') ',1)[1].split()[19]==str(old['birth_ticks']);assert was_live,'Inspect current publisher; do not duplicate an unknown controller'
 cmd=Path('/proc',str(old['pid']),'cmdline').read_bytes().split(b'\0');assert old['command'][2].encode()in cmd and b'--watch'in cmd
 initial=(canonical/'current.json').read_bytes();(root/'before_current.json').write_bytes(initial)
 (root/'replacement_reason.json').write_text(json.dumps(dict(scope='Replace task-owned catalogue publisher only; no training, goal, network route or conversion worker is stopped.',authorization='Active user goal requires complete unified clean index; v5 staged and verified the omitted 1875 existing chart pairs before replacement.',old_publisher=old,validated_stage=candidate),indent=2))
 os.kill(old['pid'],signal.SIGTERM);deadline=time.monotonic()+60
 while stat.exists()and stat.read_text().rsplit(') ',1)[1].split()[19]==str(old['birth_ticks']):
  if stat.read_text().rsplit(') ',1)[1].split()[0]=='Z':break
  if time.monotonic()>deadline:raise RuntimeError('Original publisher remains live; keep its pointer and do not start another publisher')
  time.sleep(.1)
 old_pointer=checked_pointer(canonical);old_bytes=(canonical/'current.json').read_bytes();(root/'quiesced_current.json').write_bytes(old_bytes)
 proc=None
 try:
  publisher.CATALOG=str(stage.relative_to(R));refresh=publisher.refresh(R);candidate=checked_pointer(stage)
  old_ids={json.loads(x)['id']for x in(R/old_pointer['index']['file']).read_bytes().splitlines()};new_ids={json.loads(x)['id']for x in(R/candidate['index']['file']).read_bytes().splitlines()};assert old_ids<=new_ids,'A previously published pair would disappear'
  publisher.atomic(canonical/'current.json',candidate)
  out=(canonical/'watch_v5.stdout.log').open('ab');err=(canonical/'watch_v5.stderr.log').open('ab');command=[sys.executable,'-u',str(S/'research_catalog_refresh_v5.py'),'--watch','--interval','60'];proc=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'));birth=Path('/proc',str(proc.pid),'stat').read_text().rsplit(') ',1)[1].split()[19]
  launch=dict(pid=proc.pid,birth_ticks=birth,command=command,source_sha256=sha((S/'research_catalog_refresh_v5.py').read_bytes()),initial_verified_pairs=len(new_ids),controller='fixed_program_no_models',old_publisher_preserved=old)
  publisher.atomic(canonical/'latest_launch_v5.json',launch)
  receipt=dict(root=str(root),old_publisher_birth_verified_and_gracefully_replaced=True,old_pairs_preserved=len(old_ids),new_pairs=len(new_ids),additional_pairs=len(new_ids-old_ids),new_pointer=candidate,refresh=refresh,launch=launch,new_conversion_calls=0,new_QA_calls=0,model_calls=0,goal_complete=False)
  (root/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');publisher.atomic(canonical/'validated_seed_promotion_v5.json',receipt);print(json.dumps(receipt))
 except BaseException:
  if proc is not None and proc.poll()is None:
   proc.terminate();proc.wait(timeout=30)
  publisher.atomic(canonical/'current.json',old_pointer)
  with(root/'fallback_v3.log').open('ab')as log:p=subprocess.Popen(old['command'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
  (root/'fallback_v3.json').write_text(json.dumps(dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],command=old['command'])))
  raise
if __name__=='__main__':main()
