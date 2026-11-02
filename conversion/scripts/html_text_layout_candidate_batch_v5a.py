"""Isolated-object fallback builder using frozen v5 registration/primitives.

No jobs, model queue, API or clean publication writes occur here. A future batch
coordinator can wrap this function with full revision CAS and candidate-only
publication. Every operation has fixed Range-derived parameters and exact-object
rollback when an original-reference crop regresses.
"""
import copy
import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import time
import uuid
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def supported_scopes(space_ids,clip_proof,inherited=()):
    """Unsupported clip objects stay EXACTLY original, including other primitives."""
    unsupported=list(clip_proof.get('unsupported') or [])
    clips=set()
    for change in clip_proof['changes']:
        bounds=change.get('source_clip_bounds')
        if (not isinstance(bounds,list) or len(bounds)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v-round(v))>=1e-8 for v in bounds)):
            unsupported.append({'cell':change['cell'],'reason':'Fractional or unsupported global clip mask; retain exact original object','source_clip_bounds':bounds})
        else:clips.add(change['cell'])
    spaces=set(space_ids);blocked={row['cell'] for row in unsupported if row.get('cell')}
    overlap=spaces&clips
    blocked|=overlap|((spaces|clips)&set(inherited))
    for cell in sorted(overlap):unsupported.append({'cell':cell,'reason':'One object needs overlapping whitespace/clip primitives; retain exact original object'})
    for cell in sorted((spaces|clips)&set(inherited)):unsupported.append({'cell':cell,'reason':'Inherited actual-glyph object is immutable in this revision'})
    return spaces-blocked,clips-blocked,unsupported


def retained_objects(before,current,objects):
    a={c.get('id'):c for c in E.fromstring(before).iter('mxCell')};b={c.get('id'):c for c in E.fromstring(current).iter('mxCell')};result=[]
    for cell in sorted({row['cell'] for row in objects if row.get('cell')}):
        assert cell in a and cell in b,'Unsupported original object disappeared'
        original=E.canonicalize(E.tostring(a[cell],encoding='unicode'));candidate=E.canonicalize(E.tostring(b[cell],encoding='unicode'))
        assert original==candidate,'An unsupported clip object was changed by another primitive'
        result.append({'cell':cell,'exact_original_object_sha256':sha(original.encode()),'unchanged':True})
    return result


def diagnostic_clip_step(operation,clip,render,tag):
    """On a group limitation, identify failed objects without fitting parameters."""
    before,after=operation['before'],operation['after']
    step={'kind':operation['kind'],'proof':operation['proof'],'before_xml':before['xml_entry'],
          'before_render':before['render_entry'],'after_xml':after['xml_entry'],
          'after_render':after['render_entry'],'after_png':after['png_entry'],'pixel_groups':[]}
    unsupported=[]
    def prove(group,label):
        targets={row['cell'] for row in group};unclipped,background=clip.diagnostic_variants(after['xml'],targets)
        a=render(unclipped,label+'_unclipped');b=render(background,label+'_background')
        pixels=clip.pixel_mask_proof(after['png'],a['png'],b['png'],group)
        assert pixels['ok'],'Current native CSS clip pixels do not match the exact source mask'
        return {'group':group,'unclipped_xml':a['xml_entry'],'unclipped_png':a['png_entry'],
                'background_xml':b['xml_entry'],'background_png':b['png_entry'],'pixel_proof':pixels}
    for index,group in enumerate(clip.disjoint_clip_groups(operation['proof'],after['native'])):
        label=tag+'_group_'+str(index)
        try:step['pixel_groups'].append(prove(group,label))
        except AssertionError as failure:
            bad=[]
            if len(group)>1:
                for number,row in enumerate(group):
                    try:prove([row],label+'_single_'+str(number))
                    except AssertionError as error:bad.append({'cell':row['cell'],'reason':str(error),'decision':'retain exact original clip object'})
            if not bad:bad=[{'cell':row['cell'],'reason':str(failure),'decision':'unproved group interaction; retain exact original clip object'} for row in group]
            unsupported.extend(bad)
    return (None,unsupported) if unsupported else (step,[])


