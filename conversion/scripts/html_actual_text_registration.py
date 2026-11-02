"""Verified glyph-only successors of existing reference-page registration.

API: registration_record(record, reference_bytes, current_xml, root=R) returns
(verified_record, current_verified_contract_or_None). It never guesses a pixel
offset. Existing canvas/optional font-only origins use QA v2's validator; the
new successor is reconstructed from frozen actual source/native glyph evidence.
"""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029')
FIELD='html_actual_text_alignment'
OWNER='conversion/auto_quality_glyph_alignment_v3'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def _owned(root,relative,digest=None):
    path=(Path(root)/relative).resolve();assert path.is_relative_to((Path(root)/OWNER).resolve()),'Glyph evidence outside owned revision workspace'
    blob=path.read_bytes()
    if digest:assert sha(blob)==digest,'Glyph evidence hash changed: '+str(relative)
    return path,blob


def _clean(root,relative,digest):
    path=(Path(root)/relative).resolve();assert path.is_relative_to((Path(root)/'clean').resolve()),'Glyph payload outside clean'
    blob=path.read_bytes();assert sha(blob)==digest,'Glyph payload hash changed';return blob


def _base_registration(record,reference,xml,root):
    # Production roots are explicit. Isolated tests replace this one resolver,
    # while the graph/source/font delta checks below still execute unchanged.
    assert Path(root).resolve()==R.resolve(),'Use an injected root-aware origin resolver for isolated tests'
    from auto_quality_common_v2 import registration_record as baseline_registration
    return baseline_registration(record,reference,xml)


def _canonical(xml):return E.canonicalize(xml if isinstance(xml,str) else xml.decode())


def _signature(fonts):
    result={}
    for font in fonts:
        if font.get('glyphCount',0):
            assert font.get('postScriptName'),'Missing actual physical face identity'
            result[font['postScriptName']]=result.get(font['postScriptName'],0)+int(font['glyphCount'])
    return result


