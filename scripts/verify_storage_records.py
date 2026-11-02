import gzip,hashlib,json,datetime
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');M=R/'reports/storage_migration';plan=json.loads((M/'migration.json').read_text());paths=plan['moves'];active=('clean_file','derived_file','reference_image','image_file','code_file','asset_root','metadata_file','original_poster','source_archive')
ordered=sorted(paths,key=len,reverse=True)
def moved(v):
 if v.startswith('clean/'):return v
 if v in paths:return paths[v]
 old=v.rpartition('/')[0]
 while old:
  if old in paths:return paths[old]+v[len(old):]
  old=old.rpartition('/')[0]
 return v
n=0;errors=[];external=[];missing=[];fingerprint=hashlib.sha256()
with (R/'release/manifest.jsonl').open('rb') as current:
 for kind in ('provided','derived'):
  with gzip.open(M/'before'/f'{kind}.jsonl.gz','rt') as before:
   for line in before:
    expected=json.loads(line);buf=next(current,None);assert buf is not None;fingerprint.update(buf);actual=json.loads(buf)
    for k in active:
     if expected.get(k):expected[k]=moved(expected[k])
     if actual.get(k):
      if not actual[k].startswith('clean/'):external.append((n,k,actual[k]))
      elif not (R/actual[k]).exists():missing.append((n,k,actual[k]))
    if actual!=expected:errors.append(n)
    n+=1
 assert next(current,None) is None
summary=json.loads((R/'release/summary.json').read_text());assert fingerprint.hexdigest()==summary['sha256']
result={'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ok':n==784171 and not errors and not external and not missing,'records':n,'record_mismatches':len(errors),'external_active_paths':len(external),'missing_active_paths':len(missing),'manifest_sha256':fingerprint.hexdigest(),'scope':'Every record equals its frozen reviewed-release record, except authorized path relocation. Pair hashes, image/code hashes, categories and provenance are unchanged. All active and auxiliary file locators now exist under clean/. Raw/source provenance fields remain historical identifiers.'}
(M/'record_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert result['ok']
