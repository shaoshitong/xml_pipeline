"""Compiler source profiles with independent source/render-domain quality.

Only used in isolated new compiler cases. Frozen initial/round-2 modules and
their files are not modified. The new policy records the profile implementation.
"""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from fixed_batch_case_v1 import R,W,raw,save,sha

POLICY='compiler_source_ir_and_full_native_quality_visibility_v1'


def configuration():
    import auto_quality_batch_v4b as qa
    import round2_font_canvas_registration_v1 as registration
    import compiler_graphviz_visibility_scene_v1 as scene
    import compiler_graphviz_visibility_text_v1 as text
    import compiler_graphviz_visibility_reproduction_v1 as reproduction
    import compiler_capture_snapshot_v1 as capture
    import compiler_graphviz_visibility_domain_v1 as domain
    for api in ('convert','validate','validate_text_render','validate_registration_setup'):
        if not callable(getattr(text,api,None)):raise RuntimeError('infrastructure_incomplete_compiler_text_frontend:'+api)
    qa.ensure_pinned();config=registration.configuration()
    bindings=dict(original_quality_policy=getattr(qa,'_compiler_original_policy_visibility_v1',qa.POLICY),
                  source_checker_sha256=sha(Path(scene.__file__).read_bytes()),
                  source_text_checker_sha256=sha(Path(text.__file__).read_bytes()),
                  source_reproduction_sha256=sha(Path(reproduction.__file__).read_bytes()),
                  capture_snapshot_checker_sha256=sha(Path(capture.__file__).read_bytes()),
                  render_domain_checker_sha256=sha(Path(domain.__file__).read_bytes()),
                  compiler_case_sha256=sha(Path(__file__).with_name('compiler_graphviz_visibility_case_v1.py').read_bytes()),
                  compiler_quality_sha256=sha(Path(__file__).read_bytes()),
                  registration_policy=config['policy'],registration_pins=config['pins'])
    digest=sha(raw(bindings))
    return dict(policy=POLICY+':'+digest[:20],policy_sha256=digest,bindings=bindings)


def diagnose(report):
    text=json.dumps(report.get('failures',[]),ensure_ascii=False)
    if report.get('exception_type') in ('ImportError','ModuleNotFoundError') or 'infrastructure_' in text:
        return 'infrastructure'
    for stage,words in [
        ('scene_extraction_or_semantic_loss',('source_coverage','source_profile','source_object','source_connector','source_arrow','invalid_editable_structure')),
        ('layout_or_coordinate_error',('canvas','Canvas','outside_page','tight canvas')),
        ('font_or_text_shaping_error',('font','Font','text_missing','text_cell')),
        ('native_render_error',('native_render_failed',)),
        ('target_render_mismatch',('raster_anomaly','fidelity','foreground','local_text_line')),
        ('editability_failure',('endpoint','movement','native_editing','label_does_not_follow')),
    ]:
        if any(word in text for word in words):return stage
    return 'unclassified_quality_failure'


def registration_record(record,reference,xml):
    """Compose an existing proven page/font origin with a new text-only delta."""
    import round2_font_canvas_registration_v1 as registration
    import compiler_graphviz_visibility_text_v1 as text
    current={key:value for key,value in record.items() if not key.startswith('_verified_')}
    try:
        # Covers a canvas proof produced AFTER text calibration, and ordinary
        # unregistered pages. It never treats a text edit as font-only.
        return registration.registration_record(current,reference,xml)
    except (AssertionError,ValueError):
        if current.get('compiler_quality_phase_visibility_v1')=='baseline' or not current.get('compiler_graphviz_visibility_text_v1'):raise
    setup=text.validate_registration_setup(current,xml)
    if setup.get('infrastructure_failure'):
        raise RuntimeError('infrastructure_compiler_text_registration_setup:'+json.dumps(setup.get('failures')))
    if not setup.get('supported') or not setup.get('ok'):
        raise ValueError('compiler_text_registration_setup_failed:'+json.dumps(setup.get('failures')))
    origin=setup['baseline_record'];origin_xml=setup['baseline_xml']
    if current.get('auto_quality_canvas_repair')!=origin.get('auto_quality_canvas_repair'):
        raise ValueError('compiler_text_registration_origin_link_changed')
    _,contract=registration.registration_record(origin,reference,origin_xml)
    if not contract:raise ValueError('compiler_text_registration_has_no_proven_page_origin')
    page=ET.fromstring(xml).find('.//mxGraphModel')
    if page is None or [float(page.get(key,'nan')) for key in ('pageWidth','pageHeight')]!=contract['output_page']:
        raise ValueError('compiler_text_registration_page_changed')
    composed={key:value for key,value in contract.items()
              if key not in ('font_only_delta_verified','same_renderer_font_delta_verified','current_revision_verified')}
    composed.update(current_revision_verified=True,source_derived_text_delta_verified=True,
                    compiler_text_registration_version='compiler_text_page_composition_v2',
                    before_text_registration=contract,text_delta_setup_evidence=setup.get('evidence',{}),
                    scope='Verified pre-text page/font origin plus hash-bound text-span delta; fresh glyph, source, fonts, pixels and movement remain mandatory.')
    return {**current,'_verified_reference_registration':composed},composed


