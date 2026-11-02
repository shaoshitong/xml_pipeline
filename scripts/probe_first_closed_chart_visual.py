#!/usr/bin/env python3
"""Six exact rows from one known CLOSED shard. Remote-only contact sheet.
Reads only the requested source manifest prefix and image/code key columns.
Never opens canonical catalogs, executes source, renders code, or changes data.
"""
import argparse,collections,hashlib,importlib.util,io,json,os,re,signal,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
SOURCE='DocTron-Hub--VinciCoder-1.6M-SFT'
PART='clean/'+SOURCE+'/part00000.parquet'
RAW='chart2code_1.parquet'
ROWS=[0,35002,70005,105008,140011,210016]
EXPECTED={'rows':210017,'row_groups':13134,'bytes':10019992455}
LOCATORS=('source','raw_file','raw_row','profile','clean_file','clean_row','format','category','image_key','code_key','image_sha256','code_sha256','image_provenance','gold_code_provenance','code_provenance','pairing','structurally_complete','code_execution_checked')
class ProbeTimeout(Exception):pass

def sha(data):return hashlib.sha256(data).hexdigest()
def state(path):
 s=path.stat();return (s.st_size,s.st_mtime_ns,s.st_ino)
def font(size):
 try:return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',size)
 except OSError:return ImageFont.load_default()

