"""Finite per-case canvas repair using the unchanged strict canvas proof bridge.

No database, model, watch, publication or old-file replacement. This adapter
only writes independently versioned candidate/proof artifacts; full QA remains
mandatory. Compatible proof paths use a new round2_v1 subtree under the frozen
validator's existing owned namespace.
"""
import hashlib,io,json,uuid
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
SCHEMA='round2_canvas_repair_v1'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
REASONS=('Native content requires full tight canvas','Canvas registration needs an independently proven current delta','unregistered_reference_canvas_difference','native_outside_reference_canvas_requires_registered_recovery')
def sha(blob):return hashlib.sha256(blob).hexdigest()
def eligible_failure(result):
    return result.get('status')=='abandoned' and any(x in str(result.get('detail','')) for x in REASONS)
def _write(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=blob:raise ValueError('immutable_round2_artifact_changed')
        return
    with path.open('xb') as f:f.write(blob)
def _json(path,value):_write(path,(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
def _checked(record,field,digest):
    relative=Path(record[field]);path=(R/relative).resolve(strict=True)
    if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to((R/'clean').resolve()):raise ValueError('canvas_payload_outside_clean:'+field)
    blob=path.read_bytes()
    if sha(blob)!=record[digest]:raise ValueError('canvas_payload_hash_mismatch:'+field)
    return blob
def validate_identity(record,job):
    j=dict(zip(JOB_COLUMNS,job)) if not isinstance(job,dict) else job
    source=json.loads(j['input_record']) if isinstance(j['input_record'],str) else j['input_record']
    if (record.get('id'),record.get('source_pair_sha256'),record.get('source_format'),record.get('category'),record.get('source'))!=(j['id'],j['id'],j['format'],j['category'],j['source']):raise ValueError('canvas_job_source_identity_mismatch')
    if (record.get('source_code_sha256'),record.get('source_image_sha256'))!=(source['code_sha256'],source['image_sha256']):raise ValueError('canvas_original_source_hash_mismatch')
    return source
def repair(record,job,work):
    """Return a proven pending candidate or a typed refusal; never qualifies it."""
    try:return _repair(record,job,work)
    except Exception as e:return {'ok':False,'reason':'round2_canvas_refused','error_type':type(e).__name__,'detail':str(e)[:5000],'model_calls':0}
def _repair(old,job,work):
    from PIL import Image
    import auto_quality_canvas_repair as frozen
    from native_padding_proof import render,plan_from_pixels,exact_pixel_proof
    from strict_canvas_gate import require_declared_page
    from harness_source_provenance import validate_source_record
    validate_identity(old,job)
    if old.get('auto_quality_canvas_repair'):raise ValueError('already_has_registered_canvas_proof_requires_separate_lineage')
    requested=Path(work).resolve(strict=True)
    if not requested.is_relative_to(W.resolve()):raise ValueError('round2_canvas_work_outside_conversion')
    xml_bytes=_checked(old,'code_file','code_sha256');old_png=_checked(old,'image_file','image_sha256')
    reference=_checked(old,'original_reference','source_image_sha256');_checked(old,'original_source_code','source_code_sha256')
    source_checks=validate_source_record(old)
    if 'original_source_code' not in source_checks:raise ValueError('immutable_source_code_not_proven')
    xml=xml_bytes.decode();size=Image.open(io.BytesIO(reference)).size
    _,metadata=frozen.page_metadata(xml,size)  # Explicit page/reference mismatch is never guessed.
    token=uuid.uuid4().hex
    proof_work=W/'auto_quality_canvas_repair_v1/round2_v1'/old['id']/token
    data=R/'clean/round2_canvas_repair_v1'/old['id'][:2]/old['id']/token
    proof_work.mkdir(parents=True,exist_ok=False);data.mkdir(parents=True,exist_ok=False)
    _json(proof_work/'before_record.json',old);_write(proof_work/'baseline.drawio',xml_bytes);_write(proof_work/'baseline.png',old_png)
    baseline_png,before=render(xml,*size,proof_work/'baseline')
    if before['canvas']!=list(size) or before['renderer_profile']!='native_page_padding_strict_v1':raise ValueError('canvas_source_page_registration_mismatch')
    renderer_digest=sha(frozen.RENDERER.read_bytes())
    if before['renderer_module_sha256']!=renderer_digest:raise ValueError('canvas_renderer_pin_mismatch')
    boundary=before['outside_page_pixel_audit']
    if boundary['white_threshold']!=255:raise ValueError('strict_outside_pixel_audit_required')
    if boundary['nonwhite_outside_pixels']:
        canvas=plan_from_pixels((proof_work/'baseline/render.padded.png').read_bytes(),before);kind='bounded_native_paint_overflow'
    else:
        if not metadata['missing_attributes_filled']:raise ValueError('no_current_overflow_or_missing_page_metadata')
        canvas={'dx':0,'dy':0,'width':size[0],'height':size[1],'original_page_in_probe':[*boundary['offset'],boundary['offset'][0]+size[0],boundary['offset'][1]+size[1]]};kind='missing_reference_page_metadata'
    candidate,metadata,geometry=frozen.transform(xml,size,canvas)
    png,after=render(candidate,*geometry['new_page'],proof_work/'candidate')
    require_declared_page(after,*geometry['new_page'])
    if after['renderer_module_sha256']!=renderer_digest:raise ValueError('canvas_renderer_changed')
    exact=exact_pixel_proof(proof_work/'baseline',proof_work/'candidate',before,after,canvas)
    _write(proof_work/'candidate.drawio',candidate.encode());_write(proof_work/'candidate.png',png)
    for path,blob in [('baseline/diagram.drawio',xml_bytes),('baseline/image.png',old_png),('diagram.drawio',candidate.encode()),('image.png',png)]:_write(data/path,blob)
    _json(data/'baseline/conversion.json',old)
    proof={'version':1,'policy':frozen.POLICY,'id':old['id'],'at':frozen.now(),'kind':kind,
     'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'source_hash_checks':source_checks,
     'old_code_sha256':old['code_sha256'],'old_image_sha256':old['image_sha256'],'new_code_sha256':sha(candidate.encode()),'new_image_sha256':sha(png),
     'baseline_record':str((data/'baseline/conversion.json').relative_to(R)),'baseline_code':str((data/'baseline/diagram.drawio').relative_to(R)),'baseline_image':str((data/'baseline/image.png').relative_to(R)),
     'candidate_code':str((data/'diagram.drawio').relative_to(R)),'candidate_image':str((data/'image.png').relative_to(R)),
     'frozen_baseline_record':str((proof_work/'before_record.json').relative_to(R)),'frozen_baseline_record_sha256':sha((proof_work/'before_record.json').read_bytes()),
     'frozen_baseline_code':str((proof_work/'baseline.drawio').relative_to(R)),'frozen_baseline_image':str((proof_work/'baseline.png').relative_to(R)),
     'frozen_candidate_code':str((proof_work/'candidate.drawio').relative_to(R)),'frozen_candidate_image':str((proof_work/'candidate.png').relative_to(R)),
     'metadata':metadata,'geometry':geometry,'canvas_plan':canvas,'exact_pixel_proof':exact,
     'old_outside_page_pixels':boundary['nonwhite_outside_pixels'],'new_outside_page_pixels':after['outside_page_pixel_audit']['nonwhite_outside_pixels'],
     'renderer_profile':after['renderer_profile'],'renderer_module_sha256':renderer_digest,
     'reference_registration':{'reference_page':list(size),'output_page':geometry['new_page'],'original_page_offset':geometry['translation'],'scale':1,'original_reference_hash':old['source_image_sha256'],'no_reference_crop':True},'accepted':False}
    _json(proof_work/'proof.json',proof);link={'proof':str((proof_work/'proof.json').relative_to(R)),'proof_sha256':sha((proof_work/'proof.json').read_bytes())}
    pending={k:v for k,v in old.items() if k not in ('automatic_quality_policy','automatic_quality_audit','accepted_at_utc','source_coverage_automatic') and not k.startswith('_verified_')}
    out={**pending,'code_file':proof['candidate_code'],'image_file':proof['candidate_image'],'code_sha256':proof['new_code_sha256'],'image_sha256':proof['new_image_sha256'],
         'render':after,'auto_quality_canvas_repair':link,'quality_state':'pending_round2_source_native_quality_checks','converted_at_utc':frozen.now()}
    _json(proof_work/'candidate_record.json',out);_json(data/'conversion.json',out)
    registration=frozen.validate_registration(out,reference,candidate)
    evidence={'schema':SCHEMA,'id':old['id'],'kind':kind,'proof':link,'geometry':geometry,'strict_original_page_and_complete_paint_unchanged':True,'outside_pixels_after':0,'registration':registration,'model_calls':0,'accepted':False}
    _json(requested/'round2_canvas_result.json',evidence)
    return {'ok':True,'record':out,'evidence':evidence,'model_calls':0,'accepted':False}
