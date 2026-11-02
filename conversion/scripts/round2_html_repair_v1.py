"""Finite HTML wrapped-word/paint-order repair; no queue, SQL write or model."""
import copy,hashlib,io,json,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda b:hashlib.sha256(b).hexdigest()
def eligible_failure(result):
 text=str(result.get('detail',''))
 return any(k in text for k in ['poster_object_coverage_mismatch','source_paint_object_missing','overlapping_source_css_paint_order_changed','css_stacking_order','word_spans_multiple_lines'])
def repair(record,job,work):
 try:
  from fixed_batch_case_v1 import checked,save,raw
  from html_source_repair_v2 import propose
  from native_worker import native
  j=dict(zip(('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid'),job)) if not isinstance(job,dict) else job
  source=json.loads(j['input_record']);old=copy.deepcopy(record)
  if old['id']!=j['id'] or old['source_format']!='html' or old['category']!='poster' or (old['source_code_sha256'],old['source_image_sha256'])!=(source['code_sha256'],source['image_sha256']):raise ValueError('html_source_identity_mismatch')
  if old.get('auto_quality_canvas_repair'):raise ValueError('html_source_repair_requires_unregistered_baseline')
  xml=checked(old['code_file'],old['code_sha256']).decode();checked(old['image_file'],old['image_sha256']);checked(old['original_source_code'],old['source_code_sha256']);checked(old['original_reference'],old['source_image_sha256'])
  work=Path(work).resolve(strict=True)
  if not work.is_relative_to(W.resolve()):raise ValueError('html_work_outside_owned_conversion')
  new,proof=propose(old,xml,work/'proposal')
  if not proof['new_editable_text_fragments'] and not proof['paint_order_changed']:raise ValueError('html_no_change_required')
  model=E.fromstring(new).find('.//mxGraphModel');width,height=[int(round(float(model.get(k,0)))) for k in ['pageWidth','pageHeight']]
  rendered=native.native_job(new,width,height,180,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
  if not rendered.get('ok'):raise ValueError('html_candidate_render_failed:'+str({k:v for k,v in rendered.items() if k!='png'})[:1500])
  png=rendered.pop('png');dest=R/'clean/round2_html_repair_v1'/old['id'][:2]/old['id']/uuid.uuid4().hex;dest.mkdir(parents=True,exist_ok=False)
  save(dest/'diagram.drawio',new.encode());save(dest/'image.png',png);save(work/'proposal.json',raw(proof))
  out={**old,'code_file':str((dest/'diagram.drawio').relative_to(R)),'code_sha256':sha(new.encode()),'image_file':str((dest/'image.png').relative_to(R)),'image_sha256':sha(png),'render':rendered['native_render'],'quality_state':'pending_round2_full_qa','round2_html_source_repair':{'evidence':str((work/'proposal.json').relative_to(R)),'original_code_sha256':old['code_sha256']}}
  for k in ['automatic_quality_policy','automatic_quality_audit','accepted_at_utc','source_coverage_automatic']:out.pop(k,None)
  out={k:v for k,v in out.items() if not k.startswith('_verified_')}
  save(dest/'conversion.json',raw(out))
  return {'ok':True,'record':out,'evidence':proof,'model_calls':0}
 except Exception as e:return {'ok':False,'reason':'round2_html_refused','error_type':type(e).__name__,'detail':str(e)[:5000],'model_calls':0}