def build(record,policy,implementation,work=None):
    from PIL import Image
    from native_worker import native
    from auto_quality_common import checked,require_rendered_text,resource_checks,structure_checks
    from auto_quality_common_v2 import image_quality
    from html_text_layout_registration_v5 import registration_record,require_same_fonts,FIELD
    import html_actual_text_alignment as glyph
    import html_actual_text_clip_alignment_v4 as clip
    import html_text_whitespace_advance_v5 as spaces
    import auto_quality_source_vector_v2 as source
    started=time.monotonic();old={key:value for key,value in record.items() if not key.startswith('_verified_')};xml=checked(R,old['code_file'],old['code_sha256']).decode();old_png=checked(R,old['image_file'],old['image_sha256']);reference=checked(R,old['original_reference'],old['source_image_sha256']);verified,contract=registration_record(old,reference,xml);source._identity(old,xml)
    if work is None:
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8];work=W/'auto_quality_html_text_layout_v5'/old['id']/(old['code_sha256']+'_'+old['image_sha256'][:16])/policy.rsplit(':',1)[-1]/stamp
    work=Path(work);assert work.resolve().is_relative_to((W/'auto_quality_html_text_layout_v5').resolve());work.mkdir(parents=True,exist_ok=False)
    def save(name,blob):path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob);return {'file':str(path.relative_to(R)),'sha256':sha(blob)}
    def json_file(name,value):return save(name,(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    files={'previous_record':json_file('previous_record.json',old),'before_xml':save('before.drawio',xml.encode()),'before_png':save('before.png',old_png)}
    dom,served,source_png,capture=glyph.capture_source(old,work/'source');files['source_dom']=json_file('source_dom.json',dom);files['source_capture']=json_file('source_capture.json',capture);files['source_png']=save('source.png',source_png)
    paint=source._paint_coverage(dom,xml,'html');offset=tuple(paint['source_layout_translation'][key] for key in ('dx','dy'));reference_offset=contract['original_page_offset'] if contract else [0,0];model=E.fromstring(xml).find('.//mxGraphModel');size=[int(round(float(model.get(key)))) for key in ('pageWidth','pageHeight')];assert contract or size==list(Image.open(io.BytesIO(reference)).size),'Reference/native canvas needs verified origin registration'
    renderer=W/'rendering_clipbox_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';render_count=0
    def render(code,label):
        nonlocal render_count
        render_count+=1
        if render_count>64:raise RuntimeError('Bounded layout native-render budget exhausted; retain original pair')
        result=native.native_job(code,*size,180,renderer,8192,runtime);assert result['ok'],'Strict native render failed at '+label;require_rendered_text(code,result['native_render']);assert result['native_render'].get('selected_image')=='declared_first_page','A separate canvas repair is needed before text layout'
        state={'xml':code,'native':result['native_render'],'png':result['png'],'xml_entry':save(label+'.drawio',code.encode()),'render_entry':json_file(label+'.render.json',result['native_render']),'png_entry':save(label+'.png',result['png'])};return state
    baseline=render(xml,'baseline');files['baseline_fresh_png']=baseline['png_entry'];files['baseline_render']=baseline['render_entry'];inherited=verified.get('_verified_html_text_layout',{}).get('combined_glyph_cells') or verified.get('_verified_glyph_alignment',{}).get('changed_cells') or []
    baseline_source=glyph.check_source_profile_v3(old,xml,baseline['native'],dom,served,offset,inherited);assert baseline_source['ok'],'Initial full source coverage is not verified'
    initial_spaces=spaces.plan(dom,baseline['native'],xml,offset);initial_clip_xml,initial_clip=clip.propose_clip_locked(xml,dom,baseline['native'],capture['viewport'],offset)
    space_scope,clip_scope,unsupported_clips=supported_scopes({row['cell'] for row in initial_spaces['objects']},initial_clip,inherited)
    original_scope={'space_advance_v5':[row['cell'] for row in initial_spaces['objects']],'clip_locked_v4':[row['cell'] for row in initial_clip['changes']]};rollbacks=[];steps=[]
    for rebuild in range(8):
        states=[];state=baseline;primitive_rollback=False
        for kind,scope in [('space_advance_v5',space_scope),('clip_locked_v4',clip_scope)]:
            if not scope:continue
            before_state=state
            if kind=='space_advance_v5':code,primitive=spaces.propose(state['xml'],spaces.plan(dom,state['native'],state['xml'],offset),scope)
            else:code,primitive=clip.propose_clip_locked(state['xml'],dom,state['native'],capture['viewport'],offset,scope)
            assert {row['cell'] for row in primitive['changes']}==scope,'A planned source object became unsupported'
            state=render(code,'rebuild_'+str(rebuild)+'_'+kind)
            if kind=='space_advance_v5':
                actual_checks=spaces.actual_advance_checks(primitive,before_state['native'],state['native']);unsupported_actual={row['cell'] for row in actual_checks if not row['ok']}
                if unsupported_actual:
                    rollbacks.append({'pass':rebuild,'reverted_cells':sorted(unsupported_actual),'reason':'Measured CSS text-run boundary changed kerning/geometry; retain exact original object','actual_advance_checks':[row for row in actual_checks if not row['ok']]});space_scope-=unsupported_actual;primitive_rollback=True;break
                spaces.verify(before_state['xml'],code,primitive,dom,before_state['native'],state['native'],offset)
            else:clip.verify_clip_locked(before_state['xml'],code,primitive,dom,before_state['native'],state['native'],capture['viewport'],offset)
            states.append({'kind':kind,'before':before_state,'after':state,'proof':primitive})
        if primitive_rollback:continue
        changed=space_scope|clip_scope
        if not changed:break
        windows=glyph.reference_windows(baseline['native'],state['native'],changed,size);local=glyph.same_crop_metrics(reference,baseline['png'],state['png'],verified,reference_offset,windows);bad={cell for cell,row in local.items() if not row['nonworsening']}
        if not bad:
            steps=[];unsupported=[]
            for index,operation in enumerate(states):
                if operation['kind']=='clip_locked_v4':
                    step,issues=diagnostic_clip_step(operation,clip,render,'rebuild_'+str(rebuild)+'_clip_mask_'+str(index));unsupported.extend(issues)
                    if step:steps.append(step)
                else:
                    a,b=operation['before'],operation['after'];steps.append({'kind':operation['kind'],'proof':operation['proof'],'before_xml':a['xml_entry'],'before_render':a['render_entry'],'after_xml':b['xml_entry'],'after_render':b['render_entry'],'after_png':b['png_entry'],'pixel_groups':[]})
            if unsupported:
                bad_clips={row['cell'] for row in unsupported};assert bad_clips<=clip_scope,'Diagnostic failure was not an owned proposed clip'
                unsupported_clips.extend(unsupported);clip_scope-=bad_clips;space_scope-=bad_clips
                rollbacks.append({'pass':rebuild,'reverted_cells':sorted(bad_clips),'reason':'Unsupported actual clip diagnostic/mask; retain exact original object','unsupported':unsupported});continue
            break
        rollbacks.append({'pass':rebuild,'reverted_cells':sorted(bad),'same_original_crop_metrics':{cell:local[cell] for cell in bad}});space_scope-=bad;clip_scope-=bad
    else:raise AssertionError('Bounded exact-object rollback did not settle; keep the original pair')
    if not space_scope|clip_scope:return work,None,{'accepted':False,'published':False,'state':'no_nonworsening_layout_changes','original_proposals':original_scope,'rollbacks':rollbacks,'unsupported_clip_objects':unsupported_clips,'unsupported_objects_retained_exactly':retained_objects(xml,xml,unsupported_clips)}
    candidate=state['xml'];new_hash=sha(candidate.encode());png_hash=sha(state['png']);files['current_xml']=save('candidate.drawio',candidate.encode());files['current_png']=save('candidate.png',state['png']);files['current_render']=json_file('candidate.render.json',state['native']);changed=space_scope|clip_scope;require_same_fonts(baseline['native'],state['native'])
    current_source=glyph.check_source_profile_v3(old,candidate,state['native'],dom,served,offset,set(inherited)|clip_scope);assert current_source['ok'],'Current complete source coverage failed'
    resources=resource_checks(R,{**old,'code_sha256':new_hash,'image_sha256':png_hash},candidate,reference);structure=structure_checks(candidate);old_quality=image_quality(reference,baseline['png'],verified,baseline['native']['actual_text_positions']);new_quality=image_quality(reference,state['png'],verified,state['native']['actual_text_positions']);assert new_quality['ssim_1024']>=old_quality['ssim_1024']-.02,'Original global fidelity regressed more than .02'
    source_regions=glyph.source_region_quality(reference,source_png,dom);diagnostics=[]
    for region in new_quality.get('worst_text_regions',[]):
        if region['ssim']<.55:diagnostics.append({'cell':region['cell'],'native_reference_line_ssim':region['ssim'],'fresh_source_reference_object_crop':source_regions.get(region['cell']),'classification':'explicit_unresolved_original_reference_region','decision_role':'Diagnostic only; final original global/foreground/each-line gates remain unchanged'})
    proof={'version':5,'builder_variant':'isolated_unsupported_object_fallback_v5a','policy':policy,'implementation':implementation,'id':old['id'],'input_code_sha256':old['code_sha256'],'input_image_sha256':old['image_sha256'],'output_code_sha256':new_hash,'output_image_sha256':png_hash,'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'files':files,'steps':steps,'source_dom_offset':list(offset),'source_viewport':capture['viewport'],'reference_offset':list(reference_offset),'changed_cells':sorted(changed),'original_proposals':original_scope,'exact_object_rollbacks':rollbacks,'unsupported_clip_objects':unsupported_clips,'unsupported_objects_retained_exactly':retained_objects(xml,candidate,unsupported_clips),'reference_windows':windows,'local_reference_validation':local,'baseline_source_coverage':baseline_source,'source_coverage':current_source,'resources':resources,'structure':structure,'reference_quality_before':old_quality,'reference_quality_after':new_quality,'explicit_unresolved_regions':diagnostics,'all_original_physical_faces_and_glyph_counts_preserved':True,'candidate_checks_passed':True,'accepted':False,'published':False,'seconds':time.monotonic()-started}
    proof_entry=json_file('evidence.json',proof);link={key:proof[key] for key in ('version','policy','input_code_sha256','input_image_sha256','output_code_sha256','output_image_sha256','source_code_sha256','source_image_sha256','changed_cells')};link.update(proof=proof_entry['file'],proof_sha256=proof_entry['sha256'],previous_record=files['previous_record']['file'],previous_record_sha256=files['previous_record']['sha256'],operation_kinds=[step['kind'] for step in steps],requires_clip_reference_boxes=bool(clip_scope or verified.get('_verified_html_text_layout',{}).get('combined_clip_cells')))
    parent=(R/old['code_file']).parent;out={**old,'code_file':str((parent/('diagram.text-layout-v5.'+new_hash[:24]+'.drawio')).relative_to(R)),'code_sha256':new_hash,'image_file':str((parent/('image.text-layout-v5.'+new_hash[:24]+'.'+png_hash[:16]+'.png')).relative_to(R)),'image_sha256':png_hash,'render':state['native'],FIELD:link,'html_text_layout_prior_pair_archive':str((work/'baseline_archive').relative_to(R)),'source_coverage':current_source['evidence']['source_coverage'],'quality_state':'pending_automatic_quality_v4_recheck','conversion_method':old.get('conversion_method','unknown')+'_measured_source_space_advances_and_fixed_clip_glyphs_v5','native_font_validation':{'ok':True,'method':'replayed_source_text_layout_with_current_actual_physical_faces_and_glyph_counts','input_code_sha256':old['code_sha256'],'output_code_sha256':new_hash,'all_actual_fonts_custom':True,'physical_faces_and_glyph_counts_preserved':True,'all_original_cell_physical_faces_and_glyph_counts_preserved':True,'font_registry_and_cell_font_styles_unchanged':True,'evidence_file':proof_entry['file'],'evidence_sha256':proof_entry['sha256']},'last_repair':{'method':'deterministic_source_text_layout_v5','policy':policy,'model':None}}
    for key in ('accepted_at_utc','automatic_quality_policy','automatic_quality_audit'):out.pop(key,None)
    assert out.get('previous_candidate_archive')==old.get('previous_candidate_archive'),'Harness source lineage changed'
    registration_record(out,reference,candidate)
    json_file('candidate_record.json',out);json_file('report.json',proof)
    return work,out,proof
