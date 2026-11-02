"""One frozen source-layout compiler attempt and independent full QA.

Owns no canonical jobs. Qualified assets/immutable metadata live in clean/;
failure means pending retry by a later compiler version, not input abandonment.
"""
import datetime
import importlib
import json
import re
from pathlib import Path
import sqlite3
import traceback
import uuid

from fixed_batch_case_v1 import R, W, checked, prepare_originals, raw, save, sha

ROUTES = {'plantuml': ('compiler_plantuml_engine_surface_candidate_v1', 'compiler_plantuml_engine_surface_quality_ro_v1')}
REQUIRED_CHECKS = {'structure', 'resources', 'render', 'source', 'text_paint', 'fonts', 'visual', 'native_editing', 'canonical_claim'}
def overlap_guard(identifier,run):
    from compiler_mermaid_alpha_iteration_overlap_v2 import guard
    result=guard(identifier,ignore_runs=(re.sub(r'_(?:B|C|mass)$','',Path(run).name),))
    if result['active']:raise ValueError('deferred_birth_verified_active_conversion_overlap')
    return result


JOB_COLUMNS = ('id', 'category', 'format', 'source', 'input_record', 'state', 'route', 'attempts',
               'updated_at', 'output_record', 'error', 'input_manifest', 'worker_pid')


def runtime_failure(value):
    from compiler_typed_runtime_failure_v1 import is_infrastructure
    if isinstance(value,list):
        value={'failures':[dict(exception_type=row.get('type')or row.get('exception_type'),reason=row.get('reason'),error=row.get('error'),infrastructure_failure=row.get('infrastructure_failure')is True)if isinstance(row,dict)else row for row in value]}
    return is_infrastructure(value)


def bindings(fmt):
    frontend, quality = ROUTES[fmt]
    compiler = importlib.import_module(frontend)
    return compiler, importlib.import_module(quality)


