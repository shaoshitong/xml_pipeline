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
import svg_analytic_source_contract_v6 as contract

from fixed_batch_case_v1 import R, W, checked, raw, save, sha
from compiler_typed_runtime_failure_v1 import diagnose as infrastructure_diagnosis,is_infrastructure,diagnostic_messages

ROUTES = {'svg': ('svg_analytic_source_contract_v6', 'compiler_svg_scene_quality_ro_v24')}
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
    if result['active']:raise ValueError('deferred_birth_verified_active_SVG_conversion_overlap')
    return result


def qualified_guard(identifier,source):
    from compiler_mermaid_alpha_qualifications_v2 import find_qualified
    if find_qualified(identifier,source,root=R)is not None:raise ValueError('already_qualified_complete_original_preserved')


def once_guard(identifier,source,compiler,run):
    import compiler_source_core_attempts_v3 as history
    state=history.guard(identifier,source,compiler.configuration(),current_run=Path(run).name,root=R,catalog=contract.CATALOG)
    if state['already_attempted']:raise ValueError('same_source_core_already_attempted_preserved')
    return state

def full_quality(report,record):
    from svg_analytic_iteration_controls_v7 import full_quality as actual
    reference=record.get('strict_native_canvas_evidence')
    if reference is None and not report.get('checks',{}).get('render',{}).get('strict_clip_canvas_proof'):
        path=Path(report['evidence_file']).parent/'native_render.json'
        if not path.resolve().is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve()):raise ValueError('strict_native_evidence_outside_owned_QA')
        reference=dict(file=str(path.relative_to(R)),sha256=sha(path.read_bytes()))
    return actual(report,record,contract.configuration(),reference)


def existing_positive_binding(candidate,record,configuration):
    """Bind immutable historical metadata to final current full-QA controls."""
    from compiler_types_program_v1 import checked as check_ref
    proof=R/contract.CONTROLS
    if sha(proof.read_bytes())!=contract.CONTROLS_SHA256:raise ValueError('existing_SVG_positive_control_proof_changed')
    bundle=json.loads(proof.read_bytes())
    if bundle['frozen_frontend']!=configuration:raise ValueError('existing_SVG_positive_current_source_core_changed')
    _,blob=check_ref(bundle['qualified_manifest']);matches=[]
    for line in blob.splitlines():
        if not line:continue
        row=json.loads(line)
        if row['id']!=record['id']:continue
        path,payload=check_ref(dict(file=row['metadata_file'],sha256=row['metadata_sha256']),clean=True)
        if path.resolve()==candidate.resolve()and sha(payload)==sha(candidate.read_bytes())and json.loads(payload)==record:matches.append(row)
    if len(matches)!=1:raise ValueError('existing_SVG_positive_not_frozen_accepted_metadata')
    return matches[0]


def stage_fresh_image(record,report,directory):
    """Archive the actual QA PNG after exact RGBA proof, preserving old bytes."""
    from PIL import Image
    import io
    if report.get('ok')is not True:raise ValueError('SVG_fresh_image_requires_successful_independent_RO_quality')
    fresh=(Path(directory)/'fresh.png').read_bytes();digest=sha(fresh)
    if digest!=report['checks']['render']['image_sha256']:raise RuntimeError('infrastructure_SVG_fresh_QA_image_changed_before_publication')
    old=checked(record['image_file'],record['image_sha256'])
    a,b=Image.open(io.BytesIO(old)),Image.open(io.BytesIO(fresh))
    if a.size!=b.size or a.convert('RGBA').tobytes()!=b.convert('RGBA').tobytes():raise ValueError('SVG_original_proposed_and_actual_fresh_native_pixels_changed')
    if digest==record['image_sha256']:return record
    code=(R/record['code_file']).resolve(strict=True)
    if not code.is_relative_to((R/'clean').resolve()):raise ValueError('SVG_final_fresh_image_requires_clean_candidate_code')
    target=code.parent/('image.native.'+digest[:24]+'.png')
    if target.exists():
        if sha(target.read_bytes())!=digest:raise RuntimeError('infrastructure_SVG_immutable_fresh_publication_image_changed')
    else:save(target,fresh)
    return {**record,'image_file':str(target.relative_to(R.resolve())),'image_sha256':digest}


def publish(record, source, report, directory):
    record=stage_fresh_image(record,report,directory)
    native=directory/'native_render.json'
    record={**record,'strict_native_canvas_evidence':dict(file=str(native.relative_to(R)),sha256=sha(native.read_bytes()))}
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
               quality_state='accepted_complete_SVG_background_rotation_SOURCE_v18_orchestration_v3',
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
                  compiler_version='svg_analytic_iteration_v1', model_calls=0, final_irrecoverable=False)
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
            existing_positive_binding(candidate,record,configuration)
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
            compiler.assert_snapshot(job,snapshot)
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
        compiler.assert_snapshot(job,snapshot)
        for field, hash_field in [('code_file', 'code_sha256'), ('image_file', 'image_sha256'),
                                 ('original_source_code', 'source_code_sha256'), ('original_reference', 'source_image_sha256')]:
            checked(record[field], record[hash_field])
        from svg_analytic_private_QA_lease_v1 import quality_database,verify_after_quality
        qa_database,lease_proof,lease_audit=quality_database(job,work)
        result['canonical_owner_guard']=lease_proof
        if lease_audit is not None:result['canonical_owner_guard_audit']=str(lease_audit.relative_to(R))
        proposal = work / 'candidate_record.json'
        save(proposal, raw(record))
        stage = 'quality'
        directory = W / 'prototype/candidate_quality_ro_v1' / ('iteration_' + work.parent.name + '_' + str(q['seq']) + '_' + uuid.uuid4().hex)
        report = quality.verify(identifier, proposal, R, compiler.QUALITY_PLUGIN_FILE, directory,database=qa_database)
        verify_after_quality(job,qa_database,lease_proof,work)
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
