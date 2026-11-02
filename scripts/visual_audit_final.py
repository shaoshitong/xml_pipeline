#!/usr/bin/env python3
"""Final remote-only stratified visual QA. Prepares no samples until fresh final
catalog + completed hash audit exist. Never executes dataset code or changes it.
Contactsheets remain on HKUST; JSON contains locators/provenance, never code text.
"""
import argparse,collections,datetime,hashlib,importlib.util,io,json,math,os,random,signal,time
from pathlib import Path

LOCATOR_FIELDS=('catalog_kind','source','category','format','clean_file','clean_row','image_key','code_key','image_file','reference_image','code_file','asset_root','image_sha256','code_sha256','source_manifest','source_manifest_line','raw_file','raw_row','profile','pairing','image_provenance','gold_code_provenance','code_provenance','provenance','alignment_verification','render_backend','render_version','code_execution_checked','render_validation_scope','source_page_index','source_page_name','native_original_page_count','native_selected_page','source_archive','source_member','source_archive_sha256','source_member_sha256','source_document_xml_sha256','original_author_gold')
ACTIVE_SCRIPTS={'curate_pairs.py','curate_archives.py','curate_derived.py','curate_native_sources.py','finalize_catalog.py'}
class AuditTimeout(Exception):pass

def utc(value):
 if not value:return None
 return datetime.datetime.fromisoformat(str(value).replace('Z','+00:00')).replace(tzinfo=datetime.timezone.utc).timestamp()
def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def sha(blob):return hashlib.sha256(blob).hexdigest()
def fingerprint(path):
 s=path.stat();return (s.st_size,s.st_mtime_ns,s.st_ino)
def owned_active_curators(root):
 out=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   if proc.stat().st_uid!=os.getuid():continue
   args=[value.decode(errors='replace') for value in (proc/'cmdline').read_bytes().split(b'\0') if value]
   found=[Path(value).name for value in args if Path(value).name in ACTIVE_SCRIPTS and str(root/'scripts') in value]
   if found:out.append({'pid':int(proc.name),'script':found[0]})
  except (OSError,ValueError):pass
 return out

def readiness(root,after):
 active=owned_active_curators(root)
 if active:return {'ready':False,'reason':'owned_curators_still_running','active':active}
 reports={}
 for name in ('summary.json','archive_summary.json','catalog_summary.json','content_audit.json'):
  path=root/'reports'/name
  try:reports[name]=json.loads(path.read_text())
  except (OSError,ValueError):return {'ready':False,'reason':'final_report_unavailable','report':name}
 catalog=reports['catalog_summary.json'];audit=reports['content_audit.json']
 try:
  if not utc(catalog.get('finished_at')) or utc(catalog.get('created_at'))<after:return {'ready':False,'reason':'catalog_not_fresh_after_cutoff'}
  for name in ('summary.json','archive_summary.json'):
   finished=utc(reports[name].get('finished_at'))
   if finished is None or finished<after or finished>utc(catalog.get('created_at'))+2:return {'ready':False,'reason':'curation_report_not_final_before_catalog','report':name}
  if not audit.get('ok') or not utc(audit.get('finished_at')) or utc(audit.get('finished_at'))<utc(catalog['finished_at']):return {'ready':False,'reason':'fresh_successful_content_hash_audit_required'}
 except (TypeError,ValueError):return {'ready':False,'reason':'invalid_final_report_timestamp'}
 return {'ready':True,'catalog_finished_at':catalog['finished_at'],'hash_audit_finished_at':audit['finished_at'],'catalog':catalog,'expected_manifest_sha256':audit.get('input_manifest_sha256',{})}

def select_records(path,kind,per_stratum,seed,expected_sha):
 rng=random.Random(seed);seen=collections.Counter();groups=collections.defaultdict(list);digest=hashlib.sha256();before=fingerprint(path)
 with path.open('rb') as stream:
  for line in stream:
   digest.update(line)
   if not line.strip():continue
   if not line.endswith(b'\n'):raise ValueError('canonical_partial_line')
   record=json.loads(line)
   if record.get('catalog_kind')!=kind:raise ValueError('canonical_kind_mismatch')
   key=(kind,record['source'],record['category'],record['format']);seen[key]+=1
   if len(groups[key])<per_stratum:groups[key].append(record)
   else:
    position=rng.randrange(seen[key])
    if position<per_stratum:groups[key][position]=record
 if fingerprint(path)!=before:raise ValueError('canonical_changed_during_selection')
 if not expected_sha or digest.hexdigest()!=expected_sha:raise ValueError('canonical_hash_differs_from_completed_content_audit')
 return groups,seen,{'sha256':digest.hexdigest(),'bytes':before[0],'mtime_ns':before[1],'rows':sum(seen.values()),'fingerprint':before}