def validate_glyph_delta(record,xml,root=R):
    """Return a trusted current-delta context, without inventing registration."""
    root=Path(root);link=record[FIELD]
    assert link['version']==3 and isinstance(link['policy'],str)
    assert sha(xml.encode())==record['code_sha256']==link['output_code_sha256'],'Glyph link does not describe the current XML'
    assert record['image_sha256']==link['output_image_sha256'],'Glyph image revision changed'
    for key in ('source_code_sha256','source_image_sha256'):
        assert record[key]==link[key],'Glyph source identity changed'
    proof_path,proof_raw=_owned(root,link['proof'],link['proof_sha256']);proof=json.loads(proof_raw)
    assert proof['version']==3 and proof['policy']==link['policy'] and proof['accepted'] is False
    for key in ('id','input_code_sha256','input_image_sha256','output_code_sha256','output_image_sha256','source_code_sha256','source_image_sha256'):
        if key=='id':assert proof[key]==record[key]
        else:assert proof[key]==link[key],'Glyph proof/link revision mismatch: '+key
    assert sorted(proof['changed_cells'])==sorted(link['changed_cells']) and proof['changed_cells'],'Glyph changed-cell set is missing or altered'
    files={}
    required={'previous_record','before_xml','before_png','baseline_fresh_png','current_xml','current_png','source_dom','baseline_render','first_xml','first_render','current_render'}
    assert required<=set(proof['files']),'Glyph lineage is missing frozen inputs'
    for name,entry in proof['files'].items():
        _,blob=_owned(root,entry['file'],entry['sha256']);files[name]=blob
    _,previous_raw=_owned(root,link['previous_record'],link['previous_record_sha256']);previous=json.loads(previous_raw)
    assert previous_raw==files['previous_record'],'Glyph previous-record references differ'
    assert previous['code_sha256']==link['input_code_sha256'] and previous['image_sha256']==link['input_image_sha256']
    assert all(previous[key]==record[key] for key in ('id','source_code_sha256','source_image_sha256'))
    assert sha(files['before_xml'])==previous['code_sha256'] and sha(files['before_png'])==previous['image_sha256']
    assert sha(files['current_xml'])==record['code_sha256'] and files['current_xml'].decode()==xml
    assert sha(files['current_png'])==record['image_sha256']
    for key,digest in [('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        assert record[key]==previous[key],'Glyph original-source path changed'
        _clean(root,record[key],record[digest])
    before_xml=files['before_xml'].decode();dom=json.loads(files['source_dom']);before=json.loads(files['baseline_render']);first=json.loads(files['first_render']);after=json.loads(files['current_render'])
    from auto_quality_source_vector_v2 import _paint_coverage,_html_paint_order,_plain
    source_paint=_paint_coverage(dom,before_xml,'html');assert source_paint['ok'],'Frozen glyph baseline source geometry is not verified'
    assert _html_paint_order(dom,before_xml)['ok'],'Frozen glyph baseline source paint order changed'
    expected_offset=[source_paint['source_layout_translation'][key] for key in ('dx','dy')]
    assert all(abs(float(a)-float(b))<1e-8 for a,b in zip(proof['source_dom_offset'],expected_offset)) and len(proof['source_dom_offset'])==2,'Glyph source offset lacks exact source-geometry proof'
    source_text={str(obj['id']+1):obj['text'] for obj in dom['objects'] if obj['type']=='text'}
    before_cells={cell.get('id'):cell for cell in E.fromstring(before_xml).iter('mxCell')}
    assert all(key in before_cells and _plain(before_cells[key].get('value',''))==text for key,text in source_text.items()),'Frozen source text/identity mismatch'
    import html_actual_text_alignment as glyph
    analysis=glyph.analyze(dom,before,before_xml,tuple(proof['source_dom_offset']));changed=set(proof['changed_cells'])
    eligibility={item['cell']:item for item in analysis['objects']}
    assert all(key in eligibility and eligibility[key]['safe_translation'] for key in changed),'Glyph delta is not derived from uniform same-face/same-size source Ranges'
    all_candidate,all_transform=glyph.translate(before_xml,analysis)
    assert _canonical(all_candidate)==_canonical(files['first_xml']),'Frozen first glyph candidate differs from the fixed Range transform'
    first_analysis=glyph.analyze(dom,first,all_candidate,tuple(proof['source_dom_offset']))
    subset=copy.deepcopy(analysis)
    for item in subset['objects']:item['safe_translation']=item['cell'] in changed
    expected,transform=glyph.translate(before_xml,subset)
    expected,bridge=glyph.bridge_renderer_rounding(expected,first_analysis,changed)
    assert _canonical(expected)==_canonical(xml),'Glyph lineage altered a shape, asset, font, clip, text, ordering or unproved geometry'
    after_analysis=glyph.analyze(dom,after,xml,tuple(proof['source_dom_offset']))
    result={item['cell']:item for item in after_analysis['objects']}
    assert all(result[key]['category']=='actual_glyphs_aligned' for key in changed),'Current actual glyphs do not match proven source Ranges'
    old_usage={row['cell']:row['fonts'] for row in before.get('actual_platform_font_usage',[])};new_usage={row['cell']:row['fonts'] for row in after.get('actual_platform_font_usage',[])}
    assert set(old_usage)==set(new_usage),'Actual native text-cell membership changed'
    for key in old_usage:
        assert _signature(old_usage.get(key,[]))==_signature(new_usage.get(key,[])) and _signature(new_usage.get(key,[])),'Original physical glyph face/count changed'
    assert all(font.get('isCustomFont') for fonts in new_usage.values() for font in fonts if font.get('glyphCount',0)),'Current glyph renderer used an unembedded font'
    assert set(proof['local_reference_validation'])==changed and all(row['nonworsening'] for row in proof['local_reference_validation'].values()),'Missing nonworsening original-reference crop proof'
    current_model=E.fromstring(xml).find('.//mxGraphModel');old_model=E.fromstring(before_xml).find('.//mxGraphModel')
    assert current_model is not None and old_model is not None and current_model.attrib==old_model.attrib,'Glyph alignment changed page/font-registry attributes'
    return {'previous_record':previous,'previous_record_file':link['previous_record'],'previous_record_sha256':link['previous_record_sha256'],'previous_xml':before_xml,'proof':proof,'proof_file':link['proof'],'proof_sha256':link['proof_sha256'],'changed_cells':sorted(changed),'current_code_sha256':record['code_sha256'],'current_image_sha256':record['image_sha256'],'source_dom_offset':expected_offset,'source_viewport':proof['source_viewport'],'allowed_range_delta_verified':True,'physical_fonts_and_all_glyph_counts_preserved':True,'all_nontext_and_font_registry_unchanged':True}


def registration_record(record,reference,xml,root=R,_depth=0):
    """QA3 entry point, called before resource/structure/current native checks."""
    assert _depth<8,'Glyph registration lineage is cyclic or too deep'
    record={key:value for key,value in record.items() if not key.startswith('_verified_')}
    assert sha(reference)==record['source_image_sha256'],'Original reference changed'
    if not record.get(FIELD):return _base_registration(record,reference,xml,root)
    context=validate_glyph_delta(record,xml,root)
    previous=context['previous_record'];before_xml=context['previous_xml']
    before_verified,contract=registration_record(previous,reference,before_xml,root,_depth+1)
    if contract:
        model=E.fromstring(xml).find('.//mxGraphModel')
        assert [float(model.get(key,'nan')) for key in ('pageWidth','pageHeight')]==contract['output_page'],'Glyph successor changed the registered canvas'
        contract={**contract,'current_revision_verified':True,'glyph_alignment_delta_verified':True,'glyph_delta_report':context['proof_file'],'glyph_delta_report_sha256':context['proof_sha256'],'current_code_sha256':record['code_sha256'],'current_image_sha256':record['image_sha256'],'scope':'Validated canvas/optional font-only origin followed solely by reconstructed actual-Range text deltas. Source, resources, fresh rendering and full original-reference fidelity remain QA gates.'}
    import io
    from PIL import Image
    import html_actual_text_alignment as glyph
    proof=context['proof'];files=proof['files'];offset=contract['original_page_offset'] if contract else [0,0]
    assert list(proof['reference_offset'])==list(offset),'Glyph reference offset lacks verified origin contract'
    blobs={name:_owned(root,entry['file'],entry['sha256'])[1] for name,entry in files.items()}
    current_size=Image.open(io.BytesIO(blobs['current_png'])).size
    before_info=json.loads(blobs['baseline_render']);current_info=json.loads(blobs['current_render'])
    windows=glyph.reference_windows(before_info,current_info,set(context['changed_cells']),current_size)
    assert windows==proof['reference_windows'],'Glyph local comparison window was altered'
    metrics=glyph.same_crop_metrics(reference,blobs['baseline_fresh_png'],blobs['current_png'],before_verified,offset,windows)
    assert all(row['nonworsening'] for row in metrics.values()),'Current Range candidate regresses an original-reference glyph crop'
    for key,row in metrics.items():
        supplied=proof['local_reference_validation'][key]
        assert row['box']==supplied['box'] and all(abs(row[name]-supplied[name])<1e-7 for name in ('before_ssim','after_ssim')),'Glyph local image proof changed'
    context['original_reference_crop_nonworsening_recomputed']=True
    public={key:value for key,value in context.items() if key not in ('previous_record','previous_xml','proof')}
    verified={**record,'_verified_glyph_alignment':public}
    if contract:verified['_verified_reference_registration']=contract
    return verified,contract
