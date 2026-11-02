#!/usr/bin/env python3
"""HKUST-only native draw.io page -> derived PNG/XML pairs, no downloads.
Reads the already pinned official drawio-diagrams ZIP in memory. Only this
source's own shards/manifest/report are written. --plan-only renders nothing.
"""
import argparse,base64,collections,concurrent.futures,copy,fcntl,hashlib,html,importlib.util,io,json,math,os,re,stat,struct,sys,tempfile,time,xml.etree.ElementTree as ET,zipfile,zlib
from pathlib import Path,PurePosixPath

SOURCE='jgraph--drawio-diagrams'
REPO='jgraph/drawio-diagrams'
COMMIT='cc78dc2e7df8cf3ad437e6f876fbc33d2d0b7e01'
DERIVATION='official_zip_native_pages_v1'
MAX_MEMBER=20*1024*1024
MAX_TOTAL=512*1024*1024
LARGE_FIELDS={'image','code','native_drawio','source_xml','source_svg'}


def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def print_compact(summary,path):
 keys=('started_at','finished_at','counts','eligible_pages','category_counts','source_rejected','source_rejection_reasons','plan_only','accepted_pairs','reused_committed_pairs','renders_finished_this_run','render_rejected','render_rejection_reasons','processed_all_eligible_pages','manifest')
 print(json.dumps({'report':str(path),**{k:summary[k] for k in keys if k in summary}},ensure_ascii=False),flush=True)
def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):
 digest=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
 return digest.hexdigest()
def atomic_json(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()))
 with tmp.open('w') as stream:json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
 os.replace(tmp,path)
