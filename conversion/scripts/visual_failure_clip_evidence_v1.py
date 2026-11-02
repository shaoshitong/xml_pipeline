"""Read-only post-hash closure of the frozen CLIP bridge evidence protocol.

No DB, renderer, browser, compiler, writer or model is invoked. This inspects
existing collector observations only; it never upgrades the collector outcome.
"""
from pathlib import Path
import copy,hashlib,json,math,os,re,stat,struct
import clip_canvas_render_v4b as adapter
SUPPORTED_ADAPTER_SHA256='59b5608a4b5bfbfdf759f4071b25c1b1bfa90f365c064529c2d060aa78565a3f'
METHOD='independent_clip_and_unconditional_strict_canvas_native_render_v4b'
ARTIFACTS={'xml':'input.drawio','request':'request.json','clip_info':'clip.native_render.json','clip_png':'clip.png','strict_info':'strict.native_render.json','strict_png':'strict.png'}
PIN_PATHS={'clip_renderer':'conversion/rendering_clipbox_strict/remote_render.py','strict_renderer':'conversion/rendering_paintbounds_strict/remote_render.py','runtime_manifest':'evaluation/assets/drawio-runtime-v32.6.1/manifest.json','adapter':'conversion/scripts/clip_canvas_render_v4b.py','strict_canvas_gate':'conversion/scripts/strict_canvas_gate.py'}
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def compact(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def bridge_json(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()
def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def inspect(report,root,owned):
 """Return applicable/complete/files; missing or unknown CLIP evidence fails closed.

 ``files`` uses root-relative regular-file locators and includes both frozen
 renderer/runtime/code pins and every raw CLIP audit artifact. Fresh audit data
 must be inside ``owned`` or the frozen canonical CLIP audit namespace.
 """
 result={'applicable':False,'complete':False,'files':[],'reason':'uninspected','accepted':False,'outcome_changed':False};entries={};witnesses={}
 try:
  root=Path(root).resolve(strict=True);owned=Path(owned).resolve(strict=True);require(owned!=root and owned.is_relative_to(root),'owned_namespace_outside_root');require(sha(Path(adapter.__file__).read_bytes())==SUPPORTED_ADAPTER_SHA256,'unsupported_loaded_clip_adapter_source')
  def path_for(locator):
   require(isinstance(locator,str) and locator and '\0' not in locator,'invalid_artifact_locator');logical=Path(locator)
   if logical.is_absolute():
    require(logical.is_relative_to(root),'artifact_outside_registered_root');relative=logical.relative_to(root)
   else:relative=logical
   require(relative.parts and '..' not in relative.parts,'artifact_locator_escape');return root/relative,relative
  def read(locator,expected=None,role=None):
   path,relative=path_for(locator);require(expected is None or digest(expected),'invalid_declared_artifact_sha');directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fd=None
   try:
    for part in relative.parts[:-1]:
     child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=child
    fd=os.open(relative.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory);before=os.fstat(fd);require(stat.S_ISREG(before.st_mode),'artifact_not_regular_file');chunks=[]
    while True:
     chunk=os.read(fd,1048576)
     if not chunk:break
     chunks.append(chunk)
    after=os.fstat(fd);keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode');identity=tuple(getattr(before,k) for k in keys);require(identity==tuple(getattr(after,k) for k in keys),'artifact_changed_during_read')
   finally:
    if fd is not None:os.close(fd)
    os.close(directory)
   raw=b''.join(chunks);actual=sha(raw);require(expected is None or actual==expected,'artifact_sha256_mismatch:'+str(relative));key=str(relative)
   if key in entries:require(entries[key]['sha256']==actual,'conflicting_artifact_digest')
   entries[key]={'file':key,'sha256':actual,'bytes':len(raw)};witnesses[key]=(path,identity)
   return raw,path
  def declared(entry,role=None,owned_only=False):
   require(isinstance(entry,dict) and isinstance(entry.get('file'),str) and digest(entry.get('sha256')),'invalid_declared_artifact');raw,path=read(entry['file'],entry['sha256'],role)
   if owned_only:require(path.is_relative_to(owned),'primary_observation_outside_owned_namespace')
   if 'bytes' in entry:require(type(entry['bytes']) is int and entry['bytes']==len(raw),'artifact_byte_length_mismatch')
   return raw,path
  def document(raw,canonical_bridge=False):
   doc=json.loads(raw);compact(doc)
   if canonical_bridge:require(bridge_json(doc)==raw,'noncanonical_frozen_bridge_artifact')
   return doc
  fresh=report.get('fresh_qa');result['applicable']=isinstance(fresh,dict) and bool((((fresh.get('report') or {}).get('checks') or {}).get('render') or {}).get('strict_clip_canvas_proof'));require(isinstance(fresh,dict),'missing_fresh_qa_observation');observations=fresh.get('observations');require(isinstance(observations,list) and len(observations)==1,'primary_render_not_unique_or_missing');ob=observations[0];require(ob.get('kind')=='primary_clip_render' and ob.get('ok') is True,'primary_render_failed_or_unknown');require(digest(ob.get('code_sha256')),'primary_code_sha_missing');expected_clip=(root/PIN_PATHS['clip_renderer']).resolve();expected_strict=(root/PIN_PATHS['strict_renderer']).resolve();renderer=Path(ob['renderer']).resolve(strict=True);result['applicable']=result['applicable'] or renderer==expected_clip;raw,info_path=declared(ob.get('native_info'),'primary_native_info',True);info=document(raw);link=info.get('clip_canvas_strict_proof_v4b')
  q=fresh.get('report') or {};qrender=(q.get('checks') or {}).get('render') or {};recorded_link=qrender.get('strict_clip_canvas_proof')
  if renderer==expected_strict and link is None and recorded_link is None:
   result.update(applicable=False,complete=True,reason='nonCLIP_actual_strict_renderer_no_CLIP_receipt',files=list(entries.values()));return result
  result['applicable']=True;require(renderer==expected_clip and isinstance(link,dict),'CLIP_renderer_or_receipt_missing_or_mixed');require(ob.get('returned_original_result_object') is True and fresh.get('same_render_result_objects_returned') is True,'original_renderer_result_identity_unproven');require(not fresh.get('observer_errors') and not fresh.get('blocked_mutation_attempts'),'observer_or_write_guard_failure')
  keys={'file','sha256','code_sha256','png_sha256','clip_renderer_sha256','strict_renderer_sha256','runtime_manifest_sha256'};require(set(link)==keys,'unknown_CLIP_receipt_schema');proof_raw,proof_path=declared(link,'CLIP_proof');base=proof_path.parent;require(proof_path.name=='proof.json' and base.parent.name==ob['code_sha256'] and re.fullmatch(r'\d{8}T\d{6}Z_[0-9a-f]{32}',base.name),'CLIP_proof_namespace_or_code_binding_mismatch');legal_canonical=root/'conversion/clip_canvas_render_v4b';require(base.is_relative_to(owned) or base.is_relative_to(legal_canonical),'CLIP_audit_namespace_not_owned_or_canonical');proof=document(proof_raw,True)
  required={'version','method','code_sha256','png_sha256','canvas','pins','runtime','artifacts','png_byte_identical','canvas_identical','old_clip_overflow_rejected','actual_font_signature_sha256','actual_text_signature_sha256','outside_page_pixel_audit','accepted','model_calls'};require(set(proof)==required and type(proof['version']) is int and proof['version']==1 and proof['method']==METHOD,'unknown_CLIP_proof_schema');require(proof['accepted'] is False and type(proof['model_calls']) is int and proof['model_calls']==0,'CLIP_proof_nonsuccess_or_model_contract');require(all(proof[k] is True for k in ('png_byte_identical','canvas_identical','old_clip_overflow_rejected')),'CLIP_dual_render_equality_proof_missing');require(digest(proof['code_sha256']) and proof['code_sha256']==ob['code_sha256']==link['code_sha256'],'CLIP_code_binding_mismatch');require(digest(proof['png_sha256']) and proof['png_sha256']==link['png_sha256'],'CLIP_png_binding_mismatch');canvas=proof['canvas'];require(isinstance(canvas,list) and len(canvas)==2 and all(type(n) is int and n>0 for n in canvas) and ob['canvas']==canvas,'CLIP_canvas_binding_mismatch');width,height=canvas
  require(set(proof['pins'])==set(PIN_PATHS),'unknown_CLIP_pin_schema');report_pins=report.get('pins');require(isinstance(report_pins,dict),'missing_frozen_collector_pins');pins=proof['pins']
  for name,relative in PIN_PATHS.items():
   entry=pins[name];declared_path=Path(entry['file']);expected=(root/relative).resolve(strict=True);require(declared_path.is_absolute() and declared_path==expected,'CLIP_pin_path_mismatch:'+name);require(report_pins.get(str(expected))==entry['sha256'],'CLIP_pin_not_bound_to_frozen_collector:'+name);declared(entry,'pin_'+name)
  require(pins['adapter']['sha256']==SUPPORTED_ADAPTER_SHA256,'unsupported_frozen_CLIP_adapter_source');require((link['clip_renderer_sha256'],link['strict_renderer_sha256'],link['runtime_manifest_sha256'])==tuple(pins[k]['sha256'] for k in ('clip_renderer','strict_renderer','runtime_manifest')),'CLIP_receipt_pin_binding_mismatch');require(ob.get('renderer_sha256')==pins['clip_renderer']['sha256'],'primary_renderer_pin_mismatch')
  artifacts=proof['artifacts'];require(isinstance(artifacts,dict) and set(artifacts)==set(ARTIFACTS),'missing_or_unknown_declared_CLIP_artifacts');data={}
  for name,filename in ARTIFACTS.items():
   entry=artifacts[name];path,_=path_for(entry['file']);require(path==base/filename,'CLIP_artifact_cross_namespace_or_name:'+name);data[name]=declared(entry,name)[0]
  require(sha(data['xml'])==proof['code_sha256'],'CLIP_XML_digest_mismatch');request=document(data['request'],True);require(set(request)=={'width','height','timeout','maxsize','pins'} and request['pins']==pins,'unknown_or_mixed_CLIP_request');require([request['width'],request['height']]==canvas and type(request['maxsize']) is int and request['maxsize']>=max(canvas) and type(request['timeout']) in (int,float) and math.isfinite(request['timeout']) and request['timeout']>0,'CLIP_request_canvas_or_size_mismatch')
  clip_info=document(data['clip_info'],True);strict_info=document(data['strict_info'],True);adapter._page(clip_info,width,height,clip=True);adapter._page(strict_info,width,height);adapter._png_page(data['clip_png'],width,height);adapter._png_page(data['strict_png'],width,height);require(isinstance(clip_info['actual_clip_boxes'],list),'actual_CLIP_boxes_missing');require(data['clip_png']==data['strict_png'] and sha(data['clip_png'])==proof['png_sha256'],'dual_native_PNG_bytes_or_hash_differ');observed_png,png_path=declared(ob.get('png'),'primary_png',True);require(observed_png==data['clip_png'],'primary_PNG_differs_from_dual_render')
  boundary=strict_info['outside_page_pixel_audit'];require(boundary['white_threshold']==255 and type(boundary['nonwhite_outside_pixels']) is int and boundary['nonwhite_outside_pixels']==0,'actual_strict_outside_page_pixels_not_zero');require(boundary['audit_always_performed'] is True and boundary['minimum_probe_margin']==32 and strict_info['probe_includes_actual_dom_paint_bounds'] is True,'missing_unconditional_actual_paint_probe');offset=boundary['offset'];padded=boundary['padded_native_render_size'];require(len(offset)==len(padded)==2 and all(type(n) is int for n in offset+padded) and min(offset)>=32 and padded[0]>=width+offset[0]+32 and padded[1]>=height+offset[1]+32,'incomplete_strict_padded_page_coverage')
  if 'outside_page_pixel_audit' in clip_info:
   old=clip_info['outside_page_pixel_audit'];require(old['white_threshold']==255 and type(old['nonwhite_outside_pixels']) is int and old['nonwhite_outside_pixels']==0,'old_CLIP_outside_page_audit_failed')
  require(proof['outside_page_pixel_audit']==boundary and info.get('outside_page_pixel_audit')==boundary,'strict_outside_audit_not_carried_exactly');require((clip_info['scale'],clip_info['translate'])==(strict_info['scale'],strict_info['translate']),'dual_native_scale_or_origin_differ');runtime=adapter._runtime(clip_info,pins['runtime_manifest']);require(runtime==adapter._runtime(strict_info,pins['runtime_manifest'])==proof['runtime'],'dual_runtime_identity_differs');fonts=adapter.font_signature(clip_info);text=adapter.text_signature(clip_info);require(fonts==adapter.font_signature(strict_info) and text==adapter.text_signature(strict_info),'dual_actual_font_or_character_signature_differs');require(sha(bridge_json(fonts))==proof['actual_font_signature_sha256'] and sha(bridge_json(text))==proof['actual_text_signature_sha256'],'declared_actual_signature_digest_mismatch')
  expected_combined=copy.deepcopy(clip_info);expected_combined['outside_page_pixel_audit']=copy.deepcopy(boundary);expected_combined['clip_canvas_strict_proof_v4b']=copy.deepcopy(link);combined_raw,_=read(str(base/'combined.native_render.json'),None,'combined_native_info');combined=document(combined_raw,True);require(compact(combined)==compact(expected_combined)==compact(info),'combined_or_primary_native_info_differs_from_actual_dual_proof')
  if qrender:
   require(recorded_link==link and qrender['code_sha256']==proof['code_sha256'] and qrender['image_sha256']==proof['png_sha256'] and qrender['canvas']==canvas,'frozen_QA_render_not_bound_to_actual_CLIP_receipt')
  for _,(path,identity) in witnesses.items():
   s=path.stat();require(tuple(getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode'))==identity,'CLIP_artifact_changed_during_closure')
  result.update(applicable=True,complete=True,reason='complete_frozen_CLIP_dual_renderer_receipt_and_all_artifacts_posthashed',files=list(entries.values()),proof={'file':str(proof_path.relative_to(root)),'sha256':sha(proof_raw)},code_sha256=proof['code_sha256'],png_sha256=proof['png_sha256'],canvas=canvas,actual_clip_boxes_preserved=True,strict_outside_page_pixels=0,renderer_runtime_pins_bound=True)
 except Exception as error:result.update(complete=False,reason=str(error),error_type=type(error).__name__,files=list(entries.values()))
 return result
