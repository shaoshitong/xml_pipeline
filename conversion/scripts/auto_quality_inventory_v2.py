"""Incremental exact-snapshot QA inventory with a private dirty-ID journal.

Only this tool's tables/triggers and the existing disposable candidate index are
written. Jobs, format queues and Harness queues are never updated. Triggers add
one small dirty-row write per normal job update, and another on output_record
assignments; both participate in the original transaction and roll back with it.
"""
import argparse
import collections
import datetime
import fcntl
import json
import os
import sqlite3
import time
from pathlib import Path

from auto_quality_inventory import (ROOT, TABLE, IDLE_STATES, HASH, classify,
                                    priority, throughput, _summary, utcnow)
from durable_sqlite import begin, commit

DIRTY = 'auto_quality_dirty_v2'
CACHE = 'auto_quality_inventory_rows_v2'
META = 'auto_quality_inventory_meta_v2'
TRIGGERS = ('auto_quality_dirty_v2_insert', 'auto_quality_dirty_v2_update',
            'auto_quality_dirty_v2_payload', 'auto_quality_dirty_v2_delete')


def initialize(db):
    """Install journal atomically before the first snapshot can be trusted."""
    begin(db)
    db.execute('CREATE TABLE IF NOT EXISTS ' + DIRTY + ''' (
      id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload_version INTEGER NOT NULL)''')
    db.execute('CREATE TABLE IF NOT EXISTS ' + CACHE + ''' (
      id TEXT PRIMARY KEY, format TEXT NOT NULL, state TEXT NOT NULL,
      worker_pid INTEGER, job_updated_at TEXT, payload_present INTEGER NOT NULL,
      payload_bytes INTEGER, method TEXT NOT NULL, route TEXT NOT NULL,
      reason TEXT NOT NULL, code_hash TEXT, image_hash TEXT, priority INTEGER NOT NULL,
      routing_record TEXT, record_kind TEXT NOT NULL,
      seen_version INTEGER NOT NULL, seen_payload_version INTEGER NOT NULL,
      observed_at TEXT NOT NULL)''')
    db.execute('CREATE TABLE IF NOT EXISTS ' + META + ' (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS ' + TABLE + ''' (
      id TEXT NOT NULL,code_hash TEXT NOT NULL,image_hash TEXT NOT NULL,
      priority INTEGER NOT NULL,route TEXT NOT NULL,reason TEXT NOT NULL,
      updated_at TEXT NOT NULL,PRIMARY KEY(id,code_hash,image_hash))''')
    db.execute('CREATE INDEX IF NOT EXISTS auto_quality_candidates_v1_route_priority ON '
               + TABLE + '(route,priority DESC,id)')
    db.execute('CREATE TRIGGER IF NOT EXISTS ' + TRIGGERS[0] + ''' AFTER INSERT ON jobs BEGIN
      INSERT INTO ''' + DIRTY + '''(id,version,payload_version) VALUES(NEW.id,1,1)
      ON CONFLICT(id) DO UPDATE SET version=version+1,payload_version=payload_version+1;
      END''')
    db.execute('CREATE TRIGGER IF NOT EXISTS ' + TRIGGERS[1] + ''' AFTER UPDATE ON jobs BEGIN
      INSERT INTO ''' + DIRTY + '''(id,version,payload_version) VALUES(NEW.id,1,0)
      ON CONFLICT(id) DO UPDATE SET version=version+1;
      INSERT INTO ''' + DIRTY + '''(id,version,payload_version)
      SELECT OLD.id,1,0 WHERE OLD.id<>NEW.id
      ON CONFLICT(id) DO UPDATE SET version=version+1;
      END''')
    db.execute('CREATE TRIGGER IF NOT EXISTS ' + TRIGGERS[2] + ''' AFTER UPDATE OF output_record ON jobs BEGIN
      INSERT INTO ''' + DIRTY + '''(id,version,payload_version) VALUES(NEW.id,1,1)
      ON CONFLICT(id) DO UPDATE SET version=version+1,payload_version=payload_version+1;
      END''')
    db.execute('CREATE TRIGGER IF NOT EXISTS ' + TRIGGERS[3] + ''' AFTER DELETE ON jobs BEGIN
      INSERT INTO ''' + DIRTY + '''(id,version,payload_version) VALUES(OLD.id,1,0)
      ON CONFLICT(id) DO UPDATE SET version=version+1;
      END''')
    commit(db)
    # Triggers are committed before seeding. Writes during the bounded seed
    # batches are therefore captured; INSERT OR IGNORE cannot reset a version.
    # New IDs inserted behind our keyset cursor are covered by INSERT trigger.
    seeded = db.execute('SELECT value FROM ' + META + ' WHERE key="journal_seeded"').fetchone()
    if not seeded:
        last_id = ''
        while True:
            rows = db.execute('SELECT id FROM jobs WHERE id>? ORDER BY id LIMIT 500',
                              (last_id,)).fetchall()
            if not rows:
                break
            begin(db)
            db.executemany('INSERT OR IGNORE INTO ' + DIRTY + ' VALUES(?,1,1)', rows)
            commit(db)
            last_id = rows[-1][0]
        begin(db)
        db.execute('INSERT INTO ' + META + ' VALUES("journal_seeded",?) ON CONFLICT(key) DO NOTHING', (utcnow(),))
        commit(db)


