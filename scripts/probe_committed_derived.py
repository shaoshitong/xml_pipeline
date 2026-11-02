#!/usr/bin/env python3
"""Read-only audit of committed derived shards. Only compact metadata is printed.
No renders, models, extraction to disk, curator changes, or catalog mutations.
"""
import argparse,collections,hashlib,html,importlib.util,io,json,re,time,xml.etree.ElementTree as ET,zipfile
from pathlib import Path,PurePosixPath
VERSION='official_offline_drawio_v1'
MAX_MEMBER=20*1024*1024

def tag(x):return x.tag.rsplit('}',1)[-1]
def sha(x):return hashlib.sha256(x).hexdigest()
def page_count(tree):
 if tag(tree)=='mxfile':return len([x for x in tree if tag(x)=='diagram'])
 return 1 if tag(tree)=='mxGraphModel' else 0

def edge_binding_info(tree):
 """Informational: draw.io also allows intentional free/floating edge endpoints."""
 cells=[n for n in tree.iter() if tag(n)=='mxCell'];ids={n.get('id') for n in cells if n.get('id')};vertices={n.get('id') for n in cells if n.get('id') and n.get('vertex')=='1'};out=collections.Counter()
 out['cells']=len(cells);out['vertices']=sum(n.get('vertex')=='1' for n in cells)
 for cell in cells:
  if cell.get('edge')!='1':continue
  out['edges']+=1;source=cell.get('source');target=cell.get('target')
  out['source_attribute_present']+=bool(source);out['target_attribute_present']+=bool(target)
  out['both_endpoint_attributes_present']+=bool(source and target)
  out['source_resolves_to_cell']+=bool(source and source in ids);out['target_resolves_to_cell']+=bool(target and target in ids)
  out['both_endpoints_resolve_to_cells']+=bool(source and target and source in ids and target in ids)
  out['source_resolves_to_vertex']+=bool(source and source in vertices);out['target_resolves_to_vertex']+=bool(target and target in vertices)
  out['both_endpoints_resolve_to_vertices']+=bool(source and target and source in vertices and target in vertices)
  out['edges_with_missing_endpoint_attribute']+=not bool(source and target)
  out['edges_with_nonresolving_endpoint_attribute']+=bool((source and source not in ids) or (target and target not in ids))
 return dict(out)

class SourceArchives:
 """Each archive hash/central directory and each member XML is read at most once."""
 def __init__(self,root,helpers):self.root=root;self.helpers=helpers;self.archives={};self.members={};self.counts=collections.Counter();self._helper=None
 def helper(self):
  if self._helper is None:
   spec=importlib.util.spec_from_file_location('audit_derived_helpers',self.helpers);self._helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(self._helper)
  return self._helper
 def archive(self,relative):
  if relative in self.archives:return self.archives[relative]
  path=(self.root/relative).resolve()
  if not path.is_relative_to(self.root) or not path.is_file():raise ValueError('source_archive_missing_or_outside_collection')
  digest=hashlib.sha256()
  with path.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
  package=zipfile.ZipFile(path);names=package.namelist();metadata_path=path.parent/'extra_asset_manifest.json';metadata=json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
  info={'package':package,'sha256':digest.hexdigest(),'metadata':metadata,'roots':{PurePosixPath(x.replace('\\','/')).parts[0] for x in names if PurePosixPath(x.replace('\\','/')).parts},'names':set(names),'name_counts':collections.Counter(names)}
  self.archives[relative]=info;self.counts['archives_hashed_and_opened']+=1;self.counts['archive_bytes_hashed']+=path.stat().st_size
  return info
 def member(self,relative,name):
  key=(relative,name)
  if key in self.members:return self.members[key]
  archive=self.archive(relative);package=archive['package']
  if archive['name_counts'].get(name)!=1:raise ValueError('source_member_missing_or_ambiguous')
  member=package.getinfo(name)
  if member.file_size>MAX_MEMBER:raise ValueError('source_member_over_20MiB')
  with package.open(member) as stream:data=stream.read(MAX_MEMBER+1)
  if len(data)>MAX_MEMBER:raise ValueError('source_member_over_20MiB')
  text=data.decode('utf-8-sig');tree=ET.fromstring(text);kind=tag(tree)
  if kind=='svg':
   # Native XML in SVG exports needs the existing bounded decoding helper.
   helper=self.helper();helper.parse_svg(text);native=helper.extract_native(tree)
   if not native:raise ValueError('source_svg_has_no_embedded_native_xml')
   document=native['code'];tree=native['tree'];self.counts['svg_members_native_extracted']+=1
  elif kind in ('mxfile','mxGraphModel'):document=text
  else:raise ValueError('source_member_not_native_document')
  pages=[x for x in tree if tag(x)=='diagram'] if tag(tree)=='mxfile' else []
  info={'member_sha256':sha(data),'document_xml_sha256':sha(document.encode()),'original_page_count':page_count(tree),'page_names':[x.get('name') for x in pages] if pages else [None],'member_format':PurePosixPath(name).suffix.lower().lstrip('.')}
  self.members[key]=info;self.counts['unique_members_read']+=1;self.counts['member_bytes_read']+=len(data)
  return info
 def close(self):
  for archive in self.archives.values():archive['package'].close()

