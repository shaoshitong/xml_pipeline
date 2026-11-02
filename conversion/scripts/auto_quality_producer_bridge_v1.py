"""Finite bridge for QA3 producer holds; never starts a model or changes media.

prepare() performs file verification outside the writer transaction. apply()
requires the caller's transaction and rechecks the complete job/queue/audit CAS.
The returned metadata must be published with that same transaction. Old queue
attempts, sessions, priorities, errors and timestamps are deliberately preserved.
"""
import argparse
import datetime
import json
import sqlite3
from pathlib import Path

import auto_quality_dispatch_v2 as core

R = Path('/backup/shaoshitong/img2code_20261029')
TABLE = 'auto_quality_producer_bridge_v1'
QA3 = 'source_execution_glyph_lineage_native_render_and_local_fidelity_v3:'
IDLE = ('rendered', 'needs_quality_repair', 'harness_review_pending')
MODEL_TABLES = ('harness_queue', 'harness_queue_v2', 'harness_queue_v3')
QUEUE_COLUMNS = 'id,state,attempts,priority,worker_pid,started_at,heartbeat,session_dir,error'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def initialize(db):
    core.initialize(db)
    db.execute('CREATE TABLE IF NOT EXISTS ' + TABLE + '''(
      id TEXT NOT NULL,semantic_revision_key TEXT NOT NULL,
      code_hash TEXT NOT NULL,image_hash TEXT NOT NULL,policy TEXT NOT NULL,
      audit_sha256 TEXT NOT NULL,receipt TEXT NOT NULL,updated_at TEXT NOT NULL,
      PRIMARY KEY(id,semantic_revision_key))''')


def exists(db, table):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def model_owned(db, identifier):
    for table in MODEL_TABLES:
        if not exists(db, table):
            continue
        columns = {r[1] for r in db.execute('PRAGMA table_info(' + table + ')')}
        condition = "state='running'" + (' OR worker_pid IS NOT NULL' if 'worker_pid' in columns else '')
        if db.execute('SELECT 1 FROM ' + table + ' WHERE id=? AND (' + condition + ')', (identifier,)).fetchone():
            return True
    return False


def _checked(root, locator, digest):
    if not locator or not core.HASH.fullmatch(str(digest or '')):
        raise ValueError('bridge_missing_file_identity')
    target = (root / locator).resolve()
    if not target.is_relative_to((root / 'clean').resolve()):
        raise ValueError('bridge_resource_outside_clean')
    raw = target.read_bytes()
    if core.sha(raw) != digest:
        raise ValueError('bridge_resource_hash_changed: ' + locator)
    return raw


def _identity(record, input_raw):
    identity = core._identity(record)
    source = json.loads(input_raw)
    for original, current in (('code_sha256', 'source_code_sha256'), ('image_sha256', 'source_image_sha256')):
        if source.get(original) != identity[current]:
            raise ValueError('bridge_authoritative_input_source_mismatch')
    return identity


def _genuine(report):
    ok, _ = core._genuine_failure(report)
    if ok:
        return True
    marker = report.get('checks', {}).get('native_marker_paint') or {}
    return (report.get('state') == 'repair_required' and not report.get('accepted')
            and marker.get('supported') is True and marker.get('ok') is False
            and bool(marker.get('failures'))
            and any(str(f).startswith('native_marker_paint_failure:') for f in report.get('failures', [])))


def _snapshot(db, identifier):
    return db.execute('SELECT state,output_record,input_record,input_manifest,worker_pid FROM jobs WHERE id=?', (identifier,)).fetchone()


