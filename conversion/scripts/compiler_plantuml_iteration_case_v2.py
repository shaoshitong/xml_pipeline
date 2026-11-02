"""One frozen source-layout compiler attempt and independent full QA.

Owns no canonical jobs. Qualified assets/immutable metadata live in clean/;
failure means pending retry by a later compiler version, not input abandonment.
"""
import datetime
import importlib
import json
from pathlib import Path
import sqlite3
import traceback
import uuid

from fixed_batch_case_v1 import R, W, checked, prepare_originals, raw, save, sha

ROUTES = {'plantuml': ('compiler_plantuml_natural_candidate_v9', 'deterministic_candidate_quality_ro_v1')}
REQUIRED_CHECKS = {'structure', 'resources', 'render', 'source', 'text_paint', 'fonts', 'visual', 'native_editing'}
JOB_COLUMNS = ('id', 'category', 'format', 'source', 'input_record', 'state', 'route', 'attempts',
               'updated_at', 'output_record', 'error', 'input_manifest', 'worker_pid')


def runtime_failure(value):
    text = json.dumps(value, ensure_ascii=False, default=str)
    return any(word in text for word in ('ModuleNotFoundError', 'ImportError', 'infrastructure_',
        'Page.captureScreenshot', 'Unable to capture screenshot', 'TargetClosedError',
        'Browser closed unexpectedly', 'Browser crashed', 'Connection closed while reading from the driver'))


def bindings(fmt):
    frontend, quality = ROUTES[fmt]
    compiler = importlib.import_module(frontend)
    return compiler, importlib.import_module(quality)


def full_quality(report, record):
    checks = report.get('checks', {})
    if report.get('ok') is not True or report.get('failures') or not REQUIRED_CHECKS <= set(checks):
        raise ValueError('incomplete_independent_full_quality')
    for name in ('source', 'visual', 'native_editing'):
        if checks[name].get('ok') is not True:
            raise ValueError('failed_mandatory_quality_stage:' + name)
    if checks['source'].get('evidence', {}).get('complete_source_coverage') is not True:
        raise ValueError('partial_source_coverage')
    if checks['source'].get('evidence',{}).get('fresh_source_grapheme_layout',{}).get('ok') is not True:
        raise ValueError('incomplete_independent_source_grapheme_layout')
    if checks['fonts'].get('all_rendered_fonts_embedded') is not True:
        raise ValueError('unembedded_actual_font')
    render = checks['render']
    if render.get('code_sha256') != record['code_sha256'] or render.get('strict_outside_page_pixels') != 0:
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
               quality_state='accepted_complete_original_plantuml_textlength_iteration_v2',
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
                  compiler_version='iterative_plantuml_source_textlength_v2', model_calls=0, final_irrecoverable=False)
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
        elif q.get('negative_control'):
            candidate = Path(q['development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R / 'clean').resolve()):
                raise ValueError('negative_candidate_not_in_clean')
            record = json.loads(candidate.read_bytes())
        else:
            stage = 'conversion'
            frontend_work = W / compiler.VERSION / 'program_runs' / work.parent.name / work.name
            attempt = compiler.convert(record, job, frontend_work)
            save(work / 'frontend_result.json', raw(attempt))
            if not attempt.get('ok'):
                result.update(status='abandoned', phase=stage, reason=attempt.get('reason') or 'source_layout_conversion_failed',
                              detail=attempt.get('detail') or attempt.get('error'),
                              infrastructure_failure=attempt.get('infrastructure_failure') is True or runtime_failure({'reason':attempt.get('reason'),'detail':attempt.get('detail'),'error':attempt.get('error')}))
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
            text = json.dumps(report.get('failures', []))
            result.update(status='abandoned', phase=stage, reason='retryable_independent_quality_failure',
                          detail=report.get('failures'), infrastructure_failure=runtime_failure(report.get('failures', [])))
        with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30) as db:
            if db.execute('select * from jobs where id=?', (identifier,)).fetchone() != job:
                raise RuntimeError('infrastructure_original_job_changed')
    except Exception as error:
        result.update(status='abandoned', phase=stage, reason='retryable_iteration_case_failure',
                      error_type=type(error).__name__, detail=str(error)[:6000],
                      infrastructure_failure=isinstance(error, (ImportError, ModuleNotFoundError)) or runtime_failure(str(error)))
        save(work / 'traceback.txt', traceback.format_exc().encode())
    save(work / 'result.json', raw(result))
    return result


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
