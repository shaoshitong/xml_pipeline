import datetime,json,os,shutil,stat
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');M=R/'reports/storage_migration'
for name in ('record_audit.json','content_audit.json'):
 report=json.loads((M/name).read_text());assert report['ok'],name
assert json.loads((M/'content_audit.json').read_text())['checked_pairs']==784171
names=['recovery_staging','logs','cases','curation_cases','env','runtime','arxiv_pilot','raw/ahazimeh--slide2svg','raw/BleachNick--CraftBench','raw/caopu--DrawAI-Bench-Lite','raw/Presto-Design--svg_basic_benchmark_v0']
report={'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authorization':'User explicitly requested deletion of listed temporary/runtime/arxiv directories and four raw sources; removal of all clean empty directories.','deleted':[],'empty_clean_directories':[]}
def size(path):
 count=0;blocks=0;logical=0
 for base,dirs,files in os.walk(path,followlinks=False):
  for name in files:
   p=Path(base)/name;s=p.lstat();count+=1;blocks+=s.st_blocks*512;logical+=s.st_size
 return {'files':count,'allocated_file_bytes':blocks,'logical_file_bytes':logical}
for name in names:
 p=R/name;assert p.is_relative_to(R) and p!=R
 if not p.exists() and not p.is_symlink():continue
 data={'path':name,**size(p)}
 # rmtree unlinks contained symlinks; it never traverses their target.
 if p.is_symlink():p.unlink()
 else:shutil.rmtree(p)
 report['deleted'].append(data)
# Only task-private Python bytecode caches, with no symlink following.
cache=[]
for base,dirs,files in os.walk(R,followlinks=False):
 if '__pycache__' in dirs:
  p=Path(base)/'__pycache__';cache.append(p);dirs.remove('__pycache__')
for p in cache:
 data={'path':str(p.relative_to(R)),**size(p)}
 if p.is_symlink():p.unlink()
 else:shutil.rmtree(p)
 report['deleted'].append(data)
for base,dirs,files in os.walk(R/'clean',topdown=False,followlinks=False):
 p=Path(base)
 if p!=R/'clean' and not any(p.iterdir()):p.rmdir();report['empty_clean_directories'].append(str(p.relative_to(R)))
assert not (R/'derived').exists()
report.update(finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),ok=True,deleted_allocated_file_bytes=sum(x['allocated_file_bytes'] for x in report['deleted']))
(M/'cleanup.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
