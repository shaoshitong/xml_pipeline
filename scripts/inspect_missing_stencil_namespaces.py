#!/usr/bin/env python3
"""Read-only candidate stencil inventory from remaining native failures.
Prints metadata only. It does not fetch URLs, render, read image columns, write
reports, or modify curators/state. Candidate paths are not observed requests.
"""
import argparse,collections,copy,hashlib,html,importlib.util,json,re,sqlite3,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
MAX_XML=20*1024*1024


def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def item_id(row):
 raw=str(row.get('source_repo') or row.get('source'))+'|'+str(row.get('source_file'))+'|'+str(row.get('source_row'))
 return hashlib.sha256((raw+'|'+str(row.get('source_svg_sha256'))).encode()).hexdigest()

def namespaces(code,h):
 if not code or len(code.encode())>MAX_XML:raise ValueError('native_xml_missing_or_oversized')
 if '<!DOCTYPE' in code.upper() or '<!ENTITY' in code.upper():raise ValueError('native_xml_dtd_or_entity')
 tree=ET.fromstring(code);pages=[x for x in tree if h.localtag(x)=='diagram'] if h.localtag(tree)=='mxfile' else []
 original_pages=len(pages) if pages else 1
 if pages:
  for page in pages[1:]:tree.remove(page)
 native=h.extract_native(tree)
 if not native:raise ValueError('native_xml_cannot_normalize')
 symbols=collections.Counter()
 for node in native['tree'].iter():
  style=html.unescape(urllib.parse.unquote(node.get('style','')))
  for name in re.findall(r'(?<![A-Za-z0-9_.])mxgraph\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+)',style):symbols['mxgraph.'+name]+=1
 candidates={}
 for symbol,count in symbols.items():
  parts=symbol[len('mxgraph.'):].split('.');namespace=parts[:-1]
  for length in range(len(namespace),0,-1):
   path='/stencils/'+'/'.join(namespace[:length])+'.xml';entry=candidates.setdefault(path,{'primary':False,'symbols':set(),'occurrences':0})
   entry['primary']|=length==len(namespace);entry['symbols'].add(symbol);entry['occurrences']+=count
 return candidates,original_pages

def official_cases(root,h,source_module):
 summary_path=root/'reports/native_sources_summary.json'
 if not summary_path.is_file():return [],{'status':'summary_missing','remaining_reported':0}
 summary=json.loads(summary_path.read_text());failed=summary.get('render_rejections',[])
 if not failed:return [],{'status':'no_remaining_render_failures','remaining_reported':0}
 expected={x.get('item_id'):x for x in failed if x.get('item_id')};keyed={(x.get('source_member'),x.get('source_page_index')):x for x in failed}
 commit=summary.get('source',{}).get('commit') or source_module.COMMIT
 source,eligible,rejected,counts=source_module.inspect_archive(root/'raw/jgraph--drawio-diagrams/source.zip',commit,h)
 found=[];matched=set()
 for row in eligible:
  failure=expected.get(row['item_id']) or keyed.get((row.get('source_member'),row.get('source_page_index')))
  if failure is None:continue
  matched.add(failure.get('item_id') or (failure.get('source_member'),failure.get('source_page_index')))
  found.append((row['code'],{'group':'official_remaining','item_id':row['item_id'],'source_member':row['source_member'],'source_page_index':row['source_page_index'],'source_page_name':row.get('source_page_name'),'failure_reason':failure.get('reason')}))
 return found,{'status':'read','remaining_reported':len(failed),'matched_eligible_pages':len(found),'unmatched_reported':len(failed)-len(matched),'source_archive_sha256':source['archive_sha256'],'source_commit':source['commit']}

def core_cases(root,h):
 dbpath=root/'manifests/derived_state.sqlite'
 if not dbpath.is_file():return [],{'status':'ledger_missing','tracked_svg_candidates':0}
 with sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True) as db:
  tracked=dict(db.execute('SELECT i.item_id,r.version FROM items i JOIN render_versions r ON r.item_id=i.item_id WHERE i.status="accepted" AND i.format="svg" AND r.version LIKE ?',(h.NATIVE_RENDER_VERSION+'%',)))
 if not tracked:return [],{'status':'no_tracked_svg_candidates','tracked_svg_candidates':0}
 manifest_rows={};partial=0
 for path in sorted((root/'manifests').glob('derived.*.jsonl')):
  if '.rejected.' in path.name:continue
  for line in path.open():
   try:row=json.loads(line)
   except ValueError:partial+=1;continue
   if row.get('reason') or row.get('format',row.get('code_format'))!='svg' or not row.get('source_svg_sha256'):continue
   ident=item_id(row)
   if ident in tracked and row.get('clean_file'):manifest_rows[ident]=row
 grouped=collections.defaultdict(list)
 for ident,row in manifest_rows.items():grouped[row['clean_file']].append((int(row['clean_row']),ident,row))
 import pyarrow.parquet as pq
 cases=[];missing_payload=[];errors=[]
 for relative,targets in sorted(grouped.items()):
  path=(root/relative).resolve()
  try:path.relative_to(root)
  except ValueError:errors.append({'file':relative,'reason':'locator_outside_collection'});continue
  try:
   pf=pq.ParquetFile(path);available=set(pf.schema_arrow.names)
   columns=[x for x in ('native_drawio','source_filename','source_repo','source_file','source_row','source_svg_sha256','native_fallback_reason','render_version','code_format') if x in available]
   if 'native_drawio' not in columns:raise ValueError('native_drawio_column_missing')
   # Only code/metadata columns are loaded. Image and source SVG columns are never read.
   wanted={index:(ident,record) for index,ident,record in targets};offset=0
   for group_index in range(pf.metadata.num_row_groups):
    rows=pf.metadata.row_group(group_index).num_rows;indices=[x for x in wanted if offset<=x<offset+rows]
    if indices:
     table=pf.read_row_group(group_index,columns=columns)
     for index in indices:
      ident,record=wanted[index];payload=table.slice(index-offset,1).to_pylist()[0];code=payload.get('native_drawio')
      ref={'group':'core_tracked_svg_remaining','item_id':ident,'clean_file':relative,'clean_row':index,'source':record.get('source'),'source_filename':payload.get('source_filename'),'source_row':payload.get('source_row'),'review_key':tracked[ident],'native_fallback_reason':payload.get('native_fallback_reason') or record.get('native_xml_fallback_reason'),'native_auxiliary_issue':record.get('native_xml_auxiliary_issue')}
      if code:cases.append((code,ref))
      else:missing_payload.append({**ref,'reason':'native_drawio_payload_missing'})
    offset+=rows
  except Exception as exc:errors.append({'file':relative,'reason':type(exc).__name__+':'+str(exc)[:150]})
 return cases,{'status':'read','tracked_svg_candidates':len(tracked),'matched_manifest_items':len(manifest_rows),'loaded_native_payloads':len(cases),'manifest_items_missing':len(tracked)-len(manifest_rows),'native_payload_missing':len(missing_payload),'metadata_read_errors':errors[:10],'missing_payload_examples':missing_payload[:5],'partial_manifest_lines_skipped':partial,'columns_policy':'native_drawio and metadata only; no image, code-render, or source_svg reads'}

