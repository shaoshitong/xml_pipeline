"""Single-revision Range glyph candidate generation, without database writes.

Artifacts stay under the immutable revision workspace. The caller owns CAS and
publication. All displacement parameters come from actual source/native Ranges;
image scores only roll a proposed object back to its exact original payload.
"""
import copy
import datetime
import hashlib
import io
import json
from pathlib import Path
import time
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda blob:hashlib.sha256(blob).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.write.tmp');temporary.write_bytes(blob);temporary.replace(path)


def generate(claim_record,policy,implementation):
    from PIL import Image
    from native_worker import native
    from auto_quality_common import checked,resource_checks,structure_checks,require_rendered_text
    from auto_quality_common_v2 import image_quality
    from html_actual_text_registration import registration_record,_signature,FIELD,OWNER
    import auto_quality_source_vector_v2 as source
    import html_actual_text_alignment as glyph
    raw=claim_record['prior_snapshot'][1];old=json.loads(raw);id=old['id'];digest=old['code_sha256']
    assert not old.get(FIELD),'This producer only aligns a source-v2 baseline once; later font/canvas successors need their own proven delta adapter'
    assert old['source_format']=='html' and old['category']=='poster'
    work=W/'auto_quality_glyph_alignment_v3'/id/(digest+'_'+old['image_sha256'][:16])/policy.rsplit(':',1)[-1];work.mkdir(parents=True,exist_ok=True)
    xml=checked(R,old['code_file'],digest).decode();old_png=checked(R,old['image_file'],old['image_sha256']);reference=checked(R,old['original_reference'],old['source_image_sha256']);source._identity(old,xml)
    from harness_source_provenance import resolve as resolve_source_provenance
    resolve_source_provenance(old)
    verified,contract=registration_record(old,reference,xml)
    reference_offset=contract['original_page_offset'] if contract else [0,0]
    model=E.fromstring(xml).find('.//mxGraphModel');size=[int(round(float(model.get(key,0)))) for key in ('pageWidth','pageHeight')]
    assert all(0<value<=8192 for value in size),'Unsupported native canvas'
    assert contract or list(Image.open(io.BytesIO(reference)).size)==size,'An unequal reference/native page requires an independently verified canvas origin'
    report={'version':3,'id':id,'at':now(),'policy':policy,'implementation':implementation,'input_code_sha256':digest,'input_image_sha256':old['image_sha256'],'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'accepted':False,'requires_full_qa3_original_reference_gates':True,'reference_offset':list(reference_offset),'timings_seconds':{}}
    def save(name,blob):atomic(work/name,blob);return {'file':str((work/name).relative_to(R)),'sha256':sha(blob)}
    files={'previous_record':save('previous_record.json',raw.encode()),'before_xml':save('before.drawio',xml.encode()),'before_png':save('before.png',old_png)}
    started=time.monotonic();dom,served,source_png,capture=glyph.capture_source(old,work/'source');report['timings_seconds']['fresh_source']=time.monotonic()-started
    files['source_dom']=save('source_dom.json',json.dumps(dom,ensure_ascii=False,sort_keys=True).encode())
    baseline_coverage=source._html_coverage(dom,xml,served);paint_order=source._html_paint_order(dom,xml)
    assert baseline_coverage['ok'] and paint_order['ok'],'Source-v2 baseline is not complete in text/geometry/assets/paint order'
    assert not [issue for issue in dom.get('unsupported',[]) if issue.get('reason')!='css_stacking_order'],'Fresh source has unresolved features'
    offset=[baseline_coverage['native_source_paint']['source_layout_translation'][key] for key in ('dx','dy')]
    report.update(source_dom_offset=offset,source_viewport=capture['viewport'],source_capture=capture,baseline_source_coverage=baseline_coverage,baseline_paint_order=paint_order,source_reference_region_diagnostic=glyph.source_region_quality(reference,source_png,dom))
    renderer=W/'rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
    def render(code):
        result=native.native_job(code,*size,180,renderer,8192,runtime);assert result['ok'],'Strict native render failed';require_rendered_text(code,result['native_render']);return result
    started=time.monotonic();baseline=render(xml);before=baseline['native_render'];report['timings_seconds']['baseline_native']=time.monotonic()-started
    assert before.get('selected_image')=='declared_first_page','Current native canvas must be registered/repaired before same-crop glyph alignment'
    files['baseline_fresh_png']=save('baseline.strict.png',baseline['png']);files['baseline_render']=save('baseline.strict_render.json',json.dumps(before,sort_keys=True).encode())
    analysis=glyph.analyze(dom,before,xml,tuple(offset));report['analysis_before']=analysis
    if not analysis['safe_translation_objects']:
        report.update(state='no_change_required',reason='No uniform same-face same-size unclipped actual-Range translation is currently proved');return work,None,report
    started=time.monotonic();candidate,transform=glyph.translate(xml,analysis);fresh=render(candidate);first_info=fresh['native_render']
    files['first_xml']=save('first.drawio',candidate.encode());files['first_render']=save('first.strict_render.json',json.dumps(first_info,sort_keys=True).encode())
    first_analysis=glyph.analyze(dom,first_info,candidate,tuple(offset));changed={item['cell'] for item in transform['changes']}
    candidate,bridge=glyph.bridge_renderer_rounding(candidate,first_analysis,changed)
    if bridge['changes']:fresh=render(candidate)
    after=glyph.analyze(dom,fresh['native_render'],candidate,tuple(offset))
    assert all(row['category']=='actual_glyphs_aligned' for row in after['objects'] if row['cell'] in changed),'Candidate actual glyphs do not match source Ranges'
    assert fresh['native_render'].get('selected_image')=='declared_first_page','Range alignment introduced overflow requiring an independent fixed-clip/page adapter'
    windows=glyph.reference_windows(before,fresh['native_render'],changed,size);passes=[];rejected=[]
    for pass_index in range(4):
        metrics=glyph.same_crop_metrics(reference,baseline['png'],fresh['png'],verified,reference_offset,{cell:windows[cell] for cell in changed})
        bad={cell for cell,row in metrics.items() if not row['nonworsening']};passes.append({'pass':pass_index,'cells':metrics,'rejected_cells':sorted(bad)})
        if not bad:break
        rejected.extend({'cell':cell,'reason':'same_original_same_crop_regressed','metrics':metrics[cell]} for cell in sorted(bad));changed-=bad
        candidate=glyph.revert_cells(xml,candidate,bad);fresh=render(candidate)
    else:
        rejected.extend({'cell':cell,'reason':'bounded_monotone_crop_rollback_did_not_settle'} for cell in sorted(changed));changed=set()
    if not changed:
        report.update(state='no_change_required',reason='All Range proposals were retained as original cells by the nonworsening crop gate',rejected_changes=rejected);return work,None,report
    # Recompute exact final windows and evidence from the retained subset; these
    # are replayed independently by the registration helper before publication.
    windows=glyph.reference_windows(before,fresh['native_render'],changed,size)
    local=glyph.same_crop_metrics(reference,baseline['png'],fresh['png'],verified,reference_offset,windows)
    assert all(row['nonworsening'] for row in local.values()),'Final exact original-reference crops regressed'
    after=glyph.analyze(dom,fresh['native_render'],candidate,tuple(offset))
    assert all(row['category']=='actual_glyphs_aligned' for row in after['objects'] if row['cell'] in changed)
    old_fonts={row['cell']:_signature(row['fonts']) for row in before['actual_platform_font_usage']};new_fonts={row['cell']:_signature(row['fonts']) for row in fresh['native_render']['actual_platform_font_usage']}
    assert old_fonts==new_fonts and all(new_fonts.values()),'Actual physical glyph face/count changed'
    assert all(font.get('isCustomFont') for row in fresh['native_render']['actual_platform_font_usage'] for font in row['fonts'] if font.get('glyphCount',0)),'Current actual font is not embedded'
    source_profile=glyph.check_source_profile_v3(old,candidate,fresh['native_render'],dom,served,tuple(offset),changed)
    assert source_profile['ok'],'Fresh mixed actual-glyph/unchanged-source coverage failed: '+repr(source_profile['failures'][:5])
    new_hash=sha(candidate.encode());png_hash=sha(fresh['png']);prospective={**old,'code_sha256':new_hash,'image_sha256':png_hash}
    structure=structure_checks(candidate);resources=resource_checks(R,prospective,candidate,reference)
    old_quality=image_quality(reference,baseline['png'],verified);new_quality=image_quality(reference,fresh['png'],verified)
    assert new_quality['ssim_1024']>=old_quality['ssim_1024']-.02,'Original-reference global metric regressed more than .02 under the same strict renderer'
    files['current_xml']=save('candidate.drawio',candidate.encode());files['current_png']=save('candidate.png',fresh['png']);files['current_render']=save('candidate.strict_render.json',json.dumps(fresh['native_render'],sort_keys=True).encode())
    report['timings_seconds']['proposal_render_and_rollback']=time.monotonic()-started
    report.update(output_code_sha256=new_hash,output_image_sha256=png_hash,files=files,changed_cells=sorted(changed),reference_windows=windows,local_reference_validation=local,local_reference_rollback_passes=passes,rejected_changes=rejected,range_transform=transform,rounding_bridge=bridge,source_profile=source_profile,source_coverage={**source_profile['evidence']['source_coverage'],'ok':True},structure=structure,resources=resources,physical_glyph_counts_by_cell=new_fonts,all_actual_fonts_custom=True,all_original_cell_physical_faces_and_glyph_counts_preserved=True,same_renderer_quality_before=old_quality,same_renderer_quality_after=new_quality,candidate_checks_passed=True,requires_canvas_repair=False)
    proof_blob=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();atomic(work/'evidence.json',proof_blob)
    link={key:report[key] for key in ('version','policy','input_code_sha256','input_image_sha256','output_code_sha256','output_image_sha256','source_code_sha256','source_image_sha256','changed_cells')};link.update(proof=str((work/'evidence.json').relative_to(R)),proof_sha256=sha(proof_blob),previous_record=files['previous_record']['file'],previous_record_sha256=files['previous_record']['sha256'])
    parent=(R/old['code_file']).parent;target_code=parent/('diagram.actual-range-v3.'+new_hash[:24]+'.drawio');target_png=parent/('image.actual-range-v3.'+new_hash[:24]+'.'+png_hash[:16]+'.png')
    font_proof={'ok':True,'method':'immutable_source_style_and_current_actual_physical_faces_glyph_counts_v3','input_code_sha256':digest,'output_code_sha256':new_hash,'input_image_sha256':old['image_sha256'],'output_image_sha256':png_hash,'all_actual_fonts_custom':True,'physical_faces_and_glyph_counts_preserved':True,'all_original_cell_physical_faces_and_glyph_counts_preserved':True,'font_registry_and_cell_font_styles_unchanged':True,'audit':str((work/'evidence.json').relative_to(R)),'policy':policy,'evidence_file':link['proof'],'evidence_sha256':link['proof_sha256']}
    out={**old,'code_file':str(target_code.relative_to(R)),'code_sha256':new_hash,'image_file':str(target_png.relative_to(R)),'image_sha256':png_hash,'render':fresh['native_render'],'source_coverage':report['source_coverage'],'native_font_validation':font_proof,FIELD:link,'conversion_method':old.get('conversion_method','unknown')+'_actual_range_glyph_alignment_v3','glyph_alignment_prior_pair_archive':str((work/'baseline_archive').relative_to(R)),'quality_state':'pending_automatic_quality_v3_recheck','converted_at_utc':now(),'last_repair':{'method':'deterministic_source_actual_range_glyph_alignment_v3','model':None,'policy':policy},'metrics':{**old.get('metrics',{}),'glyph_alignment_original_reference_ssim_before':old_quality['ssim_1024'],'glyph_alignment_original_reference_ssim_after':new_quality['ssim_1024']}}
    for key in ('accepted_at_utc','automatic_quality_policy','automatic_quality_audit'):out.pop(key,None)
    # Full lineage reconstruction, origin registration and same-crop metric
    # replay occur even before versioned clean payloads are created.
    registration_record(out,reference,candidate)
    atomic(work/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode());atomic(work/'report.json',proof_blob)
    return work,out,report
