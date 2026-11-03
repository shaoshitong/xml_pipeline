"""Verify received final artifact bytes using HKUST3 CPU, without storing them."""
from pathlib import Path,PurePosixPath
import argparse,datetime,hashlib,json,sys,tarfile
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/goal500_final_delivery_v1';NAME='random100_new540_final_seed20261103100_v1';SAMPLE=R/'clean/review_samples'/NAME
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['archive','directory']);a=p.parse_args();receipt=json.loads(SAMPLE.with_suffix('.receipt.json').read_text())
 if a.mode=='archive':
  h=hashlib.sha256();count=0
  while True:
   b=sys.stdin.buffer.read(1024**2)
   if not b:break
   h.update(b);count+=len(b)
  assert h.hexdigest()==receipt['archive_sha256'] and count==receipt['archive_bytes'],'received_archive_mismatch';result=dict(archive_SHA256=h.hexdigest(),bytes=count)
 else:
  raw=(SAMPLE/'files.json').read_bytes();expected=json.loads(raw);expected['files.json']=dict(sha256=sha(raw),bytes=len(raw));seen=set();count=0
  with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as tar:
   for m in tar:
    path=PurePosixPath(m.name)
    assert not path.is_absolute() and '..' not in path.parts
    if m.isdir():continue
    assert m.isfile() and path.parts[0]==NAME and len(path.parts)>1,'unsupported_stream_member';key=PurePosixPath(*path.parts[1:]).as_posix();assert key in expected and key not in seen,'unexpected_or_duplicate_stream_file';meta=expected[key];assert m.size==meta['bytes'];h=hashlib.sha256()
    with tar.extractfile(m) as f:
     for b in iter(lambda:f.read(1024**2),b''):h.update(b);count+=len(b)
    assert h.hexdigest()==meta['sha256'],'received_file_SHA256_mismatch:'+key;seen.add(key)
  assert seen==set(expected),'received_preview_files_missing';result=dict(files_verified=len(seen),bytes=count,all_file_SHA256_match=True)
 result.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),ok=True,mode=a.mode,CPU_host='HKUST3',input='actual received local final artifact streamed back over SSH without local hashing/decoding',new_index_SHA256=receipt['index_sha256']);(D/('local_'+a.mode+'_verification.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
