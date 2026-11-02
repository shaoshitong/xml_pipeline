"""Fresh HTML glyph coverage; unchanged objects retain every source-v2 gate.

QA3 calls check_html_profile(record, xml, native_render=fresh_info) AFTER its
single current native render. Standalone use renders once if info is absent.
Only the registration helper may establish the trusted changed-cell lineage.
"""
import datetime
import hashlib
import json
from pathlib import Path
import uuid
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
FIELD='html_actual_text_alignment'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def check_html_profile(record,xml,native_render=None):
    import auto_quality_source_vector_v2 as source
    if not record.get(FIELD):return source.check_vector_profile(record,xml)
    result={'supported':True,'ok':False,'profile':'fresh_html_actual_range_glyph_and_unchanged_source_geometry_v3','failures':[],'evidence':{}}
    try:
        assert record.get('source_format')=='html' and record.get('category')=='poster','Glyph profile requires an HTML poster'
        source._identity(record,xml)
        trusted=record.get('_verified_glyph_alignment')
        if trusted is None:
            from html_actual_text_registration import registration_record
            reference=source._read_clean(record['original_reference'],record['source_image_sha256'])
            record,_=registration_record(record,reference,xml)
            trusted=record['_verified_glyph_alignment']
        link=record[FIELD]
        assert trusted['current_code_sha256']==record['code_sha256']==sha(xml.encode()) and trusted['current_image_sha256']==record['image_sha256'],'Trusted glyph lineage is stale'
        assert trusted['proof_sha256']==link['proof_sha256'] and trusted['changed_cells']==sorted(link['changed_cells']),'Trusted glyph scope changed'
        assert trusted['allowed_range_delta_verified'] and trusted['physical_fonts_and_all_glyph_counts_preserved'] and trusted['all_nontext_and_font_registry_unchanged'],'Unproved glyph lineage'
        assert trusted['original_reference_crop_nonworsening_recomputed'],'Original-reference crop proof has not been replayed'
        import html_actual_text_alignment as glyph
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
        work=W/'auto_quality_glyph_alignment_v3_fresh_source'/record['id']/record['code_sha256']/stamp
        dom,served,_,capture=glyph.capture_source(record,work)
        if native_render is None:
            from native_worker import native
            model=E.fromstring(xml).find('.//mxGraphModel');size=[int(round(float(model.get(key,0)))) for key in ('pageWidth','pageHeight')]
            fresh=native.native_job(xml,*size,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
            assert fresh['ok'],'Fresh current native render failed'
            native_render=fresh['native_render']
        assert native_render and native_render.get('actual_text_positions') is not None and native_render.get('actual_platform_font_usage') is not None,'Fresh actual native glyph/font evidence is required'
        paint=source._paint_coverage(dom,xml,'html')
        actual_offset=[paint['source_layout_translation'][key] for key in ('dx','dy')]
        assert all(abs(a-b)<1e-8 for a,b in zip(actual_offset,trusted['source_dom_offset'])),'Fresh source/native nontext registration changed'
        # Glyph movement can change nominal text boxes; the prototype checker
        # waives only those changed cells whose every fresh actual grapheme is
        # within .08px. Images, stencils, text values, source clips, order,
        # unchanged text geometry and all unresolved source features remain gates.
        checked=glyph.check_source_profile_v3(record,xml,native_render,dom,served,tuple(actual_offset),trusted['changed_cells'])
        from html_actual_text_registration import _owned,_signature
        _,proof_blob=_owned(R,link['proof'],link['proof_sha256']);proof=json.loads(proof_blob)
        _,baseline_blob=_owned(R,proof['files']['baseline_render']['file'],proof['files']['baseline_render']['sha256']);before=json.loads(baseline_blob)
        old={row['cell']:_signature(row['fonts']) for row in before['actual_platform_font_usage']};current={row['cell']:_signature(row['fonts']) for row in native_render['actual_platform_font_usage']}
        assert old==current and all(current.values()),'Fresh original physical faces/glyph counts changed'
        assert all(font.get('isCustomFont') for row in native_render['actual_platform_font_usage'] for font in row['fonts'] if font.get('glyphCount',0)),'Fresh actual physical font is not embedded'
        result.update(ok=checked['ok'],failures=checked['failures'],evidence={**checked['evidence'],'fresh_source_capture':capture,'fresh_source_work':str(work.relative_to(R)),'current_output_image_sha256':record['image_sha256'],'verified_glyph_lineage_sha256':link['proof_sha256'],'fresh_actual_native_evidence_reused':True,'all_original_physical_faces_and_glyph_counts_preserved':True,'full_original_reference_global_foreground_and_local_gates_required':True})
    except Exception as exc:
        result['failures'].append({'reason':'glyph_source_profile_validation_error','error':repr(exc)[:1500]})
    return result
