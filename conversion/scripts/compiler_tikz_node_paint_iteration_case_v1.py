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
import compiler_tikz_node_paint_source_contract_v1 as contract

from fixed_batch_case_v1 import R, W, checked, raw, save, sha
from compiler_typed_runtime_failure_v1 import diagnose as infrastructure_diagnosis,is_infrastructure,diagnostic_messages

ROUTES = {'tikz': ('compiler_tikz_node_paint_source_contract_v1', 'compiler_tikz_node_paint_quality_ro_v5')}
REQUIRED_CHECKS = {'structure', 'resources', 'render', 'source', 'text_paint', 'fonts', 'visual', 'native_editing'}
JOB_COLUMNS = ('id', 'category', 'format', 'source', 'input_record', 'state', 'route', 'attempts',
               'updated_at', 'output_record', 'error', 'input_manifest', 'worker_pid')

def bindings(fmt):
    frontend, quality = ROUTES[fmt]
    compiler = importlib.import_module(frontend)
    return compiler, importlib.import_module(quality)


def quality_failure_diagnosis(report):
    """Normalize only the known RO-QA exception-record schema.

    Its top-level failures records use ``type`` for the caught exception name.
    This adapter never interprets generic frontend detail or source-object type
    fields as exceptions, and it never mutates the original QA report.
    """
    normalized={**report}
    if isinstance(report.get('failures'),list):
        normalized['failures']=[{**item,'exception_type':item['type']}if isinstance(item,dict)and isinstance(item.get('type'),str)else item for item in report['failures']]
    return infrastructure_diagnosis(normalized)


def ordinary_overlap_guard(identifier,ignore_runs=()):
    from compiler_mermaid_alpha_iteration_overlap_v2 import guard
    result=guard(identifier,ignore_runs=ignore_runs)
    if result['active']:raise ValueError('deferred_birth_verified_active_TikZ_conversion_overlap')
    return result


def qualified_guard(identifier,source):
    from compiler_mermaid_alpha_qualifications_v2 import find_qualified
    if find_qualified(identifier,source,root=R)is not None:raise ValueError('already_qualified_complete_original_preserved')


def once_guard(identifier,source,compiler,run):
    import compiler_source_core_attempts_v3 as history
    state=history.guard(identifier,source,compiler.configuration(),current_run=Path(run).name,root=R,catalog=contract.CATALOG)
    if state['already_attempted']:raise ValueError('same_source_core_already_attempted_preserved')
    return state