def prepare(db, identifier, *, policy, root=R):
    """Read-only plan: only a committed typed current-revision QA3 failure qualifies."""
    root = Path(root)
    rejected = {'ok': False, 'id': identifier}
    if not isinstance(policy, str) or not policy.startswith(QA3):
        return {**rejected, 'reason': 'active_qa3_policy_required'}
    if not exists(db, 'harness_queue_v3'):
        return {**rejected, 'reason': 'queue_missing'}
    queue = db.execute('SELECT ' + QUEUE_COLUMNS + ' FROM harness_queue_v3 WHERE id=?', (identifier,)).fetchone()
    job = _snapshot(db, identifier)
    if not queue or queue[1] != 'held_for_quality_v3' or queue[4] is not None:
        return {**rejected, 'reason': 'not_an_idle_quality_v3_hold'}
    if not job or job[0] not in IDLE or job[4] is not None or not job[3] or model_owned(db, identifier):
        return {**rejected, 'reason': 'job_or_model_owned_or_ineligible'}
    record = json.loads(job[1])
    if record.get('id') != identifier:
        raise ValueError('bridge_job_record_identity_mismatch')
    _identity(record, job[2])
    args = (identifier, record['code_sha256'], record['image_sha256'], policy)
    exception = db.execute('SELECT * FROM auto_quality_exceptions_v1 WHERE id=? AND code_hash=? AND image_hash=? AND policy=?', args).fetchone()
    audit = db.execute('SELECT * FROM auto_quality_audits_v1 WHERE id=? AND code_hash=? AND image_hash=? AND policy=?', args).fetchone()
    if not exception or exception[4:6] != ('source_geometry_or_harness', 'pending') or not audit or audit[4] != 'repair_required':
        return {**rejected, 'reason': 'no_committed_current_typed_qa3_failure'}
    report = json.loads(audit[5])
    expected = {'id': identifier, 'policy': policy, 'input_code_sha256': record['code_sha256'],
                'input_image_sha256': record['image_sha256'],
                'source_code_sha256': record['source_code_sha256'], 'source_image_sha256': record['source_image_sha256']}
    if (any(report.get(k) != v for k, v in expected.items()) or not _genuine(report)
            or exception[6] != '; '.join(report.get('failures', []))):
        return {**rejected, 'reason': 'qa3_report_identity_or_concrete_failure_unverified'}
    xml = _checked(root, record['code_file'], record['code_sha256']).decode()
    _checked(root, record['image_file'], record['image_sha256'])
    _checked(root, record.get('original_source_code'), record['source_code_sha256'])
    _checked(root, record.get('original_reference'), record['source_image_sha256'])
    if record.get('original_source_data'):
        _checked(root, record['original_source_data'], record.get('source_data_sha256'))
    key = core.semantic_revision_key(record, xml)
    prior = db.execute('SELECT dispatched FROM ' + core.TABLE + ' WHERE id=? AND semantic_revision_key=?', (identifier, key)).fetchone() if exists(db, core.TABLE) else None
    if prior and prior[0]:
        return {**rejected, 'reason': 'semantic_revision_already_dispatched'}
    return {'ok': True, 'id': identifier, 'reason': 'verified_current_qa3_producer_hold',
            'job': tuple(job), 'queue': tuple(queue), 'exception': tuple(exception),
            'audit': tuple(audit), 'record': record, 'report': report,
            'semantic_revision_key': key, 'audit_sha256': core.sha(audit[5].encode())}


def apply(db, plan, *, root=R):
    """Return (metadata, receipt), without BEGIN/COMMIT, filesystem or jobs writes."""
    if not db.in_transaction:
        raise RuntimeError('bridge apply requires the caller-owned writer transaction')
    if not plan.get('ok'):
        return plan.get('record'), {'released': False, 'reason': plan.get('reason')}
    root = Path(root)
    identifier = plan['id']
    record = plan['record']
    if record != json.loads(plan['job'][1]) or plan['report'] != json.loads(plan['audit'][5]):
        return record, {'released': False, 'reason': 'plan_payload_changed_after_preparation'}
    unchanged = _snapshot(db, identifier) == plan['job']
    unchanged = unchanged and db.execute('SELECT ' + QUEUE_COLUMNS + ' FROM harness_queue_v3 WHERE id=?', (identifier,)).fetchone() == plan['queue']
    args = (identifier, record['code_sha256'], record['image_sha256'], plan['report']['policy'])
    unchanged = unchanged and db.execute('SELECT * FROM auto_quality_exceptions_v1 WHERE id=? AND code_hash=? AND image_hash=? AND policy=?', args).fetchone() == plan['exception']
    unchanged = unchanged and db.execute('SELECT * FROM auto_quality_audits_v1 WHERE id=? AND code_hash=? AND image_hash=? AND policy=?', args).fetchone() == plan['audit']
    if not unchanged or model_owned(db, identifier):
        return record, {'released': False, 'reason': 'stale_job_queue_audit_or_active_model'}
    fresh = prepare(db, identifier, policy=plan['report']['policy'], root=root)
    if not fresh['ok'] or fresh['semantic_revision_key'] != plan['semantic_revision_key']:
        return record, {'released': False, 'reason': fresh.get('reason', 'changed_semantic_revision')}
    key = plan['semantic_revision_key']
    updated, feedback = core._feedback(record, plan['report'], key)
    receipt = {'source': 'automatic_quality', 'released': True, 'id': identifier,
               'reason': 'verified_current_qa3_quality_v3_hold_released',
               'queue_state_before': 'held_for_quality_v3', 'queue_state_after': 'held_for_source_v5',
               'semantic_revision_key': key, 'policy': plan['report']['policy'],
               'checked_code_sha256': record['code_sha256'], 'checked_image_sha256': record['image_sha256'],
               'audit_sha256': plan['audit_sha256'], 'at': now(), 'model_calls_started_by_bridge': 0}
    changed = db.execute("UPDATE harness_queue_v3 SET state='held_for_source_v5' WHERE id=? AND state='held_for_quality_v3' AND worker_pid IS NULL", (identifier,)).rowcount
    if changed != 1:
        raise RuntimeError('bridge_queue_cas_failed')
    feedback['dispatch_evidence'] = receipt
    stamp = now()
    db.execute('INSERT INTO ' + core.TABLE + ''' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(id,semantic_revision_key) DO UPDATE SET
      dispatched=1,state=excluded.state,queue_state_before=excluded.queue_state_before,
      queue_state_after=excluded.queue_state_after,policy=excluded.policy,
      feedback=excluded.feedback,updated_at=excluded.updated_at''',
      (identifier, key, record['source_code_sha256'], record['source_image_sha256'],
       record.get('source_data_sha256'), record['code_sha256'], record['image_sha256'],
       1, receipt['reason'], 'held_for_quality_v3', 'held_for_source_v5', None, None,
       plan['report']['policy'], json.dumps(feedback, ensure_ascii=False), stamp, stamp))
    db.execute('INSERT INTO ' + TABLE + ' VALUES(?,?,?,?,?,?,?,?)',
               (identifier, key, record['code_sha256'], record['image_sha256'],
                plan['report']['policy'], plan['audit_sha256'], json.dumps(receipt, ensure_ascii=False), stamp))
    return updated, receipt


