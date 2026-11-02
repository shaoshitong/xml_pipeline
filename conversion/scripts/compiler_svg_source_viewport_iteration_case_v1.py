"""One frozen source-layout compiler attempt and independent full QA.

Owns no canonical jobs. Qualified assets/immutable metadata live in clean/;
failure means pending retry by a later compiler version, not input abandonment.
"""
import datetime
import os
import errno
import importlib
import json
import re
from compiler_typed_runtime_failure_v1 import diagnose as infrastructure_diagnosis, is_infrastructure
from pathlib import Path
import sqlite3
import traceback
import uuid

from fixed_batch_case_v1 import R, W, checked, prepare_originals, raw, save, sha

ROUTES = {'svg': ('compiler_svg_source_viewport_frontend_v1', 'compiler_svg_source_viewport_quality_ro_v1')}
REQUIRED_CHECKS = {'structure', 'resources', 'render', 'source', 'text_paint', 'fonts', 'visual', 'native_editing'}
JOB_COLUMNS = ('id', 'category', 'format', 'source', 'input_record', 'state', 'route', 'attempts',
               'updated_at', 'output_record', 'error', 'input_manifest', 'worker_pid')


def quality_runtime_diagnosis(report):
    return infrastructure_diagnosis({'failures':[{'error_type':x.get('type'),'reason':x.get('reason')}for x in report.get('failures',[])if isinstance(x,dict)]})


def bindings(fmt):
    frontend, quality = ROUTES[fmt]
    compiler = importlib.import_module(frontend)
    return compiler, importlib.import_module(quality)


def overlap_guard(identifier,run):
    from compiler_mermaid_alpha_iteration_overlap_v2 import guard
    state=guard(identifier,ignore_runs=(re.sub(r'_(?:B|C|mass)$','',Path(run).name),))
    if state['active']:raise ValueError('deferred_birth_verified_active_conversion_overlap')
    return state

def qualified_guard(identifier,source):
    from compiler_mermaid_alpha_qualifications_v2 import find_qualified
    if find_qualified(identifier,source,root=R)is not None:raise ValueError('already_qualified_complete_original_preserved')


def canonical_owner_evidence(pid):
    """Only definite ENOENT on a mounted/readable proc permits stale claims."""
    if pid is None:return {'policy':'readonly_canonical_owner_v1','worker_pid':None,'decision':'no_claim','canonical_mutations':0}
    result={'policy':'readonly_canonical_owner_v1','worker_pid':pid,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'live_or_uncertain_defer','canonical_mutations':0}
    try:
        if isinstance(pid,bool)or int(pid)<=0:raise ValueError('invalid_claim_PID')
        pid=int(pid);mount=[line for line in Path('/proc/mounts').read_text().splitlines()if len(line.split())>=3 and line.split()[1:3]==['/proc','proc']]
        if not mount:raise ValueError('proc_mount_not_proven')
        proc_stat=os.stat('/proc');self_stat=Path('/proc/self/stat').read_bytes();result['proc_mount']={'mountpoint':'/proc','filesystem':'proc','device':proc_stat.st_dev,'self_stat_sha256':sha(self_stat),'readable':True}
        try:os.stat('/proc/'+str(pid))
        except OSError as error:
            if error.errno==errno.ENOENT:result.update(decision='definite_dead_ENOENT',errno=errno.ENOENT,proc_path='/proc/'+str(pid))
            else:result['probe_error']=type(error).__name__+':'+str(error)
    except (OSError,ValueError,TypeError)as error:result['probe_error']=type(error).__name__+':'+str(error)
    return result

