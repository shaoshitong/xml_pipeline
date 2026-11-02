"""Read-only canonical request adapter; original HTML source core stays v9.

This adapter adds the singular unit representation and source/capture seal
needed by the shared once journal. Its own file never enters SourceCore pins.
"""
import copy,hashlib,json,sqlite3
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
FRONTEND='html_source_paragraph_frontend_v9'
VERSION=FRONTEND
UNIT='fresh_HTML_complete_inline_formatting_paragraph_SOURCE_exact_paint_v9'
QUALITY_PLUGIN_FILE=W/'scripts/html_source_paragraph_frontend_v9.py'
CATALOG='release/compiler_iterations/source_core_attempts/manual_catalog_20261101_v5_html_paragraph.json'
CATALOG_SHA256='83a20ca5be3e84f4c4e3890d97832f81423426e81c0dc347b3107f59095427d3'
CORE_KEY='0ce9c0d02c29b59028191b25a9586d9f19c5c45c342f5cc71c45ad269da76c8f'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
sha=lambda data:hashlib.sha256(data).hexdigest()


def configuration(data_root=R):
 import html_source_paragraph_frontend_v9 as frontend
 import compiler_source_core_attempts_v3 as history
 cfg={**frontend.configuration(data_root),'unit':frontend.UNITS['html']}
 if history.core_identity(cfg)['key']!=CORE_KEY:raise RuntimeError('infrastructure_HTML_original_source_core_changed')
 if sha((R/CATALOG).read_bytes())!=CATALOG_SHA256:raise RuntimeError('infrastructure_HTML_manual_once_catalog_changed')
 return cfg


def canonical_job(given):
 if isinstance(given,dict):
  if set(given)!=set(JOB_COLUMNS):raise ValueError('HTML_canonical_job_requires_all13_columns')
  job=dict(given)
 else:
  if len(given)!=len(JOB_COLUMNS):raise ValueError('HTML_canonical_job_requires_all13_columns')
  job=dict(zip(JOB_COLUMNS,given))
 source=json.loads(job['input_record'])
 if(source.get('pair_sha256'),source.get('category'),source.get('format'),source.get('source'))!=(job['id'],job['category'],job['format'],job['source']):raise ValueError('HTML_complete_canonical_source_identity_changed')
 if source['format']!='html'or source['category']not in('poster',):raise ValueError('HTML_original_source_outside_requested_scope')
 return job


def capture_snapshot(given):
 import html_source_paragraph_frontend_v9 as frontend
 job=canonical_job(given);source,manifest,code,reference=frontend.source_inputs(job)
 if source!=json.loads(job['input_record'])or manifest!=json.loads(job['input_manifest']):raise RuntimeError('infrastructure_HTML_fullcanonical_source_or_manifest_changed')
 if(source['pair_sha256'],sha(code),sha(reference))!=(job['id'],source['code_sha256'],source['image_sha256']):raise RuntimeError('infrastructure_HTML_original_source_payload_changed')
 from PIL import Image
 import io
 viewport=list(Image.open(io.BytesIO(reference)).size)
 asset=manifest.get('asset_root')
 asset_identity=asset_snapshot(asset)
 return dict(schema='HTML_full_canonical_original_payload_asset_snapshot_v9',id=job['id'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],input_record_sha256=sha(job['input_record'].encode()),input_manifest_sha256=sha(job['input_manifest'].encode()),input_source_code=manifest['source_code'],input_reference_image=manifest['reference_image'],original_source_viewport=viewport,original_asset_root=asset,asset_directory_snapshot=asset_identity)


def asset_snapshot(locator):
 import os
 if locator is None:return None
 path=(R/locator).resolve(strict=True)
 if not path.is_relative_to((R/'clean').resolve())or not path.is_dir():raise ValueError('HTML_original_asset_root_not_registered_clean_directory')
 entries=[]
 for directory,dirs,files in os.walk(path,followlinks=False):
  for name in sorted(dirs+files):
   p=Path(directory)/name
   if p.is_symlink():raise ValueError('HTML_asset_symlink_requires_later_source_repair')
   if p.is_file():entries.append(dict(path=str(p.relative_to(path)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size))
   elif not p.is_dir():raise ValueError('HTML_nonregular_asset_requires_later_source_repair')
 return dict(root=str(path.relative_to(R.resolve())),files=len(entries),content_sha256=sha(json.dumps(sorted(entries,key=lambda x:x['path']),sort_keys=True,separators=(',',':')).encode()))


def assert_snapshot(job,snapshot):
 if capture_snapshot(job)!=snapshot:raise RuntimeError('infrastructure_HTML_source_asset_snapshot_changed_before_or_after_call')
 return True


def static_support(given):
 import html_source_paragraph_frontend_v9 as frontend
 job=canonical_job(given);result=frontend.static_support(job)
 if not isinstance(result,dict)or type(result.get('supported'))is not bool:raise RuntimeError('infrastructure_HTML_source_support_not_typed')
 if result['supported']:result={**result,'source_capture_snapshot':capture_snapshot(job)}
 return result


def original(record,given):
 job=canonical_job(given);identifier=job['id']
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:row=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
 if row is None or canonical_job(row)!=job:raise RuntimeError('infrastructure_HTML_canonical_job_changed_before_preparation')
 snapshot=capture_snapshot(job);frozen=(record or{}).get('compiler_source_capture_snapshot')
 if frozen is not None and frozen!=snapshot:raise RuntimeError('infrastructure_HTML_frozen_original_source_capture_changed')
 source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest'])
 def original_locator(field,key,digest):
  value=(record or{}).get(field)
  if value:
   path=(R/value).resolve()
   if path.is_relative_to((R/'clean').resolve())and path.is_file()and sha(path.read_bytes())==digest:return str(path.relative_to(R.resolve()))
  return manifest[key]
 seed=dict(id=identifier,source_pair_sha256=identifier,source_record=source,category=source['category'],source=source['source'],source_format='html',format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=original_locator('original_source_code','source_code',source['code_sha256']),original_reference=original_locator('original_reference','reference_image',source['image_sha256']),original_asset_root=manifest.get('asset_root'),compiler_source_capture_snapshot=frozen or snapshot,model=None)
 return seed,row


def convert(record,job,work):
 import html_source_paragraph_frontend_v9 as frontend
 return frontend.convert(record,job,work)
