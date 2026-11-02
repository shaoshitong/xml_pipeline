"""New compiler source profiles with unchanged full native quality gates.

Only used in isolated new compiler cases. Frozen initial/round-2 modules and
their files are not modified. The new policy records the profile implementation.
"""
import hashlib
import json
from pathlib import Path

from fixed_batch_case_v1 import R,W,raw,save,sha

POLICY='compiler_source_ir_and_full_native_quality_v1'


def configuration():
    import auto_quality_batch_v4b as qa
    import round2_font_canvas_registration_v1 as registration
    import compiler_scene_v1 as scene
    import compiler_source_reproduction_v1 as reproduction
    import compiler_capture_snapshot_v1 as capture
    qa.ensure_pinned();config=registration.configuration()
    bindings=dict(original_quality_policy=getattr(qa,'_compiler_original_policy_v1',qa.POLICY),
                  source_checker_sha256=sha(Path(scene.__file__).read_bytes()),
                  source_reproduction_sha256=sha(Path(reproduction.__file__).read_bytes()),
                  capture_snapshot_checker_sha256=sha(Path(capture.__file__).read_bytes()),
                  compiler_case_sha256=sha(Path(__file__).with_name('compiler_case_v1.py').read_bytes()),
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


def verify(record,job,work,index=0):
    import auto_quality_batch_v4b as qa
    import clip_canvas_render_v4b as clip
    import round2_font_canvas_registration_v1 as registration
    import compiler_scene_v1 as scene
    work=Path(work).resolve()
    if not work.is_relative_to((W/'compiler_v1').resolve()):
        raise ValueError('compiler_quality_work_outside_owner')
    qa.ensure_pinned()
    if not hasattr(qa,'_compiler_original_profile_v1'):
        qa._compiler_original_profile_v1=qa.profile
        qa._compiler_original_policy_v1=qa.POLICY
    config=configuration();bindings=config['bindings']
    def source_profile(current,xml,source,native_info=None):
        from compiler_capture_snapshot_v1 import check_snapshot
        check_snapshot(current,current.get('compiler_source_capture_snapshot'))
        if not current.get('compiler_scene_graphviz_v1'):
            return qa._compiler_original_profile_v1(current,xml,source,native_info)
        before,baseline=qa.source_baseline(current,xml)
        check_snapshot(before,current['compiler_source_capture_snapshot'])
        result=scene.validate(before,baseline)
        if result.get('infrastructure_failure'):
            raise RuntimeError('infrastructure_compiler_source_checker:'+json.dumps(result.get('failures')))
        if before is not current:
            result['evidence'].update(current_code_sha256=sha(xml.encode()),
                                      canvas_only_transformation_independently_verified=True)
        return result
    qa.profile=source_profile
    qa.registration_record=registration.registration_record
    qa.POLICY=config['policy']
    qa.W=work/('qa_'+str(index));clip.OWNER=str((work/('clip_'+str(index))).relative_to(R))
    _,report,out,directory=qa.verify((job[0],job[5],json.dumps(record,ensure_ascii=False),job[4],job[6]))
    report['compiler_quality_bindings']=bindings
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