def full_quality(report, record):
    checks = report.get('checks', {})
    if report.get('ok') is not True or report.get('failures') or not REQUIRED_CHECKS <= set(checks):
        raise ValueError('incomplete_independent_full_quality')
    if checks['canonical_claim'].get('conversion_allowed')is not True or checks['canonical_claim'].get('canonical_fields_changed')is not False:
        raise ValueError('canonical_claim_not_independently_observed_safe')
    for name in ('source', 'visual', 'native_editing'):
        if checks[name].get('ok') is not True:
            raise ValueError('failed_mandatory_quality_stage:' + name)
    if checks['source'].get('evidence', {}).get('complete_source_coverage') is not True:
        raise ValueError('partial_source_coverage')
    if checks['source'].get('evidence',{}).get('fresh_source_grapheme_layout',{}).get('ok') is not True:
        raise ValueError('incomplete_independent_source_grapheme_layout')
    if checks['source'].get('evidence',{}).get('complete_source_label_reference_visual',{}).get('ok') is not True:
        raise ValueError('incomplete_complete_source_label_original_reference_quality')
    fresh=checks['source']['evidence'].get('fresh_source_proof',{})
    view=fresh.get('source_viewport_independent_proof',{});inspection=fresh.get('source_surface_inspection',{})
    if not fresh.get('whole_original_source_RGBA_exact',{}).get('ok')or not(view.get('raw_default_and_fixed_viewport_all_primitive_screen_geometry_and_CSS_identical')and view.get('raw_and_canonical_unclipped_pixels_equal')and view.get('explicit_source_finite_surface_clipping')and view.get('surface_from_same_official_PNG_paint_stream')):
        raise ValueError('incomplete_exact_original_source_or_independent_official_source_surface_proof')
    if not(inspection.get('strict_outside_source_inspection_pixels')==0 and inspection.get('all_primitive_geometry_style_font_retained')and inspection.get('original_DOM_and_pixels_restored')and inspection.get('no_reference_or_candidate_pixels_used')):
        raise ValueError('incomplete_entire_original_source_paint_inspection')
    semantics=checks['source']['evidence'].get('semantic_and_paint',{})
    if semantics.get('source_engine_semantics',{}).get('geometry_used_to_infer_connections_or_parents') is not False:
        raise ValueError('missing_true_official_Entity_Link_semantics')
    editing=checks['native_editing'].get('actual_every_engine_entity_container_and_owned_paint_editing',{})
    if not editing.get('ok') or editing.get('entities_checked')!=len(semantics.get('engine_entities',{})):
        raise ValueError('incomplete_every_official_entity_container_editing')
    if checks['fonts'].get('all_rendered_fonts_embedded') is not True:
        raise ValueError('unembedded_actual_font')
    render = checks['render']
    if render.get('code_sha256') != record['code_sha256'] or render.get('strict_outside_source_inspection_pixels') != 0 or render.get('complete_native_paint_inspected')is not True or render.get('explicit_original_source_surface_clipping')is not True:
        raise ValueError('fresh_render_not_bound_to_candidate')
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
    target = (R / record['image_file']).resolve(strict=True) if record.get('image_sha256') == digest else code.parent / ('image.native.' + digest[:24] + '.png')
    if target.exists() and sha(target.read_bytes()) != digest:
        raise RuntimeError('infrastructure_immutable_published_image_changed')
    save(target, fresh)
    out = {k: v for k, v in record.items() if not k.startswith('_verified_')}
    out.update(image_file=str(target.relative_to(R)), image_sha256=digest,
               automatic_quality_policy=report['quality_policy'],
               automatic_quality_audit=str((directory / 'report.json').relative_to(R)),
               quality_state='accepted_official_plantuml_engine_semantic_source_same_paint_v1',
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
                  compiler_version='official_plantuml_engine_semantic_iteration_v1', model_calls=0, final_irrecoverable=False)
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
        if q.get('source_record_sha256') and sha((job[9] or '').encode()) != q['source_record_sha256']:
            raise RuntimeError('infrastructure_selected_baseline_revision_changed')
        if (identifier, source['category'], source['format']) != (source['pair_sha256'], job[1], job[2]):
            raise ValueError('original_scope_identity_mismatch')
        from compiler_plantuml_engine_canonical_claim_v1 import require_available
        result['canonical_claim']=require_available(dict(zip(JOB_COLUMNS,job)))
        overlap_guard(identifier,q.get('run',''))
        compiler, quality = bindings(job[2])
        if q['compiler_unit'] != compiler.UNITS['plantuml']:
            raise ValueError('wrong_source_compiler_unit')
        support = compiler.static_support(dict(zip(JOB_COLUMNS, job)))
        if not support['supported']:
            raise ValueError('source_outside_current_compiler_support:' + json.dumps(support['reasons']))
        record = json.loads(job[9]) if job[9] else dict(id=identifier, source_pair_sha256=identifier,
                        category=job[1], source_format=job[2], source=job[3], format='drawio',
                        source_code_sha256=source['code_sha256'], source_image_sha256=source['image_sha256'])
        record = authoritative_originals(record, source, json.loads(job[11]) if job[11] else None, work)
        record = {**record,'source_record':source}  # Canonical source equally for B/C.
        baseline = q.get('evaluation_phase') == 'baseline'
        if baseline and q['mode'] == 'batch':
            raise ValueError('baseline_cannot_run_as_production_batch')
        if baseline:
            if not job[9]:
                raise ValueError('baseline_has_no_existing_candidate')
            if (record['code_sha256'], record['image_sha256']) != (q['baseline_code_sha256'], q['baseline_image_sha256']):
                raise ValueError('baseline_revision_changed')
        elif q.get('existing_development_candidate'):
            if q['mode']!='development' or q.get('evaluation_phase')!='control_positive':
                raise ValueError('existing_positive_only_for_development_controller_control')
            candidate=Path(q['existing_development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R/'clean').resolve()):raise ValueError('development_positive_not_in_clean')
            record=json.loads(candidate.read_bytes())
            if (record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(identifier,source['code_sha256'],source['image_sha256']):raise ValueError('development_positive_original_identity_changed')
            if record.get('candidate_quality_adapter',{}).get('policy')!=compiler.configuration()['policy']:raise ValueError('development_positive_frozen_frontend_changed')
        elif q.get('negative_control'):
            candidate = Path(q['development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R / 'clean').resolve()):
                raise ValueError('negative_candidate_not_in_clean')
            record = json.loads(candidate.read_bytes())
        else:
            stage = 'conversion'
            frontend_work = W / compiler.VERSION / 'program_runs' / work.parent.name / work.name
            source_owner=W/compiler.source.VERSION/'candidate_sources'/identifier
            previous_source_proofs=set(source_owner.glob('*/source_proof.json'))
            overlap_guard(identifier,q.get('run',''))
            result['canonical_claim']=require_available(dict(zip(JOB_COLUMNS,job)))
            from compiler_plantuml_engine_once_v1 import claim
            result['normal_frontend_call_claim']=claim(identifier,source,compiler,request_path)
            attempt = compiler.convert(record, job, frontend_work)
            save(work / 'frontend_result.json', raw(attempt))
            if not attempt.get('ok'):
                result.update(status='abandoned', phase=stage, reason=attempt.get('reason') or 'source_layout_conversion_failed',
                              detail=attempt.get('detail') or attempt.get('error'),
                              infrastructure_failure=attempt.get('infrastructure_failure') is True or runtime_failure(attempt))
                # Preserve the actual source failure instead of masking every
                # DOM/frontend error behind 'source_reference_not_reproduced'.
                # This diagnostic never grants qualification or changes QA.
                new_proofs=set(source_owner.glob('*/source_proof.json'))-previous_source_proofs
                if len(new_proofs)==1:
                    path=next(iter(new_proofs));blob=path.read_bytes();evidence=json.loads(blob)
                    if evidence.get('static_support',{}).get('source_id')==identifier:
                        detail=evidence.get('detail') or evidence.get('reason')
                        import re
                        typed=re.search(r'(typed_[A-Za-z0-9_]+)',str(detail))
                        result['source_failure']={'file':str(path.relative_to(R)),'sha256':sha(blob),'reason':typed[1] if typed else evidence.get('reason'),'detail':detail,'source_only_diagnostic_not_acceptance':True}
                save(work / 'result.json', raw(result))
                return result
            record = attempt['record']
        for field, hash_field in [('code_file', 'code_sha256'), ('image_file', 'image_sha256'),
                                 ('original_source_code', 'source_code_sha256'), ('original_reference', 'source_image_sha256')]:
            checked(record[field], record[hash_field])
        proposal = work / 'candidate_record.json'
        save(proposal, raw(record))
        stage = 'quality'
        directory = W / 'prototype/candidate_quality_ro_v1' / ('iteration_' + work.parent.name + '_' + str(q['seq']) + '_' + uuid.uuid4().hex)
        report = quality.verify(identifier, proposal, R, Path(compiler.__file__), directory)
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
            result['source_failure_reasons']=report.get('checks',{}).get('source',{}).get('failures',[])
            text = json.dumps(report.get('failures', []))
            result.update(status='abandoned', phase=stage, reason='retryable_independent_quality_failure',
                          detail=report.get('failures'), infrastructure_failure=runtime_failure(report.get('failures', [])))
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30) as db:
            if db.execute('select * from jobs where id=?', (identifier,)).fetchone() != job:
                raise RuntimeError('infrastructure_original_job_changed')
    except Exception as error:
        result.update(status='abandoned', phase=stage, reason='retryable_iteration_case_failure',
                      error_type=type(error).__name__, detail=str(error)[:6000],
                      infrastructure_failure=__import__('compiler_typed_runtime_failure_v1').is_infrastructure(exception=error))
        save(work / 'traceback.txt', traceback.format_exc().encode())
    save(work / 'result.json', raw(result))
    return result


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