def full_quality(report, record):
    import compiler_tikz_node_paint_quality_ro_v5 as quality
    implementation=report.get('implementation_pins')or{}
    if report.get('version')!=quality.VERSION or not implementation or report.get('quality_policy')!=quality.VERSION+':'+quality.sha(quality.canonical(implementation))[:20]:raise ValueError('unbound_or_wrong_independent_TikZ_QA5_contract')
    if report.get('id')!=record.get('id')or report.get('canonical_mutations')!=0 or report.get('model_calls')!=0:raise ValueError('independent_TikZ_QA_original_identity_or_readonly_contract_changed')
    source_proof=record.get('compiler_tikz_node_paint_viewport_v2')or{}
    if report.get('profile_policy')!=source_proof.get('policy')or any(implementation.get(path)!=digest for path,digest in source_proof.get('pins',{}).items()):raise ValueError('independent_TikZ_QA_source_core_not_bound')
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
    if not (render.get('export_mode')=='complete_native_paint_fixed_inspection_export_v1' and
            render.get('paint_safety_frame')=='full_paint_inspection_viewport' and
            render.get('strict_outside_export_pixels')==0 and render.get('strict_outside_inspection_pixels')==0 and
            render.get('complete_source_paint_retained')is True and render.get('model_geometry_preserved')is True and
            type(render.get('original_declared_page_outside_pixels'))is int and render['original_declared_page_outside_pixels']>=0 and
            isinstance(render.get('export_plan'),dict) and render.get('native_svg_export_frame')):
        raise ValueError('incomplete_fixed_native_source_paint_export_contract')
    profile=record.get('compiler_tikz_node_paint_viewport_v2')or {};files=profile.get('files',{})
    for key in ('candidate_xml','candidate_png','native_padding_proof','unshifted_native_xml','native_export_before_inspection','native_export_after_inspection','native_export_before_svg','native_export_after_svg','native_export_before_info','native_export_after_info'):
        item=files.get(key)or {};checked(item.get('file',''),item.get('sha256',''))
    if (files['candidate_xml']['sha256'],files['candidate_png']['sha256'])!=(record['code_sha256'],record['image_sha256']):
        raise ValueError('full_export_payload_not_bound_to_candidate')
    if (files['native_export_after_inspection']['sha256'],files['native_export_after_svg']['sha256'])!=(render.get('full_native_inspection_png_sha256'),render.get('native_svg_export_sha256')):
        raise ValueError('fresh_full_native_inspection_or_SVG_export_changed')
    from tikz_node_paint_export_contract_v4 import registration
    registration(record,checked(record['original_reference'],record['source_image_sha256']),checked(record['code_file'],record['code_sha256']).decode(),R)
    domain=checks.get('compiler_source_render_domain')or{}
    if domain.get('ok')is not True or domain.get('every_source_text_primitive_checked')is not True or domain.get('source_glyphs',{}).get('ok')is not True or domain.get('source_glyphs',{}).get('tolerance_px')!=.03:raise ValueError('missing_complete_actual_PDF_source_render_domain')
    if domain.get('visual',{}).get('thresholds',{}).get('each_text_line_ssim')!=.55 or domain['visual'].get('ok')is not True:raise ValueError('Source_text_primitive_local_fidelity_gate_changed')
    original=checks['visual'].get('original_reference_visual')or{}
    if any(failure!='local_text_line_ssim_below_0.55'for failure in original.get('failures',[])):raise ValueError('original_reference_global_tile_or_foreground_failure')
    if checks['source']['evidence'].get('source_label_driver_ownership_complete')is not True:raise ValueError('actual_PGF_node_paint_ownership_missing')
    from tikz_node_paint_editing_v4 import validate_report
    validate_report(checks['native_editing'])
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
    target = (R / record['image_file']).resolve(strict=True) if record['image_sha256'] == digest else code.parent / ('image.native.' + digest[:24] + '.png')
    if target.exists():
        if sha(target.read_bytes()) != digest:
            raise RuntimeError('infrastructure_immutable_published_image_changed')
    else:
        save(target, fresh)
    out = {k: v for k, v in record.items() if not k.startswith('_verified_')}
    out.update(image_file=str(target.relative_to(R)), image_sha256=digest,
               quality_state='accepted_complete_PGF_node_paint_Source_core2_QA5_v1',
               automatic_quality_policy=report['quality_policy'],
               automatic_quality_audit=str((directory / 'report.json').relative_to(R)),
               accepted_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               model=None, model_configuration={'external_model_calls': 0, 'deterministic_compiler': True})
    manifest = manifest_row(out, R)[0]
    return manifest


