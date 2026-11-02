#!/usr/bin/env python3
"""Read-only metadata detail for remaining native candidates; no fetch/render/images."""
import argparse,collections,html,json,re,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path


def final_line(error):
 value=str(error or '').strip().splitlines()
 return (value[-1] if value else '')[:300]

def safe_url(url):
 try:part=urllib.parse.urlsplit(html.unescape(url))
 except ValueError:return {'scheme':'invalid'}
 if part.scheme not in ('http','https','file'):return {'scheme':part.scheme}
 keys=[]
 for token in part.query.split('&'):
  key=urllib.parse.unquote_plus(token.split('=',1)[0])
  if key and key not in keys:keys.append(key if re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}',key) else '[other]')
 return {'scheme':part.scheme,'host':part.hostname,'path':part.path[:350],'query_keys':keys[:15]}

def static_details(code,h):
 tree=ET.fromstring(code);pages=[x for x in tree if h.localtag(x)=='diagram'] if h.localtag(tree)=='mxfile' else []
 if pages:
  for page in pages[1:]:tree.remove(page)
 native=h.extract_native(tree)
 if not native:return {'error':'cannot_normalize_native'}
 fonts=set();urls={};relative_images=set()
 for node in native['tree'].iter():
  for key,value in node.attrib.items():
   value=html.unescape(urllib.parse.unquote(value))
   if key.lower() in ('fontfamily','font-family'):fonts.add(value[:100])
   fonts.update(x.strip()[:100] for x in re.findall(r'(?:^|;)fontFamily=([^;]+)',value,re.I))
   for url in re.findall(r'https?://[^\s\"\'<>;]+',value):
    item=safe_url(url);urls[json.dumps(item,sort_keys=True)]=item
   relative_images.update(x[:160] for x in re.findall(r'(?:^|;)image=((?:/?img/lib/)[^;]+)',value,re.I))
 return {'font_families_from_xml':sorted(fonts)[:20],'url_metadata':list(urls.values())[:12],'relative_builtin_image_references':sorted(relative_images)[:12],'has_embedded_data_image':bool(re.search(r'data:image/',native['code'],re.I))}

def main(args):
 root=args.root.resolve();scripts=Path(__file__).resolve().parent
 import importlib.util
 def load(path,name):
  spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
 inv=load(scripts/'inspect_missing_stencil_namespaces.py','remaining_namespace_inventory');h=load(scripts/'curate_derived.py','remaining_helpers');ns=load(scripts/'curate_native_sources.py','remaining_official_sources')
 cache_path=root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';cache=json.loads(cache_path.read_text());cached=set(cache.get('assets',{}))
 summary=json.loads((root/'reports/native_sources_summary.json').read_text());official_failure={x.get('item_id'):x for x in summary.get('render_rejections',[])}
 cases,official=inv.official_cases(root,h,ns);core_cases,core=inv.core_cases(root,h);cases.extend(core_cases);target_ids={ref['item_id'] for code,ref in core_cases};latest={}
 for path in sorted((root/'manifests').glob('derived.*.rejected.jsonl')):
  for line in path.open():
   try:row=json.loads(line)
   except ValueError:continue
   if row.get('event')!='native_upgrade_retained_existing_svg':continue
   ident=row.get('item_id') or inv.item_id(row)
   if ident in target_ids:latest[ident]=row
 details=[];counts=collections.Counter()
 for code,ref in cases:
  ident=ref['item_id'];failure=official_failure.get(ident) if ref['group']=='official_remaining' else latest.get(ident,{})
  reason=(failure or {}).get('reason') or ref.get('native_auxiliary_issue') or ref.get('native_fallback_reason')
  last=final_line((failure or {}).get('error'))
  if not last and ref.get('native_auxiliary_issue'):last=ref['native_auxiliary_issue']
  paths,_=inv.namespaces(code,h);missing=[path for path in paths if path not in cached];present=[path for path in paths if path in cached]
  counts[ref['group']+'|'+(last or reason or 'unknown')]+=1
  details.append({**ref,'current_failure_reason':reason,'current_error_last_line':last,'missing_primary_namespace_candidates':[path for path in missing if paths[path]['primary']],'missing_parent_namespace_candidates':[path for path in missing if not paths[path]['primary']],'cached_namespace_candidates':present,**static_details(code,h)})
 result={'read_only':True,'no_fetch_no_render_no_image_reads':True,'cache_id':cache.get('cache_id'),'cached_path_count':len(cached),'official':official,'core':core,'failure_counts':dict(counts),'cases':details,'note':'Namespace paths are candidates, not observed requests. Current core errors come from the latest retained-SVG diagnostic; original shard fallback text may be older.'}
 print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/backup/shaoshitong/img2code_20261029'));main(parser.parse_args())