def load_helpers(path=None):
 path=Path(path) if path else Path(__file__).resolve().with_name('curate_derived.py')
 spec=importlib.util.spec_from_file_location('native_sources_derived_helpers',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for name in ('extract_native','native_asset_issue','classify','native_job','renderer_path','NATIVE_RENDER_VERSION'):
  if not hasattr(module,name):raise ValueError('required native helper missing: '+name)
 return module

def clean_member(name):
 name=name.replace('\\','/');p=PurePosixPath(name)
 if not name or p.is_absolute() or '..' in p.parts or '\x00' in name or re.match(r'^[A-Za-z]:',name):raise ValueError('unsafe_zip_member_path')
 return str(p)

def path_domain_issue(member):
 parts=PurePosixPath(member).parts
 # This is a source-specific guard for icon/mockup collections; graph nodes
 # may still use ordinary native shapes in an otherwise eligible diagram.
 if any(re.fullmatch(r'icons?|cliparts?|stencils?|wireframes?|mockups?|chemistry|chemical|molecules?|circuits?|geometry|geometric',x,re.I) for x in parts[:-1]):return 'excluded_member_directory_domain'
 if re.search(r'(?:^|[/_. -])(?:wireframe|mockup|logo|chemical|molecule|circuit|geometry)(?:s)?(?:$|[/_. -])',member,re.I):return 'excluded_member_filename_domain'
 return None

def selected_pages(tree,h):
 tag=h.localtag(tree)
 if tag=='mxGraphModel':yield 0,1,None,copy.deepcopy(tree);return
 if tag!='mxfile':raise ValueError('not_native_drawio_document')
 pages=[x for x in tree if h.localtag(x)=='diagram']
 if not pages:raise ValueError('native_document_has_no_pages')
 for index,page in enumerate(pages):
  selected=ET.Element(tree.tag,dict(tree.attrib))
  selected.append(copy.deepcopy(page))
  yield index,len(pages),page.get('name'),selected

def dimensions(native,h):
 model=next((x for x in native['tree'].iter() if h.localtag(x)=='mxGraphModel'),None)
 if model is None:raise ValueError('native_page_has_no_graph_model')
 def dim(key,default):
  try:value=float(model.get(key,default))
  except (ValueError,TypeError):raise ValueError('invalid_native_page_dimensions')
  if not math.isfinite(value) or value<=0:raise ValueError('invalid_native_page_dimensions')
  return math.ceil(value)
 width,height=dim('pageWidth',1280),dim('pageHeight',720)
 if max(width,height)>8192 or width*height>64000000:raise ValueError('native_page_canvas_exceeds_renderer_limit')
 return width,height

def guard_page(selected,member,page_name,h):
 native=h.extract_native(selected)
 if not native:raise ValueError('no_normalized_native_page')
 problem=h.native_asset_issue(native)
 if problem:raise ValueError(problem)
 # Same raster guard as the official renderer, surfaced before rendering.
 if re.search(r'data:image|https?://[^;"\s]+\.(?:png|jpe?g|webp)',native['code'],re.I):raise ValueError('native_raster_or_external_raster_dependency')
 width,height=dimensions(native,h)
 placeholder=ET.Element('svg',{'width':str(width),'height':str(height)})
 category,basis,facts=h.classify({'filename':str(PurePosixPath(member).name),'description':page_name or ''},member,placeholder,native,collections.Counter())
 if category is None:raise ValueError(basis)
 return native,width,height,category,basis,facts

def inspect_archive(archive,expected_commit,h):
 archive_sha=file_sha(archive);metadata_path=archive.parent/'extra_asset_manifest.json'
 metadata=json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
 if metadata.get('commit') and metadata['commit']!=expected_commit:raise ValueError('archive_manifest_commit_mismatch')
 if metadata.get('sha256') and metadata['sha256']!=archive_sha:raise ValueError('archive_manifest_sha256_mismatch')
 rejects=[];eligible=[];counts=collections.Counter();seen_codes={};license_record=None
 with zipfile.ZipFile(archive) as package:
  members=sorted(package.infolist(),key=lambda x:x.filename);total=sum(x.file_size for x in members)
  if total>MAX_TOTAL:raise ValueError('archive_uncompressed_total_over_512MB')
  roots={PurePosixPath(x.filename.replace('\\','/')).parts[0] for x in members if PurePosixPath(x.filename.replace('\\','/')).parts}
  root_pin=any(x=='drawio-diagrams-'+expected_commit for x in roots)
  if not root_pin and metadata.get('commit')!=expected_commit:raise ValueError('fixed_commit_not_verified_by_manifest_or_zip_root')
  for member in members:
   if member.is_dir():continue
   counts['archive_files']+=1
   try:name=clean_member(member.filename)
   except ValueError as exc:rejects.append({'member':member.filename,'reason':str(exc)});continue
   mode=member.external_attr>>16
   if stat.S_ISLNK(mode):rejects.append({'member':name,'reason':'zip_symlink_member'});continue
   if member.file_size>MAX_MEMBER:
    if PurePosixPath(name).suffix.lower() in ('.xml','.drawio','.svg'):rejects.append({'member':name,'reason':'native_member_over_20MB'})
    continue
   if PurePosixPath(name).name.lower() in ('license','license.txt','license.md'):
    data=package.read(member);text=data.decode('utf-8',errors='replace')
    if license_record is None or PurePosixPath(name).name.lower()=='license':license_record={'member':name,'sha256':sha(data),'text':text,'recognized_apache_2_0':'Apache License' in text and 'Version 2.0' in text}
   suffix=PurePosixPath(name).suffix.lower()
   if suffix not in ('.xml','.drawio','.svg'):continue
   counts['candidate_members']+=1
   issue=path_domain_issue(name)
   if issue:rejects.append({'member':name,'reason':issue});continue
   try:
    with package.open(member) as stream:data=stream.read(MAX_MEMBER+1)
    if len(data)>MAX_MEMBER:raise ValueError('native_member_over_20MB')
    text=data.decode('utf-8-sig')
    if '<!ENTITY' in text.upper() or ('<!DOCTYPE' in text.upper() and suffix!='.svg'):raise ValueError('native_xml_dtd_or_entity')
    tree=ET.fromstring(text);source_svg=None
    if h.localtag(tree)=='svg':
     h.parse_svg(text);native=h.extract_native(tree)
     if not native:raise ValueError('svg_without_embedded_native_xml')
     source_svg=text;tree=native['tree'];source_xml=native['code']
    elif h.localtag(tree) in ('mxfile','mxGraphModel'):source_xml=text
    else:raise ValueError('not_native_drawio_document')
    counts['native_documents']+=1
    for page_index,page_count,page_name,selected in selected_pages(tree,h):
     counts['source_pages']+=1
     ref={'member':name,'source_page_index':page_index,'source_page_name':page_name,'original_page_count':page_count}
     try:
      native,width,height,category,basis,facts=guard_page(selected,name,page_name,h)
      code=native['code'];code_sha=sha(code.encode())
      if code_sha in seen_codes:
       rejects.append({**ref,'reason':'duplicate_selected_xml_code','duplicate_of':seen_codes[code_sha]});continue
      item_id=sha((DERIVATION+'|'+archive_sha+'|'+expected_commit+'|'+name+'|'+str(page_index)+'|'+code_sha+'|'+h.NATIVE_RENDER_VERSION).encode())
      record={'item_id':item_id,'source':SOURCE,'source_repo':SOURCE,'source_repository':REPO,'source_repository_url':'https://github.com/'+REPO,'source_commit':expected_commit,'source_archive_sha256':archive_sha,'source_file':name,'source_member':name,'source_member_sha256':sha(data),'source_row':page_index,'source_page_index':page_index,'source_page_name':page_name,'source_filename':PurePosixPath(name).name,'native_original_page_count':page_count,'native_selected_page':0,'source_format':'drawio','source_member_format':suffix.lstrip('.'),'source_xml':code,'source_xml_sha256':code_sha,'source_xml_scope':'selected_source_page_only','source_document_xml_sha256':sha(source_xml.encode()),'source_svg':None,'source_svg_sha256':None,'code':code,'code_sha256':code_sha,'code_format':'drawio','format':'drawio','native_drawio':code,'native_drawio_scope':'selected_source_page_only','category':category,'semantic_basis':basis,'structure_json':json.dumps(facts,ensure_ascii=False),'width':width,'height':height,'derivation_version':DERIVATION,'render_version':h.NATIVE_RENDER_VERSION}
      eligible.append(record);seen_codes[code_sha]={'member':name,'source_page_index':page_index}
     except Exception as exc:rejects.append({**ref,'reason':str(exc)[:220] if isinstance(exc,ValueError) else type(exc).__name__})
   except Exception as exc:rejects.append({'member':name,'reason':str(exc)[:220] if isinstance(exc,ValueError) else type(exc).__name__})
 source={'repository':REPO,'commit':expected_commit,'archive_sha256':archive_sha,'archive_bytes':archive.stat().st_size,'commit_verification':'download_manifest_and_or_commit_named_zip_root','download_manifest_present':bool(metadata),'zip_root_matches_commit':root_pin,'license':'Apache-2.0 repository; retain original notices; third-party assets may retain separate rights','license_record':license_record,'provenance_note':'Official repository native document. Original figure authorship and original-author gold status are not verified. Images here are newly derived from the selected native XML page, not independent reference images.'}
 return source,eligible,rejects,counts

def public_record(row,relative_file,index):
 record={k:v for k,v in row.items() if k not in LARGE_FIELDS and k not in ('native_render_json','structure_json')}
 record.update({'clean_file':relative_file,'clean_row':index,'derived_file':relative_file,'derived_row':index,'image_key':'image','code_key':'code','gold_code_provenance':row['code_provenance'],'format':'drawio','structurally_complete':True,'native_xml_selected_as_code':True,'original_author_gold':False})
 record['native_render']=json.loads(row['native_render_json']);record['structure']=json.loads(row.get('structure_json') or '{}')
 return record

def rendered_row(item,result,archive_relative,source):
 if not result.get('ok'):raise ValueError('cannot_publish_failed_render')
 png=result['png'];info=result['native_render']
 if not png.startswith(b'\x89PNG') or not info.get('network_and_file_resources_blocked') or info.get('blocked_resource_requests')!=0:raise ValueError('native_renderer_evidence_invalid')
 row=dict(item);row.update({'image':{'bytes':png,'path':item['item_id']+'.png'},'image_sha256':sha(png),'width':info['output_size'][0],'height':info['output_size'][1],'source_archive':archive_relative,'source_license':source['license'],'source_license_member':(source.get('license_record') or {}).get('member'),'source_license_sha256':(source.get('license_record') or {}).get('sha256'),'original_author_gold':False,'image_provenance':'rendered_from_selected_native_drawio','code_provenance':'official_repository_native_drawio_author_unverified','pairing':'derived_from_native_drawio','render_backend':'official_offline_drawio','code_execution_checked':True,'render_validation_scope':'selected_source_page_render_only_network_and_file_resources_blocked','native_render_json':json.dumps(info,ensure_ascii=False),'render_seconds':result['seconds']})
 return row

def arrow_schema(pa):
 strings=['item_id','source','source_repo','source_repository','source_repository_url','source_commit','source_archive','source_archive_sha256','source_file','source_member','source_member_sha256','source_page_name','source_filename','source_format','source_member_format','source_xml_sha256','source_xml_scope','source_document_xml_sha256','native_drawio_scope','source_svg_sha256','code_sha256','code_format','format','category','semantic_basis','structure_json','derivation_version','render_version','image_sha256','source_license','source_license_member','source_license_sha256','image_provenance','code_provenance','pairing','render_backend','render_validation_scope','native_render_json']
 fields=[(x,pa.string()) for x in strings]+[(x,pa.large_string()) for x in ('source_xml','source_svg','code','native_drawio')]+[(x,pa.int32()) for x in ('source_page_index','native_original_page_count','native_selected_page','width','height')]+[('source_row',pa.int64()),('code_execution_checked',pa.bool_()),('original_author_gold',pa.bool_()),('render_seconds',pa.float64()),('image',pa.struct([('bytes',pa.binary()),('path',pa.string())]))]
 return pa.schema(fields)

def recover_committed(out,root,eligible_ids,source,h,pq):
 found={}
 for path in sorted(out.glob('pairs-*.parquet')):
  pf=pq.ParquetFile(path);available=set(pf.schema_arrow.names)
  if not {'item_id','derivation_version','source_archive_sha256','native_render_json'}.issubset(available):raise ValueError('own_output_contains_unrecognized_shard_schema')
  columns=[x for x in pf.schema_arrow.names if x not in LARGE_FIELDS]
  for index,row in enumerate(pq.read_table(path,columns=columns).to_pylist()):
   if row.get('item_id') not in eligible_ids or row.get('derivation_version')!=DERIVATION or row.get('source_archive_sha256')!=source['archive_sha256'] or row.get('source_commit')!=source['commit'] or row.get('render_version')!=h.NATIVE_RENDER_VERSION:continue
   if row.get('image_provenance')!='rendered_from_selected_native_drawio' or not row.get('image_sha256') or not row.get('code_sha256'):raise ValueError('own_committed_shard_contract_invalid')
   found[row['item_id']]=public_record(row,str(path.relative_to(root)),index)
 return found

def publish_manifest(path,records):
 # Only call after all referenced shards have been closed and atomically renamed.
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()))
 with tmp.open('w') as stream:
  for row in records:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
  stream.flush();os.fsync(stream.fileno())
 os.replace(tmp,path)

