"""Add content-pinned official CDN stencil candidates without changing old assets."""
import argparse,concurrent.futures,hashlib,importlib.util,json,re,time
from pathlib import Path

def main(root,candidates):
 spec=importlib.util.spec_from_file_location('cache_installer',Path(__file__).with_name('cache_drawio_stencils.py'))
 tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
 base=root/'evaluation/assets/drawio-runtime-v32.6.1';path=base/'manifest.json';old=path.read_bytes();manifest=json.loads(old);assets=manifest['assets']
 for record in assets.values():
  p=base/record['cache_file']
  if not p.is_file() or tool.digest(p)!=record['sha256']:raise ValueError('existing_runtime_asset_integrity_failure')
 data=json.loads(candidates.read_text());items=data.get('missing_candidate_paths',[]) if isinstance(data,dict) else data
 wanted=[]
 for record in items:
  name=record['path'] if isinstance(record,dict) else record
  if isinstance(record,dict) and not record.get('primary_namespace_case_count'):continue
  if not re.fullmatch(r'/stencils/[A-Za-z0-9_./-]+\.xml',name) or any(x in ('','..','.') for x in name.split('/')[2:]):raise ValueError('invalid_stencil_candidate_path')
  if name not in assets:wanted.append(name)
 failures=[];added=[]
 def fetch(name):
  try:return name,*tool.fetch_cdn_stencil(name[len('/stencils/'):]),None
  except Exception as e:return name,None,None,type(e).__name__
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for name,body,origin,error in pool.map(fetch,sorted(set(wanted))):
   if error:failures.append({'path':name,'error_type':error});continue
   relative=name[1:];sha=hashlib.sha256(body).hexdigest();tool.atomic(base/relative,body)
   assets[name]={'cache_file':relative,'sha256':sha,'bytes':len(body),**origin};added.append(name)
 if added:
  tool.atomic(base/('manifest.'+manifest['cache_id']+'.json'),old)
  basis={'viewer_bundle_sha256':manifest['viewer_bundle_sha256'],'assets':[(name,x['sha256'],x['bytes']) for name,x in sorted(assets.items())]}
  manifest['cache_id']=hashlib.sha256(json.dumps(basis,separators=(',',':')).encode()).hexdigest();manifest['updated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  tool.atomic(path,(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
 result={'finished_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'cache_id':manifest['cache_id'],'added_paths':added,'unavailable_candidates':failures,'asset_count':len(assets),'note':'Namespace candidates are not proof of renderer requests. Only verified local XML assets can be served; missing candidates remain blocked.'}
 tool.atomic(root/'reports/stencil_cache_extension.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--candidates',type=Path,required=True);a=p.parse_args();main(a.root.resolve(),a.candidates)