def quality_database(job,work,database=None):
    """Preserve real raw row; clear only a definitely dead lease in a QA copy."""
    database=Path(database or W/'jobs.sqlite').resolve(strict=True)
    with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30)as d:
        rawrow=d.execute('select * from jobs where id=?',(job[0],)).fetchone();schema=d.execute("select sql from sqlite_master where type='table' and name='jobs'").fetchone()[0]
    if rawrow!=job:raise RuntimeError('infrastructure_canonical_row_changed_before_owner_guard')
    proof=canonical_owner_evidence(job[12]);proof['canonical_raw_row_sha256']=sha(raw(list(job)))
    if proof['decision']=='no_claim':return database,proof,None
    if proof['decision']!='definite_dead_ENOENT':raise ValueError('deferred_live_or_uncertain_canonical_owner')
    owner=Path(work)/'canonical_owner_guard';owner.mkdir(parents=True,exist_ok=False);save(owner/'canonical_raw_row.json',raw(list(job)));private=list(job);private[12]=None
    private_db=owner/'readonly_QA_metadata.sqlite'
    with sqlite3.connect(private_db)as d:d.execute(schema);d.execute('insert into jobs values ('+','.join('?'for _ in private)+')',private)
    with sqlite3.connect('file:'+str(private_db)+'?mode=ro',uri=True)as d:stored=d.execute('select * from jobs where id=?',(job[0],)).fetchone()
    differences=[i for i,(a,b)in enumerate(zip(job,stored))if a!=b]
    if differences!=[12]or stored[12]is not None:raise RuntimeError('infrastructure_private_QA_copy_changed_authoritative_data')
    proof.update(private_copy_only_clears_worker_pid=True,changed_columns=['worker_pid'],original_worker_pid=job[12],private_row_sha256=sha(raw(list(stored))))
    save(owner/'private_row.json',raw(list(stored)));save(owner/'proof.json',raw(proof))
    with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)as d:
        if d.execute('select * from jobs where id=?',(job[0],)).fetchone()!=job:raise RuntimeError('infrastructure_canonical_row_changed_by_owner_guard')
    return private_db,proof,owner/'proof.json'