def main_run(args):
 root=args.root.resolve();archive=(args.archive or root/'raw'/SOURCE/'source.zip').resolve()
 if not archive.is_file():raise ValueError('already_downloaded_source_zip_missing')
 try:archive_relative=str(archive.relative_to(root))
 except ValueError:raise ValueError('source_zip_must_be_inside_remote_collection')
 if not re.fullmatch('[0-9a-f]{40}',args.commit):raise ValueError('expected_commit_must_be_40_hex')
 if not 1<=args.workers<=2 or not 1<=args.timeout<=30:raise ValueError('workers_must_be_1_or_2_and_timeout_at_most_30')
 if not 1<=args.max_side<=3072 or not 1<=args.shard_rows<=512:raise ValueError('max_side_must_be_1_to_3072_and_shard_rows_1_to_512')
 h=load_helpers(args.helpers);source,eligible,rejected,counts=inspect_archive(archive,args.commit,h)
 planned=[{k:x.get(k) for k in ('item_id','source_member','source_page_index','source_page_name','native_original_page_count','category','code_sha256','semantic_basis')} for x in eligible]
 summary={'started_at':now(),'source':source,'counts':dict(counts),'eligible_pages':len(eligible),'category_counts':dict(collections.Counter(x['category'] for x in eligible)),'source_rejected':len(rejected),'source_rejection_reasons':dict(collections.Counter(x['reason'] for x in rejected)),'plan_only':args.plan_only,'derivation_version':DERIVATION,'render_version':h.NATIVE_RENDER_VERSION,'eligible_page_inventory':planned,'source_rejections':rejected,'note':'All accepted PNGs are new renders of the selected native XML page; no independent original/reference-image pairing or original-author gold is claimed.'}
 reports=root/'reports';reports.mkdir(parents=True,exist_ok=True)
 if args.plan_only:
  atomic_json(reports/'native_sources_plan.json',summary);print_compact(summary,reports/'native_sources_plan.json');return 0
 import pyarrow as pa,pyarrow.parquet as pq
 out=root/'derived'/SOURCE;out.mkdir(parents=True,exist_ok=True);manifest=root/'manifests'/('derived.'+SOURCE+'.jsonl');lock=(out/'.native_sources.lock').open('a+')
 try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('this_native_source_curator_is_already_running')
 try:
  eligible_ids={x['item_id'] for x in eligible};records=recover_committed(out,root,eligible_ids,source,h,pq);reused=len(records)
  previous_path=reports/'native_sources_summary.json';previous=json.loads(previous_path.read_text()) if previous_path.is_file() else {};previous_failures={x['item_id']:x for x in previous.get('render_rejections',[]) if x.get('item_id') in eligible_ids} if previous.get('source',{}).get('archive_sha256')==source['archive_sha256'] else {}
  failed=[];buffer=[];buffer_bytes=0;next_part=max([int(re.fullmatch(r'pairs-(\d+)\.parquet',p.name).group(1)) for p in out.glob('pairs-*.parquet') if re.fullmatch(r'pairs-(\d+)\.parquet',p.name)]+[-1])+1;schema=arrow_schema(pa);renderer=h.renderer_path(root,args.drawio_renderer)
  def flush():
   nonlocal next_part,buffer_bytes
   if not buffer:return
   target=out/f'pairs-{next_part:05d}.parquet';tmp=target.with_name(target.name+'.tmp.'+str(os.getpid()))
   pq.write_table(pa.Table.from_pylist(buffer,schema=schema),tmp,compression='zstd')
   with tmp.open('rb') as stream:os.fsync(stream.fileno())
   os.replace(tmp,target)
   for index,row in enumerate(buffer):records[row['item_id']]=public_record(row,str(target.relative_to(root)),index)
   buffer.clear();buffer_bytes=0;next_part+=1
  pending={};finished=0
  def collect(done):
   nonlocal buffer_bytes,finished
   for future in done:
    item=pending.pop(future);finished+=1
    try:
     result=future.result()
     if not result.get('ok'):failed.append({'item_id':item['item_id'],'source_member':item['source_member'],'source_page_index':item['source_page_index'],'reason':result.get('reason'),'error':result.get('error')});continue
     row=rendered_row(item,result,archive_relative,source)
    except Exception as exc:
     failed.append({'item_id':item['item_id'],'source_member':item['source_member'],'source_page_index':item['source_page_index'],'reason':'render_result_exception','error':type(exc).__name__+':'+str(exc)[:400]});continue
    buffer.append(row);buffer_bytes+=len(result['png'])+len(item['code'].encode())+len(item['source_xml'].encode())
    # Disk/commit errors are fatal; never turn an uncommitted row into a filter rejection.
    if len(buffer)>=args.shard_rows or buffer_bytes>=32*1024*1024:flush()
   if finished and finished%25==0:print(json.dumps({'event':'native_source_progress','renders_finished':finished,'committed_or_reused_pairs':len(records),'buffered_pairs':len(buffer),'render_rejections':len(failed)}),flush=True)
  with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
   for item in eligible:
    if item['item_id'] in records:continue
    if item['item_id'] in previous_failures and not args.retry_failed:failed.append(previous_failures[item['item_id']]);continue
    future=pool.submit(h.native_job,item['code'],item['width'],item['height'],args.timeout,renderer,args.max_side);pending[future]=item
    if len(pending)>=args.workers*2:
     done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED);collect(done)
   while pending:
    done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED);collect(done)
  flush()
  ordered=[records[x['item_id']] for x in eligible if x['item_id'] in records]
  publish_manifest(manifest,ordered)
  summary.update({'plan_only':False,'finished_at':now(),'accepted_pairs':len(ordered),'reused_committed_pairs':reused,'renders_finished_this_run':finished,'render_rejected':len(failed),'render_rejection_reasons':dict(collections.Counter(x['reason'] for x in failed)),'render_rejections':failed,'manifest':str(manifest.relative_to(root)),'all_manifest_locators_committed_before_publish':True,'processed_all_eligible_pages':len(ordered)+len(failed)==len(eligible)})
  atomic_json(reports/'native_sources_summary.json',summary);print_compact(summary,reports/'native_sources_summary.json')
  return 0 if summary['processed_all_eligible_pages'] else 1
 finally:lock.close()