def slim_record(raw):
    """Discard font base64/DOM/geometry; preserve every field used for routing."""
    if raw is None:
        return None, 'none'
    try:
        record = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, 'malformed'
    if not isinstance(record, dict):
        return None, 'nonobject'
    result = {key: record.get(key) for key in ('source_format', 'conversion_method',
              'code_sha256', 'image_sha256', 'edges', 'bound_edges')}
    coverage = record.get('source_coverage')
    result['source_coverage'] = ({key: coverage.get(key) for key in ('ok', 'status')}
                                 if isinstance(coverage, dict) else None)
    connectivity = record.get('connectivity')
    result['connectivity'] = ({'complete': connectivity.get('complete')}
                              if isinstance(connectivity, dict) else None)
    metrics = record.get('metrics')
    result['metrics'] = ({key: metrics.get(key) for key in
                         ('original_reference_ssim_512', 'reference_ssim_512')}
                         if isinstance(metrics, dict) else None)
    result['native_embedded_fonts'] = bool(record.get('native_embedded_fonts'))
    result['fonts'] = bool(record.get('fonts'))
    return result, 'object'


def _classify(fmt, state, owner, record, kind):
    value = [] if kind == 'nonobject' else record
    return classify(fmt, state, owner, value, malformed=kind == 'malformed')


def _eligible(state, owner, record, route):
    return (route in ('graph', 'vector', 'native', 'repair') and
            state in IDLE_STATES and owner is None and isinstance(record, dict) and
            bool(HASH.fullmatch(str(record.get('code_sha256', '')))) and
            bool(HASH.fullmatch(str(record.get('image_sha256', '')))))


