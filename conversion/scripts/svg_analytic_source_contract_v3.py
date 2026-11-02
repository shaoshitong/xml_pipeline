"""Read-only canonical request adapter; original SVG source core stays v2.

This adapter adds the singular unit representation and source/capture seal
needed by the shared once journal. Its own file never enters SourceCore pins.
"""
import copy,hashlib,json,sqlite3
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
FRONTEND='compiler_svg_general_guard_v8'
VERSION='compiler_svg_scene_frontend_v12'
UNIT='general_svg_v12_analytic_endpoint_cubic_bezier_nested_groups_actual_shadow_layout_use_instances_source_compositing_order_guard_v8'
QUALITY_PLUGIN_FILE=W/'scripts/compiler_svg_general_guard_v8.py'
CATALOG='release/compiler_iterations/source_core_attempts/manual_catalog_svg_actual_shadow_layout_20261102_v6.json'
CATALOG_SHA256='4e2a76b0bdafef205fc2c717d9a30ebfc225b8ce3f0d27b003a0d1bcded5ca3b'
CORE_KEY='a55037567b7746db66cdb914ccbe3db71b0de337a5513d275ee760ab89287733'
CONTROLS='release/compiler_iterations/controls/svg_actual_shadow_layout_20261102_v12/proof.json'
CONTROLS_SHA256='d28b52a19223b1741baac78dd3c542a0cbd2aad479f214a08fa36487025de377'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
sha=lambda data:hashlib.sha256(data).hexdigest()


def configuration(data_root=R):
 import compiler_svg_general_guard_v8 as frontend
 import compiler_source_core_attempts_v3 as history
 cfg={**frontend.configuration(data_root),'unit':frontend.UNITS['svg']}
 if history.core_identity(cfg)['key']!=CORE_KEY:raise RuntimeError('infrastructure_SVG_original_source_core_changed')
 if sha((R/CATALOG).read_bytes())!=CATALOG_SHA256:raise RuntimeError('infrastructure_SVG_manual_once_catalog_changed')
 return cfg


def canonical_job(given):
 if isinstance(given,dict):
  if set(given)!=set(JOB_COLUMNS):raise ValueError('SVG_canonical_job_requires_all13_columns')
  job=dict(given)
 else:
  if len(given)!=len(JOB_COLUMNS):raise ValueError('SVG_canonical_job_requires_all13_columns')
  job=dict(zip(JOB_COLUMNS,given))
 source=json.loads(job['input_record'])
 if(source.get('pair_sha256'),source.get('category'),source.get('format'),source.get('source'))!=(job['id'],job['category'],job['format'],job['source']):raise ValueError('SVG_complete_canonical_source_identity_changed')
 if source['format']!='svg'or source['category']not in('scientific_diagram',):raise ValueError('SVG_original_source_outside_requested_scope')
 return job


def capture_snapshot(given):
 import compiler_svg_general_guard_v8 as frontend
 from compiler_svg_scene_frontend_v12 import _inputs
 job=canonical_job(given);source,code,reference=_inputs(job);manifest=json.loads(job['input_manifest'])
 if source!=json.loads(job['input_record']):raise RuntimeError('infrastructure_SVG_complete_original_source_payload_changed')
 if(source['pair_sha256'],sha(code),sha(reference))!=(job['id'],source['code_sha256'],source['image_sha256']):raise RuntimeError('infrastructure_SVG_original_source_payload_changed')
 from PIL import Image
 import io
 viewport=list(Image.open(io.BytesIO(reference)).size)
 return dict(schema='SVG_full_canonical_original_payload_snapshot_v1',id=job['id'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],input_record_sha256=sha(job['input_record'].encode()),input_manifest_sha256=sha(job['input_manifest'].encode()),input_source_code=manifest['source_code'],input_reference_image=manifest['reference_image'],original_source_viewport=viewport)


def assert_snapshot(job,snapshot):
 if capture_snapshot(job)!=snapshot:raise RuntimeError('infrastructure_SVG_frozen_original_source_snapshot_changed')
 return True


def static_support(given):
 import compiler_svg_general_guard_v8 as frontend
 job=canonical_job(given);result=frontend.static_support(job)
 if not isinstance(result,dict)or type(result.get('supported'))is not bool:raise RuntimeError('infrastructure_SVG_source_support_not_typed')
 if result['supported']:result={**result,'source_capture_snapshot':capture_snapshot(job)}
 return result


def original(record,given):
 job=canonical_job(given);identifier=job['id']
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:row=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
 if row is None or canonical_job(row)!=job:raise RuntimeError('infrastructure_SVG_canonical_job_changed_before_preparation')
 snapshot=capture_snapshot(job);frozen=(record or{}).get('compiler_source_capture_snapshot')
 if frozen is not None and frozen!=snapshot:raise RuntimeError('infrastructure_SVG_frozen_original_source_capture_changed')
 source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest'])
 def original_locator(field,key,digest):
  value=(record or{}).get(field)
  if value:
   path=(R/value).resolve()
   if path.is_relative_to((R/'clean').resolve())and path.is_file()and sha(path.read_bytes())==digest:return str(path.relative_to(R))
  return manifest[key]
 seed=dict(id=identifier,source_pair_sha256=identifier,source_record=source,category=source['category'],source=source['source'],source_format='svg',format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=original_locator('original_source_code','source_code',source['code_sha256']),original_reference=original_locator('original_reference','reference_image',source['image_sha256']),compiler_source_capture_snapshot=frozen or snapshot,model=None)
 return seed,row


def convert(record,job,work):
 import compiler_svg_general_guard_v8 as frontend
 return frontend.convert(record,job,work)