def full_quality(report, record):
    checks = report.get('checks', {})
    if report.get('ok') is not True or report.get('failures') or not REQUIRED_CHECKS <= set(checks):
        raise ValueError('incomplete_independent_full_quality')
    for name in ('source', 'visual', 'native_editing'):
        if checks[name].get('ok') is not True:
            raise ValueError('failed_mandatory_quality_stage:' + name)
    if checks['source'].get('evidence', {}).get('complete_source_coverage') is not True:
        raise ValueError('partial_source_coverage')
    if checks['fonts'].get('all_rendered_fonts_embedded') is not True:
        raise ValueError('unembedded_actual_font')
    render = checks['render']
    if render.get('code_sha256') != record['code_sha256'] or render.get('image_sha256') != record['image_sha256']:
        raise ValueError('fresh_render_not_bound_to_candidate')
    if not (render.get('export_mode')=='original_recorded_SVG_surface_viewport_clip_v1' and
            render.get('paint_safety_frame')=='full_unclipped_native_paint_inspection_viewport' and
            render.get('strict_outside_inspection_pixels')==0 and
            render.get('complete_native_model_paint_inspected')is True and render.get('model_geometry_preserved')is True and
            render.get('graph_view_unchanged')is True and render.get('native_inspection_to_export_pixels_exact')is True and
            render.get('actual_native_dom_bounds_contained_in_source_inspection')is True and
            type(render.get('unclipped_native_outside_source_viewport_pixels'))is int and render['unclipped_native_outside_source_viewport_pixels']>=0):
        raise ValueError('incomplete_original_source_surface_native_inspection_contract')
    rootclip=render.get('native_outer_svg_inspection_clip_policy')or {}
    if not (rootclip.get('only_actual_graph_outer_SVG_and_container_clips_disabled')is True and
            rootclip.get('inspection_computed_overflow')==rootclip.get('inspection_container_computed_overflow')=='visible' and
            rootclip.get('model_unchanged')is True):raise ValueError('hidden_native_inspection_paint')
    evidence=checks['source']['evidence'];source_checks=evidence.get('checks')or {}
    mandatory={'semantics','glyphs','physical_fonts','same_domain_pixels','source_primitive_pixels','full_inspection_pixels','full_source_primitive_pixels','source_viewport'}
    if not mandatory<=source_checks.keys()or not all(source_checks[k].get('ok')is True for k in mandatory):raise ValueError('incomplete_source_visible_and_full_inspection_domain_gates')
    sourceproof=evidence.get('fresh_sourceproof')or {};contact=sourceproof.get('source_surface_contact')or {}
    if not (sourceproof.get('source_code_sha256')==record['source_code_sha256'] and sourceproof.get('source_image_sha256')==record['source_image_sha256'] and
            sourceproof.get('source_reference',{}).get('ok')is True and contact.get('source_surface_contact')is True and
            contact.get('original_reference_pixels_or_scores_used')is False):raise ValueError('source_surface_contact_or_original_reference_unproved')
    frame=source_checks['source_viewport']['fresh_source_root_clip'];plan=frame['plan']
    if not (frame.get('all_primitive_geometry_style_font_retained')is True and frame.get('original_DOM_and_pixels_restored')is True and
            frame.get('strict_outside_source_inspection_pixels')==0 and frame.get('no_reference_or_candidate_pixels_used')is True and
            frame.get('standalone_root_default_overflow_not_inferred')is True):raise ValueError('source_original_viewport_and_complete_paint_not_independently_proved')
    if render.get('source_inspection_plan')!={k:plan[k]for k in ('x','y','width','height')}or render.get('source_viewport')!=[0,0,plan['source_width'],plan['source_height']]:raise ValueError('source_native_viewport_frame_mismatch')
    for field in ('source_render_png','source_full_inspection','native_full_inspection','native_svg_export','source_viewport_proof'):
        path=(R/record[field]).resolve(strict=True)
        if not path.is_relative_to((R/'clean').resolve()):raise ValueError('final_source_viewport_payload_outside_clean')
        checked(record[field],record[field+'_sha256'])
    if record['native_full_inspection_sha256']!=render.get('full_native_inspection_png_sha256')or record['native_svg_export_sha256']!=render.get('native_svg_export_sha256'):raise ValueError('fresh_full_native_inspection_or_SVG_export_changed')
    if contact['source_engine_png_sha256']!=record['source_render_png_sha256']:raise ValueError('source_contact_not_bound_to_actual_source_render')
    from compiler_svg_source_viewport_export_v1 import verify_declaration
    verify_declaration(checked(record['code_file'],record['code_sha256']).decode(),plan)
    for name, digest in report.get('implementation_pins', {}).items():
        if sha(Path(name).read_bytes()) != digest:
            raise RuntimeError('infrastructure_independent_QA_pin_changed:' + name)
    return True


def publish(record, source, report, directory):
    full_quality(report, record)
    from qualified_index_v4 import manifest_row, require_source
    require_source(record, source)
    fresh = (directory / 'fresh.png').read_bytes()
    digest = sha(fresh)
    if digest != report['checks']['render']['image_sha256']:
        raise RuntimeError('infrastructure_fresh_native_image_changed')
    code = (R / record['code_file']).resolve(strict=True)
    if not code.is_relative_to((R / 'clean').resolve()) or sha(code.read_bytes()) != record['code_sha256']:
        raise RuntimeError('infrastructure_candidate_code_changed_before_publication')
    target = code.parent / ('image.native.' + digest[:24] + '.png')
    if target.exists() and sha(target.read_bytes()) != digest:
        raise RuntimeError('infrastructure_immutable_published_image_changed')
    save(target, fresh)
    out = {k: v for k, v in record.items() if not k.startswith('_verified_')}
    out.update(image_file=str(target.relative_to(R)), image_sha256=digest,
               automatic_quality_policy=report['quality_policy'],
               automatic_quality_audit=str((directory / 'report.json').relative_to(R)),
               quality_state='accepted_complete_original_svg_surface_inspection_v1',
               accepted_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               model=None, model_configuration={'external_model_calls': 0, 'deterministic_compiler': True})
    manifest = manifest_row(out, R)[0]
    return manifest


