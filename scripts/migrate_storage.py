"""Authorized HKUST-only consolidation. No data programs executed."""
import collections,datetime,gzip,hashlib,json,os,shutil
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029'); M=R/'reports/storage_migration';M.mkdir(parents=True,exist_ok=True)
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ACTIVE=('clean_file','derived_file','reference_image','image_file','code_file','asset_root','metadata_file','original_poster','source_archive')
if (M/'migration.json').exists():raise SystemExit('Existing migration receipt; inspect before rerunning')
# Original small completion snapshots and compressed catalogs are retained as historical evidence.
before=M/'before';before.mkdir(exist_ok=True)
for name in ('provided.jsonl','derived.jsonl','summary.json','acceptance.json','complete.json'):
 src=R/'release'/name
 if name.endswith('.jsonl'):
  with src.open('rb') as inp,gzip.open(before/(name+'.gz'),'wb',compresslevel=1) as out:shutil.copyfileobj(inp,out)
 else:shutil.copy2(src,before/name)
paths={};dirs=set();records=0;fieldpaths=collections.Counter()
for kind in ('provided','derived'):
 for line in (R/'release'/f'{kind}.jsonl').open():
  x=json.loads(line);records+=1
  for key in ACTIVE:
   value=x.get(key)
   if not value:continue
   p=Path(value)
   assert (R/p).exists(),(key,value)
   assert not p.is_absolute() and '..' not in p.parts,(key,value)
   if p.parts[0] in ('raw','extracted'):
    assert len(p.parts)>2
    dest=Path('clean')/p.parts[1]/'source_files'/p.parts[0]/Path(*p.parts[2:])
    paths[value]=str(dest);fieldpaths[key]+=1
    if key=='asset_root':dirs.add(value)
# Derivation provenance is metadata; payloads are organized by source under clean.
for p in (R/'derived').iterdir():
 if p.is_dir():
  dest=R/'clean'/p.name
  if dest.exists():
   assert not any(dest.iterdir()),str(dest)
   dest.rmdir()
  paths[str(p.relative_to(R))]=str(dest.relative_to(R));dirs.add(str(p.relative_to(R)))
# Exclude individual moves covered by a whole directory move.
roots=sorted(dirs,key=lambda s:(len(Path(s).parts),s));selected=[]
for item in roots:
 if not any(Path(item).is_relative_to(Path(parent)) for parent in selected):selected.append(item)
moves={p:paths[p] for p in selected}
for p,d in sorted(paths.items()):
 if not any(Path(p).is_relative_to(Path(parent)) for parent in selected):moves[p]=d
plan={'started_at_utc':now(),'records_before':records,'moves':moves,'external_active_fields':dict(fieldpaths),'status':'planned'}
(M/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
for src,dst in moves.items():
 a=R/src;b=R/dst;assert a.exists() and not a.is_symlink(),src;assert not b.exists(),dst
 b.parent.mkdir(parents=True,exist_ok=True);old=a.stat();a.rename(b);new=b.stat();assert (old.st_ino,old.st_dev,old.st_size)==(new.st_ino,new.st_dev,new.st_size),(src,dst)
# Update active locators only; source lineage remains historical and explicitly marked.
def rewrite(value):
 if value.startswith('clean/'):return value
 if value in paths:return paths[value]
 for parent in selected:
  if Path(value).is_relative_to(Path(parent)):return str(Path(paths[parent])/Path(value).relative_to(Path(parent)))
 return value
stats={};allimages=set();allpairs=set();total=0;h=hashlib.sha256();dest=R/'release/manifest.jsonl';tmp=dest.with_suffix('.tmp')
with tmp.open('wb') as out:
 for kind in ('provided','derived'):
  counts={k:collections.Counter() for k in ('formats','categories','sources')};n=0
  for line in (R/'release'/f'{kind}.jsonl').open():
   x=json.loads(line)
   for key in ACTIVE:
    if x.get(key):
     x[key]=rewrite(x[key]);assert x[key].startswith('clean/'),(key,x[key]);assert (R/x[key]).exists(),x[key]
   b=(json.dumps(x,ensure_ascii=False)+'\n').encode();out.write(b);h.update(b);n+=1;allimages.add(x['image_sha256']);allpairs.add(x['pair_sha256'])
   for k,f in [('formats','format'),('categories','category'),('sources','source')]:counts[k][x[f]]+=1
  stats[kind]={'pairs':n,**{k:dict(v) for k,v in counts.items()}};total+=n
os.replace(tmp,dest)
assert total==784171 and len(allpairs)==total
summary={'created_at_utc':now(),'status':'storage_migrated_pending_content_audit','manifest':str(dest),'sha256':h.hexdigest(),'total_pairs':total,'unique_pairs':len(allpairs),'unique_images':len(allimages),'groups':stats,'storage':'All active payload locators are under clean/. catalog_kind preserves provided/derived provenance. raw_file and source_manifest fields are historical lineage, not loading dependencies.','before':'reports/storage_migration/before/'}
(R/'release/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for name in ('provided.jsonl','derived.jsonl','acceptance.json','complete.json'):(R/'release'/name).unlink()
for folder in ('clean','derived'):
 p=R/folder/'manifest.jsonl'
 if p.exists():
  with p.open('rb') as inp,gzip.open(before/(folder+'_baseline_manifest.jsonl.gz'),'wb',compresslevel=1) as out:shutil.copyfileobj(inp,out)
  p.unlink()
remaining=list((R/'derived').iterdir());assert not remaining,remaining;(R/'derived').rmdir()
plan.update(status='migrated_pending_content_audit',finished_at_utc=now(),manifest_sha256=h.hexdigest(),total_pairs=total,move_count=len(moves));(M/'migration.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps({k:v for k,v in plan.items() if k!='moves'}),flush=True)