def run(request_path):
    q = json.loads(Path(request_path).read_bytes())
    identifier, work, source = q['id'], Path(q['work']).resolve(), q['source']
    stage = 'input'
    result = dict(id=identifier, seq=q['seq'], compiler_unit=q['compiler_unit'], cluster=q.get('cluster'),
                  source_code_sha256=source['code_sha256'], source_image_sha256=source['image_sha256'],
                  compiler_version='tikz_node_paint_iteration_v1', model_calls=0, final_irrecoverable=False)
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
        ordinary_overlap_guard(identifier,ignore_runs=(re.sub(r'_(?:B|C|mass)$','',Path(q.get('run','')).name),))
        compiler, quality = bindings(job[2])
        if q['compiler_unit'] != compiler.UNIT:
            raise ValueError('wrong_source_compiler_unit')
        support = compiler.static_support(dict(zip(JOB_COLUMNS, job)))
        if not support['supported']:
            raise ValueError('source_outside_current_compiler_support:' + json.dumps(support['reasons']))
        snapshot = q.get('source_capture_snapshot')
        if not snapshot or support.get('source_capture_snapshot') != snapshot:
            raise RuntimeError('infrastructure_frozen_selected_source_capture_changed')
        baseline = q.get('evaluation_phase') == 'baseline'
        if baseline and q['mode'] == 'batch':
            raise ValueError('baseline_cannot_run_as_production_batch')
        # C compiles authoritative source; stale cached candidate metadata must
        # never block a new frontend before it even runs.
        record = json.loads(job[9]) if baseline and job[9] else dict(id=identifier, source_pair_sha256=identifier,
                        category=job[1], source_format=job[2], source=job[3], format='drawio',
                        source_code_sha256=source['code_sha256'], source_image_sha256=source['image_sha256'])
        # Existing authoritative clean originals are resolved read-only. The
        # selected source/capture seal is supplied before any conversion, and
        # original() verifies it rather than replacing it with a new snapshot.
        record['compiler_source_capture_snapshot'] = snapshot
        seed, original_job = compiler.original(record, job)
        if original_job != job:
            raise RuntimeError('infrastructure_original_job_changed_before_conversion')
        record.update(seed)
        if baseline:
            if not job[9]:
                raise ValueError('baseline_has_no_existing_candidate')
            if (record['code_sha256'], record['image_sha256']) != (q['baseline_code_sha256'], q['baseline_image_sha256']):
                raise ValueError('baseline_revision_changed')
        elif q.get('existing_development_candidate'):
            if q['mode']!='development'or q.get('evaluation_phase')!='control_positive':raise ValueError('existing_positive_only_for_development_control')
            candidate=Path(q['existing_development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R/'clean').resolve()):raise ValueError('development_positive_not_in_clean')
            record=json.loads(candidate.read_bytes())
            if(record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(identifier,source['code_sha256'],source['image_sha256']):raise ValueError('development_positive_original_identity_changed')
            configuration=compiler.configuration()
            proof=record.get('compiler_tikz_node_paint_viewport_v2')or{}
            if proof.get('policy')!=configuration['policy']or proof.get('pins')!=configuration['pins']:raise ValueError('development_positive_source_representation_changed')
        elif q.get('negative_control'):
            candidate = Path(q['development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R / 'clean').resolve()):
                raise ValueError('negative_candidate_not_in_clean')
            record = json.loads(candidate.read_bytes())
        else:
            frontend_work = W / compiler.VERSION / 'program_runs' / work.parent.name / work.name
            ordinary_overlap_guard(identifier,ignore_runs=(re.sub(r'_(?:B|C|mass)$','',Path(q.get('run','')).name),))
            qualified_guard(identifier,source)
            once_guard(identifier,source,compiler,q.get('run',''))
            from compiler_plantuml_engine_canonical_claim_v1 import diagnose as claim_diagnose
            claim=claim_diagnose(dict(zip(JOB_COLUMNS,job)))
            if not claim['conversion_allowed']:raise ValueError('deferred_live_or_unproved_canonical_worker_claim')
            stage = 'conversion'
            attempt = compiler.convert(record, job, frontend_work)
            save(work / 'frontend_result.json', raw(attempt))
            if not attempt.get('ok'):
                diagnosis=infrastructure_diagnosis(attempt)
                result.update(status='abandoned', phase=stage, reason=attempt.get('reason') or 'source_layout_conversion_failed',
                              detail=attempt.get('detail') or attempt.get('error'),
                              infrastructure_failure=diagnosis['infrastructure_failure'],infrastructure_diagnosis=diagnosis)
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
        report = quality.verify(identifier, proposal, R, compiler.QUALITY_PLUGIN_FILE, directory)
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
            diagnosis=quality_failure_diagnosis(report)
            result.update(status='abandoned', phase=stage, reason='retryable_independent_quality_failure',
                          detail=report.get('failures'), infrastructure_failure=diagnosis['infrastructure_failure'],infrastructure_diagnosis=diagnosis)
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30) as db:
            if db.execute('select * from jobs where id=?', (identifier,)).fetchone() != job:
                raise RuntimeError('infrastructure_original_job_changed')
    except Exception as error:
        diagnosis=infrastructure_diagnosis(error)
        result.update(status='abandoned', phase=stage, reason='retryable_iteration_case_failure',
                      error_type=type(error).__name__, detail=str(error)[:6000],
                      infrastructure_failure=diagnosis['infrastructure_failure'],infrastructure_diagnosis=diagnosis)
        save(work / 'traceback.txt', traceback.format_exc().encode())
    save(work / 'result.json', raw(result))
    return result


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