def main(args):
 import pyarrow.parquet as pq
 root=args.root.resolve();began=time.monotonic();source=root/'raw'/SOURCE;part=root/PART;manifest=root/'manifests'/(SOURCE+'.jsonl');core_path=root/'scripts/curate_pairs.py';spec=importlib.util.spec_from_file_location('six_row_core',core_path);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
 def expired(signum,frame):raise ProbeTimeout('bounded_probe_timeout')
 previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,args.seconds)
 try:
  before=state(part);pf=pq.ParquetFile(part);footer={'rows':pf.metadata.num_rows,'row_groups':pf.metadata.num_row_groups,'bytes':before[0]}
  if footer!=EXPECTED:raise ValueError('closed_shard_footer_differs_from_requested_snapshot')
  summary=json.loads((root/'reports/summary.json').read_text());files=summary.get('sources',{}).get(SOURCE,{}).get('files',[]);source_report=next((item for item in files if Path(item.get('raw','')).name==RAW),None)
  if not source_report or source_report.get('accepted')!=EXPECTED['rows']:raise ValueError('closed_file_report_does_not_match_footer')
  initial_manifest_bytes=manifest.stat().st_size;pattern=re.compile(rb'"clean_row"\s*:\s*(?:'+b'|'.join(str(row).encode() for row in ROWS)+rb')\s*[,}]');records={};scanned=0
  with manifest.open('rb') as stream:
   while stream.tell()<initial_manifest_bytes and scanned<args.max_manifest_mib*1024*1024:
    line=stream.readline();scanned+=len(line)
    if stream.tell()>initial_manifest_bytes or not line.endswith(b'\n'):break
    if not pattern.search(line):continue
    record=json.loads(line)
    if record.get('clean_file')!=PART or record.get('clean_row') not in ROWS:continue
    if record.get('raw_file')!=RAW or record.get('source')!=SOURCE:raise ValueError('selected_manifest_source_or_raw_file_mismatch')
    if record['clean_row'] in records:raise ValueError('duplicate_selected_clean_row_locator')
    records[record['clean_row']]=record
    if len(records)==len(ROWS):break
  if len(records)!=len(ROWS):raise ValueError('requested_manifest_locators_not_all_available_in_bounded_prefix')
  width=1800;height=1040;tile_w=600;tile_h=480;top=60;canvas=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(canvas);big=font(21);small=font(16)
  draw.text((12,8),'EARLY QA | one closed Vinci chart shard | SIX PROVIDED samples | no source execution',font=big,fill='#161616')
  draw.text((12,36),'Only the six requested clean rows. This is not final canonical or exhaustive domain verification.',font=small,fill='#555555')
  samples=[];errors=[];offsets=[];cumulative=0
  for group in range(pf.metadata.num_row_groups):
   offsets.append((cumulative,cumulative+pf.metadata.row_group(group).num_rows));cumulative=offsets[-1][1]
  for index,cleanrow in enumerate(ROWS):
   record=records[cleanrow];x=(index%3)*tile_w;y=top+(index//3)*tile_h;draw.rectangle((x+2,y+2,x+tile_w-3,y+tile_h-3),outline='#8b8b8b',width=2);draw.text((x+10,y+8),'S'+str(index+1)+' clean '+str(cleanrow)+' | raw '+str(record.get('raw_row')),font=big,fill='#163d58');draw.text((x+10,y+34),str(record.get('category'))+' / '+str(record.get('format'))+' / provided',font=small,fill='#333333')
   item={'sample_id':'S'+str(index+1),'clean_row':cleanrow,'sheet_cell':{'row':index//3,'column':index%3},'locator':{key:record[key] for key in LOCATORS if key in record},'status':'pending'}
   try:
    group=next(i for i,(start,end) in enumerate(offsets) if start<=cleanrow<end);offset=cleanrow-offsets[group][0];columns=sorted({record['image_key'],record['code_key']});meta=pf.metadata.row_group(group);requested=sum(meta.column(i).total_uncompressed_size for i in range(meta.num_columns) if meta.column(i).path_in_schema.split('.')[0] in columns)
    if requested>args.max_rowgroup_mib*1024*1024:raise ValueError('selected_columns_rowgroup_bound_exceeded')
    raw=pf.read_row_group(group,columns=columns).slice(offset,1).to_pylist()[0];blob=core.image_bytes(raw[record['image_key']],source);key=record['code_key'];code=core.code_value(raw)[0] if key in ('messages','conversations','conversation') else core.text_content(raw.get(key))
    if record.get('profile'):code=core.unwrap_code(code)
    if not blob or sha(blob)!=record['image_sha256']:raise ValueError('provided_image_sha256_mismatch')
    if sha(code.encode())!=record['code_sha256']:raise ValueError('provided_code_sha256_mismatch')
    with Image.open(io.BytesIO(blob)) as image:
     if image.width*image.height>64000000:raise ValueError('provided_image_pixel_bound_exceeded')
     image.load();rgba=ImageOps.exif_transpose(image).convert('RGBA');background=Image.new('RGBA',rgba.size,'white');background.alpha_composite(rgba);thumb=ImageOps.contain(background.convert('RGB'),(576,396));canvas.paste(thumb,(x+(tile_w-thumb.width)//2,y+65+(396-thumb.height)//2));item['image_size']=list(image.size);item['image_format']=image.format
    item.update(status='ok',image_sha256_checked=True,code_sha256_checked=True,code_chars=len(code),image_bytes=len(blob),row_group=group,row_offset=offset,read_columns=columns,selected_columns_uncompressed_bytes=requested)
   except ProbeTimeout:raise
   except Exception as exc:
    allowed={'selected_columns_rowgroup_bound_exceeded','provided_image_sha256_mismatch','provided_code_sha256_mismatch','provided_image_pixel_bound_exceeded'};item.update(status='error',error_type=type(exc).__name__,reason=str(exc) if str(exc) in allowed else None);errors.append({'sample_id':item['sample_id'],'error_type':type(exc).__name__,'reason':item.get('reason')});draw.text((x+12,y+120),'ERROR - see metadata',font=small,fill='#ba1111')
   samples.append(item)
  if state(part)!=before:raise ValueError('requested_closed_shard_changed_during_probe')
  destination=root/'reports/first_closed_chart_visual';destination.mkdir(parents=True,exist_ok=True);sheet=destination/'contactsheet.jpg';metadata=destination/'samples.json';temp=sheet.with_name(sheet.name+'.tmp.'+str(os.getpid()));canvas.save(temp,format='JPEG',quality=92,optimize=True);os.replace(temp,sheet)
  result={'ok':not errors,'source_data_read_only':True,'canonical_catalogs_opened':False,'no_models_renderers_or_source_execution':True,'observed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'closed_part':PART,'footer':footer,'raw_file':RAW,'manifest_bytes_at_snapshot':initial_manifest_bytes,'manifest_prefix_bytes_scanned':scanned,'requested_clean_rows':ROWS,'samples':samples,'errors':errors,'contactsheet':str(sheet.relative_to(root)),'contactsheet_dimensions':[width,height],'contactsheet_sha256':sha(sheet.read_bytes()),'metadata_file':str(metadata.relative_to(root)),'seconds':round(time.monotonic()-began,2),'caveat':'Exactly six early-domain QA samples from a newly closed shard. Not a final canonical count, a full-stratum audit, or a guarantee of exhaustive non-web semantics or code/image rendering equivalence.'}
  temp=metadata.with_name(metadata.name+'.tmp.'+str(os.getpid()));temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');os.replace(temp,metadata);print(json.dumps({key:result[key] for key in ('ok','observed_at_utc','footer','requested_clean_rows','errors','contactsheet','contactsheet_dimensions','contactsheet_sha256','metadata_file','seconds')},ensure_ascii=False),flush=True);return int(bool(errors))
 except (ProbeTimeout,ValueError,OSError) as exc:
  known={'bounded_probe_timeout','closed_shard_footer_differs_from_requested_snapshot','closed_file_report_does_not_match_footer','selected_manifest_source_or_raw_file_mismatch','duplicate_selected_clean_row_locator','requested_manifest_locators_not_all_available_in_bounded_prefix','requested_closed_shard_changed_during_probe'};print(json.dumps({'ok':False,'error_type':type(exc).__name__,'reason':str(exc) if str(exc) in known else None,'source_data_read_only':True,'canonical_catalogs_opened':False,'seconds':round(time.monotonic()-began,2)}),flush=True);return 2
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/backup/shaoshitong/img2code_20261029'));parser.add_argument('--seconds',type=int,default=90);parser.add_argument('--max-rowgroup-mib',type=int,default=64);parser.add_argument('--max-manifest-mib',type=int,default=384);raise SystemExit(main(parser.parse_args()))