def verify(record,job,work,index=0):
    import auto_quality_batch_v4b as qa
    import clip_canvas_render_v4b as clip
    import round2_font_canvas_registration_v1 as registration
    import compiler_graphviz_visibility_scene_v1 as scene
    import compiler_graphviz_visibility_text_v1 as text
    import compiler_graphviz_visibility_domain_v1 as domain
    work=Path(work).resolve()
    if not work.is_relative_to((W/'compiler_graphviz_visibility_v1').resolve()):
        raise ValueError('compiler_quality_work_outside_owner')
    qa.ensure_pinned()
    if not hasattr(qa,'_compiler_original_profile_visibility_v1'):
        qa._compiler_original_profile_visibility_v1=qa.profile
        qa._compiler_original_policy_visibility_v1=qa.POLICY
        qa._compiler_original_rendered_text_visibility_v1=qa.require_rendered_text
    if not hasattr(qa,'_compiler_original_image_quality_visibility_v1'):
        qa._compiler_original_image_quality_visibility_v1=qa.image_quality
    config=configuration();bindings=config['bindings']
    current_record={};text_render={};render_domain={};fresh_native={}
    def source_profile(current,xml,source,native_info=None):
        from compiler_capture_snapshot_v1 import check_snapshot
        check_snapshot(current,current.get('compiler_source_capture_snapshot'))
        current_record['record']=current
        baseline_phase=current.get('compiler_quality_phase_visibility_v1')=='baseline'
        if baseline_phase and not current.get('compiler_scene_graphviz_visibility_v1'):
            return qa._compiler_original_profile_visibility_v1(current,xml,source,native_info)
        before,baseline=qa.source_baseline(current,xml)
        if not baseline_phase and before.get('compiler_graphviz_visibility_text_v1')!=current.get('compiler_graphviz_visibility_text_v1'):
            # A pre-text canvas baseline lacks the new setup proof; validate
            # the complete composed current scene instead of discarding it.
            before,baseline=current,xml
        check_snapshot(before,current['compiler_source_capture_snapshot'])
        result=scene.validate(before,baseline) if baseline_phase else text.validate(before,baseline)
        if result.get('infrastructure_failure'):
            raise RuntimeError('infrastructure_compiler_source_checker:'+json.dumps(result.get('failures')))
        if before is not current:
            result['evidence'].update(current_code_sha256=sha(xml.encode()),
                                      canvas_only_transformation_independently_verified=True)
        return result
    def require_rendered_text(xml,native_info):
        fresh_native.update(xml=xml,info=native_info)
        original=qa._compiler_original_rendered_text_visibility_v1(xml,native_info)
        current=current_record.get('record')
        if current is None:raise RuntimeError('infrastructure_compiler_source_profile_not_executed')
        if current.get('compiler_quality_phase_visibility_v1')!='baseline':
            checked=text.validate_text_render(current,xml,native_info)
            text_render.update(checked)
            if checked.get('infrastructure_failure'):
                raise RuntimeError('infrastructure_compiler_text_render_checker:'+json.dumps(checked.get('failures')))
            if not checked.get('supported') or not checked.get('ok'):
                raise ValueError('compiler_text_render_failure:'+json.dumps(checked.get('failures')))
        return original
    def image_quality(reference,png,current,text_positions=None):
        original=qa._compiler_original_image_quality_visibility_v1(reference,png,current,text_positions)
        if not fresh_native or not current_record.get('record'):
            raise RuntimeError('infrastructure_compiler_missing_fresh_render_for_domain_check')
        domain_work=W/'compiler_graphviz_visibility_domain_v1'/'quality'/work.relative_to(W/'compiler_graphviz_visibility_v1')/('attempt_'+str(index))
        checked=domain.check(current,fresh_native['xml'],fresh_native['info'],png,reference,domain_work)
        render_domain.update(checked)
        if checked.get('infrastructure_failure'):
            raise RuntimeError('infrastructure_compiler_render_domain:'+json.dumps(checked.get('failures')))
        # Only the diagnosed cross-renderer line SSIM is diagnostic. All source
        # pairing, same-renderer pixels, source-derived glyph/paint checks and
        # original global/tile/foreground gates remain necessary, for B and C.
        retained=[failure for failure in original.get('failures',[])
                  if failure!='local_text_line_ssim_below_0.55']
        if checked.get('supported') is not True or checked.get('ok') is not True or checked.get('failures')!=[]:
            retained.append('independent_source_render_domain_not_passed')
        return {**original,'ok':not retained,'failures':retained,
                'original_reference_visual':original,
                'cross_renderer_local_text_is_diagnostic':True,
                'source_replay_visual':checked.get('source_replay_visual'),
                'scope':'Original global, tile and foreground gates plus independent full same-renderer source fidelity; original cross-renderer line scores retained as diagnostics.'}
    qa.profile=source_profile
    qa.require_rendered_text=require_rendered_text
    qa.image_quality=image_quality
    qa.registration_record=registration_record
    qa.POLICY=config['policy']
    qa.W=work/('qa_'+str(index));clip.OWNER=str((work/('clip_'+str(index))).relative_to(R))
    _,report,out,directory=qa.verify((job[0],job[5],json.dumps(record,ensure_ascii=False),job[4],job[6]))
    report['compiler_quality_bindings']=bindings
    if text_render:report['checks']['compiler_text_render']=text_render
    if render_domain:report['checks']['compiler_render_domain']=render_domain
    report['diagnostic_stage']=None if out and report.get('state')=='qualified' else diagnose(report)
    report['infrastructure_failure']=report['diagnostic_stage']=='infrastructure'
    save(Path(directory)/'audit.json',raw(report))
    return report,out,Path(directory)


def publish(out,report,directory,source):
    if not out or report.get('state')!='qualified':
        raise ValueError('cannot_publish_incomplete_compiler_quality')
    png=(Path(directory)/'fresh.png').read_bytes()
    if sha(png)!=out['image_sha256']:raise ValueError('compiler_fresh_image_hash_changed')
    save(R/out['image_file'],png)
    from qualified_index_v4 import manifest_row,require_source
    require_source(out,source)
    return manifest_row(out,R)[0]
