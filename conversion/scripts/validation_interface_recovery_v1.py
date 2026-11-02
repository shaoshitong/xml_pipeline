"""Reopen budget decisions supported only by known validator interface errors.

Never changes candidates, queues, source payloads, history or model budgets.
An immutable receipt retains the complete prior decision and exact CAS rows.
"""
import argparse, hashlib, json, os, sqlite3, time
from pathlib import Path

ROOT = Path('/backup/shaoshitong/img2code_20261029')
ERRORS = {"KeyError('source_render_svg')", "AssertionError('missing pinned source layout variant')"}
IDLE = {'rendered', 'needs_quality_repair', 'harness_review_pending', 'needs_fallback'}
sha = lambda value: hashlib.sha256(value).hexdigest()
canonical = lambda value: (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
now = lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def only_interface_errors(failures):
    if not failures:
        return False
    for failure in failures:
        prefix = 'source_coverage_failure: '
        if not isinstance(failure, str) or not failure.startswith(prefix):
            return False
        try:
            items = json.loads(failure[len(prefix):])
        except (ValueError, TypeError):
            return False
        if not isinstance(items, list) or not items:
            return False
        if not all(isinstance(item, dict) and item.get('reason') == 'source_profile_validation_error' and item.get('error') in ERRORS for item in items):
            return False
    return True


def row(db, table, identifier):
    cursor = db.execute('select * from ' + table + ' where id=?', (identifier,))
    names = [item[0] for item in cursor.description]
    values = cursor.fetchall()
    require(len(values) == 1, 'not_exactly_one_' + table)
    return dict(zip(names, values[0]))


def payloads(root, candidate):
    result = {}
    for field, digest in (('code_file', 'code_sha256'), ('image_file', 'image_sha256'), ('original_reference', 'source_image_sha256'), ('original_source_code', 'source_code_sha256')):
        path = (root / candidate[field]).resolve(strict=True)
        require(path.is_relative_to((root / 'clean').resolve()), 'payload_outside_clean')
        require(sha(path.read_bytes()) == candidate[digest], 'payload_hash_changed')
        result[candidate[field]] = candidate[digest]
    return result


def prepare(db, identifier, root=ROOT):
    root = Path(root)
    owner_path = root / 'conversion/auto_quality_owner.json'
    owner_raw = owner_path.read_bytes()
    owner = json.loads(owner_raw)
    job = row(db, 'jobs', identifier)
    outcome = row(db, 'processing_outcomes_v2', identifier)
    require(job['state'] in IDLE and job.get('worker_pid') is None, 'job_not_idle')
    require(outcome['status'] == 'abandoned' and outcome['reason'] == 'lifetime_model_budget_exhausted_quality_failed', 'not_budget_abandonment')
    candidate, source, prior = (json.loads(job['output_record']), json.loads(job['input_record']), json.loads(outcome['record']))
    require(candidate['id'] == candidate['source_pair_sha256'] == source['pair_sha256'] == identifier, 'original_identity_changed')
    require(candidate['category'] == source['category'] == outcome['category'] == job['category'] and source['category'] in ('scientific_diagram', 'poster'), 'category_changed')
    require(candidate['source_format'] == source['format'] == job['format'] == outcome['format'], 'format_changed')
    for stem in ('code', 'image'):
        require(source[stem + '_sha256'] == candidate['source_' + stem + '_sha256'] == outcome['source_' + stem + '_hash'] == prior['source_' + stem + '_sha256'], 'source_hash_changed')
        require(candidate[stem + '_sha256'] == prior[stem + '_sha256'], 'candidate_changed')
    require(prior['confirmed_model_calls'] >= 2 and prior['history_snapshot_id'], 'missing_historical_budget_evidence')
    require(only_interface_errors(prior['failed_qa_reasons']), 'prior_failure_not_only_known_interface_errors')
    def failure_audit(policy):
        return db.execute('select state,record,updated_at from auto_quality_audits_v1 where id=? and code_hash=? and image_hash=? and policy=?', (identifier, candidate['code_sha256'], candidate['image_sha256'], policy)).fetchone()
    qa_policy = owner['policy']
    qa = failure_audit(qa_policy)
    qa_scope = 'current_policy_interface_error'
    if qa is None:
        qa_policy = prior['failed_qa_policy']
        qa = failure_audit(qa_policy)
        qa_scope = 'historical_exact_revision_interface_error_requires_fresh_current_validation'
    require(qa is not None and qa[0] == 'repair_required', 'no_exact_interface_failure_audit')
    audit = json.loads(qa[1])
    require(audit.get('id') == identifier and audit.get('accepted') is False and only_interface_errors(audit.get('failures')), 'current_failure_not_only_known_interface_errors')
    for key, field in (('input_code_sha256', 'code_sha256'), ('input_image_sha256', 'image_sha256'), ('source_code_sha256', 'source_code_sha256'), ('source_image_sha256', 'source_image_sha256')):
        require(audit.get(key) == candidate[field], 'failure_audit_identity_changed')
    return {'id': identifier, 'prepared_at': now(), 'job': job, 'outcome': outcome, 'qa': list(qa), 'qa_policy': qa_policy, 'qa_scope': qa_scope, 'owner_sha256': sha(owner_raw), 'owner_policy': owner['policy'], 'payload_hashes': payloads(root, candidate), 'new_model_calls': 0, 'model_budget_preserved': True}


def apply(db, plan, root=ROOT, publish=False):
    root = Path(root)
    fresh = prepare(db, plan['id'], root)
    require({k: v for k, v in fresh.items() if k != 'prepared_at'} == {k: v for k, v in plan.items() if k != 'prepared_at'}, 'fresh_plan_changed')
    document = {'version': 1, 'at': now(), 'action': 'restore_pending_for_known_validator_interface_recovery', 'prior_state_is_not_semantic_failure': True, 'plan': plan, 'new_model_calls': 0, 'source_jobs_queues_history_and_model_budgets_unchanged': True}
    blob = canonical(document)
    relative = Path('conversion/validation_interface_recovery_v1') / plan['id'] / ('recovery.' + sha(blob) + '.json')
    if publish:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        require(path.parent.resolve().is_relative_to((root / 'conversion').resolve()), 'receipt_outside_owned_area')
        try:
            with path.open('xb') as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            require(path.read_bytes() == blob, 'receipt_conflict')
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    db.execute('begin immediate')
    try:
        checked = prepare(db, plan['id'], root)
        require({k: v for k, v in checked.items() if k != 'prepared_at'} == {k: v for k, v in plan.items() if k != 'prepared_at'}, 'full_cas_changed')
        if not publish:
            db.rollback()
            return {'id': plan['id'], 'state': 'dry_run_current', 'decision_file_written': False}
        require((root / relative).read_bytes() == blob, 'receipt_changed')
        prior = plan['outcome']
        record = {'id': plan['id'], 'reason': 'Known validator interface errors require deterministic recovery, not a semantic conversion verdict.', 'recovery_receipt': str(relative), 'recovery_receipt_sha256': sha(blob), 'new_model_calls': 0, 'model_budget_preserved': True, 'code_sha256': json.loads(plan['job']['output_record'])['code_sha256'], 'image_sha256': json.loads(plan['job']['output_record'])['image_sha256']}
        columns = list(prior)
        count = db.total_changes
        cursor = db.execute("update processing_outcomes_v2 set status='pending',reason='validation_interface_recovery_pending',record=?,updated_at=? where " + ' and '.join(key + ' is ?' for key in columns), (canonical(record).decode(), now(), *(prior[key] for key in columns)))
        require(cursor.rowcount == 1 and db.total_changes - count == 1, 'outcome_cas_or_side_effect_failure')
        db.commit()
        return {'id': plan['id'], 'state': 'recovery_pending', 'receipt': str(relative), 'sha256': sha(blob), 'model_budget_preserved': True}
    except BaseException:
        db.rollback()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    audit = json.loads((ROOT / 'conversion/abandoned_validation_errors_v1_audit.json').read_text())
    db = sqlite3.connect(ROOT / 'conversion/jobs.sqlite', timeout=60, isolation_level=None)
    results = []
    for item in audit['records']:
        try:
            result = apply(db, prepare(db, item['id']), publish=args.publish)
        except (ValueError, OSError, KeyError) as error:
            result = {'id': item['id'], 'state': 'retained', 'reason': str(error)}
        results.append(result)
    report = {'at': now(), 'publish': args.publish, 'records': results, 'model_calls': 0}
    (ROOT / 'conversion/validation_interface_recovery_v1_latest.json').write_bytes(canonical(report))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
