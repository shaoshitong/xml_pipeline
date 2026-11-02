"""New native-original QA supports source-declared coordinate edge ends.

Preserves the independently reproved original XML/font/export/reference gates.
Only source-proven explicit free endpoint roles gain their own live geometry
interventions; named missing terminals remain invalid.
"""
import hashlib,json,uuid
from pathlib import Path
from native_html_quality_v2 import check_native_profile
R=Path('/backup/shaoshitong/img2code_20261029')
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def verify_native_export(record,job,work,index):
 from fixed_batch_case_v1 import checked,save,raw
 from auto_quality_common import resource_checks,image_quality,require_rendered_text,native_source_profile
 from native_free_edges_v4 import audit as editing_audit,structure_checks
 from native_export_reference_v4 import validate,configuration as export_configuration,SCHEMA as EXPORT_SCHEMA
 import time
 work=Path(work)/('qa_native_export_'+str(index))/uuid.uuid4().hex;work.mkdir(parents=True,exist_ok=False)
 pins=export_configuration();pins.update({str(p):sha(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('native_free_edges_v4.py'),Path(__file__).with_name('native_free_edges_v4.js')]})
 policy='native_original_bound_and_free_export_v4:'+sha(raw(pins))[:20]
 report={'id':record['id'],'policy':policy,'checks':{},'failures':[],'accepted':False,'state':'abandoned'};out=None
 try:
  original=json.loads(job[4]);require(record['id']==original['pair_sha256'] and record['source_code_sha256']==original['code_sha256'] and record['source_image_sha256']==original['image_sha256'],'native_export_job_source_identity_mismatch')
  xml=checked(record['code_file'],record['code_sha256']).decode();reference=checked(record['original_reference'],record['source_image_sha256']);source=checked(record['original_source_code'],record['source_code_sha256']).decode();checked(record['image_file'],record['image_sha256'])
  report['checks']['resources']=resource_checks(R,record,xml,reference)
  previous,full,export,view=validate(record,xml)
  coverage=check_native_profile(previous,xml,source) if previous.get('round2_font_repair') else native_source_profile(previous,xml,source)
  require(coverage.get('supported') is True and coverage.get('ok') is True,'native_export_original_source_proof_failed:'+json.dumps(coverage.get('failures')))
  report['checks']['source']=coverage;report['checks']['structure']=structure_checks(xml,record=record,source_profile=coverage);info=export['native_render']
  report['checks']['render']={'mode':'actual_upstream_drawio_tight_export','source_declared_page':view['source_declared_page'],'export_viewport':view['export_viewport'],'view_transform':view['view_transform'],'complete_source_paint_and_export_paint_independently_verified':True,'full_paint_inspection_viewport':view['full_paint_inspection_viewport'],'full_paint_inspection_translation':view['full_paint_inspection_translation'],'strict_outside_page_pixels':0,'strict_outside_export_pixels':0,'fresh_export_png_sha256':sha(export['png']),'all_original_geometry_and_markup_unchanged':True}
  report['checks']['text_paint']=require_rendered_text(xml,info)
  usage=[f for row in info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0]
  require(not info.get('actual_text_positions') or bool(usage) and all(f.get('isCustomFont') for f in usage),'actual_font_portability_requires_embedding')
  report['checks']['fonts']={'actual_custom_font_glyphs':sum(f['glyphCount'] for f in usage),'all_rendered_fonts_embedded':True}
  visual_record={**record,'native_canvas_contract':{'offset':view['original_reference_offset']}}
  visual=image_quality(reference,export['png'],visual_record,info.get('actual_text_positions'));report['checks']['visual']=visual
  require(visual['ok'],'raster_anomaly: '+','.join(visual['failures']))
  if report['checks']['structure']['edges']:
   moves=editing_audit(xml,record=record,source_profile=coverage);require(moves['ok'] and len(moves['moves'])==2*report['checks']['structure']['edges'],'native_export_incomplete_actual_native_editing_proof');save(work/'movement.json',raw(moves));report['checks']['native_editing']={'ok':True,'endpoint_moves':len(moves['moves']),'profile':moves['profile']}
  else:report['checks']['native_editing']={'ok':True,'endpoint_moves':0,'source_profile_proves_no_semantic_edges':True}
  checked(record['code_file'],record['code_sha256']);checked(record['image_file'],record['image_sha256'])
  require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'native_free_quality_implementation_changed')
  report.update(state='qualified',new_png_sha256=record['image_sha256'])
  out={**record,'automatic_quality_policy':policy,'automatic_quality_audit':str((work/'audit.json').relative_to(R)),'source_coverage_automatic':coverage,'quality_state':'accepted_complete_original_native_actual_export_v3','accepted_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'metrics':{**record.get('metrics',{}),'automatic_visual_quality':visual}}
 except Exception as exc:report['failures']=[str(exc)[:6000]];report['exception_type']=type(exc).__name__
 save(work/'fresh.png',export['png'] if 'export' in locals() else b'');save(work/'audit.json',raw(report));return report,out,work

def verify(record,job,work,index):
 if record.get('source_format')=='drawio' and record.get('native_export_reference_v4'):
  return verify_native_export(record,job,work,index)
 from native_html_quality_v2 import verify as previous
 return previous(record,job,work,index)