def read_pair(record,root,core,pq,max_rowgroup):
 if record.get('clean_file'):
  path=(root/record['clean_file']).resolve()
  if not path.is_relative_to(root):raise ValueError('parquet_locator_outside_collection')
  pf=pq.ParquetFile(path);offset=record['clean_row'];group=0
  if not isinstance(offset,int) or offset<0:raise ValueError('invalid_clean_row')
  while group<pf.metadata.num_row_groups and offset>=pf.metadata.row_group(group).num_rows:offset-=pf.metadata.row_group(group).num_rows;group+=1
  if group>=pf.metadata.num_row_groups:raise ValueError('clean_row_out_of_bounds')
  columns=sorted({record['image_key'],record['code_key']});meta=pf.metadata.row_group(group);requested=sum(meta.column(i).total_uncompressed_size for i in range(meta.num_columns) if meta.column(i).path_in_schema.split('.')[0] in columns)
  if requested>max_rowgroup:raise ValueError('selected_columns_rowgroup_exceeds_bound')
  row=pf.read_row_group(group,columns=columns).slice(offset,1).to_pylist()[0];data=core.image_bytes(row[record['image_key']],root/'raw'/record['source']);key=record['code_key'];code=core.code_value(row)[0] if key in ('messages','conversations','conversation') else core.text_content(row.get(key))
  if record.get('profile'):code=core.unwrap_code(code)
  return data,code,{'parquet_footer_rows':pf.metadata.num_rows,'row_group':group,'row_offset':offset,'read_columns':columns,'selected_column_uncompressed_bytes':requested}
 image=(root/(record.get('reference_image') or record.get('image_file') or '')).resolve();codefile=(root/(record.get('code_file') or '')).resolve()
 if not image.is_relative_to(root) or not codefile.is_relative_to(root):raise ValueError('standalone_locator_outside_collection')
 if image.stat().st_size>64*1024*1024 or codefile.stat().st_size>20*1024*1024:raise ValueError('standalone_sample_exceeds_bound')
 return image.read_bytes(),codefile.read_text(),{'standalone':True}

