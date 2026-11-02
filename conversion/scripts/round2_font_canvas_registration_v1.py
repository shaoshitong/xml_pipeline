"""Independent same-renderer font delta atop a fully verified canvas origin.

This replaces only a cross-renderer equality assumption. Both real same-context
images must be exact, fonts must be the same physical faces, source graph must
be unchanged, and the caller must still run complete fresh native/source/
original-reference/local-text/editability quality gates under its NEW policy.
"""
import hashlib,json,uuid,xml.etree.ElementTree as E
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
POLICY='same_renderer_physical_font_delta_registered_canvas_round2_v1'
LOADED_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def dump(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def read_owned(path,folder,checks):
 path=Path(path).resolve(strict=True);require(path.is_relative_to(folder.resolve()),'font_canvas_unowned_evidence')
 blob=path.read_bytes();checks[str(path)]=sha(blob);return blob
def configuration():
 scripts=Path(__file__).parent
 paths=[Path(__file__),scripts/'auto_quality_canvas_repair.py',scripts/'auto_quality_common_v4.py',scripts/'auto_quality_common_v3.py',scripts/'auto_quality_common_v2.py',scripts/'native_source_font_profile_v4.py',scripts/'native_padding_proof.py',scripts/'portable_native_fonts.py',scripts/'round2_font_repair_v1.py',scripts/'strict_canvas_gate.py',scripts/'native_worker.py',W/'rendering_paintbounds_strict/remote_render.py',W/'rendering_canvas_padding_proof/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
 pins={str(p.resolve()):sha(p.read_bytes()) for p in paths}
 return {'policy':POLICY+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20],'pins':pins}
def _verify(record,reference,xml,work=None):
 from auto_quality_canvas_repair import validate_registration_origin
 from native_source_font_profile_v4 import verify_assets,verify_changes,signature,_models,_pixels
 from native_worker import native
 from strict_canvas_gate import require_declared_page
 require(sha(Path(__file__).read_bytes())==LOADED_SHA,'font_canvas_hook_module_changed')
 cfg=configuration();checks={}
 contract=validate_registration_origin(record,reference)
 proof=record.get('round2_font_repair');require(isinstance(proof,dict),'font_canvas_missing_round2_font_proof')
 require(proof.get('version')=='observed_physical_font_only_round2_v1' and proof.get('ok') is True and proof.get('accepted') is False,'font_canvas_unverified_font_proof')
 require((proof.get('input_code_sha256'),proof.get('output_code_sha256'),proof.get('output_image_sha256'))==(contract['origin_code_sha256'],record['code_sha256'],record['image_sha256']),'font_canvas_wrong_current_delta_hash')
 require(proof.get('source_code_sha256')==record['source_code_sha256'] and proof.get('source_image_sha256')==record['source_image_sha256'],'font_canvas_wrong_source_identity')
 audit=(R/proof['audit']).resolve(strict=True);owner=W/'auto_quality_font_repair_v1/round2_v1'
 require(audit.is_relative_to(owner) and audit.name=='report.json','font_canvas_font_proof_outside_round2_owner')
 folder=audit.parent;stored=json.loads(read_owned(audit,owner,checks));require(stored==proof,'font_canvas_font_proof_changed')
 before=read_owned(folder/'before.drawio',folder,checks).decode();previous=json.loads(read_owned(folder/'before_record.json',folder,checks))
 candidate=read_owned(folder/'candidate.drawio',folder,checks).decode();candidate_record=json.loads(read_owned(folder/'candidate_record.json',folder,checks))
 details=json.loads(read_owned(folder/'font_details.json',folder,checks));observations=json.loads(read_owned(folder/'observations.json',folder,checks))
 require(sha(before.encode())==contract['origin_code_sha256'] and sha(xml.encode())==record['code_sha256'] and candidate==xml,'font_canvas_frozen_xml_delta_changed')
 for r in [previous,candidate_record]:
  require(all(r.get(k)==record.get(k) for k in ['id','source_pair_sha256','source_code_sha256','source_image_sha256','source_format','category','source']),'font_canvas_frozen_record_source_changed')
 require(previous.get('auto_quality_canvas_repair')==record.get('auto_quality_canvas_repair') and candidate_record.get('auto_quality_canvas_repair')==record.get('auto_quality_canvas_repair'),'font_canvas_origin_contract_changed')
 require(candidate_record.get('round2_font_repair')==proof and candidate_record['code_sha256']==record['code_sha256'] and candidate_record['image_sha256']==record['image_sha256'],'font_canvas_candidate_metadata_changed')
 origin=read_owned(R/contract['frozen_origin_code'],W/'auto_quality_canvas_repair_v1',checks)
 require(origin.decode()==before,'font_canvas_delta_not_from_proven_origin')
 faces=verify_assets(R,record,_models(before)[1],_models(xml)[1],checks)
 changed=verify_changes(before,xml,details,observations,faces)
 require(changed,'font_canvas_no_actual_font_delta')
 from auto_quality_common import checked
 checked(R,record['code_file'],record['code_sha256']);checked(R,record['image_file'],record['image_sha256'])
 width,height=contract['output_page'];renderer=W/'rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
 baseline=native.native_job(before,width,height,180,renderer,8192,runtime)
 current=native.native_job(xml,width,height,180,renderer,8192,runtime)
 require(baseline.get('ok') is True and current.get('ok') is True,'font_canvas_same_context_native_render_failed')
 require_declared_page(baseline['native_render'],width,height);require_declared_page(current['native_render'],width,height)
 require(_pixels(baseline['png'])==_pixels(current['png']),'font_canvas_same_renderer_pixels_changed')
 require(_pixels(current['png'])==_pixels(checked(R,record['image_file'],record['image_sha256'])),'font_canvas_current_stored_png_differs_from_fresh_same_renderer')
 old_signature=signature(baseline['native_render']['actual_platform_font_usage'])
 current_signature=signature(current['native_render']['actual_platform_font_usage'],custom=True)
 observed_signature=signature(observations,'actual_fonts')
 require(old_signature and old_signature==current_signature==observed_signature,'font_canvas_physical_ps_glyph_counts_changed')
 require(all(i in old_signature for i in changed),'font_canvas_changed_cell_missing_actual_glyphs')
 for path,h in {**cfg['pins'],**checks}.items():require(sha(Path(path).read_bytes())==h,'font_canvas_pinned_evidence_changed:'+path)
 if work is None:work=W/'round2_font_canvas_registration_v1'/record['id']/record['code_sha256']/uuid.uuid4().hex
 work=Path(work).resolve();require(work.is_relative_to(W.resolve()),'font_canvas_output_outside_conversion');work.mkdir(parents=True,exist_ok=False)
 (work/'baseline.same_renderer.png').write_bytes(baseline['png']);(work/'current.same_renderer.png').write_bytes(current['png'])
 dump(work/'baseline.native_info.json',baseline['native_render']);dump(work/'current.native_info.json',current['native_render'])
 evidence={'policy':cfg['policy'],'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],
  'canvas_origin_code_sha256':contract['origin_code_sha256'],'current_code_sha256':record['code_sha256'],'changed_cells':sorted(changed),'verified_font_faces':faces,
  'same_renderer_font_delta_verified':True,'same_renderer_before_after_pixels_exact':True,'actual_physical_ps_and_glyph_counts_preserved':True,'all_current_glyphs_custom':True,
  'strict_page_verified_before_and_after':True,'pixel_renderer':str(renderer.relative_to(R)),'baseline_png_sha256':sha(baseline['png']),'current_png_sha256':sha(current['png']),
  'physical_glyph_signature':current_signature,'pins':cfg['pins'],'evidence_checks':checks,'accepted':False,'remaining_requirements':'Full fresh original-reference fidelity/local text/source coverage/editability remain mandatory.'}
 dump(work/'proof.json',evidence)
 # Do not set the legacy font_only_delta_verified flag: it specifically implies
 # a cross-renderer PNG equality that this independently versioned proof replaces.
 return {**contract,'current_revision_verified':True,'same_renderer_font_delta_verified':True,
         'round2_font_canvas_policy':cfg['policy'],'round2_font_canvas_evidence':str((work/'proof.json').relative_to(R)),
         'round2_font_canvas_evidence_sha256':sha((work/'proof.json').read_bytes())}
def registration_record(record,reference,xml):
 if not (record.get('auto_quality_canvas_repair') and record.get('round2_font_repair')):
  from auto_quality_common_v4 import registration_record as original
  return original(record,reference,xml)
 # If the canvas was produced AFTER a font repair, its current XML is already
 # exactly the fully proved canvas revision; retain the full v4 registration.
 from auto_quality_canvas_repair import validate_registration
 try:validate_registration(record,reference,xml)
 except AssertionError:pass
 else:
  from auto_quality_common_v4 import registration_record as original
  return original(record,reference,xml)
 contract=_verify(record,reference,xml)
 record={k:v for k,v in record.items() if not k.startswith('_verified_')}
 return {**record,'_verified_reference_registration':contract},contract
