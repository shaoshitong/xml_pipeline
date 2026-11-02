"""Recover retained initial-native paint into registered pending proposals.

No canonical claims, updates or publication API is provided. Raw tight captures
remain raw evidence. A fresh strict render proves the whole original page and
all native paint survive the existing bounded integer page transformation.
"""
import argparse,base64,collections,copy,hashlib,html,io,json,os,sqlite3,sys,time,unicodedata,uuid
from pathlib import Path
import xml.etree.ElementTree as E
import initial_conversion_supervisor_v1b as initial

R=initial.R;W=initial.W
OWNER='conversion/initial_native_canvas_recovery_v1'
POLICY='retained_initial_native_registered_canvas_v1'
MARKER='initial_native_canvas_recovery_v1'
CANVAS_REASONS=('native_outside_reference_canvas_requires_registered_recovery','native_dimensions_require_larger_renderer_tier')
REQUIRED=('source.tex','reference.bin','source.pdf','source_render.svg','source_render.png','source_dom.json','candidate.drawio','candidate.png','native_render.json')
sha=lambda value:hashlib.sha256(value).hexdigest()
canonical=lambda value:(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode()

class Retained(ValueError):pass
def require(condition,reason):
    if not condition:raise Retained(reason)
def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
def write_json(path,value):atomic(path,canonical(value))
def entry(path,root=R):return {'file':str(Path(path).relative_to(root)),'sha256':sha(Path(path).read_bytes())}
def owned(root,value,owner=OWNER):
    path=(Path(root)/value).resolve();require(path.is_relative_to((Path(root)/owner).resolve()),'artifact_outside_owned_recovery');return path

def configuration(root=R):
    root=Path(root).resolve();scripts=Path(__file__).resolve().parent
    names=['initial_native_canvas_recovery_v1.py','initial_conversion_supervisor_v1.py','initial_conversion_supervisor_v1b.py','initial_conversion_case_v1.py','initial_conversion_case_v1b.py','initial_conversion_process_v1.py','pdf_to_native.py','pdf_fonts.py','svg_convert_v2.py','svg_convert_v3.py','tikz_connectivity.py','native_padding_proof.py','native_page_padding.py','auto_quality_canvas_repair.py','strict_canvas_gate.py','native_worker.py']
    paths=[scripts/name for name in names]+[root/'conversion/rendering_canvas_padding_proof/remote_render.py',root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
    pins={str(path):sha(path.read_bytes()) for path in paths};return {'root':str(root),'policy':POLICY+':'+sha(canonical(pins))[:20],'pins':pins,'max_side':8192,'max_area':64000000}
def check_pins(config):
    for path,digest in config['pins'].items():require(sha(Path(path).read_bytes())==digest,'pinned_recovery_implementation_changed:'+path)

def json_metadata(value):
    if isinstance(value,dict):return {key:json_metadata(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [json_metadata(item) for item in value]
    if value is None or isinstance(value,(str,int,float,bool)):return value
    if type(value).__name__ in ['Point','Rect','Quad','Matrix'] and type(value).__module__.split('.')[0] in ['pymupdf','fitz']:
        return {'pdf_geometry_type':type(value).__name__,'values':[json_metadata(item) for item in value]}
    raise Retained('unknown_metadata_type_preserved_as_typed_failure:'+type(value).__name__)

def _snapshot(db,identifier,key=None):
    job=initial.snapshot(db,identifier);outcome=initial.outcome_snapshot(db,identifier);execution=initial.execution_snapshot(db,identifier);queues={}
    for table in ['harness_queue','harness_queue_v2','harness_queue_v3']:
        if initial.exists(db,table):queues[table]={'columns':[row[1] for row in db.execute('PRAGMA table_info('+table+')')],'rows':db.execute('SELECT * FROM '+table+' WHERE id=?',(identifier,)).fetchall()}
    stage=db.execute('SELECT * FROM '+initial.TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone() if key else None
    recovery=db.execute('SELECT * FROM '+initial.RECOVERY+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone() if key else None
    return {'job':job,'outcome':outcome,'execution':execution,'queues':queues,'stage':stage,'recovery':recovery}

def context(db,identifier,config):
    require(not db.in_transaction,'fresh_readonly_context_required');root=Path(config['root']);require(tuple(row[1] for row in db.execute('PRAGMA table_info(jobs)'))==initial.JOB_COLUMNS,'unknown_jobs_schema');job=initial.snapshot(db,identifier);require(job is not None,'missing_job');original=json.loads(job[4]);manifest=json.loads(job[11]);require(job[5]=='initial_conversion_deferred_v1' and job[12] is None and job[9] is None and job[2]=='tikz','not_current_idle_initial_native_deferred');require(original['pair_sha256']==manifest['id']==identifier and original['format']==manifest['source_format']=='tikz' and original['category']==job[1] and original['source']==job[3],'source_identity_mismatch');execution=initial.execution_snapshot(db,identifier);require(execution and execution[1]=='tikz_source_rendered','current_source_pdf_unavailable');pdf=json.loads(execution[2]);key=(identifier,'native',original['code_sha256'],original['image_sha256'],pdf['pdf_sha256']);snapshot=_snapshot(db,identifier,key);require(snapshot['outcome'] and snapshot['outcome'][5]=='pending' and snapshot['outcome'][1:5]==(job[1],'tikz',key[2],key[3]),'not_matching_pending_original');require(not initial.model_busy(db,identifier),'paid_or_model_owner_busy');stage=snapshot['stage'];recovery=snapshot['recovery'];require(stage and stage[5]=='deferred_recovery_tier' and recovery,'no_matching_terminal_initial_recovery');record=json.loads(recovery[6]);claim=record['claim'];result=record.get('result') or {};require(recovery[5] in CANVAS_REASONS and result.get('reason')==recovery[5],'typed_resource_or_runtime_recovery_not_canvas');require(tuple(claim['key'])==key and claim['token']==stage[8] and claim['policy']==stage[9] and stage[8]==Path(record['work']).name,'terminal_nonce_or_source_revision_mismatch');require(tuple(claim['prior_execution'])==execution,'source_execution_receipt_changed');require(original==json.loads(claim['prior_snapshot'][4]) and manifest==json.loads(claim['prior_snapshot'][11]),'authoritative_input_snapshot_changed');require((manifest['code_sha256'],manifest['image_sha256'])==key[2:4] and pdf['source_code_sha256']==key[2] and pdf['pages']==1,'source_or_pdf_revision_mismatch');work=owned(root,record['work'],initial.OWNER);inventory_entry=result['partial_artifact_inventory'];inventory_path=owned(root,inventory_entry['file'],initial.OWNER);inventory_raw=inventory_path.read_bytes();require(inventory_path.parent==work and sha(inventory_raw)==inventory_entry['sha256'],'partial_inventory_changed');inventory=json.loads(inventory_raw);by={row['file']:row for row in inventory['files']};files={}
    for name in REQUIRED:
        path=work/name;row=by.get(str(path.relative_to(root)));require(row and row.get('sha256') and path.is_file(),'missing_retained_canvas_asset:'+name);raw=path.read_bytes();require(sha(raw)==row['sha256'],'retained_asset_hash_changed:'+name);files[name]=entry(path,root)
    font_files=[]
    for path in sorted((work/'fonts').glob('*')):
        if path.is_file():
            row=by.get(str(path.relative_to(root)));require(row and row.get('sha256')==sha(path.read_bytes()),'retained_font_asset_changed');font_files.append(entry(path,root))
    source_checks={}
    for field,digest in [('source_code',key[2]),('reference_image',key[3])]:
        path=(root/manifest[field]).resolve();require(path.is_relative_to(root) and sha(path.read_bytes())==digest,'authoritative_source_payload_changed');source_checks[field]=entry(path,root)
    require(files['source.tex']['sha256']==key[2] and files['reference.bin']['sha256']==key[3] and files['source.pdf']['sha256']==key[4],'retained_source_or_pdf_hash_mismatch');request=json.loads((work/'request.json').read_text());raw_result=json.loads((work/'result.json').read_text());require(request['id']==raw_result['id']==identifier and request['stage']==raw_result['stage']=='native' and request['source']==original and request['manifest']==manifest and request['stage_input_hash']==key[4] and raw_result['reason']==recovery[5],'retained_request_identity_mismatch');require(request['execution']==pdf,'retained_pdf_execution_changed')
    return {'id':identifier,'key':list(key),'snapshot':snapshot,'original':original,'manifest':manifest,'execution':pdf,'claim_token':claim['token'],'original_claim_policy':claim['policy'],'raw_work':str(work.relative_to(root)),'raw_files':files,'font_files':font_files,'source_checks':source_checks,'inventory':inventory_entry,'recovery_reason':recovery[5],'original_result_details':raw_result.get('details'),'config':config}

def revalidate(db,ctx):
    try:return canonical(_snapshot(db,ctx['id'],tuple(ctx['key'])))==canonical(ctx['snapshot'])
    except (ValueError,TypeError,sqlite3.Error):return False

def verify_outside_audit(directory,info):
    from PIL import Image,ImageChops
    audit=info['outside_page_pixel_audit'];require(audit['white_threshold']==255,'strict255_probe_required');image=Image.open(Path(directory)/'render.padded.png').convert('RGB');require(list(image.size)==audit['padded_native_render_size'],'padded_probe_dimensions_changed');left,top=audit['offset'];width,height=info['canvas'];require(all(type(value) is int and value>=0 for value in [left,top,width,height]) and left+width<=image.width and top+height<=image.height,'invalid_declared_page_in_padded_probe');difference=ImageChops.difference(image,Image.new('RGB',image.size,'white'));channels=difference.split();ink=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2]).point(lambda value:255 if value else 0);ink.paste(0,(left,top,left+width,top+height));actual=sum(ink.histogram()[1:]);require(actual==audit['nonwhite_outside_pixels'],'actual_padded_outside_count_differs_from_renderer_audit');return actual

def registered_canvas(xml,reference,work,render_fn=None):
    from PIL import Image
    from auto_quality_canvas_repair import page_metadata,transform
    from native_padding_proof import render,plan_from_pixels,exact_pixel_proof
    from strict_canvas_gate import require_declared_page
    work=Path(work);work.mkdir(parents=True,exist_ok=True);size=Image.open(io.BytesIO(reference)).size;page_metadata(xml,size);render_fn=render_fn or render;before_png,before=render_fn(xml,*size,work/'baseline');require(before.get('canvas')==list(size) and before.get('renderer_profile')=='native_page_padding_strict_v1','baseline_not_registered_to_reference');boundary=before['outside_page_pixel_audit'];verify_outside_audit(work/'baseline',before)
    if boundary['nonwhite_outside_pixels']:
        canvas=plan_from_pixels((work/'baseline/render.padded.png').read_bytes(),before);kind='complete_native_paint_registered_integer_expansion'
    else:
        canvas={'dx':0,'dy':0,'width':size[0],'height':size[1],'original_page_in_probe':[*boundary['offset'],boundary['offset'][0]+size[0],boundary['offset'][1]+size[1]]};kind='fresh_strict_declared_page_revalidation'
    new_xml,metadata,geometry=transform(xml,size,canvas);png,after=render_fn(new_xml,*geometry['new_page'],work/'candidate');require_declared_page(after,*geometry['new_page']);require(verify_outside_audit(work/'candidate',after)==0,'actual_outside_paint_remains');require(before['renderer_profile']==after['renderer_profile'] and before['renderer_module_sha256']==after['renderer_module_sha256'],'renderer_changed_during_registered_proof');exact=exact_pixel_proof(work/'baseline',work/'candidate',before,after,canvas);require(list(Image.open(io.BytesIO(png)).size)==geometry['new_page'],'candidate_png_not_full_registered_page');atomic(work/'candidate.drawio',new_xml.encode());atomic(work/'candidate.png',png)
    original=Image.open(io.BytesIO(reference)).convert('RGBA');source=Image.new('RGBA',original.size,'white');source.alpha_composite(original);source=source.convert('RGB');composite=Image.new('RGB',tuple(geometry['new_page']),'white');dx,dy=geometry['translation'];composite.paste(source,(dx,dy));require(composite.crop((dx,dy,dx+size[0],dy+size[1])).tobytes()==source.tobytes(),'reference_composition_cropped_or_scaled');composite.save(work/'registered_reference.png')
    return {'kind':kind,'xml':new_xml,'png':png,'before':before,'after':after,'canvas_plan':canvas,'metadata':metadata,'geometry':geometry,'exact_pixel_proof':exact,'reference_composition':{'file':str(work/'registered_reference.png'),'sha256':sha((work/'registered_reference.png').read_bytes()),'reference_rgb_pixels_sha256':sha(source.tobytes()),'full_reference_pixels_preserved':True,'scale':1}}

def regenerate_raw(ctx,work):
    root=Path(ctx['config']['root']);sys.path.append(str(root/'conversion/runtime/python_packages'));import pymupdf
    from pdf_to_native import source_svg,attach_fonts
    from svg_convert_v2 import build
    from tikz_connectivity import bind
    files=ctx['raw_files'];pdf=(root/files['source.pdf']['file']).read_bytes();doc=pymupdf.open(stream=pdf,filetype='pdf')
    try:require(len(doc)==1,'multiframe_pdf_not_supported_by_this_adapter');svg,fonts,pdfstats=source_svg(doc,doc[0],work)
    finally:doc.close()
    require(sha(svg.encode())==files['source_render.svg']['sha256'],'fresh_pdf_source_svg_differs_from_retained_source');raw_font_files={Path(item['file']).name:item['sha256'] for item in ctx['font_files']}
    for font in fonts.values():require(raw_font_files.get(Path(font['file']).name)==font['sha256']==sha(Path(font['file']).read_bytes()),'fresh_pdf_font_bytes_differ_from_retained_fonts')
    require({Path(font['file']).name for font in fonts.values()}==set(raw_font_files),'font_asset_set_changed');dom=json.loads((root/files['source_dom.json']['file']).read_text());source=(root/files['source.tex']['file']).read_bytes();width,height=ctx['manifest']['width'],ctx['manifest']['height'];xml,stats=build(dom,width,height);xml=attach_fonts(xml,fonts);xml,connectivity=bind(xml,dom,source.decode());require(sha(xml.encode())==files['candidate.drawio']['sha256'],'raw_native_reconstruction_not_byte_identical');cells=list(E.fromstring(xml).iter('mxCell'));norm=lambda text:unicodedata.normalize('NFKC',html.unescape(text));require(collections.Counter(norm(obj['text']) for obj in dom['objects'] if obj['type']=='text')==collections.Counter(norm(cell.get('value')) for cell in cells if cell.get('value')),'raw_source_text_counter_differs');return {'svg':svg,'fonts':fonts,'pdf_conversion':json_metadata(pdfstats),'svg_conversion':json_metadata(stats),'connectivity':json_metadata(connectivity),'raw_xml':xml,'vertices':sum(cell.get('vertex')=='1' for cell in cells),'edges':sum(cell.get('edge')=='1' for cell in cells),'bound_edges':sum(bool(cell.get('edge')=='1' and cell.get('source') and cell.get('target')) for cell in cells),'native_text_counter_equal':True}

def build(request,work):
    from PIL import Image
    ctx=copy.deepcopy(request['context']);config=ctx['config'];root=Path(config['root']);work=owned(root,str(Path(work)));check_pins(config);original_files=ctx['raw_files'];frozen_files={}
    for name,witness in original_files.items():
        raw=(root/witness['file']).read_bytes();require(sha(raw)==witness['sha256'],'raw_asset_changed_before_freeze');path=work/'retained_raw'/name;atomic(path,raw);frozen_files[name]=entry(path,root)
    frozen_fonts=[]
    for witness in ctx['font_files']:
        path=work/'retained_raw/fonts'/Path(witness['file']).name;raw=(root/witness['file']).read_bytes();require(sha(raw)==witness['sha256'],'raw_font_changed_before_freeze');atomic(path,raw);frozen_fonts.append(entry(path,root))
    ctx['raw_files']=frozen_files;ctx['font_files']=frozen_fonts;raw_files=ctx['raw_files'];raw_xml=(root/raw_files['candidate.drawio']['file']).read_text();raw_png=(root/raw_files['candidate.png']['file']).read_bytes();reference=(root/raw_files['reference.bin']['file']).read_bytes();regeneration=regenerate_raw(ctx,work/'regenerated_source');registered=registered_canvas(raw_xml,reference,work/'registration');geometry=registered['geometry'];version=work.name;dest=Path('clean/drawio_unified')/ctx['id'][:2]/ctx['id']/'initial_registered_canvas_v1'/version;loc=lambda name:str(dest/name);publish={}
    def payload(locator,path):publish[locator]=entry(path,root);return locator
    ext=Image.open(io.BytesIO(reference)).format.lower();font_records=[]
    for font in regeneration['fonts'].values():
        path=Path(font['file']);metadata={key:value for key,value in font.items() if key not in ['uri','glyph_advances','file']};metadata['file']=payload(loc('fonts/'+path.name),path);font_records.append(metadata)
    source=ctx['original'];common={'id':ctx['id'],'source_pair_sha256':ctx['id'],'source':source['source'],'category':source['category'],'source_format':'tikz','source_record':source,'source_code_sha256':ctx['key'][2],'source_image_sha256':ctx['key'][3],'original_reference':payload(loc('original_image.'+ext),root/raw_files['reference.bin']['file']),'original_source_code':payload(loc('original_source.tex'),root/raw_files['source.tex']['file']),'source_render_pdf':payload(loc('source_render.pdf'),root/raw_files['source.pdf']['file']),'source_render_pdf_sha256':ctx['key'][4],'source_render_svg':payload(loc('source_render.svg'),root/raw_files['source_render.svg']['file']),'source_render_svg_sha256':raw_files['source_render.svg']['sha256'],'source_render_png':payload(loc('source_render.png'),root/raw_files['source_render.png']['file']),'source_render_png_sha256':raw_files['source_render.png']['sha256'],'source_dom':payload(loc('source_dom.json'),root/raw_files['source_dom.json']['file']),'source_dom_sha256':raw_files['source_dom.json']['sha256'],'format':'drawio','model':None,'fonts':font_records,'vertices':regeneration['vertices'],'edges':regeneration['edges'],'bound_edges':regeneration['bound_edges'],'native_text_counter_equal':True,'pdf_conversion':regeneration['pdf_conversion'],'svg_conversion':regeneration['svg_conversion'],'connectivity':regeneration['connectivity'],'execution_audit':str(Path(ctx['execution']['directory'])/'preparation.json'),'converted_at_utc':initial.now()}
    baseline={**common,'code_file':payload(loc('raw_origin/diagram.drawio'),root/raw_files['candidate.drawio']['file']),'code_sha256':raw_files['candidate.drawio']['sha256'],'image_file':payload(loc('raw_origin/image.png'),root/raw_files['candidate.png']['file']),'image_sha256':raw_files['candidate.png']['sha256'],'render':json.loads((root/raw_files['native_render.json']['file']).read_text()),'quality_state':'retained_unregistered_initial_native_proposal','conversion_method':'frozen_initial_native_metadata_reconstruction_only'};baseline_file=work/'baseline_record.json';write_json(baseline_file,baseline);payload(loc('raw_origin/conversion.json'),baseline_file);issues=regeneration['pdf_conversion']['issues']+regeneration['svg_conversion']['issues']+regeneration['connectivity']['issues'];core={**common,'code_file':payload(loc('diagram.drawio'),work/'registration/candidate.drawio'),'code_sha256':sha(registered['xml'].encode()),'image_file':payload(loc('image.png'),work/'registration/candidate.png'),'image_sha256':sha(registered['png']),'render':registered['after'],'unresolved_issues':issues,'quality_state':'pending_fixed_source_native_quality_checks','conversion_method':POLICY};core_file=work/'candidate_core_record.json';write_json(core_file,core)
    frozen_assets={}
    for name,path in [('baseline_record',baseline_file),('candidate_core_record',core_file),('baseline_code',root/raw_files['candidate.drawio']['file']),('baseline_image',root/raw_files['candidate.png']['file']),('candidate_code',work/'registration/candidate.drawio'),('candidate_image',work/'registration/candidate.png')]:frozen_assets[name]=entry(path,root)
    render_assets={}
    for stage in ['baseline','candidate']:
        for name in ['native_render.json','render.padded.png','render.stable_page.png','render.png']:
            path=work/'registration'/stage/name
            if path.exists():render_assets[stage+'/'+name]=entry(path,root)
    proof={'version':1,'policy':config['policy'],'id':ctx['id'],'source_code_sha256':ctx['key'][2],'source_image_sha256':ctx['key'][3],'stage_input_hash':ctx['key'][4],'raw_terminal_nonce':ctx['claim_token'],'raw_recovery_reason':ctx['recovery_reason'],'raw_tight_png_is_not_declared_page_proof':True,'raw_files':raw_files,'source_checks':ctx['source_checks'],'raw_font_files':ctx['font_files'],'source_svg_and_raw_xml_reconstruction_exact':True,'frozen_assets':frozen_assets,'render_assets':render_assets,'metadata':registered['metadata'],'geometry':geometry,'canvas_plan':registered['canvas_plan'],'exact_pixel_proof':registered['exact_pixel_proof'],'reference_registration':{'reference_page':[ctx['manifest']['width'],ctx['manifest']['height']],'output_page':geometry['new_page'],'original_page_offset':geometry['translation'],'scale':1,'no_reference_crop':True},'registered_reference':entry(work/'registration/registered_reference.png',root),'kind':registered['kind'],'pins':config['pins'],'baseline_clean_record':loc('raw_origin/conversion.json'),'baseline_clean_code':baseline['code_file'],'baseline_clean_image':baseline['image_file'],'accepted':False,'model_calls':0};proof_path=work/'proof.json';write_json(proof_path,proof);out={**core,MARKER:{'proof':str(proof_path.relative_to(root)),'proof_sha256':sha(proof_path.read_bytes())}};write_json(work/'candidate_record.json',out);payload(loc('conversion.json'),work/'candidate_record.json');report={'id':ctx['id'],'state':'pending_registered_native_candidate','accepted':False,'model_calls':0,'kind':registered['kind'],'geometry':geometry,'old_raw_tight_png_page':list(Image.open(io.BytesIO(raw_png)).size),'reference_page':[ctx['manifest']['width'],ctx['manifest']['height']],'candidate_page':geometry['new_page'],'old_actual_outside_pixels':registered['before']['outside_page_pixel_audit']['nonwhite_outside_pixels'],'new_actual_outside_pixels':registered['after']['outside_page_pixel_audit']['nonwhite_outside_pixels'],'source_svg_reconstruction_exact':True,'raw_xml_reconstruction_exact':True,'font_assets':len(font_records),'proof':out[MARKER]};proposal={'record':out,'baseline_record':baseline,'publish_files':publish,'report':report,'context':ctx};write_json(work/'proposal.json',proposal);validate_registration(out,reference,registered['xml'],root);check_pins(config);return proposal

def validate_registration(record,reference,xml,root=R,data_root=None):
    from PIL import Image
    from auto_quality_canvas_repair import verify_transform
    from native_padding_proof import exact_pixel_proof
    from strict_canvas_gate import require_declared_page
    root=Path(root);link=record[MARKER];proof_path=owned(root,link['proof']);raw=proof_path.read_bytes();require(sha(raw)==link['proof_sha256'],'registration_proof_hash_changed');proof=json.loads(raw);require(proof['version']==1 and proof['policy'].startswith(POLICY+':'),'unknown_registration_policy');require(record['id']==proof['id'] and record['source_code_sha256']==proof['source_code_sha256'] and record['source_image_sha256']==sha(reference)==proof['source_image_sha256'],'registration_source_identity_changed')
    for path,digest in proof['pins'].items():require(sha(Path(path).read_bytes())==digest,'registration_pin_changed')
    for witness in list(proof['raw_files'].values())+list(proof['source_checks'].values())+proof['raw_font_files']+list(proof['frozen_assets'].values())+list(proof['render_assets'].values())+[proof['registered_reference']]:
        path=(root/witness['file']).resolve();require(path.is_relative_to(root) and sha(path.read_bytes())==witness['sha256'],'registration_asset_hash_changed')
    frozen=proof['frozen_assets'];baseline=json.loads((root/frozen['baseline_record']['file']).read_text());core=json.loads((root/frozen['candidate_core_record']['file']).read_text());require({key:value for key,value in record.items() if key!=MARKER}==core,'candidate_metadata_differs_from_frozen_core');candidate=(root/frozen['candidate_code']['file']).read_text();old=(root/frozen['baseline_code']['file']).read_text();require(candidate==xml and sha(xml.encode())==record['code_sha256'] and record['image_sha256']==frozen['candidate_image']['sha256'],'current_candidate_differs_from_proven_origin');verify_transform(old,candidate,proof['metadata'],proof['geometry']);folder=proof_path.parent/'registration';before=json.loads((folder/'baseline/native_render.json').read_text());after=json.loads((folder/'candidate/native_render.json').read_text());require(after==record['render'],'render_metadata_changed');require_declared_page(after,*proof['geometry']['new_page']);require(before['renderer_module_sha256']==after['renderer_module_sha256']==sha((root/'conversion/rendering_canvas_padding_proof/remote_render.py').read_bytes()),'registered_renderer_changed');require(before['canvas']==list(Image.open(io.BytesIO(reference)).size)==proof['geometry']['old_page'],'registered_original_page_changed');require(exact_pixel_proof(folder/'baseline',folder/'candidate',before,after,proof['canvas_plan'])==proof['exact_pixel_proof'],'registered_complete_paint_or_original_page_changed');composition=Image.open(root/proof['registered_reference']['file']).convert('RGB');ref=Image.open(io.BytesIO(reference)).convert('RGBA');white=Image.new('RGBA',ref.size,'white');white.alpha_composite(ref);dx,dy=proof['geometry']['translation'];require(composition.size==tuple(proof['geometry']['new_page']) and composition.crop((dx,dy,dx+ref.width,dy+ref.height)).tobytes()==white.convert('RGB').tobytes(),'registered_reference_changed_or_cropped');require(proof['reference_registration']=={'reference_page':proof['geometry']['old_page'],'output_page':proof['geometry']['new_page'],'original_page_offset':proof['geometry']['translation'],'scale':1,'no_reference_crop':True},'registration_contract_changed')
    verify_outside_audit(folder/'baseline',before);require(verify_outside_audit(folder/'candidate',after)==0,'registered_candidate_has_actual_outside_paint')
    raw_files=proof['raw_files'];require(baseline['render']==json.loads((root/raw_files['native_render.json']['file']).read_text()),'raw_tight_render_was_relabelled');require(record['fonts']==baseline['fonts'],'canvas_recovery_font_metadata_changed');font_assets={Path(item['file']).name:item for item in proof['raw_font_files']};fonts={}
    for font in baseline['fonts']:
        witness=font_assets.get(Path(font['file']).name);require(witness and witness['sha256']==font['sha256'],'baseline_font_metadata_does_not_bind_retained_font');blob=(root/witness['file']).read_bytes();fonts[font['family']]={'family':font['family'],'uri':'data:font/otf;base64,'+base64.b64encode(blob).decode()}
    from svg_convert_v2 import build as rebuild
    from pdf_to_native import attach_fonts
    from tikz_connectivity import bind
    dom=json.loads((root/raw_files['source_dom.json']['file']).read_text());rebuilt,_=rebuild(dom,*proof['geometry']['old_page']);rebuilt=attach_fonts(rebuilt,fonts);rebuilt,_=bind(rebuilt,dom,(root/raw_files['source.tex']['file']).read_text());require(rebuilt==old,'retained_source_dom_fonts_do_not_reconstruct_baseline_xml')
    if data_root is not None:
        for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_png','source_render_png_sha256')]:require(sha((Path(data_root)/record[key]).read_bytes())==record[digest],'materialized_payload_changed')
        for font in record['fonts']:require(sha((Path(data_root)/font['file']).read_bytes())==font['sha256'],'materialized_font_changed')
    return {'version':1,**proof['reference_registration'],'source_code_sha256':proof['source_code_sha256'],'source_image_sha256':proof['source_image_sha256'],'origin_code_sha256':record['code_sha256'],'origin_image_sha256':record['image_sha256'],'origin_record':str((proof_path.parent/'candidate_record.json').relative_to(root)),'origin_record_sha256':sha((proof_path.parent/'candidate_record.json').read_bytes()),'frozen_origin_code':frozen['candidate_code']['file'],'frozen_origin_image':frozen['candidate_image']['file'],'baseline_record':proof['baseline_clean_record'],'baseline_record_sha256':frozen['baseline_record']['sha256'],'baseline_code':proof['baseline_clean_code'],'baseline_code_sha256':frozen['baseline_code']['sha256'],'baseline_image':proof['baseline_clean_image'],'baseline_image_sha256':frozen['baseline_image']['sha256'],'frozen_baseline_record':frozen['baseline_record']['file'],'frozen_baseline_code':frozen['baseline_code']['file'],'frozen_baseline_image':frozen['baseline_image']['file'],'proof':link['proof'],'proof_sha256':link['proof_sha256'],'renderer_profile':after['renderer_profile'],'renderer_module_sha256':after['renderer_module_sha256'],'scope':'Registration and complete paint/page preservation only; source semantics, actual fonts, editability and visual fidelity require independent QA.'}

def materialize_private(proposal,directory,root=R):
    root=Path(root);directory=owned(root,str(Path(directory)));directory.mkdir(parents=True,exist_ok=False)
    for locator,witness in proposal['publish_files'].items():
        target=(directory/locator).resolve();require(target.is_relative_to(directory/'clean'),'private_locator_outside_clean');source=(root/witness['file']).resolve();raw=source.read_bytes();require(sha(raw)==witness['sha256'],'private_proposal_asset_changed');atomic(target,raw)
    return directory

def registration_record(record,reference,xml,root=R,data_root=None):
    current={key:value for key,value in record.items() if not key.startswith('_verified_')};contract=validate_registration(current,reference,xml,root,data_root);return {**current,'_verified_reference_registration':contract},contract

def source_baseline(record,reference,xml,root=R,data_root=None):
    contract=validate_registration(record,reference,xml,root,data_root);baseline=json.loads((Path(root)/contract['frozen_baseline_record']).read_text());before=(Path(root)/contract['frozen_baseline_code']).read_text();return baseline,before

def prepare(db,identifier,config,work=None,timeout=360):
    check_pins(config);ctx=context(db,identifier,config);root=Path(config['root']);work=Path(work) if work else root/OWNER/identifier/(ctx['key'][4]+'_'+uuid.uuid4().hex);work=owned(root,str(work));work.mkdir(parents=True,exist_ok=False);request={'context':ctx,'accepted':False,'model_calls':0};write_json(work/'request.json',request)
    from initial_conversion_process_v1 import run
    env={key:os.environ[key] for key in ['PATH','HOME','LANG','LC_ALL','TMPDIR'] if key in os.environ};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=str(root/'env'));process=run([sys.executable,str(Path(__file__).resolve()),'--case',str(work/'request.json')],work,timeout,env);write_json(work/'isolation.json',process);require(process['cleanup_complete'],'owned_recovery_subtree_cleanup_incomplete');require(process['ok'] and (work/'proposal.json').exists(),'typed_recovery_runtime_failure_retained:'+str(process));proposal=json.loads((work/'proposal.json').read_text());require(revalidate(db,ctx),'initial_recovery_source_snapshot_changed');reference=(root/ctx['raw_files']['reference.bin']['file']).read_bytes();xml=(root/proposal['publish_files'][proposal['record']['code_file']]['file']).read_text();validate_registration(proposal['record'],reference,xml,root);check_pins(config);return work,proposal,proposal['report']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',type=Path,required=True);args=parser.parse_args();request=json.loads(args.case.read_text())
    try:build(request,args.case.parent)
    except BaseException as error:
        import traceback
        write_json(args.case.parent/'typed_failure.json',{'state':'retained_recovery_failure','error_type':type(error).__name__,'error':str(error)[:3000],'traceback':traceback.format_exc(),'accepted':False,'model_calls':0});raise
