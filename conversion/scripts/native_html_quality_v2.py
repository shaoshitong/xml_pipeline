"""Original native source with independently checked rich single-face fonts.

Reuses the existing font asset and font-only graph delta verifiers. A new
policy binds this adapter. Every other source, resource, pixels, text, strict
canvas and editing gate remains mandatory in the frozen full validator.
"""
import hashlib,json,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
SCHEMA='native_rich_single_face_original_graph_v2'
MODULE_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def sha(blob):return hashlib.sha256(blob).hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def verify_font_changes(before,xml,details,observations,faces):
 from native_source_font_profile_v4 import canonical_font_only,_models,_cells,style_values,_font_blob,_ext
 changes=details.get('changes');require(isinstance(changes,list) and changes and not details.get('issues'),'rich_font_missing_or_invalid_changes')
 changed={c['cell'] for c in changes};require(len(changed)==len(changes),'rich_font_duplicate_changed_cell')
 require(canonical_font_only(before,changed)==canonical_font_only(xml,changed),'rich_font_nonfont_original_graph_or_markup_changed')
 oldcells=_cells(_models(before)[0]);cells=_cells(_models(xml)[0]);observed={r['cell']:r for r in observations}
 require(len(observed)==len(observations),'rich_font_duplicate_observation')
 for change in changes:
  cid=change['cell'];row=observed[cid];style=style_values(cells[cid]);actual=[f for f in row['actual_fonts'] if f.get('glyphCount',0)>0]
  require(actual and all(f.get('isCustomFont') is False for f in actual),'rich_font_input_not_observed_system_faces')
  families=style.get('fontFamily','').split(',');require(families==change.get('families') and all(f in faces for f in families),'rich_font_unverified_family_stack')
  selected=[faces[f] for f in families];require({f['postscript'] for f in selected}=={f['postScriptName'] for f in actual},'rich_font_family_stack_differs_from_actual_faces')
  require(len({(f['bold'],f['italic']) for f in selected})==1,'rich_font_mixed_styles_require_independent_runs')
  before_flags=change['before_flags'];after_flags=change['after_flags']
  require(type(before_flags) is int and type(after_flags) is int and before_flags>=0 and after_flags>=0,'rich_font_invalid_style_flags')
  require(before_flags==int(row['style'].get('fontStyle',0)) and after_flags==int(style.get('fontStyle',0)),'rich_font_observed_style_mismatch')
  require(change.get('before_family')==row['style'].get('fontFamily'),'rich_font_observed_original_family_mismatch')
  expected=before_flags & ~(1 if selected[0]['bold'] else 0) & ~(2 if selected[0]['italic'] else 0)
  require(after_flags==expected,'rich_font_synthetic_style_not_absorbed_by_exact_physical_face')
  oldstyle=style_values(oldcells[cid])
  if 'fontStyle' in oldstyle:require((int(oldstyle['fontStyle'])&~3)==(before_flags&~3),'rich_font_original_nonfont_flags_changed')
  if style.get('fontSource'):
   require(len(families)==1 and _font_blob(style['fontSource'])==_font_blob(_ext(_models(xml)[1])[families[0]]),'rich_font_cell_font_source_mismatch')
 return changed

