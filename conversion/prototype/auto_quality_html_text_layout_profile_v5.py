"""QA4 fresh-source and current native proof for replayed text-layout v5.

The caller reuses its single current native render. Clip steps additionally need
actual_clip_boxes (the existing clipbox_strict renderer already emits them).
No full original-image gate is relaxed or substituted here.
"""
import datetime
import hashlib
import json
from pathlib import Path
import uuid
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';FIELD='html_text_layout_v5'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def check_html_profile(record,xml,native_render=None):
    if not record.get(FIELD):
        from auto_quality_html_glyph_profile_v3 import check_html_profile as prior
        return prior(record,xml,native_render=native_render)
    result={'supported':True,'ok':False,'profile':'fresh_source_space_advances_fixed_clip_and_inherited_glyph_geometry_v5','failures':[],'evidence':{}}
    try:
        import auto_quality_source_vector_v2 as source
        from html_text_layout_registration_v5 import registration_record,replay_steps,owned,require_same_fonts,require_same_actual_positions
        assert record.get('source_format')=='html' and record.get('category')=='poster','Text-layout profile requires an HTML poster'
        source._identity(record,xml);trusted=record.get('_verified_html_text_layout')
        if trusted is None:
            reference=source._read_clean(record['original_reference'],record['source_image_sha256']);record,_=registration_record(record,reference,xml);trusted=record['_verified_html_text_layout']
        link=record[FIELD];assert trusted['current_code_sha256']==record['code_sha256']==sha(xml.encode()) and trusted['current_image_sha256']==record['image_sha256'] and trusted['proof_sha256']==link['proof_sha256'],'Trusted text-layout lineage is stale'
        assert trusted['deterministic_steps_replayed'] and trusted['all_original_physical_faces_and_glyph_counts_preserved'] and trusted['all_nontext_geometry_assets_and_font_registry_unchanged'] and trusted['original_fixed_crops_nonworsening_recomputed'],'Incomplete text-layout registration proof'
        proof=json.loads(owned(R,{'file':link['proof'],'sha256':link['proof_sha256']}))
        import html_actual_text_alignment as glyph
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8];work=W/'auto_quality_html_text_layout_v5_fresh_source'/record['id']/record['code_sha256']/stamp
        dom,served,_,capture=glyph.capture_source(record,work)
        # Recompute parameters against fresh source Ranges/CSS clips. Hashed
        # source-DOM flags alone can never authorize a nominal-box waiver.
        replayed=replay_steps(proof,R,dom_override=dom)
        assert replayed['whitespace_cells']==trusted['whitespace_cells'] and replayed['clip_cells']==trusted['clip_cells'],'Fresh source changed the proved operation scope'
        if native_render is None:
            from native_worker import native
            model=E.fromstring(xml).find('.//mxGraphModel');size=[int(round(float(model.get(key)))) for key in ('pageWidth','pageHeight')]
            fresh=native.native_job(xml,*size,180,W/'rendering_clipbox_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];native_render=fresh['native_render']
        require_same_actual_positions(replayed['current_native'],native_render);require_same_fonts(replayed['current_native'],native_render)
        paint=source._paint_coverage(dom,xml,'html');offset=[paint['source_layout_translation'][key] for key in ('dx','dy')];assert all(abs(a-b)<=1e-8 for a,b in zip(offset,trusted['source_dom_offset'])),'Fresh source nontext/page translation changed'
        checked=glyph.check_source_profile_v3(record,xml,native_render,dom,served,tuple(offset),trusted['combined_glyph_cells'])
        if trusted['combined_clip_cells']:
            import html_actual_text_clip_alignment_v4 as clip
            assert native_render.get('actual_clip_boxes') is not None,'Fresh native clip reference boxes are required for clip-layout revisions'
            actual={row['cell']:row['clips'] for row in native_render['actual_clip_boxes']};objects={str(row['id']+1):row for row in dom['objects'] if row['type']=='text'}
            for key in trusted['combined_clip_cells']:
                assert len(actual.get(key,[]))==1,'Fresh current clip is missing or duplicated'
                expected=clip.source_rectangle(objects[key],capture['viewport'],tuple(offset));measured=clip.native_rectangle(actual[key][0]);assert all(abs(a-b)<=.03 for a,b in zip(measured,expected)),'Fresh actual clip moved away from the source CSS mask'
        result.update(ok=checked['ok'],failures=checked['failures'],evidence={**checked['evidence'],'current_output_image_sha256':record['image_sha256'],'versioned_layout_proof_sha256':link['proof_sha256'],'fresh_source_capture':capture,'fresh_source_work':str(work.relative_to(R)),'fresh_native_render_reused':True,'fresh_source_deterministic_steps_replayed':replayed['steps'],'whitespace_cells':trusted['whitespace_cells'],'fixed_clip_cells':trusted['combined_clip_cells'],'new_fixed_clip_cells':trusted['clip_cells'],'all_original_physical_faces_and_glyph_counts_preserved':True,'logical_text_geometry_assets_and_font_registry_unchanged':True,'original_reference_global_foreground_and_each_local_line_gates_still_required':True})
    except Exception as error:result['failures'].append({'reason':'text_layout_source_profile_validation_error','error':repr(error)[:1800]})
    return result