def main(args):
 import pyarrow.parquet as pq
 from PIL import Image,ImageChops
 root=args.root.resolve();started=time.time();counter=collections.Counter();issues=collections.Counter();examples={};samples={'native':[],'native_source':[],'fallback':[],'svg':[]};by_source={};shards=[];expected={};manifestcounts=collections.Counter();bindings=collections.Counter();bindings_by_source={};archives=SourceArchives(root,args.helpers or root/'scripts/curate_derived.py')
 def issue(key,ref,detail=None):
  issues[key]+=1
  if len(examples.setdefault(key,[]))<5:examples[key].append({**ref,**({'detail':detail} if detail is not None else {})})
 for p in sorted((root/'derived').glob('*/pairs-*.parquet')):
  if p.stat().st_mtime>started-args.grace_seconds:counter['fresh_shards_not_in_snapshot']+=1;continue
  try:
   pf=pq.ParquetFile(p);names=set(pf.schema_arrow.names)
   if 'render_version' not in names:counter['legacy_schema_shards_excluded']+=1;continue
   shards.append((p,pf,names));counter['new_schema_committed_shards']+=1;counter['new_schema_committed_rows']+=pf.metadata.num_rows
  except Exception as exc:issue('unreadable_committed_shard',{'file':str(p.relative_to(root))},type(exc).__name__+':'+str(exc)[:200])
 snapshot_files={str(p.relative_to(root)) for p,_,_ in shards}
 for path in sorted((root/'manifests').glob('derived.*.jsonl')):
  if '.rejected.' in path.name:continue
  with path.open() as stream:
   for line in stream:
    try:record=json.loads(line)
    except ValueError:counter['manifest_partial_or_invalid_lines']+=1;continue
    locator=record.get('clean_file') or record.get('derived_file')
    if locator not in snapshot_files:continue
    index=record.get('clean_row',record.get('derived_row'));key=(locator,index)
    if key in expected:issue('duplicate_manifest_locator',{'file':locator,'row':index})
    expected[key]=record;manifestcounts[record.get('format',record.get('code_format','unknown'))]+=1
 columns=['source_repo','source_file','source_row','source_filename','category','image','source_svg','source_svg_sha256','code','code_format','native_drawio','image_provenance','code_provenance','pairing','render_backend','width','height','semantic_basis','code_sha256','image_sha256','render_version','code_execution_checked','render_validation_scope','native_render_json','native_fallback_reason','native_original_page_count','native_selected_page','source_format','source_xml','source_xml_sha256','source_xml_scope','native_drawio_scope','source_page_index','source_page_name','source_archive','source_archive_sha256','source_member','source_member_sha256','source_member_format','source_document_xml_sha256','source_commit','source_repository','original_author_gold']
 common_fields=['source_repo','source_file','source_row','code_sha256','image_sha256','image_provenance','code_provenance','pairing','render_backend','width','height','render_version','code_execution_checked','render_validation_scope']
 native_source_fields=['source_format','source_xml_sha256','source_xml_scope','native_drawio_scope','source_page_index','source_page_name','source_archive','source_archive_sha256','source_member','source_member_sha256','source_member_format','source_document_xml_sha256','source_commit','source_repository','original_author_gold','native_original_page_count','native_selected_page','source_svg_sha256']
 for path,pf,names in shards:
  rel=str(path.relative_to(root));index=0
  for batch in pf.iter_batches(batch_size=1,columns=[x for x in columns if x in names]):
   for row in batch.to_pylist():
    ref={'file':rel,'row':index,'source':row.get('source_repo'),'source_filename':row.get('source_filename')};key=(rel,index);index+=1;fmt=row.get('code_format');native_source=row.get('source_format')=='drawio';counter['format_'+str(fmt)]+=1;source=by_source.setdefault(row.get('source_repo','unknown'),collections.Counter());source[fmt]+=1
    if row.get('render_version')==VERSION:counter['native_renderer_version_v1_rows']+=1
    record=expected.get(key)
    if record is None:issue('missing_snapshot_manifest_locator',ref)
    else:
     for field in common_fields+(native_source_fields if native_source else []):
      if record.get(field)!=row.get(field):issue('manifest_parquet_field_mismatch',ref,{'field':field,'manifest':record.get(field),'parquet':row.get(field)})
     if record.get('format',record.get('code_format'))!=fmt:issue('manifest_parquet_format_mismatch',ref)
    code=(row.get('code') or '').encode();svg=(row.get('source_svg') or '').encode();image=row.get('image') or {};blob=image.get('bytes') if isinstance(image,dict) else image
    if sha(code)!=row.get('code_sha256'):issue('selected_code_hash_mismatch',ref)
    if native_source:
     counter['native_source_rows']+=1
     if row.get('source_svg') is not None or row.get('source_svg_sha256') is not None:issue('native_source_unexpected_svg_payload',ref)
     counter['native_source_svg_hash_not_applicable']+=1
    elif sha(svg)!=row.get('source_svg_sha256'):issue('source_svg_hash_mismatch',ref)
    if not isinstance(blob,bytes):issue('image_bytes_missing',ref);continue
    if sha(blob)!=row.get('image_sha256'):issue('png_hash_mismatch',ref)
    dims=None;bbox=None
    try:
     with Image.open(io.BytesIO(blob)) as im:
      im.load();dims=list(im.size)
      if im.format!='PNG':issue('image_is_not_png',ref,im.format)
      if dims!=[row.get('width'),row.get('height')]:issue('png_dimensions_mismatch',ref,{'png':dims,'row':[row.get('width'),row.get('height')]})
      rgb=im.convert('RGB');bbox=ImageChops.difference(rgb,Image.new('RGB',im.size,'white')).getbbox()
      if not bbox:issue('blank_white_png',ref)
    except Exception as exc:issue('png_decode_error',ref,type(exc).__name__+':'+str(exc)[:200])
    sample={**ref,'category':row.get('category'),'format':fmt,'image_provenance':row.get('image_provenance'),'code_provenance':row.get('code_provenance'),'render_backend':row.get('render_backend'),'render_version':row.get('render_version'),'code_execution_checked':row.get('code_execution_checked'),'pairing':row.get('pairing'),'png_size':dims,'png_bytes':len(blob),'nonwhite_bbox':bbox,'native_original_page_count':row.get('native_original_page_count'),'native_selected_page':row.get('native_selected_page')}
    if fmt=='drawio':
     counter['native_xml_pairs']+=1
     conditions={'image_provenance':('rendered_from_selected_native_drawio',row.get('image_provenance')),'pairing':('derived_from_native_drawio',row.get('pairing')),'code_provenance':('official_repository_native_drawio_author_unverified' if native_source else 'embedded_exporter_drawio_author_unverified',row.get('code_provenance')),'render_backend':('official_offline_drawio',row.get('render_backend')),'render_version':(VERSION,row.get('render_version')),'selected_page':(0,row.get('native_selected_page')),'render_checked':(True,row.get('code_execution_checked'))}
     if native_source:
      conditions.update({'source_xml_scope':('selected_source_page_only',row.get('source_xml_scope')),'native_drawio_scope':('selected_source_page_only',row.get('native_drawio_scope')),'original_author_gold':(False,row.get('original_author_gold')),'render_validation_scope':('selected_source_page_render_only_network_and_file_resources_blocked',row.get('render_validation_scope'))})
      if row.get('source_xml')!=row.get('code'):issue('native_selected_source_xml_differs_from_code',ref)
      if sha((row.get('source_xml') or '').encode())!=row.get('source_xml_sha256') or row.get('source_xml_sha256')!=row.get('code_sha256'):issue('native_selected_source_xml_hash_mismatch',ref)
      if row.get('native_drawio')!=row.get('code'):issue('native_selected_aux_xml_differs_from_code',ref)
      page_index=row.get('source_page_index');total=row.get('native_original_page_count')
      if not isinstance(page_index,int) or isinstance(page_index,bool) or not isinstance(total,int) or isinstance(total,bool) or not 0<=page_index<total:issue('native_original_page_index_out_of_bounds',ref,{'index':page_index,'page_count':total})
      sample.update({'source_page_index':page_index,'source_member':row.get('source_member'),'source_xml_scope':row.get('source_xml_scope')})
      if args.skip_source_archives:counter['native_source_archive_verification_skipped']+=1
      else:
       try:
        archive=archives.archive(row.get('source_archive') or '');member=archives.member(row.get('source_archive') or '',row.get('source_member') or '')
        for field,want,have in [('source_archive_sha256',row.get('source_archive_sha256'),archive['sha256']),('source_member_sha256',row.get('source_member_sha256'),member['member_sha256']),('source_document_xml_sha256',row.get('source_document_xml_sha256'),member['document_xml_sha256']),('native_original_page_count',total,member['original_page_count']),('source_member_format',row.get('source_member_format'),member['member_format'])]:
         if want!=have:issue('native_source_archive_metadata_mismatch',ref,{'field':field,'parquet':want,'archive':have})
        commit=row.get('source_commit');metadata=archive['metadata'];root_pin=bool(commit and 'drawio-diagrams-'+commit in archive['roots'])
        if not isinstance(commit,str) or not re.fullmatch('[0-9a-f]{40}',commit) or not (root_pin or metadata.get('commit')==commit):issue('native_source_commit_not_verified',ref)
        if metadata.get('sha256') and metadata['sha256']!=archive['sha256']:issue('native_source_download_manifest_archive_sha_mismatch',ref)
        if metadata.get('commit') and metadata['commit']!=commit:issue('native_source_download_manifest_commit_mismatch',ref)
        if isinstance(page_index,int) and 0<=page_index<len(member['page_names']) and member['page_names'][page_index]!=row.get('source_page_name'):issue('native_source_original_page_name_mismatch',ref)
        counter['native_source_archive_row_checks']+=1
       except Exception as exc:issue('native_source_archive_verification_error',ref,type(exc).__name__+':'+str(exc)[:200])
     for field,(want,have) in conditions.items():
      if have!=want:issue('native_contract_mismatch',ref,{'field':field,'expected':want,'actual':have})
     try:
      tree=ET.fromstring(code);pages=[x for x in tree if tag(x)=='diagram'] if tag(tree)=='mxfile' else [];selected_count=page_count(tree)
      if selected_count!=1:issue('selected_native_not_exactly_one_page',ref,selected_count)
      labels=[]
      for n in tree.iter():
       if tag(n)=='mxCell':
        value=' '.join(re.sub('<[^>]*>',' ',html.unescape(n.get('value',''))).split())
        if value and value not in labels:labels.append(value[:160])
      coverage=edge_binding_info(tree);bindings.update(coverage);bindings_by_source.setdefault(row.get('source_repo','unknown'),collections.Counter()).update(coverage)
      sample.update({'labels_first_12':labels[:12],'selected_page_count':selected_count,'selected_page_name':pages[0].get('name') if pages else None,'edge_binding_information':coverage})
      if row.get('native_drawio') and not native_source:
       aux=ET.fromstring(row['native_drawio']);actual_original=page_count(aux)
       if row.get('native_original_page_count')!=actual_original:issue('native_original_page_count_mismatch',ref,{'metadata':row.get('native_original_page_count'),'actual_aux':actual_original})
     except Exception as exc:issue('native_xml_parse_error',ref,type(exc).__name__+':'+str(exc)[:200])
     try:
      info=json.loads(row.get('native_render_json') or '{}');sample['selected_image']=info.get('selected_image');sample['viewer_bundle_sha256']=info.get('viewer_bundle_sha256');sample['graph_bounds']=info.get('graphBounds')
      if not info.get('network_and_file_resources_blocked') or info.get('blocked_resource_requests')!=0:issue('native_offline_contract_mismatch',ref,{'network_blocked':info.get('network_and_file_resources_blocked'),'blocked_requests':info.get('blocked_resource_requests')})
      if info.get('output_size')!=dims:issue('native_renderer_png_size_mismatch',ref,{'renderer':info.get('output_size'),'png':dims})
      if not info.get('viewer_bundle_sha256'):issue('native_viewer_sha_missing',ref)
      if record is not None and record.get('native_render')!=info:issue('manifest_native_render_evidence_mismatch',ref)
     except ValueError:issue('native_renderer_json_invalid',ref)
     sample_group='native_source' if native_source else 'native'
     if len(samples[sample_group])<args.samples:samples[sample_group].append(sample)
    else:
     counter['svg_pairs']+=1
     if native_source:issue('native_source_code_format_not_drawio',ref,fmt)
     if code!=svg:issue('selected_svg_code_differs_from_source_svg',ref)
     if row.get('image_provenance')!='rendered_from_source_svg' or row.get('pairing')!='derived_from_source_svg':issue('svg_contract_mismatch',ref)
     fallback=row.get('native_fallback_reason')
     if fallback:
      counter['native_fallback_rows']+=1;counter['fallback_'+fallback]+=1;sample['fallback_reason']=fallback
      if record is not None and record.get('native_xml_fallback_reason')!=fallback:issue('fallback_reason_manifest_mismatch',ref,{'parquet':fallback,'manifest':record.get('native_xml_fallback_reason')})
      if row.get('code_provenance')!='dataset_svg':issue('fallback_still_claims_native_provenance',ref)
      if len(samples['fallback'])<args.samples:samples['fallback'].append(sample)
     elif len(samples['svg'])<min(args.samples,3):samples['svg'].append(sample)
    counter['png_and_selected_code_hashes_checked']+=1
 archives.close()
 binding_report={'informational_only':True,'note':'Floating/unbound edge terminals can be intentional; these counts alone do not create audit issues.','counts':dict(bindings),'by_source':{k:dict(v) for k,v in bindings_by_source.items()}}
 report={'snapshot_started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(started)),'read_only':True,'scope':'New-schema committed derived shards, excluding files newer than grace period; old canonical manifest is not used. No model calls or render reruns. Source archives are read only and cached.','grace_seconds':args.grace_seconds,'counts':dict(counter),'manifest_format_counts':dict(manifestcounts),'by_source':{k:dict(v) for k,v in by_source.items()},'source_archive_cache':dict(archives.counts),'edge_binding_information':binding_report,'issue_counts':dict(issues),'issue_examples':examples,'metadata_samples':samples,'seconds':round(time.time()-started,2)}
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/backup/shaoshitong/img2code_20261029'));p.add_argument('--samples',type=int,default=6);p.add_argument('--grace-seconds',type=int,default=5);p.add_argument('--helpers',type=Path);p.add_argument('--skip-source-archives',action='store_true');main(p.parse_args())