def check_native_profile(record,xml,source,native_info=None):
 from native_source_font_profile_v4 import _models,_pixels,verify_assets,verify_changes,signature
 from native_worker import normalize,native
 from auto_quality_common import checked
 result={'supported':record.get('source_format')=='drawio','ok':False,'profile':'original_native_exact_graph_physical_font_only_v4','failures':[],'evidence':{},'accepted':False}
 checks={}
 def read(path):
  path=Path(path).resolve(strict=True);require(path.is_relative_to(R.resolve()),'rich_font_evidence_outside_root');blob=path.read_bytes();checks[str(path)]=sha(blob);return blob
 try:
  require(sha(Path(__file__).read_bytes())==MODULE_SHA,'rich_font_verifier_changed')
  require(record.get('id')==record.get('source_pair_sha256'),'rich_font_original_id_mismatch')
  require(sha(source.encode())==record['source_code_sha256'] and sha(xml.encode())==record['code_sha256'],'rich_font_source_or_candidate_hash_mismatch')
  proof=record['round2_font_repair'];audit=(R/proof['audit']).resolve(strict=True)
  owner=(R/'conversion/auto_quality_font_repair_v1/round2_v1'/record['id']).resolve()
  require(audit.is_relative_to(owner) and audit.name=='report.json','rich_font_unowned_proof')
  require(json.loads(read(audit))==proof and proof.get('ok') is True and proof.get('accepted') is False,'rich_font_report_changed')
  folder=audit.parent;before=read(folder/'before.drawio').decode();previous=json.loads(read(folder/'before_record.json'));candidate=read(folder/'candidate.drawio').decode();current=json.loads(read(folder/'candidate_record.json'))
  details=json.loads(read(folder/'font_details.json'));observations=json.loads(read(folder/'observations.json'))
  normalized,pages,_=normalize(source)
  require(pages==1 and before==normalized,'rich_font_input_not_exact_normalized_original')
  require(sha(before.encode())==previous['code_sha256']==proof['input_code_sha256'],'rich_font_original_revision_mismatch')
  require(candidate==xml and current['code_sha256']==proof['output_code_sha256']==record['code_sha256'],'rich_font_current_revision_mismatch')
  require(current['image_sha256']==proof['output_image_sha256']==record['image_sha256'],'rich_font_current_png_mismatch')
  require(current.get('round2_font_repair')==proof,'rich_font_current_frozen_proof_mismatch')
  for obj in [previous,current]:
   require(all(obj.get(k)==record.get(k) for k in ('id','source_pair_sha256','source_code_sha256','source_image_sha256','source_format','category','source')),'rich_font_frozen_identity_mismatch')
  require(not previous.get('auto_quality_canvas_repair') and not record.get('auto_quality_canvas_repair'),'rich_font_canvas_requires_separate_delta_proof')
  for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
   require((R/record[field]).resolve().is_relative_to((R/'clean').resolve()),'rich_font_asset_outside_clean');checked(R,record[field],record[digest])
  faces=verify_assets(R,record,_models(before)[1],_models(xml)[1],checks)
  changed=verify_font_changes(before,xml,details,observations,faces)
  model=_models(xml)[1];size=[int(round(float(model.get(k,0)))) for k in ('pageWidth','pageHeight')]
  require(all(0<n<=8192 for n in size),'rich_font_unsupported_page')
  renderer=R/'conversion/rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';read(renderer);read(runtime)
  baseline=native.native_job(before,*size,180,renderer,8192,runtime);fresh=native.native_job(xml,*size,180,renderer,8192,runtime)
  require(baseline.get('ok') and fresh.get('ok'),'rich_font_fresh_render_failure')
  currentpng=checked(R,record['image_file'],record['image_sha256']);frozenpng=read(folder/'candidate.png')
  require(_pixels(baseline['png'])==_pixels(fresh['png'])==_pixels(currentpng)==_pixels(frozenpng),'rich_font_fresh_native_pixels_changed')
  oldsig=signature(baseline['native_render']['actual_platform_font_usage']);newsig=signature(fresh['native_render']['actual_platform_font_usage'],custom=True)
  require(oldsig and oldsig==newsig==signature(observations,'actual_fonts'),'rich_font_fresh_physical_glyph_signature_changed')
  if native_info is not None:require(signature(native_info['actual_platform_font_usage'],custom=True)==newsig,'rich_font_caller_fresh_signature_changed')
  require(all(cid in oldsig for cid in changed),'rich_font_unobserved_changed_cell')
  require(all(sha(Path(p).read_bytes())==h for p,h in checks.items()),'rich_font_evidence_changed_during_verification')
  result.update(ok=True,evidence={'schema':SCHEMA,'current_code_sha256':record['code_sha256'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'source_pages':1,'normalized_original_exactly_equals_frozen_before_xml':True,'font_only_delta_independently_verified':True,'fresh_before_after_and_all_frozen_png_pixels_identical':True,'physical_faces_and_glyph_counts_preserved':True,'unchanged_source_objects_except_portable_font_styles':True,'actual_platform_font_signature':newsig,'changed_cells':sorted(changed),'font_asset_count':len(faces),'verifier_sha256':MODULE_SHA,'evidence_checks':checks,'accepted':False})
 except Exception as exc:result['failures']=[{'reason':'native_rich_font_source_proof_invalid','type':type(exc).__name__,'error':str(exc)[:2200]}]
 return result

def verify_native_export(record,job,work,index):
 from fixed_batch_case_v1 import checked,save,raw
 from auto_quality_common import structure_checks,resource_checks,image_quality,require_rendered_text,native_source_profile
 from native_source_editing_v4 import audit as editing_audit
 from native_export_reference_v3 import validate,configuration,SCHEMA as EXPORT_SCHEMA
 import time
 work=Path(work)/('qa_native_export_'+str(index))/uuid.uuid4().hex;work.mkdir(parents=True,exist_ok=False)
 policy=EXPORT_SCHEMA+':'+sha(raw(configuration()))[:20]
 report={'id':record['id'],'policy':policy,'checks':{},'failures':[],'accepted':False,'state':'abandoned'};out=None
 try:
  original=json.loads(job[4]);require(record['id']==original['pair_sha256'] and record['source_code_sha256']==original['code_sha256'] and record['source_image_sha256']==original['image_sha256'],'native_export_job_source_identity_mismatch')
  xml=checked(record['code_file'],record['code_sha256']).decode();reference=checked(record['original_reference'],record['source_image_sha256']);source=checked(record['original_source_code'],record['source_code_sha256']).decode();checked(record['image_file'],record['image_sha256'])
  report['checks']['structure']=structure_checks(xml)
  report['checks']['resources']=resource_checks(R,record,xml,reference)
  previous,full,export,view=validate(record,xml)
  coverage=check_native_profile(previous,xml,source) if previous.get('round2_font_repair') else native_source_profile(previous,xml,source)
  require(coverage.get('supported') is True and coverage.get('ok') is True,'native_export_original_source_proof_failed:'+json.dumps(coverage.get('failures')))
  report['checks']['source']=coverage;info=export['native_render']
  report['checks']['render']={'mode':'actual_upstream_drawio_tight_export','source_declared_page':view['source_declared_page'],'export_viewport':view['export_viewport'],'view_transform':view['view_transform'],'complete_declared_page_paint_and_export_paint_independently_verified':True,'strict_outside_page_pixels':0,'strict_outside_export_pixels':0,'fresh_export_png_sha256':sha(export['png']),'all_original_geometry_and_markup_unchanged':True}
  report['checks']['text_paint']=require_rendered_text(xml,info)
  usage=[f for row in info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0]
  require(not info.get('actual_text_positions') or bool(usage) and all(f.get('isCustomFont') for f in usage),'actual_font_portability_requires_embedding')
  report['checks']['fonts']={'actual_custom_font_glyphs':sum(f['glyphCount'] for f in usage),'all_rendered_fonts_embedded':True}
  visual=image_quality(reference,export['png'],record,info.get('actual_text_positions'));report['checks']['visual']=visual
  require(visual['ok'],'raster_anomaly: '+','.join(visual['failures']))
  if report['checks']['structure']['edges']:
   moves=editing_audit(xml,record=record,source_profile=coverage);require(moves['ok'] and len(moves['moves'])==2*report['checks']['structure']['edges'],'native_export_incomplete_actual_native_editing_proof');save(work/'movement.json',raw(moves));report['checks']['native_editing']={'ok':True,'endpoint_moves':len(moves['moves']),'profile':moves['profile']}
  else:report['checks']['native_editing']={'ok':True,'endpoint_moves':0,'source_profile_proves_no_semantic_edges':True}
  checked(record['code_file'],record['code_sha256']);checked(record['image_file'],record['image_sha256'])
  report.update(state='qualified',new_png_sha256=record['image_sha256'])
  out={**record,'automatic_quality_policy':policy,'automatic_quality_audit':str((work/'audit.json').relative_to(R)),'source_coverage_automatic':coverage,'quality_state':'accepted_complete_original_native_actual_export_v3','accepted_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'metrics':{**record.get('metrics',{}),'automatic_visual_quality':visual}}
 except Exception as exc:report['failures']=[str(exc)[:6000]];report['exception_type']=type(exc).__name__
 save(work/'fresh.png',export['png'] if 'export' in locals() else b'');save(work/'audit.json',raw(report));return report,out,work

def verify(record,job,work,index):
 """Run all frozen QA under a policy that binds the new source proof adapter."""
 if record.get('native_export_reference_v3'):return verify_native_export(record,job,work,index)
 import auto_quality_batch_v4b as qa
 import round2_case_v1 as full
 original=qa.profile;frozen=getattr(qa,'_round2_frozen_policy',qa.POLICY)
 def profile(record,xml,source,native_info=None):
  if record.get('source_format')=='drawio' and record.get('native_export_canvas_v2'):
   from native_export_canvas_v2 import validate
   try:
    previous,before,evidence=validate(record,xml)
    result=check_native_profile(previous,before,source,native_info=native_info) if previous.get('round2_font_repair') else original(previous,before,source,native_info)
    result['evidence'].update(current_code_sha256=record['code_sha256'],canvas_only_transformation_independently_verified=True,native_export_canvas=evidence)
    return result
   except Exception as exc:return {'supported':True,'ok':False,'profile':'native_export_canvas_v2','failures':[{'reason':'native_export_lineage_invalid','error':str(exc)}],'evidence':{}}
  if record.get('source_format')=='drawio' and record.get('round2_font_repair') and not record.get('auto_quality_canvas_repair'):
   return check_native_profile(record,xml,source,native_info=native_info)
  return original(record,xml,source,native_info)
 pins={p.name:sha(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('native_html_compiler_v2.py'),Path(__file__).with_name('native_export_canvas_v2.py')]}
 qa.profile=profile;qa._round2_frozen_policy=frozen+':'+SCHEMA+':'+sha(json.dumps(pins,sort_keys=True).encode())
 try:return full.verify(record,job,work,index)
 finally:qa.profile=original;qa._round2_frozen_policy=frozen