def main(args):
 root=args.root.resolve();script_dir=Path(__file__).resolve().parent;h=module(args.helpers or script_dir/'curate_derived.py','missing_stencil_helpers');source_module=module(args.native_sources or script_dir/'curate_native_sources.py','missing_stencil_official_sources')
 cache_path=args.runtime_cache or root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';cache=json.loads(cache_path.read_text()) if cache_path.is_file() else {};cached=set(cache.get('assets',{}))
 cases,official=official_cases(root,h,source_module);core={'status':'not_requested'}
 if not args.official_only:
  extra,core=core_cases(root,h);cases.extend(extra)
 paths={};empty=[];errors=[];by_group=collections.Counter()
 for code,ref in cases:
  by_group[ref['group']]+=1
  try:candidates,original_pages=namespaces(code,h)
  except Exception as exc:errors.append({**ref,'reason':type(exc).__name__+':'+str(exc)[:150]});continue
  if not candidates:
   if len(empty)<args.examples:empty.append(ref)
  for path,entry in candidates.items():
   aggregate=paths.setdefault(path,{'path':path,'candidate_only':True,'cached':path in cached,'case_count':0,'primary_namespace_case_count':0,'parent_prefix_only_case_count':0,'symbol_occurrences':0,'groups':collections.Counter(),'symbols':set(),'examples':[]})
   aggregate['case_count']+=1;aggregate['primary_namespace_case_count']+=bool(entry['primary']);aggregate['parent_prefix_only_case_count']+=not entry['primary'];aggregate['symbol_occurrences']+=entry['occurrences'];aggregate['groups'][ref['group']]+=1;aggregate['symbols'].update(entry['symbols'])
   if len(aggregate['examples'])<args.examples:aggregate['examples'].append({**ref,'original_native_pages':original_pages,'inspected_native_page':0})
 ordered=[]
 for path,entry in sorted(paths.items(),key=lambda item:(-item[1]['case_count'],item[0])):
  entry['groups']=dict(entry['groups']);entry['symbols']=sorted(entry['symbols'])[:12];ordered.append(entry)
 result={'read_only':True,'candidate_only':True,'no_fetch_no_render_no_image_reads':True,'candidate_method':'For style identifiers mxgraph.<namespace>.<shape>, propose /stencils/<namespace folders>.xml plus shorter namespace-prefix alternatives. These are metadata candidates, not proof of a browser request; unknown paths may return 404.','cache_id':cache.get('cache_id'),'cached_path_count':len(cached),'cached_paths':sorted(cached),'official':official,'core':core,'inspected_cases_by_group':dict(by_group),'unique_candidate_paths':len(ordered),'missing_candidate_paths':[x for x in ordered if not x['cached']],'already_cached_candidates':[x for x in ordered if x['cached']],'cases_without_style_namespaces_examples':empty,'parse_errors':errors[:10]}
 print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path);p.add_argument('--helpers',type=Path);p.add_argument('--native-sources',type=Path);p.add_argument('--runtime-cache',type=Path);p.add_argument('--official-only',action='store_true');p.add_argument('--examples',type=int,default=3);p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:
  h=module(Path(__file__).resolve().with_name('curate_derived.py'),'namespace_fixture_helpers');code='<mxfile><diagram><mxGraphModel><root><mxCell style="shape=mxgraph.office.devices.desktop;resIcon=mxgraph.aws4.ec2"/></root></mxGraphModel></diagram><diagram><mxGraphModel><root><mxCell style="shape=mxgraph.ignore.other"/></root></mxGraphModel></diagram></mxfile>';result,count=namespaces(code,h);assert count==2;assert set(result)=={'/stencils/office/devices.xml','/stencils/office.xml','/stencils/aws4.xml'};assert result['/stencils/office/devices.xml']['primary'];assert not result['/stencils/office.xml']['primary'];assert '/stencils/ignore.xml' not in result;print('{"self_test":"passed","checks":["nested namespace candidates","prefix alternatives marked","only selected first page inspected"]}')
 elif a.root:main(a)
 else:p.error('--root required')
