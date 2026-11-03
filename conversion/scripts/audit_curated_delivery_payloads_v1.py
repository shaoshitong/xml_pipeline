"""Audit immutable curated payloads and provenance, without conversion or QA calls."""
from pathlib import Path
import collections,concurrent.futures,datetime,fcntl,hashlib,json,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def stamp(name):
 p=R/name;q=p.resolve(strict=True);assert q.is_relative_to(R/'clean');s=q.stat()
 return dict(file=name,resolved=str(q.relative_to(R)),device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
def main():
 from research_catalog_refresh_v5 import Assets
 from priority_source_complexity_filter_v1 import native
 parent=R/'clean/curated_delivery_payload_audit_v1';parent.mkdir(exist_ok=True)
 with(parent/'audit.lock').open('a+')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);started=time.monotonic();pointer=read(R/'clean/curated_complex_research_delivery/current.json');ref=pointer['pairs'];b=(R/ref['file']).read_bytes();assert sha(b)==ref['sha256'];rows=[json.loads(l)for l in b.splitlines()];assert len(rows)==pointer['unique_code_RGBA_pairs']
  previous={}
  if(parent/'current.json').exists():
   old=read(parent/'current.json');p=R/old['rows']['file'];body=p.read_bytes();assert sha(body)==old['rows']['sha256'];previous={r['id']:r for r in map(json.loads,body.splitlines())if r['status']=='payload_valid'}
  root=parent/uuid.uuid4().hex;root.mkdir();write(root/'input_pointer.json',pointer);(root/'input_pairs.jsonl').write_bytes(b)
  manifests={}
  for r in rows:
   assert r['format']=='drawio'and r['code_file'].endswith('.drawio')and r['source_records']and r['curation_memberships']
   for source in r['source_records']:
    name=source['manifest']
    if name not in manifests:
     p=R/name;assert p.resolve().is_relative_to(R/'clean');raw=p.read_bytes();manifests[name]=dict(reference=asset(p),lines=raw.splitlines())
    assert source['complete_upstream_record_preserved_in_manifest']is True
    line=manifests[name]['lines'][source['line']-1];saved=json.loads(line)
    assert(saved['code_sha256'],saved['image_sha256'])==(r['code_sha256'],r['image_sha256']),'backlink_does_not_match_exact_pair'
  def check(r):
   try:
    stamps={k:stamp(r[k])for k in ['code_file','image_file']};old=previous.get(r['id']);identity=dict(code_sha256=r['code_sha256'],image_sha256=r['image_sha256'],stamps=stamps)
    if old and all(old.get(k)==v for k,v in identity.items())and old['pixels']==r['image_pixels']:
     result=dict(old,reused_unchanged_payload=True)
    else:
     verifier=Assets(R);verifier.verify(r['code_file'],r['code_sha256'],primary=True,xml=True);_,image=verifier.verify(r['image_file'],r['image_sha256'],primary=True,image=True);assert image['pixels']==r['image_pixels'];features=native((R/r['code_file']).read_text());assert features['native_vertices']>1,'single_object_wrapper';assert features['label_characters']>0,'no_editable_native_labels'
     result=dict(id=r['id'],status='payload_valid',**identity,pixels=image['pixels'],native_structure=features,reused_unchanged_payload=False)
    assert stamps=={k:stamp(r[k])for k in stamps},'payload_changed_during_audit'
    result.update(quality_views=r['quality_views'],curation_memberships=r['curation_memberships'],upstream_backlinks_checked=len(r['source_records']));return result
   except Exception as e:return dict(id=r['id'],status='audit_error',reason=type(e).__name__+':'+str(e))
  output=root/'payload_audit.jsonl';done=[]
  with output.open('w')as f,concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
   for result in pool.map(check,rows):
    f.write(json.dumps(result,sort_keys=True)+'\n');f.flush();done.append(result)
    if len(done)%100==0:write(root/'progress.json',dict(completed=len(done),total=len(rows),errors=sum(r['status']=='audit_error'for r in done),elapsed_seconds=time.monotonic()-started))
  report=dict(root=str(root),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=len(rows),counts=dict(collections.Counter(r['status']for r in done)),fresh_payloads=sum(not r.get('reused_unchanged_payload',False)for r in done),unchanged_payloads_reused=sum(r.get('reused_unchanged_payload',False)for r in done),provenance_manifests=[v['reference']for v in manifests.values()],source_pointer=asset(root/'input_pointer.json'),source_pairs=ref,audit_rows=asset(output),seconds=time.monotonic()-started,producer=asset(Path(__file__)),qualification_unchanged=True,new_normal_calls=0,new_QA_calls=0,new_model_calls=0,goal_complete=False)
  write(root/'summary.json',report)
  for p in root.iterdir():p.chmod(0o444)
  value=dict(summary=asset(root/'summary.json'),rows=asset(output),input_pairs=ref,counts=report['counts'],goal_complete=False);tmp=parent/'current.tmp';write(tmp,value);tmp.replace(parent/'current.json');print(json.dumps(report),flush=True)
  if report['counts'].get('audit_error',0):raise SystemExit(1)
if __name__=='__main__':main()
