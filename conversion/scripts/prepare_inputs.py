"""Prepare verified per-job inputs on HKUST, streaming each source Parquet once."""
import collections,hashlib,importlib.util,io,json,os,sqlite3,sys,time
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image
from native_worker import R,W,now
import curate_pairs as core
sha=lambda b:hashlib.sha256(b).hexdigest()
db=sqlite3.connect(W/'jobs.sqlite');db.execute('PRAGMA busy_timeout=30000')
if 'input_manifest' not in [x[1] for x in db.execute('PRAGMA table_info(jobs)')]:db.execute('ALTER TABLE jobs ADD COLUMN input_manifest TEXT');db.commit()
groups=collections.defaultdict(list);standalone=[];total=0
for id,raw,cached in db.execute('SELECT id,input_record,input_manifest FROM jobs'):
 if cached:
  x=json.loads(cached)
  if (R/x['reference_image']).is_file() and (R/x['source_code']).is_file():continue
 record=json.loads(raw);record['_id']=id;total+=1
 if record.get('clean_file'):groups[record['clean_file']].append(record)
 else:standalone.append(record)
counts=collections.Counter();errors=[];start=time.monotonic();progress=W/'input_preparation_progress.json'
def save_bytes(p,b):
 p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+'.tmp');temp.write_bytes(b);temp.replace(p)
def store(record,data,code,row=None):
 id=record['_id'];assert data and sha(data)==record['image_sha256'];assert code is not None and sha(code.encode())==record['code_sha256'];im=Image.open(io.BytesIO(data));mime=Image.MIME[im.format];directory=W/'inputs'/id[:2]/id
 if record.get('clean_file'):
  ref=directory/'reference.bin';source=directory/'source.txt';save_bytes(ref,data);save_bytes(source,code.encode())
 else:ref=R/(record.get('reference_image') or record['image_file']);source=R/record['code_file']
 assets=[]
 if record.get('panel_assets'):
  assert row is not None
  for p in record['panel_assets']:
   import re
   m=re.fullmatch(r'panels\[(\d+)\]\.image',p['image_key']);assert m
   blob=core.image_bytes(row['panels'][int(m.group(1))]['image'],R/'clean'/record['source']/'source_files');assert blob and sha(blob)==p['image_sha256'];name=Path(p['file_name']);assert not name.is_absolute() and '..' not in name.parts;file=directory/'assets'/name;save_bytes(file,blob);assets.append({'file':str(file.relative_to(R)),'source_name':str(name),'sha256':p['image_sha256']})
 manifest={'id':id,'reference_image':str(ref.relative_to(R)),'source_code':str(source.relative_to(R)),'image_sha256':record['image_sha256'],'code_sha256':record['code_sha256'],'mime_type':mime,'width':im.width,'height':im.height,'source_format':record['format'],'asset_root':record.get('asset_root'),'panel_assets':assets,'prepared_at_utc':now()}
 db.execute('UPDATE jobs SET input_manifest=? WHERE id=?',(json.dumps(manifest),id));counts['prepared']+=1
 if counts['prepared']%128==0:db.commit();progress.write_text(json.dumps({'time':now(),'counts':dict(counts),'errors':len(errors),'total_to_prepare':total})+'\n')
for file,records in sorted(groups.items()):
 wanted=collections.defaultdict(list)
 for r in records:wanted[r['clean_row']].append(r)
 columns=sorted({r[k] for r in records for k in ('image_key','code_key')}|{r['asset_key'] for r in records if r.get('asset_key')});offset=0
 try:
  for batch in pq.ParquetFile(R/file).iter_batches(batch_size=64,columns=columns):
   selected={i:wanted.pop(offset+i) for i in range(batch.num_rows) if offset+i in wanted}
   if selected:
    for i,row in enumerate(batch.to_pylist()):
     for r in selected.get(i,[]):
      try:
       data=core.image_bytes(row[r['image_key']],R/'clean'/r['source']/'source_files');code=core.code_value(row)[0] if r['code_key'] in ('messages','conversations','conversation') else core.text_content(row[r['code_key']]);code=core.unwrap_code(code) if r.get('profile') else code;store(r,data,code,row)
      except Exception as e:errors.append({'id':r['_id'],'error':type(e).__name__+': '+str(e)[:300]})
   offset+=batch.num_rows
  for missing in wanted.values():
   for r in missing:errors.append({'id':r['_id'],'error':'missing_parquet_row'})
 except Exception as e:errors.append({'file':file,'error':type(e).__name__+': '+str(e)[:300]})
 db.commit();print(json.dumps({'time':now(),'file':file,'prepared':counts['prepared'],'errors':len(errors)}),flush=True)
for r in standalone:
 try:store(r,(R/(r.get('reference_image') or r['image_file'])).read_bytes(),(R/r['code_file']).read_text())
 except Exception as e:errors.append({'id':r['_id'],'error':type(e).__name__+': '+str(e)[:300]})
db.commit();prepared=db.execute('SELECT COUNT(*) FROM jobs WHERE input_manifest IS NOT NULL').fetchone()[0];result={'finished_at_utc':now(),'ok':not errors and prepared==131904,'prepared_total':prepared,'newly_prepared':counts['prepared'],'errors':errors,'seconds':time.monotonic()-start,'no_models_called':True,'all_payloads_remote':True};(W/'input_preparation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='errors'}),flush=True)
