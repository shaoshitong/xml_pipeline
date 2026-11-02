"""Metadata-selected official native export with source-complete portable fonts."""
from pathlib import Path
import json,hashlib,uuid,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='drawio_author_version_frontend_v2';UNIT='original_author_metadata_version_native_full_paint_and_physical_fonts_layout_owner_v2'
UNITS={'drawio':UNIT}
sha=lambda b:hashlib.sha256(b).hexdigest()
def configuration(data_root=R):
 if Path(data_root).resolve()!=R:raise ValueError('author_native_requires_HKUST_root')
 from compiler_native_source_repair_frontend_v2 import configuration as base
 from drawio_author_version_export_v3 import configuration as runtime
 from drawio_author_source_input_v1 import INDEX,INDEX_SHA
 pins=dict(base()['pins']);pins[str(INDEX)]=INDEX_SHA
 for version in ('27.0.9','28.0.6'):pins.update(runtime(version)['pins'])
 for name in ('drawio_author_source_input_v1.py','drawio_author_version_dev_v1.py','drawio_author_native_model_semantics_v1.py','drawio_author_runtime_session_v1.py','drawio_author_version_fonts_v3.py','drawio_author_version_frontend_v2.py','drawio_author_version_quality_ro_v2.py','drawio_author_version_editing_v2.py','drawio_author_version_editing_v2.js','compiler_plantuml_engine_canonical_claim_v1.py'):
  p=W/'scripts'/name;pins[str(p)]=sha(p.read_bytes())
 return {'policy':VERSION+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20],'pins':pins,'unit':UNIT,'source_only_profile':'Original PNG author metadata version27.0.9/28.0.6, literal scale1/border0, one complete Gold-matching source page, no math or unresolved page/environment variables. Full paint/font/visual/editing remain mandatory.','model_calls':0}
def original(record,given,database=W/'jobs.sqlite'):
 from drawio_author_source_input_v1 import load
 result=load(given,database);s=result['source'];seed={'id':s['pair_sha256'],'source_pair_sha256':s['pair_sha256'],'category':s['category'],'source':s['source'],'source_format':'drawio','format':'drawio','source_code_sha256':s['code_sha256'],'source_image_sha256':s['image_sha256'],'original_source_code':result['original_source_code'],'original_reference':result['original_reference'],'compiler_source_capture_snapshot':result['snapshot'],'source_record':s,'model':None}
 if(record or{}).get('compiler_source_capture_snapshot')and record['compiler_source_capture_snapshot']!=result['snapshot']:raise ValueError('author_original_source_capture_snapshot_changed')
 return seed,result

def static_support(given):
 out={'supported':False,'unit':UNIT,'source_only':True,'reasons':[]}
 try:
  seed,inputs=original(None,given);out.update(supported=True,source_capture_snapshot=seed['compiler_source_capture_snapshot'],source_code_sha256=seed['source_code_sha256'],source_image_sha256=seed['source_image_sha256'],author_export_profile=inputs['source_profile'])
 except Exception as e:out['reasons']=[str(e)[:2000]]
 return out

def convert(record,given,work):
 import drawio_author_version_fonts_v3 as fonts
 from compiler_plantuml_engine_canonical_claim_v1 import require_available
 from compiler_typed_runtime_failure_v1 import diagnose
 try:
  work=Path(work).resolve();assert work.is_relative_to((W/VERSION).resolve());work.mkdir(parents=True,exist_ok=False)
  seed,inputs=original(record,given);claim=require_available(inputs['job']);result=fonts.compile(inputs['normalized_author_XML'],inputs['source_profile'],work/'independent_physical_font_binding')
  destination=R/'clean'/VERSION/seed['id'][:2]/seed['id']/uuid.uuid4().hex;destination.mkdir(parents=True,exist_ok=False)
  fonts.save(destination/'diagram.drawio',result['xml'].encode());fonts.save(destination/'image.png',result['png']);fonts.save(destination/'source_font_proof.json',fonts.raw(result['proof']))
  candidate={**seed,'code_file':str((destination/'diagram.drawio').relative_to(R)),'code_sha256':sha(result['xml'].encode()),'image_file':str((destination/'image.png').relative_to(R)),'image_sha256':sha(result['png']),'render':result['info'],'native_embedded_fonts':result['assets'],'conversion_method':VERSION,'author_native_source':{'source_export_profile':inputs['source_profile'],'font_policy':fonts.POLICY,'proof_file':str((destination/'source_font_proof.json').relative_to(R)),'proof_sha256':sha(fonts.raw(result['proof'])),'source_capture_snapshot':inputs['snapshot'],'original_canonical_claim_readonly':claim},'model_configuration':{'external_model_calls':0}}
  fonts.save(work/'candidate_record.json',fonts.raw(candidate));return {'ok':True,'record':candidate,'record_file':str(work/'candidate_record.json'),'model_calls':0}
 except Exception as e:
  d=diagnose(e);return {'ok':False,'reason':str(e).split(':',1)[0],'detail':str(e)[:6500],'error_type':type(e).__name__,'infrastructure_failure':d['infrastructure_failure'],'infrastructure_diagnosis':d,'model_calls':0}