def _previous(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _refresh(root=ROOT, expected_total=131904, _after_snapshot=None):
    """One bounded refresh; dirty versions catch equal/backdated timestamps.

    _after_snapshot is an isolated concurrency-test hook, not used in production.
    """
    started = time.monotonic()
    root = Path(root)
    work = root / 'conversion'
    path = work / 'auto_quality_inventory.json'
    previous = _previous(path)
    db = sqlite3.connect(work / 'jobs.sqlite', timeout=2)
    db.execute('PRAGMA busy_timeout=2000')
    initialize(db)
    db.execute('BEGIN')
    total = db.execute('SELECT count(*) FROM jobs').fetchone()[0]
    if total != expected_total:
        db.rollback()
        db.close()
        raise AssertionError('Scope differs from expected total: %d != %d' % (total, expected_total))
    observed = utcnow()
    last = db.execute('SELECT value FROM ' + META + ' WHERE key="verified_snapshot_at_utc"').fetchone()
    watermark = None
    if last:
        try:
            watermark = (datetime.datetime.fromisoformat(last[0]) -
                         datetime.timedelta(seconds=2)).isoformat()
        except ValueError:
            pass
    # BLOB length uses the stored byte count and does not scan the huge TEXT.
    query = '''SELECT j.id,j.format,j.state,j.worker_pid,j.updated_at,
       j.output_record IS NOT NULL,length(CAST(j.output_record AS BLOB)),
       coalesce(d.version,0),coalesce(d.payload_version,0),
       c.format,c.state,c.worker_pid,c.job_updated_at,c.payload_present,c.payload_bytes,
       c.method,c.route,c.reason,c.code_hash,c.image_hash,c.priority,
       c.routing_record,c.record_kind,c.seen_version,c.seen_payload_version,
       q.id,q.route,q.reason,q.priority
       FROM jobs j LEFT JOIN ''' + DIRTY + ''' d ON d.id=j.id
       LEFT JOIN ''' + CACHE + ''' c ON c.id=j.id
       LEFT JOIN ''' + TABLE + ''' q ON q.id=j.id AND q.code_hash=c.code_hash AND q.image_hash=c.image_hash'''
    totals = collections.Counter(total_jobs=total)
    states = collections.Counter()
    routes = collections.Counter()
    reasons = collections.Counter()
    formats = collections.Counter()
    methods = collections.Counter()
    cache_updates = []
    candidates = []
    read_payloads = 0
    reused_payloads = 0
    metadata_changes = 0
    same_timestamp_dirty = 0
    recent_timestamp_rows = 0
    eligible_count = 0
    for row in db.execute(query):
        (identifier, fmt, state, owner, updated, present, size, version, payload_version,
         old_fmt, old_state, old_owner, old_updated, old_present, old_size,
         old_method, old_route, old_reason, old_code, old_image, old_priority,
         stored_record, old_kind, old_version, old_payload_version,
         queued_id, queued_route, queued_reason, queued_priority) = row
        uncached = old_version is None
        dirty = uncached or version != old_version
        thin_changed = uncached or (fmt, state, owner, updated, present, size) != (
                       old_fmt, old_state, old_owner, old_updated, old_present, old_size)
        # Inclusive overlap is retained for timestamp-based observability. Exact
        # completeness comes from versioned triggers, including backdated writes.
        recent_timestamp_rows += bool(watermark and isinstance(updated, str) and updated >= watermark)
        payload_changed = (uncached or payload_version != old_payload_version or
                           present != old_present or size != old_size)
        if payload_changed:
            raw = db.execute('SELECT output_record FROM jobs WHERE id=?', (identifier,)).fetchone()[0]
            record, kind = slim_record(raw)
            read_payloads += bool(present)
        else:
            record = json.loads(stored_record) if stored_record else None
            kind = old_kind
            reused_payloads += bool(present)
        route, reason = _classify(fmt, state, owner, record, kind)
        method = record.get('conversion_method', 'unknown') if isinstance(record, dict) else 'no_valid_output_record'
        if not isinstance(method, str):
            method = 'invalid_method_metadata'
        score = priority(record) if isinstance(record, dict) else 0
        code_hash = record.get('code_sha256') if isinstance(record, dict) else None
        image_hash = record.get('image_sha256') if isinstance(record, dict) else None
        if not isinstance(code_hash, str):
            code_hash = None
        if not isinstance(image_hash, str):
            image_hash = None
        states[state] += 1
        totals['candidates_with_output_record'] += bool(present)
        totals['accepted'] += state == 'accepted'
        totals['worker_owned'] += owner is not None
        routes[route] += 1
        reasons[(route, reason)] += 1
        formats[(fmt, route)] += 1
        methods[(fmt, method, route)] += 1
        if dirty or thin_changed:
            metadata_changes += 1
            same_timestamp_dirty += bool(not uncached and dirty and updated == old_updated)
            cache_updates.append((identifier, fmt, state, owner, updated, present, size,
                                  method, route, reason, code_hash, image_hash, score,
                                  json.dumps(record, separators=(',', ':')) if record is not None else None,
                                  kind, version, payload_version, observed))
        if _eligible(state, owner, record, route):
            eligible_count += 1
            if dirty or thin_changed or queued_id is None or (queued_route, queued_reason, queued_priority) != (route, reason, score):
                candidates.append((identifier, code_hash, image_hash, score, route, reason,
                                   observed, state, version, payload_version))
    db.rollback()
    if _after_snapshot is not None:
        _after_snapshot()
    upsert_cache = '''INSERT INTO ''' + CACHE + ''' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
       ON CONFLICT(id) DO UPDATE SET format=excluded.format,state=excluded.state,
       worker_pid=excluded.worker_pid,job_updated_at=excluded.job_updated_at,
       payload_present=excluded.payload_present,payload_bytes=excluded.payload_bytes,
       method=excluded.method,route=excluded.route,reason=excluded.reason,
       code_hash=excluded.code_hash,image_hash=excluded.image_hash,priority=excluded.priority,
       routing_record=excluded.routing_record,record_kind=excluded.record_kind,
       seen_version=excluded.seen_version,seen_payload_version=excluded.seen_payload_version,
       observed_at=excluded.observed_at'''
    # Never clear the dirty version. A write after the read snapshot has a newer
    # version and remains visible even when this older cache snapshot is committed.
    for offset in range(0, len(cache_updates), 500):
        begin(db)
        db.executemany(upsert_cache, cache_updates[offset:offset + 500])
        commit(db)
    statement = '''INSERT INTO ''' + TABLE + '''
      (id,code_hash,image_hash,priority,route,reason,updated_at)
      SELECT ?,?,?,?,?,?,? WHERE EXISTS (
       SELECT 1 FROM jobs j JOIN ''' + DIRTY + ''' d ON d.id=j.id
       WHERE j.id=? AND j.state=? AND j.worker_pid IS NULL
       AND d.version=? AND d.payload_version=?)
      ON CONFLICT(id,code_hash,image_hash) DO UPDATE SET
      priority=excluded.priority,route=excluded.route,reason=excluded.reason,updated_at=excluded.updated_at'''
    upserted = 0
    for offset in range(0, len(candidates), 500):
        begin(db)
        for row in candidates[offset:offset + 500]:
            identifier, code_hash, image_hash, score, route, reason, at, state, version, payload_version = row
            upserted += db.execute(statement, (identifier, code_hash, image_hash, score, route,
                                              reason, at, identifier, state, version, payload_version)).rowcount
        commit(db)
    begin(db)
    retired = db.execute('''DELETE FROM ''' + TABLE + ''' AS q WHERE NOT EXISTS (
       SELECT 1 FROM jobs j JOIN ''' + DIRTY + ''' d ON d.id=j.id
       JOIN ''' + CACHE + ''' c ON c.id=j.id
       WHERE j.id=q.id AND j.worker_pid IS NULL
       AND j.state IN ('rendered','needs_quality_repair','harness_review_pending','harness_rendered','needs_fallback')
       AND d.version=c.seen_version AND d.payload_version=c.seen_payload_version
       AND c.code_hash=q.code_hash AND c.image_hash=q.image_hash
       AND c.route IN ('graph','vector','native','repair'))''').rowcount
    removed_cache = db.execute('DELETE FROM ' + CACHE + ' WHERE NOT EXISTS (SELECT 1 FROM jobs j WHERE j.id=' + CACHE + '.id)').rowcount
    db.execute('INSERT INTO ' + META + ' VALUES("verified_snapshot_at_utc",?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (observed,))
    commit(db)
    actual_queue = dict(db.execute('SELECT route,count(*) FROM ' + TABLE + ' GROUP BY route'))
    cache_count = db.execute('SELECT count(*) FROM ' + CACHE).fetchone()[0]
    db.close()
    for key in ('candidates_with_output_record', 'accepted', 'worker_owned'):
        totals[key] += 0
    report = {'schema_version': 2, 'observed_at_utc': observed, 'root': str(root),
              'expected_total': expected_total, 'totals': dict(totals),
              'states': dict(sorted(states.items())), 'routes': dict(sorted(routes.items())),
              'by_format_and_route': _summary(formats, ('format', 'route')),
              'by_method_and_route': _summary(methods, ('format', 'method', 'route')),
              'by_reason': _summary(reasons, ('route', 'reason')),
              'candidate_index': {'table': TABLE, 'snapshot_idle_valid_revisions': eligible_count,
                    'upserted_current_revisions': upserted, 'stale_revisions_removed': retired,
                    'current_rows_by_route': actual_queue},
              'incremental': {'journal': DIRTY, 'cache': CACHE, 'cache_rows': cache_count,
                    'thin_metadata_rows_scanned': total, 'changed_metadata_rows': metadata_changes,
                    'large_payloads_parsed': read_payloads, 'large_payloads_reused': reused_payloads,
                    'same_timestamp_dirty_rows': same_timestamp_dirty,
                    'rows_in_inclusive_timestamp_window': recent_timestamp_rows,
                    'deleted_cache_rows': removed_cache, 'inclusive_timestamp_watermark': watermark,
                    'exact_change_detection': 'Monotone dirty version and payload version in writer transaction; includes equal/backdated timestamps and ownership/state transitions.',
                    'dirty_versions_never_cleared': True},
              'policy': {'no_jobs_or_existing_queue_mutations': True,
                    'private_jobs_triggers_installed': list(TRIGGERS),
                    'no_quality_acceptance_by_inventory': True,
                    'all_input_jobs_accounted_for': sum(routes.values()) == expected_total,
                    'low_similarity_candidates_retained': True, 'worker_ownership_not_reset': True},
              'elapsed_seconds': round(time.monotonic() - started, 3), 'goal_complete': False}
    report['throughput'] = throughput(previous, report)
    temporary = path.with_name(path.name + '.%d.tmp' % os.getpid())
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)
    return report


def refresh(root=ROOT, expected_total=131904, _after_snapshot=None):
    # Serialize inventory producers; converter job writers remain independent.
    with (Path(root)/'conversion'/'auto_quality_inventory_v2.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _refresh(root,expected_total,_after_snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--expected-total', type=int, default=131904)
    args = parser.parse_args()
    print(json.dumps(refresh(args.root, args.expected_total), ensure_ascii=False))


if __name__ == '__main__':
    main()