def _atomic(path, data):
    temporary = path.with_name(path.name + '.producer-bridge-v1.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def publish(db, plan, *, root=R):
    """Optional finite CLI publisher with metadata and SQL rollback."""
    root = Path(root)
    conversion = root / plan['record']['code_file']
    conversion = conversion.parent / 'conversion.json'
    replacement = None
    old = None
    db.execute('BEGIN IMMEDIATE')
    try:
        updated, receipt = apply(db, plan, root=root)
        if receipt['released']:
            replacement = (json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode()
            old = conversion.read_bytes() if conversion.exists() else None
            _atomic(conversion, replacement)
            state, raw, inp, manifest, owner = plan['job']
            changed = db.execute('''UPDATE jobs SET output_record=?,updated_at=? WHERE id=? AND
              state=? AND output_record=? AND input_record=? AND input_manifest=? AND worker_pid IS NULL''',
              (json.dumps(updated, ensure_ascii=False), now(), plan['id'], state, raw, inp, manifest)).rowcount
            if changed != 1:
                raise RuntimeError('bridge_job_metadata_cas_failed')
        db.commit()
        return receipt
    except BaseException:
        db.rollback()
        if replacement is not None and conversion.exists() and conversion.read_bytes() == replacement:
            if old is None:
                conversion.unlink()
            else:
                _atomic(conversion, old)
        raise


def run_once(*, root=R, policy=None, limit=10000, enabled=False):
    root = Path(root)
    if not 1 <= limit <= 10000:
        raise ValueError('bridge limit must be 1..10000')
    work = root / 'conversion'
    policy = policy or json.loads((work / 'auto_quality_owner.json').read_text())['policy']
    target = str(work / 'jobs.sqlite')
    db = sqlite3.connect(target if enabled else 'file:' + target + '?mode=ro', uri=not enabled, timeout=2)
    try:
        if enabled:
            db.execute('BEGIN IMMEDIATE')
            initialize(db)
            db.commit()
        identifiers = [row[0] for row in db.execute("SELECT id FROM harness_queue_v3 WHERE state='held_for_quality_v3' AND worker_pid IS NULL ORDER BY id LIMIT ?", (limit,))]
        result = {'at': now(), 'policy': policy, 'publish': enabled, 'selected': len(identifiers),
                  'would_release': 0, 'released': 0, 'results': [], 'model_calls_started_by_bridge': 0}
        for identifier in identifiers:
            try:
                plan = prepare(db, identifier, policy=policy, root=root)
                result['would_release'] += int(plan['ok'])
                receipt = publish(db, plan, root=root) if enabled and plan['ok'] else {'id': identifier, 'released': False, 'reason': plan['reason']}
                result['released'] += int(receipt['released'])
                result['results'].append(receipt)
            except Exception as exc:
                db.rollback()
                result['results'].append({'id': identifier, 'released': False, 'error': str(exc)[:1000]})
        return result
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=R)
    parser.add_argument('--policy')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 10000:
        parser.error('--limit must be 1..10000')
    print(json.dumps(run_once(root=args.root, policy=args.policy, limit=args.limit, enabled=args.publish), ensure_ascii=False))


if __name__ == '__main__':
    main()