def authoritative_originals(record, source, manifest, work):
    """Only old candidate locators may fall back; authoritative hashes never do."""
    try:
        return prepare_originals(record, source, manifest, work)
    except (OSError, ValueError):
        if not manifest:
            raise
        # Verify both authoritative originals before discarding stale locators.
        checked(manifest['source_code'], source['code_sha256'])
        checked(manifest['reference_image'], source['image_sha256'])
        replacement={k:v for k,v in record.items() if k not in ('original_source_code','original_reference')}
        return prepare_originals(replacement, source, manifest, work)


def run(request_path):
    q = json.loads(Path(request_path).read_bytes())
    identifier, work, source = q['id'], Path(q['work']).resolve(), q['source']
    stage = 'input'
    result = dict(id=identifier, seq=q['seq'], compiler_unit=q['compiler_unit'], cluster=q.get('cluster'),
                  source_code_sha256=source['code_sha256'], source_image_sha256=source['image_sha256'],
                  compiler_version='iterative_svg_source_surface_inspection_v1', model_calls=0, final_irrecoverable=False)
    try:
        if not work.is_relative_to((W / 'compiler_iterations').resolve()):
            raise ValueError('case_outside_owned_iteration_work')
        for name, digest in q['pins'].items():
            if sha(Path(name).read_bytes()) != digest:
                raise RuntimeError('infrastructure_iteration_implementation_changed:' + name)
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30) as db:
            job = db.execute('select * from jobs where id=?', (identifier,)).fetchone()
        if not job or json.loads(job[4]) != source:
            raise ValueError('authoritative_original_identity_changed')
        if sha((job[9] or '').encode()) != q.get('source_record_sha256'):
            raise RuntimeError('infrastructure_selected_baseline_revision_changed')
        if (identifier, source['category'], source['format']) != (source['pair_sha256'], job[1], job[2]):
            raise ValueError('original_scope_identity_mismatch')
        previous=json.loads(job[9])if job[9]else{}
        if(q.get('baseline_code_sha256'),q.get('baseline_image_sha256'))!=(previous.get('code_sha256'),previous.get('image_sha256')):raise ValueError('selected_baseline_asset_snapshot_changed')
        owner=canonical_owner_evidence(job[12])
        if owner['decision']not in ('no_claim','definite_dead_ENOENT'):raise ValueError('deferred_live_or_uncertain_canonical_owner')
        overlap_guard(identifier,q.get('run',''))
        compiler, quality = bindings(job[2])
        if q['compiler_unit'] != compiler.UNITS['svg']:
            raise ValueError('wrong_source_compiler_unit')
        support = compiler.static_support(dict(zip(JOB_COLUMNS, job)))
        if not support['supported']:
            raise ValueError('source_outside_current_compiler_support:' + json.dumps(support['reasons']))
        baseline = q.get('evaluation_phase') == 'baseline'
        record = json.loads(job[9]) if baseline and job[9] else dict(id=identifier, source_pair_sha256=identifier,
                        category=job[1], source_format=job[2], source=job[3], format='drawio',
                        source_code_sha256=source['code_sha256'], source_image_sha256=source['image_sha256'])
        record = authoritative_originals(record, source, json.loads(job[11]) if job[11] else None, work)
        if baseline and q['mode'] == 'batch':
            raise ValueError('baseline_cannot_run_as_production_batch')
        if baseline:
            if not job[9]:
                raise ValueError('baseline_has_no_existing_candidate')
            if (record['code_sha256'], record['image_sha256']) != (q['baseline_code_sha256'], q['baseline_image_sha256']):
                raise ValueError('baseline_revision_changed')
        elif q.get('existing_development_candidate'):
            if q['mode']!='development' or q.get('evaluation_phase')!='control_positive':raise ValueError('existing_positive_only_for_development_controller_control')
            candidate=Path(q['existing_development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to(R/'clean'):raise ValueError('development_positive_not_in_clean')
            record=json.loads(candidate.read_bytes())
            if(record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(identifier,source['code_sha256'],source['image_sha256']):raise ValueError('development_positive_original_identity_changed')
        elif q.get('negative_control'):
            candidate = Path(q['development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R / 'clean').resolve()):
                raise ValueError('negative_candidate_not_in_clean')
            record = json.loads(candidate.read_bytes())
        else:
            stage = 'conversion'
            frontend_work = W / compiler.VERSION / 'program_runs' / work.parent.name / work.name
            qualified_guard(identifier,source)
            overlap_guard(identifier,q.get('run',''))
            attempt = compiler.convert(record, job, frontend_work)
            save(work / 'frontend_result.json', raw(attempt))
            if not attempt.get('ok'):
                result.update(status='abandoned', phase=stage, reason=attempt.get('reason') or 'source_layout_conversion_failed',
                              detail=attempt.get('detail') or attempt.get('error'),
                              infrastructure_failure=is_infrastructure(attempt),infrastructure_diagnosis=infrastructure_diagnosis(attempt))
                save(work / 'result.json', raw(result))
                return result
            record = attempt['record']
        for field, hash_field in [('code_file', 'code_sha256'), ('image_file', 'image_sha256'),
                                 ('original_source_code', 'source_code_sha256'), ('original_reference', 'source_image_sha256')]:
            checked(record[field], record[hash_field])
        qa_database,owner_proof,owner_audit=quality_database(job,work)
        record={**record,'canonical_owner_guard':owner_proof}
        result['canonical_owner_guard']=owner_proof
        if owner_audit is not None:result['canonical_owner_guard_audit']=str(owner_audit.relative_to(R))
        proposal = work / 'candidate_record.json'
        save(proposal, raw(record))
        stage = 'quality'
        directory = W / 'prototype/candidate_quality_ro_v1' / ('iteration_' + work.parent.name + '_' + str(q['seq']) + '_' + uuid.uuid4().hex)
        report = quality.verify(identifier, proposal, R, Path(compiler.__file__), directory,database=qa_database)
        after_owner=canonical_owner_evidence(job[12])
        if after_owner['decision']not in ('no_claim','definite_dead_ENOENT'):raise ValueError('deferred_canonical_owner_became_live_or_uncertain_during_QA')
        result.update(quality_report=str((directory / 'report.json').relative_to(R)),
                      quality_policy=report.get('quality_policy'), quality_failures=report.get('failures'),
                      candidate_code_sha256=record['code_sha256'], candidate_image_sha256=record['image_sha256'])
        if q.get('negative_control'):
            result.update(status='abandoned', phase='negative_control', reason='negative_false_acceptance' if report.get('ok') else 'negative_correctly_rejected',
                          negative_false_acceptance=report.get('ok') is True)
        elif report.get('ok'):
            result.update(status='qualified', phase=stage, reason='independent_full_source_native_quality_passed',
                          manifest=publish(record, source, report, directory))
        else:
            diagnosis=quality_runtime_diagnosis(report)
            result.update(status='abandoned', phase=stage, reason='retryable_independent_quality_failure',
                          detail=report.get('failures'), infrastructure_failure=diagnosis['infrastructure_failure'],infrastructure_diagnosis=diagnosis)
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30) as db:
            if db.execute('select * from jobs where id=?', (identifier,)).fetchone() != job:
                raise RuntimeError('infrastructure_original_job_changed')
    except Exception as error:
        result.update(status='abandoned', phase=stage, reason='retryable_iteration_case_failure',
                      error_type=type(error).__name__, detail=str(error)[:6000],
                      infrastructure_failure=is_infrastructure(exception=error),infrastructure_diagnosis=infrastructure_diagnosis(exception=error))
        save(work / 'traceback.txt', traceback.format_exc().encode())
    save(work / 'result.json', raw(result))
    return result


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
