#!/usr/bin/env python3
"""Cache pinned official draw.io runtime stencils on HKUST only."""
import argparse,hashlib,json,os,time,urllib.parse,xml.etree.ElementTree as ET,zipfile
from pathlib import Path,PurePosixPath
import requests
VERSION='v32.6.1'
COMMIT='84487b4891cbc0f32d7e30f34cf878c87cb1f414'
WAR_SHA='44dd56958c8408963457dc98f04d2228408ac145c7aa1d8e6895d9c88d5e42aa'
WAR_SIZE=48958551
VIEWER_SHA='0c12ccf10dcaf0d0ef40ca60a5bc881ba27b57e076797ee39bce46602371f769'
URL='https://github.com/jgraph/drawio/releases/download/v32.6.1/draw.war'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def atomic(p,data):
 p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.tmp.'+str(os.getpid()))
 with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 temp.replace(p)
def download(path):
 if path.is_file() and path.stat().st_size==WAR_SIZE and digest(path)==WAR_SHA:return
 part=path.with_suffix('.war.part')
 for attempt in range(4):
  proxy=('http://127.0.0.1:7890' if attempt%2==0 else 'http://127.0.0.1:18997')
  offset=part.stat().st_size if part.exists() else 0
  if offset>WAR_SIZE:raise ValueError('runtime_partial_file_exceeds_expected_size')
  if offset==WAR_SIZE:break
  session=requests.Session();session.trust_env=False
  try:
   headers={'User-Agent':'img2code-pinned-runtime-cache/1.0','Cache-Control':'no-cache'}
   if offset:headers['Range']='bytes='+str(offset)+'-'
   response=session.get(URL+'?download=1&task_cache='+str(time.time_ns()),headers=headers,proxies={'http':proxy,'https':proxy},stream=True,timeout=(12,25))
   if response.status_code not in (200,206):raise ValueError('http_status_'+str(response.status_code))
   if response.status_code==206 and not response.headers.get('Content-Range','').startswith('bytes '+str(offset)+'-'):raise ValueError('unexpected_content_range')
   discard=offset if response.status_code==200 else 0
   with part.open('ab') as f:
    for chunk in response.iter_content(1024*1024):
     if discard:
      skip=min(discard,len(chunk));discard-=skip;chunk=chunk[skip:]
     if chunk:f.write(chunk)
     if f.tell()>WAR_SIZE:raise ValueError('runtime_response_exceeds_expected_size')
   response.close()
   if part.stat().st_size==WAR_SIZE:break
  except Exception as exc:
   print(json.dumps({'event':'runtime_download_retry','attempt':attempt+1,'error_type':type(exc).__name__,'saved_bytes':part.stat().st_size if part.exists() else 0}),flush=True)
   time.sleep(2)
  finally:session.close()
 if not part.is_file() or part.stat().st_size!=WAR_SIZE or digest(part)!=WAR_SHA:raise ValueError('pinned_runtime_archive_size_or_sha256_mismatch')
 part.replace(path)
def fetch_cdn_stencil(name):
 url='https://viewer.diagrams.net/stencils/'+name
 last=None
 for proxy in ('http://127.0.0.1:7890','http://127.0.0.1:18997'):
  s=requests.Session();s.trust_env=False
  try:
   r=s.get(url,proxies={'http':proxy,'https':proxy},headers={'User-Agent':'Mozilla/5.0'},timeout=(8,15))
   if r.status_code!=200:raise ValueError('stencil_http_status_'+str(r.status_code))
   data=r.content
   if len(data)>20*1024*1024 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('invalid_cdn_stencil_size_or_dtd')
   if ET.fromstring(data).tag.rsplit('}',1)[-1]!='shapes':raise ValueError('unexpected_cdn_stencil_root')
   return data,{'source_url':url,'source_kind':'official_viewer_CDN_content_pinned_snapshot','etag':r.headers.get('ETag'),'last_modified':r.headers.get('Last-Modified'),'source_commit_verified':False}
  except Exception as exc:last=type(exc).__name__
  finally:s.close()
 raise ValueError('cdn_stencil_fetch_failed_'+str(last))
