"""Replayable glyph-v3 -> fixed-clip-v4 / source-space-v5 lineage for QA4.

No registration offset is fitted to pixels. The old canvas/font/glyph origin is
validated first; immutable source/native Range evidence reconstructs every new
text-only step. Original-reference crops are independently recomputed.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');OWNER='conversion/auto_quality_html_text_layout_v5';FIELD='html_text_layout_v5'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def owned(root,entry):
    path=(Path(root)/entry['file']).resolve();assert path.is_relative_to((Path(root)/OWNER).resolve()),'Text-layout evidence outside the owned revision';blob=path.read_bytes();assert sha(blob)==entry['sha256'],'Text-layout evidence hash changed';return blob


def _base_registration(record,reference,xml,root):
    assert Path(root).resolve()==R.resolve(),'Isolated tests need an explicit root-aware origin resolver'
    if record.get('html_actual_text_alignment'):
        from html_actual_text_registration import registration_record as original
        return original(record,reference,xml,root)
    from auto_quality_common_v2 import registration_record as original
    return original(record,reference,xml)


def _signature_rows(info):
    from html_actual_text_registration import _signature
    return {row['cell']:_signature(row['fonts']) for row in info['actual_platform_font_usage']}


def require_same_fonts(before,after):
    a,b=_signature_rows(before),_signature_rows(after);assert a==b and all(b.values()),'Any original physical face/glyph count changed'
    assert all(font.get('isCustomFont') for row in after['actual_platform_font_usage'] for font in row['fonts'] if font.get('glyphCount',0)),'Actual physical font is not embedded'


def require_same_actual_positions(expected,current,tolerance=.03):
    flatten=lambda info:{row['cell']:[char for run in row['runs'] for char in run['chars']] for row in info['actual_text_positions']}
    a,b=flatten(expected),flatten(current);assert set(a)==set(b),'Fresh actual text-cell membership changed'
    for key in a:
        assert [char['text'] for char in a[key]]==[char['text'] for char in b[key]],'Fresh actual rendered logical text changed'
        assert all(abs(old[name]-new[name])<=tolerance for old,new in zip(a[key],b[key]) for name in ('x','y','width','height')),'Fresh actual glyph positions differ from the replayed candidate'


def replay_steps(proof,root=R,dom_override=None):
    """Recompute the deterministic XML and native/font/clip proof for each step."""
    files=proof['files'];read=lambda name:owned(root,files[name]);dom=dom_override if dom_override is not None else json.loads(read('source_dom'));offset=tuple(proof['source_dom_offset']);viewport=proof['source_viewport'];xml=read('before_xml').decode();info=json.loads(read('baseline_render'));steps=[];space_cells=set();clip_cells=set()
    assert proof['steps'],'Text-layout proof has no steps'
    for step in proof['steps']:
        before_xml=owned(root,step['before_xml']).decode();before_info=json.loads(owned(root,step['before_render']));after_xml=owned(root,step['after_xml']).decode();after_info=json.loads(owned(root,step['after_render']));after_png=owned(root,step['after_png'])
        assert E.canonicalize(before_xml)==E.canonicalize(xml),'Text-layout operation chain was reordered or skipped'
        require_same_actual_positions(info,before_info);require_same_fonts(info,before_info)
        changed={row['cell'] for row in step['proof']['changes']};assert changed,'Empty text-layout operation'
        assert not changed&(space_cells|clip_cells),'One source object may be changed by only one new primitive per revision'
        if step['kind']=='space_advance_v5':
            import html_text_whitespace_advance_v5 as spaces
            verification=spaces.verify(before_xml,after_xml,step['proof'],dom,before_info,after_info,offset);space_cells|=changed
            assert not step.get('pixel_groups'),'Whitespace steps cannot carry an unrelated clip waiver'
        elif step['kind']=='clip_locked_v4':
            import html_actual_text_clip_alignment_v4 as clip
            verification=clip.verify_clip_locked(before_xml,after_xml,step['proof'],dom,before_info,after_info,viewport,offset);groups=clip.disjoint_clip_groups(step['proof'],after_info)
            assert len(groups)==len(step['pixel_groups']),'Clip raster-mask proof groups are missing'
            for expected,actual in zip(groups,step['pixel_groups']):
                assert actual['group']==expected,'Clip influence grouping or source mask changed'
                ids={row['cell'] for row in expected};unclipped,background=clip.diagnostic_variants(after_xml,ids)
                assert E.canonicalize(unclipped)==E.canonicalize(owned(root,actual['unclipped_xml']).decode()) and E.canonicalize(background)==E.canonicalize(owned(root,actual['background_xml']).decode()),'Clip diagnostic XML has an unrelated change'
                pixels=clip.pixel_mask_proof(after_png,owned(root,actual['unclipped_png']),owned(root,actual['background_png']),expected);assert pixels['ok'],'Actual native pixels do not implement the source clip mask'
            clip_cells|=changed
        else:raise AssertionError('Unsupported text-layout primitive: '+str(step['kind']))
        require_same_fonts(before_info,after_info);steps.append({'kind':step['kind'],'cells':sorted(changed),'verification':verification});xml,info=after_xml,after_info
    assert E.canonicalize(xml)==E.canonicalize(read('current_xml').decode()),'Final XML differs from the replayed steps'
    require_same_actual_positions(info,json.loads(read('current_render')));require_same_fonts(info,json.loads(read('current_render')))
    assert sha(owned(root,proof['steps'][-1]['after_png']))==sha(read('current_png')),'Current PNG is not the last operation render'
    return {'steps':steps,'whitespace_cells':sorted(space_cells),'clip_cells':sorted(clip_cells),'changed_cells':sorted(space_cells|clip_cells),'source_dom':dom,'current_native':info}


def registration_record(record,reference,xml,root=R,_depth=0):
    assert _depth<8,'Text-layout lineage is cyclic or too deep'
    record={key:value for key,value in record.items() if not key.startswith('_verified_')}
    assert sha(reference)==record['source_image_sha256'],'Original reference hash changed'
    if not record.get(FIELD):return _base_registration(record,reference,xml,root)
    link=record[FIELD];assert link['version']==5;assert link['output_code_sha256']==record['code_sha256']==sha(xml.encode()) and link['output_image_sha256']==record['image_sha256'],'Current text-layout link is stale'
    for key in ('source_code_sha256','source_image_sha256'):assert link[key]==record[key],'Original source identity changed'
    proof_entry={'file':link['proof'],'sha256':link['proof_sha256']};proof=json.loads(owned(root,proof_entry));assert proof['version']==5 and proof['policy']==link['policy'] and proof['accepted'] is False
    for key in ('id','input_code_sha256','input_image_sha256','output_code_sha256','output_image_sha256','source_code_sha256','source_image_sha256'):
        assert proof[key]==(record[key] if key=='id' else link[key]),'Text-layout proof/link identity changed'
    files=proof['files'];required={'previous_record','before_xml','before_png','baseline_fresh_png','baseline_render','source_dom','source_capture','source_png','current_xml','current_png','current_render'};assert required<=set(files),'Frozen text-layout inputs missing'
    for entry in files.values():owned(root,entry)
    previous_entry={'file':link['previous_record'],'sha256':link['previous_record_sha256']};assert files['previous_record']==previous_entry;previous=json.loads(owned(root,previous_entry));before_xml=owned(root,files['before_xml']).decode();current_png=owned(root,files['current_png'])
    assert previous['code_sha256']==link['input_code_sha256']==sha(before_xml.encode()) and previous['image_sha256']==link['input_image_sha256']==sha(owned(root,files['before_png']))
    assert xml==owned(root,files['current_xml']).decode() and sha(current_png)==record['image_sha256']
    for key in ('id','source_code_sha256','source_image_sha256','original_source_code','original_reference'):assert record[key]==previous[key],'Text-layout changed original source identity/locator'
    for key in ('source_pair_sha256','source_record','original_asset_root','source_assets','original_vector_assets','native_embedded_fonts','fonts','previous_candidate_archive','source_font_recovery_archive','html_actual_text_alignment','auto_quality_canvas_repair','native_canvas_contract','native_page_padding'):
        assert record.get(key)==previous.get(key),'Text-layout changed source/font/canvas/archive metadata: '+key
    for pathkey,digestkey in [('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        path=(Path(root)/record[pathkey]).resolve();assert path.is_relative_to((Path(root)/'clean').resolve()) and sha(path.read_bytes())==record[digestkey],'Original clean source changed'
    previous_verified,contract=registration_record(previous,reference,before_xml,root,_depth+1)
    inherited=previous_verified.get('_verified_html_text_layout',{}).get('combined_glyph_cells') or previous_verified.get('_verified_glyph_alignment',{}).get('changed_cells') or []
    inherited_clips=previous_verified.get('_verified_html_text_layout',{}).get('combined_clip_cells',[])
    replayed=replay_steps(proof,root);changed=set(replayed['changed_cells']);assert changed and sorted(changed)==sorted(link['changed_cells'])==sorted(proof['changed_cells']);assert not changed&set(inherited),'The new operation changed an inherited actual-glyph proof object'
    from auto_quality_source_vector_v2 import _paint_coverage,_html_paint_order,_plain
    dom=replayed['source_dom'];capture=json.loads(owned(root,files['source_capture']))
    assert capture['source_code_sha256']==record['source_code_sha256'] and capture['source_image_sha256']==record['source_image_sha256'],'Source capture identity changed'
    from PIL import Image
    assert proof['source_viewport']==capture['viewport']==list(Image.open(io.BytesIO(reference)).size),'Source capture viewport changed'
    assert capture['fresh_source_dom_sha256']==sha(json.dumps(dom,sort_keys=True).encode()) and capture['fresh_source_png_sha256']==sha(owned(root,files['source_png'])),'Source capture DOM/PNG changed'
    paint=_paint_coverage(dom,before_xml,'html');offset=[paint['source_layout_translation'][key] for key in ('dx','dy')];assert list(proof['source_dom_offset'])==offset,'Source offset lacks immutable nontext geometry evidence'
    assert _html_paint_order(dom,before_xml)['ok'],'Baseline source paint ordering changed'
    import html_actual_text_alignment as glyph
    before_info=json.loads(owned(root,files['baseline_render']));actual_before={row['cell']:row for row in glyph.analyze(dom,before_info,before_xml,tuple(offset))['objects']};permitted={'source_text_position_changed','source_object_size_changed'}
    assert all(error.get('reason') in permitted and error.get('cell') in inherited and actual_before[error['cell']]['category']=='actual_glyphs_aligned' for error in paint['errors']),'Baseline source geometry is unproved'
    cells={cell.get('id'):cell for cell in E.fromstring(before_xml).iter('mxCell')};assert all(str(obj['id']+1) in cells and _plain(cells[str(obj['id']+1)].get('value',''))==obj['text'] for obj in dom['objects'] if obj['type']=='text'),'Baseline source text/ID changed'
    before_model=E.fromstring(before_xml).find('.//mxGraphModel');model=E.fromstring(xml).find('.//mxGraphModel');assert before_model is not None and model is not None and before_model.attrib==model.attrib,'Text-layout changed page/font registry'
    offset_reference=contract['original_page_offset'] if contract else [0,0];assert list(proof['reference_offset'])==list(offset_reference),'Reference offset lacks verified canvas origin'
    if contract:assert [float(model.get(key)) for key in ('pageWidth','pageHeight')]==contract['output_page'],'Text-layout successor changed the registered page'
    from PIL import Image
    size=Image.open(io.BytesIO(current_png)).size
    page=[float(model.get(key)) for key in ('pageWidth','pageHeight')]
    assert list(size)==page and (contract is not None or list(Image.open(io.BytesIO(reference)).size)==page),'Text-layout native/reference page has no verified registration'
    current_info=json.loads(owned(root,files['current_render']));windows=glyph.reference_windows(before_info,current_info,changed,size);assert windows==proof['reference_windows'],'Fixed original-reference crop windows changed'
    local=glyph.same_crop_metrics(reference,owned(root,files['baseline_fresh_png']),current_png,previous_verified,offset_reference,windows);assert set(local)==set(proof['local_reference_validation']) and all(row['nonworsening'] for row in local.values()),'An original-reference object crop regressed'
    for key,row in local.items():assert row['box']==proof['local_reference_validation'][key]['box'] and all(abs(row[name]-proof['local_reference_validation'][key][name])<=1e-7 for name in ('before_ssim','after_ssim')),'Frozen original crop evidence changed'
    context={'current_code_sha256':record['code_sha256'],'current_image_sha256':record['image_sha256'],'proof_file':link['proof'],'proof_sha256':link['proof_sha256'],'previous_record_file':link['previous_record'],'previous_record_sha256':link['previous_record_sha256'],'source_dom_offset':offset,'source_viewport':proof['source_viewport'],'whitespace_cells':replayed['whitespace_cells'],'clip_cells':replayed['clip_cells'],'changed_cells':sorted(changed),'inherited_glyph_cells':sorted(inherited),'combined_clip_cells':sorted(set(inherited_clips)|set(replayed['clip_cells'])),'combined_glyph_cells':sorted(set(inherited)|set(replayed['clip_cells'])),'deterministic_steps_replayed':True,'all_original_physical_faces_and_glyph_counts_preserved':True,'all_nontext_geometry_assets_and_font_registry_unchanged':True,'original_fixed_crops_nonworsening_recomputed':True}
    verified={**record,'_verified_html_text_layout':context}
    if contract:
        contract={**contract,'current_revision_verified':True,'html_text_layout_delta_verified':True,'text_layout_proof':link['proof'],'text_layout_proof_sha256':link['proof_sha256'],'current_code_sha256':record['code_sha256'],'current_image_sha256':record['image_sha256']};verified['_verified_reference_registration']=contract
    return verified,contract