def main(args):
 import pyarrow.parquet as pq
 from PIL import Image,ImageDraw,ImageFont,ImageOps
 root=args.root.resolve();after=utc(args.after_utc);state=readiness(root,after)
 if not state['ready']:print(json.dumps(state),flush=True);return 2
 began=time.monotonic();deadline=began+args.seconds;spec=importlib.util.spec_from_file_location('visual_final_core',root/'scripts/curate_pairs.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
 groups={};seen=collections.Counter();snapshots={};paths={'provided':root/'clean/manifest.jsonl','derived':root/'derived/manifest.jsonl'}
 for kind,path in paths.items():
  # Old full-content auditor labels its provided input hash as 'clean'.
  expected=state['expected_manifest_sha256'].get('clean' if kind=='provided' else 'derived');chosen,counts,snapshot=select_records(path,kind,args.per_stratum,args.seed,expected);groups.update(chosen);seen.update(counts);snapshots[kind]=snapshot
  if snapshot['rows']!=state['catalog']['groups'][kind]['pairs']:raise ValueError('manifest_rows_differ_from_final_catalog')
 samples=[(key,row) for key,rows in sorted(groups.items()) for row in rows];dest=(root/args.output).resolve()
 if not dest.is_relative_to(root/'reports'):raise ValueError('output_must_be_under_collection_reports')
 dest.mkdir(parents=True,exist_ok=True)
 try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
 except OSError:font=ImageFont.load_default()
 inventory=[];sheets=[];errors=[];successful=collections.Counter();page=None;sheet=None
 def expired(signum,frame):raise AuditTimeout('bounded_visual_audit_timeout')
 previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(0.1,deadline-time.monotonic()))
 try:
  for index,(key,record) in enumerate(samples):
   if index%12==0:
    page=Image.new('RGB',(1800,1120),'#e5e5e5');draw=ImageDraw.Draw(page);draw.text((8,5),'FINAL VISUAL SAMPLE | provided and derived separated | no exhaustive semantic guarantee',font=font,fill='black')
   x=(index%4)*450;y=40+((index//4)%3)*360;image_provenance=record.get('image_provenance') or record.get('provenance') or 'unspecified';code_provenance=record.get('gold_code_provenance') or record.get('code_provenance') or record.get('provenance') or 'unspecified'
   title=str(index).zfill(3)+' '+key[0]+' '+key[2]+' '+key[3]+'\n'+key[1][:58]+'\nimg: '+image_provenance[:57];draw.multiline_text((x+6,y+5),title,font=font,fill='black')
   item={'sample_id':index,'stratum':{'kind':key[0],'source':key[1],'category':key[2],'format':key[3]},'stratum_population':seen[key],'sheet':'sheet_'+str(index//12).zfill(2)+'.jpg','sheet_cell':{'row':(index//4)%3,'column':index%4},'image_provenance':image_provenance,'code_provenance':code_provenance,'locator':{name:record[name] for name in LOCATOR_FIELDS if name in record},'status':'pending'}
   try:
    data,code,readmeta=read_pair(record,root,core,pq,args.max_rowgroup_mib*1024*1024)
    if not data or sha(data)!=record['image_sha256']:raise ValueError('sample_image_hash_mismatch')
    if code is None or sha(code.encode())!=record['code_sha256']:raise ValueError('sample_code_hash_mismatch')
    with Image.open(io.BytesIO(data)) as image:
     if image.width*image.height>64000000:raise ValueError('sample_pixel_bound_exceeded')
     image.load();oriented=ImageOps.exif_transpose(image).convert('RGBA');background=Image.new('RGBA',oriented.size,'white');background.alpha_composite(oriented);thumb=ImageOps.contain(background.convert('RGB'),(438,280));page.paste(thumb,(x+(450-thumb.width)//2,y+72+(280-thumb.height)//2));item['image_size']=list(image.size)
    item.update(status='ok',code_chars=len(code),read_metadata=readmeta);successful[key]+=1
   except AuditTimeout:raise
   except Exception as exc:
    # No exception message can accidentally include raw source/image bytes.
    item.update(status='read_error',error_type=type(exc).__name__,reason=str(exc) if str(exc) in {'sample_image_hash_mismatch','sample_code_hash_mismatch','selected_columns_rowgroup_exceeds_bound','sample_pixel_bound_exceeded'} else None);errors.append({'sample_id':index,'stratum':item['stratum'],'error_type':type(exc).__name__,'reason':item.get('reason')});draw.text((x+10,y+100),'READ ERROR - see metadata',font=font,fill='red')
   inventory.append(item)
   if index%12==11 or index==len(samples)-1:
    sheet=dest/('sheet_'+str(index//12).zfill(2)+'.jpg');page.save(sheet,quality=91);sheets.append(str(sheet.relative_to(root)))
 except AuditTimeout:errors.append({'reason':'bounded_visual_audit_timeout','planned':len(samples),'completed':len(inventory)})
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
 for kind,path in paths.items():
  if fingerprint(path)!=tuple(snapshots[kind]['fingerprint']):errors.append({'reason':'canonical_changed_after_selection','kind':kind})
 strata=[{'kind':key[0],'source':key[1],'category':key[2],'format':key[3],'population':seen[key],'sampled':len(groups[key]),'successful_images':successful[key]} for key in sorted(groups)]
 result={'ok':not errors and len(inventory)==len(samples),'started_utc':datetime.datetime.fromtimestamp(time.time()-(time.monotonic()-began),datetime.timezone.utc).isoformat(),'finished_utc':now(),'seed':args.seed,'sampling':'Up to '+str(args.per_stratum)+' deterministic reservoir samples in EVERY final source/category/format/kind stratum; no format allowlist.','after_utc':args.after_utc,'catalog_finished_at':state['catalog_finished_at'],'full_hash_audit_finished_at':state['hash_audit_finished_at'],'input_manifests':{kind:{name:value for name,value in meta.items() if name!='fingerprint'} for kind,meta in snapshots.items()},'samples_planned':len(samples),'samples_completed':len(inventory),'strata':strata,'stratum_count':len(groups),'read_errors':errors,'sheets':sheets,'metadata_file':str((dest/'sample_locators.json').relative_to(root)),'seconds':round(time.monotonic()-began,2),'source_data_read_only':True,'no_models_renders_or_dataset_code_execution':True,'caveats':['Provided includes provider-supplied, synthetic, and reconstructed pairs; it does not mean original-author gold. Derived renders remain a separate kind. Individual image/code provenance is retained.','This bounded visual sample can expose web/geometry/misclassification examples but cannot guarantee exhaustive domain correctness, dependency completeness, or reference/code rendering equivalence. Full hash audit verifies stored bytes/locators, not complete semantics.','No dataset source prefix or image bytes appear in the JSON metadata. Images/contact sheets remain on HKUST.']}
 (dest/'sample_locators.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n');(dest/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({key:result[key] for key in ('ok','finished_utc','seed','samples_planned','samples_completed','stratum_count','read_errors','sheets','metadata_file','seconds')},ensure_ascii=False),flush=True);return int(not result['ok'])
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/backup/shaoshitong/img2code_20261029'));parser.add_argument('--after-utc',required=True);parser.add_argument('--seed',type=int,default=20261030);parser.add_argument('--per-stratum',type=int,default=2);parser.add_argument('--seconds',type=int,default=180);parser.add_argument('--max-rowgroup-mib',type=int,default=128);parser.add_argument('--output',default='reports/visual_audit_final');raise SystemExit(main(parser.parse_args()))