def self_test():
 h=load_helpers();model='<mxGraphModel pageWidth="600" pageHeight="400"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="Input x &lt; y" vertex="1"/><mxCell id="3" value="Encoder" vertex="1"/><mxCell id="4" value="Output" vertex="1"/><mxCell id="5" edge="1"/><mxCell id="6" edge="1"/></root></mxGraphModel>'
 comp=zlib.compressobj(wbits=-15);compressed=base64.b64encode(comp.compress(__import__('urllib.parse',fromlist=['quote']).quote(model).encode())+comp.flush()).decode()
 xml='<mxfile><diagram name="safe">'+model+'</diagram><diagram name="UI">'+model.replace('Input x &lt; y','login form').replace('value="Encoder"','value="Encoder" style="shape=mxgraph.mockup.browser"')+'</diagram><diagram name="compressed">'+compressed+'</diagram><diagram name="external">'+model.replace('value="Encoder"','value="Encoder" style="image=https://example.invalid/a.png"')+'</diagram><diagram name="active">'+model.replace('value="Encoder"','value="&lt;img src=x onerror=alert(1)&gt;"')+'</diagram></mxfile>'
 with tempfile.TemporaryDirectory(prefix='native-source-fixtures-') as directory:
  root=Path(directory);archive=root/'source.zip';prefix='drawio-diagrams-'+COMMIT+'/'
  with zipfile.ZipFile(archive,'w') as z:
   z.writestr(prefix+'flow.xml',xml);z.writestr(prefix+'plain.drawio',model);z.writestr(prefix+'icons/flow.xml',model);z.writestr(prefix+'geometry/triangle.xml',model);z.writestr(prefix+'LICENSE','Apache License\nVersion 2.0\n');z.writestr('../escape.xml',model)
  source,items,rejected,counts=inspect_archive(archive,COMMIT,h)
  multi=[x for x in items if x['source_member'].endswith('/flow.xml')]
  assert [x['source_page_index'] for x in multi]==[0,2],items
  assert all(x['native_original_page_count']==5 and x['native_selected_page']==0 for x in multi)
  for x in multi:
   selected=ET.fromstring(x['code']);assert len(selected.findall('diagram'))==1;assert x['source_xml']==x['code']==x['native_drawio'] and x['source_xml_scope']=='selected_source_page_only';assert x['source_svg'] is None;assert 'Input x < y' in [n.get('value') for n in selected.iter('mxCell')]
  reasons={x['reason'] for x in rejected};assert {'web_ui_or_wireframe_domain','external_drawio_image_dependency','active_drawio_html_content','excluded_member_directory_domain','unsafe_zip_member_path'}.issubset(reasons),reasons
  item=items[0];fake={'ok':True,'png':b'\x89PNG\r\n\x1a\nfixture','native_render':{'network_and_file_resources_blocked':True,'blocked_resource_requests':0,'output_size':[600,400]},'seconds':0}
  row=rendered_row(item,fake,'raw/source.zip',source);record=public_record(row,'derived/'+SOURCE+'/pairs-00000.parquet',0);assert row['code_sha256']==sha(row['code'].encode()) and row['image_sha256']==sha(fake['png']);assert record['source_page_index']==0 and record['original_author_gold'] is False and record['code_execution_checked'] is True
  try:rendered_row(item,{'ok':False},'raw/source.zip',source);raise AssertionError('failed render accepted')
  except ValueError:pass
  # A failed run never calls publish; an atomic publication names committed rows only.
  manifest=root/'manifest.jsonl';assert not manifest.exists();publish_manifest(manifest,[record]);before=manifest.read_bytes();publish_manifest(manifest,[record]);assert manifest.read_bytes()==before
  assert clean_member('a/b.xml')=='a/b.xml'
  # Exercise the real control flow with an in-memory fake Arrow adapter. This
  # tests commit/recovery/manifest ordering without requiring local datasets,
  # a local browser, or falsely claiming an actual GraphViewer render.
  import contextlib,pickle,types
  class Rows:
   def __init__(self,rows):self.rows=rows
   def to_pylist(self):return self.rows
   @classmethod
   def from_pylist(cls,rows,schema=None):return cls(rows)
  class PF:
   def __init__(self,path):
    self.rows=pickle.loads(Path(path).read_bytes());self.schema_arrow=types.SimpleNamespace(names=list(self.rows[0]) if self.rows else [])
  pa=types.ModuleType('pyarrow');pq=types.ModuleType('pyarrow.parquet')
  for name in ('string','large_string','int32','int64','bool_','float64','binary'):setattr(pa,name,lambda:None)
  pa.schema=lambda x:x;pa.struct=lambda x:x;pa.Table=Rows;pa.parquet=pq
  pq.ParquetFile=PF
  pq.read_table=lambda path,columns:Rows([{k:row.get(k) for k in columns} for row in pickle.loads(Path(path).read_bytes())])
  pq.write_table=lambda table,path,**kw:Path(path).write_bytes(pickle.dumps(table.rows))
  old_pa=sys.modules.get('pyarrow');old_pq=sys.modules.get('pyarrow.parquet');old_loader=globals()['load_helpers'];old_job=h.native_job
  sys.modules['pyarrow']=pa;sys.modules['pyarrow.parquet']=pq;globals()['load_helpers']=lambda path=None:h
  calls=[]
  def fake_native_job(*args):calls.append(args[0]);return fake
  h.native_job=fake_native_job
  args=argparse.Namespace(root=root,archive=archive,commit=COMMIT,helpers=None,drawio_renderer=None,workers=2,timeout=30,max_side=3072,shard_rows=2,plan_only=False,retry_failed=False)
  try:
   with contextlib.redirect_stdout(io.StringIO()):assert main_run(args)==0
   canonical=root/'manifests'/('derived.'+SOURCE+'.jsonl');saved=canonical.read_bytes();assert len(calls)==len(items)
   committed=list((root/'derived'/SOURCE).glob('pairs-*.parquet'));before=len(committed)
   with contextlib.redirect_stdout(io.StringIO()):assert main_run(args)==0
   assert len(calls)==len(items) and canonical.read_bytes()==saved
   canonical.unlink() # Simulate a crash after shard commit and before publication.
   with contextlib.redirect_stdout(io.StringIO()):assert main_run(args)==0
   assert canonical.read_bytes()==saved and len(calls)==len(items)
   assert len(list((root/'derived'/SOURCE).glob('pairs-*.parquet')))==before
   # A new archive generation with a simulated disk error must leave the old
   # manifest intact; the exception is fatal, not a render-filter rejection.
   with zipfile.ZipFile(archive,'a') as z:z.writestr(prefix+'new-flow.xml',model.replace('Encoder','Transformer'))
   def disk_failure(*args,**kw):raise OSError('synthetic disk failure')
   pq.write_table=disk_failure
   try:
    with contextlib.redirect_stdout(io.StringIO()):main_run(args)
    raise AssertionError('commit failure did not propagate')
   except OSError:pass
   assert canonical.read_bytes()==saved
  finally:
   h.native_job=old_job;globals()['load_helpers']=old_loader
   if old_pa is None:sys.modules.pop('pyarrow',None)
   else:sys.modules['pyarrow']=old_pa
   if old_pq is None:sys.modules.pop('pyarrow.parquet',None)
   else:sys.modules['pyarrow.parquet']=old_pq
 print(json.dumps({'self_test':'passed','fixtures':['plain native model','mixed safe/UI/compressed/external/active pages','escaped label fidelity','directory/path exclusions','failed render cannot become pair','selected XML/PNG hashes','idempotent atomic manifest publication','committed orphan shard recovery','disk failure preserves old manifest']}),flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--commit',default=COMMIT);p.add_argument('--helpers',type=Path);p.add_argument('--drawio-renderer',type=Path);p.add_argument('--plan-only',action='store_true');p.add_argument('--retry-failed',action='store_true');p.add_argument('--workers',type=int,default=2);p.add_argument('--timeout',type=int,default=30);p.add_argument('--max-side',type=int,default=3072);p.add_argument('--shard-rows',type=int,default=64);p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:self_test();return 0
 if not a.root:p.error('--root required')
 return main_run(a)
if __name__=='__main__':raise SystemExit(main())
