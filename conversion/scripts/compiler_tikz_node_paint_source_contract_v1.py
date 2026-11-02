"""Read-only canonical request adapter; original TikZ source core stays v2.

This adapter adds the singular unit representation and source/capture seal
needed by the shared once journal. Its own file never enters SourceCore pins.
"""
import copy,hashlib,json,sqlite3
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
FRONTEND='compiler_tikz_node_paint_viewport_v2'
VERSION=FRONTEND
UNIT='pdfLaTeX2025_Poppler100dpi_node_owned_label_native_v2'
QUALITY_PLUGIN_FILE=W/'scripts/compiler_tikz_node_paint_viewport_v2.py'
CATALOG='release/compiler_iterations/source_core_attempts/manual_catalog_20261101_v4_tikz_node_paint.json'
CATALOG_SHA256='643501535d705a7ac847681cc00ba436def8efbdd50ed6eb91fc39d2adc2f37d'
CORE_KEY='ccff8a4b37030d746b9b90b38469c8ee4ed4733dd4f8bef48a8a31dc068fed5f'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
sha=lambda data:hashlib.sha256(data).hexdigest()


def configuration(data_root=R):
 import compiler_tikz_node_paint_viewport_v2 as frontend
 import compiler_source_core_attempts_v3 as history
 cfg={**frontend.configuration(data_root),'unit':frontend.UNITS['tikz']}
 if history.core_identity(cfg)['key']!=CORE_KEY:raise RuntimeError('infrastructure_TikZ_original_source_core_changed')
 if sha((R/CATALOG).read_bytes())!=CATALOG_SHA256:raise RuntimeError('infrastructure_TikZ_manual_once_catalog_changed')
 return cfg


def canonical_job(given):
 if isinstance(given,dict):
  if set(given)!=set(JOB_COLUMNS):raise ValueError('TikZ_canonical_job_requires_all13_columns')
  job=dict(given)
 else:
  if len(given)!=len(JOB_COLUMNS):raise ValueError('TikZ_canonical_job_requires_all13_columns')
  job=dict(zip(JOB_COLUMNS,given))
 source=json.loads(job['input_record'])
 if(source.get('pair_sha256'),source.get('category'),source.get('format'),source.get('source'))!=(job['id'],job['category'],job['format'],job['source']):raise ValueError('TikZ_complete_canonical_source_identity_changed')
 if source['format']!='tikz'or source['category']not in('scientific_diagram','poster'):raise ValueError('TikZ_original_source_outside_requested_scope')
 return job


def capture_snapshot(given):
 import compiler_tikz_node_paint_viewport_v2 as frontend
 job=canonical_job(given);source,code,reference=frontend.inputs(job);manifest=json.loads(job['input_manifest'])
 if(source['pair_sha256'],sha(code),sha(reference))!=(job['id'],source['code_sha256'],source['image_sha256']):raise RuntimeError('infrastructure_TikZ_original_source_payload_changed')
 return dict(schema='TikZ_full_canonical_original_payload_snapshot_v1',id=job['id'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],input_record_sha256=sha(job['input_record'].encode()),input_manifest_sha256=sha(job['input_manifest'].encode()),input_source_code=manifest['source_code'],input_reference_image=manifest['reference_image'])


def static_support(given):
 import compiler_tikz_node_paint_viewport_v2 as frontend
 job=canonical_job(given);result=frontend.static_support(job)
 if not isinstance(result,dict)or type(result.get('supported'))is not bool:raise RuntimeError('infrastructure_TikZ_source_support_not_typed')
 if result['supported']:result={**result,'source_capture_snapshot':capture_snapshot(job)}
 return result


def original(record,given):
 job=canonical_job(given);identifier=job['id']
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:row=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
 if row is None or canonical_job(row)!=job:raise RuntimeError('infrastructure_TikZ_canonical_job_changed_before_preparation')
 snapshot=capture_snapshot(job);frozen=(record or{}).get('compiler_source_capture_snapshot')
 if frozen is not None and frozen!=snapshot:raise RuntimeError('infrastructure_TikZ_frozen_original_source_capture_changed')
 source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest'])
 def original_locator(field,key,digest):
  value=(record or{}).get(field)
  if value:
   path=(R/value).resolve()
   if path.is_relative_to((R/'clean').resolve())and path.is_file()and sha(path.read_bytes())==digest:return str(path.relative_to(R))
  return manifest[key]
 seed=dict(id=identifier,source_pair_sha256=identifier,source_record=source,category=source['category'],source=source['source'],source_format='tikz',format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=original_locator('original_source_code','source_code',source['code_sha256']),original_reference=original_locator('original_reference','reference_image',source['image_sha256']),compiler_source_capture_snapshot=frozen or snapshot,model=None)
 return seed,row


def convert(record,job,work):
 import compiler_tikz_node_paint_viewport_v2 as frontend
 return frontend.convert(record,job,work)