def main(root):
 root=root.resolve();assets=root/'evaluation/assets';base=assets/'drawio-runtime-v32.6.1';base.mkdir(parents=True,exist_ok=True)
 viewer=assets/'viewer-static.min.js'
 if not viewer.is_file() or digest(viewer)!=VIEWER_SHA:raise ValueError('cached_viewer_version_or_sha_mismatch')
 existing=base/'manifest.json'
 if existing.is_file():
  previous=json.loads(existing.read_text());records=previous.get('assets',{})
  valid=previous.get('viewer_bundle_sha256')==VIEWER_SHA and {'/stencils/flowchart.xml','/stencils/aws4.xml'}.issubset(records)
  for record in records.values():
   item=base/record['cache_file']
   valid=valid and item.resolve().is_relative_to(base.resolve()) and not item.is_symlink() and item.is_file() and digest(item)==record['sha256']
  if valid:
   print(json.dumps({'status':'already_complete','manifest':str(existing),'cache_id':previous['cache_id'],'stencil_files':len(records),'expanded_cache_preserved':True}),flush=True);return
 war=base/'draw.war';download(war);entries={};licenses=[]
 with zipfile.ZipFile(war) as package:
  bad=package.testzip()
  if bad:raise ValueError('pinned_war_crc_failure')
  for item in package.infolist():
   name=item.filename;p=PurePosixPath(name)
   if not name.startswith('stencils/') or item.is_dir():continue
   if p.is_absolute() or '..' in p.parts or '\\' in name or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('unsafe_runtime_archive_member')
   is_xml=name.lower().endswith('.xml');is_license=p.name.lower().startswith(('license','notice','readme'))
   if not (is_xml or is_license):continue
   if item.file_size>20*1024*1024:raise ValueError('runtime_asset_over_20MB')
   data=package.read(item);target=base/name
   if target.is_symlink() or not target.resolve().is_relative_to(base.resolve()):raise ValueError('unsafe_runtime_cache_target')
   sha=hashlib.sha256(data).hexdigest()
   if is_xml:
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('runtime_stencil_dtd_or_entity')
    tree=ET.fromstring(data)
    if tree.tag.rsplit('}',1)[-1]!='shapes':raise ValueError('unexpected_runtime_stencil_root_'+tree.tag)
    entries['/'+name]={'cache_file':name,'sha256':sha,'bytes':len(data),'archive_member':name}
   else:licenses.append({'cache_file':name,'sha256':sha,'bytes':len(data)})
   if not target.is_file() or digest(target)!=sha:atomic(target,data)
 # The official WAR intentionally omits these libraries; GraphViewer loads
 # them from its official CDN. Preserve their actual origin rather than
 # falsely attributing CDN bytes to the release Git commit.
 for name in ('flowchart.xml','aws4.xml'):
  key='/stencils/'+name
  if key in entries:continue
  data,origin=fetch_cdn_stencil(name);relative='stencils/'+name
  atomic(base/relative,data)
  entries[key]={'cache_file':relative,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),**origin}
 basis={'version':VERSION+' viewer + official CDN stencil snapshot','commit':None,'viewer_release_commit':COMMIT,'archive_sha256':WAR_SHA,'archive_role':'release reference and license source; CDN stencil bytes are pinned separately','stencil_source_kind':'official_viewer_CDN_content_pinned_snapshot','viewer_bundle_sha256':VIEWER_SHA,'assets':entries}
 cache_id=hashlib.sha256(json.dumps(basis,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 manifest={**basis,'cache_id':cache_id,'status':'complete','created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_url':URL,'github_asset_id':669900622,'archive_bytes':WAR_SIZE,'archive_file':'draw.war','licenses':licenses,
  'runtime_scope':'Official version-pinned stencil XML served from local bytes only for exact viewer.diagrams.net/stencils paths; no arbitrary external resources.'}
 atomic(base/'manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps({'status':'complete','manifest':str(base/'manifest.json'),'cache_id':cache_id,'stencil_files':len(entries),'stencil_bytes':sum(x['bytes'] for x in entries.values()),'license_files':len(licenses),'archive_sha256':WAR_SHA}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root)
