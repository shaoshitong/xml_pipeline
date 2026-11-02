"""Snapshot all conversion jobs and queue current, idle revisions for batch QA.

This module does not accept results or mutate the jobs/Harness/format queues.  Its
new table is a disposable current-candidate index; authoritative job history stays
in the existing conversion database.  All runtime output belongs on HKUST.
"""
import argparse
import collections
import datetime
import json
import math
import os
import re
import sqlite3
import time
from pathlib import Path

from durable_sqlite import begin, commit

ROOT = Path('/backup/shaoshitong/img2code_20261029')
TABLE = 'auto_quality_candidates_v1'
IDLE_STATES = frozenset(('rendered', 'needs_quality_repair',
                         'harness_review_pending', 'harness_rendered',
                         'needs_fallback'))
HASH = re.compile(r'^[0-9a-f]{64}$')
VECTOR_FORMATS = frozenset(('svg', 'python', 'plantuml', 'html'))


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _coverage_ok(record):
    coverage = record.get('source_coverage') or {}
    if not isinstance(coverage, dict):
        return False
    return coverage.get('ok') is True or coverage.get('status') in (
        'node_edge_text_match', 'complete', 'verified')


def priority(record):
    """Prioritize inexpensive, well-instrumented profiles, never exclude low SSIM."""
    value = 0
    if _coverage_ok(record):
        value += 40
    connectivity = record.get('connectivity') or {}
    if isinstance(connectivity, dict) and connectivity.get('complete') is True:
        value += 40
    if record.get('native_embedded_fonts') or record.get('fonts'):
        value += 10
    if record.get('edges') is not None and record.get('edges') == record.get('bound_edges'):
        value += 10
    metrics = record.get('metrics') or {}
    if not isinstance(metrics, dict):
        metrics = {}
    score = metrics.get('original_reference_ssim_512',
                        metrics.get('reference_ssim_512'))
    if isinstance(score, (int, float)) and math.isfinite(score):
        value += round(max(0.0, min(1.0, score)) * 20)
    return value


def classify(fmt, state, worker_pid, record, malformed=False):
    """Return (route, reason); acceptance is always an upstream explicit state."""
    if state == 'accepted':
        return 'accepted', 'already_accepted'
    # A worker PID is an ownership claim, not proof that it died.  Never turn a
    # stale-looking claim into a free slot; separate recovery must prove exit.
    if worker_pid is not None or state not in IDLE_STATES:
        if state.startswith('queued') or (record is None and state.endswith('_source_rendered')):
            return 'wait', 'conversion_payload_not_ready'
        return 'defer', 'worker_owned_or_nonidle_state'
    if malformed:
        return 'repair', 'malformed_output_record'
    if record is None:
        if state == 'needs_fallback':
            return 'repair', 'conversion_failed_without_candidate'
        return 'wait', 'conversion_payload_not_ready'
    if not isinstance(record, dict):
        return 'repair', 'output_record_is_not_object'
    if not HASH.fullmatch(str(record.get('code_sha256', ''))) or not HASH.fullmatch(str(record.get('image_sha256', ''))):
        return 'repair', 'candidate_revision_hash_missing_or_invalid'
    if state == 'needs_fallback':
        return 'repair', 'conversion_failed_with_candidate_retained'
    source_format = record.get('source_format') or fmt
    if not isinstance(source_format, str):
        return 'repair', 'candidate_source_format_invalid'
    if source_format == 'mermaid':
        return 'graph', 'mermaid_source_graph_profile'
    if source_format == 'tikz':
        connectivity = record.get('connectivity') or {}
        if isinstance(connectivity, dict) and connectivity.get('complete') is True and record.get('conversion_method') == 'source_named_tikz_nodes_and_native_bound_paths_v1':
            return 'graph', 'literal_tikz_source_graph_profile'
        return 'repair', 'tikz_source_graph_profile_unresolved'
    if source_format in VECTOR_FORMATS:
        return 'vector', source_format + '_source_vector_profile'
    if source_format in ('drawio', 'xml'):
        return 'native', 'original_native_graph_profile'
    return 'repair', 'source_format_profile_unavailable'


def _summary(counter, labels):
    return [dict(zip(labels, key), count=value)
            for key, value in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def throughput(previous, snapshot):
    """Net corpus growth, not events or inflight work misreported as completions."""
    if not previous:
        return {'available': False, 'reason': 'first_snapshot'}
    try:
        before = datetime.datetime.fromisoformat(previous['observed_at_utc'])
        after = datetime.datetime.fromisoformat(snapshot['observed_at_utc'])
        seconds = (after - before).total_seconds()
        if seconds <= 0:
            raise ValueError('nonpositive interval')
        old = previous['totals']
        new = snapshot['totals']
        native_delta = new['candidates_with_output_record'] - old['candidates_with_output_record']
        accepted_delta = new['accepted'] - old['accepted']
    except (KeyError, TypeError, ValueError):
        return {'available': False, 'reason': 'previous_snapshot_incompatible'}
    return {'available': True, 'interval_seconds': round(seconds, 3),
            'baseline_observed_at_utc': previous['observed_at_utc'],
            'native_candidate_net_change': native_delta,
            'accepted_net_change': accepted_delta,
            'native_candidate_net_pairs_per_hour': round(native_delta * 3600 / seconds, 3),
            'accepted_net_pairs_per_hour': round(accepted_delta * 3600 / seconds, 3),
            'interpretation': 'Net difference of authoritative corpus counts between snapshots; not conversion attempts, inflight work, model scores, or per-stage service rate.'}


def initialize(db):
    begin(db)
    db.execute('CREATE TABLE IF NOT EXISTS ' + TABLE + ''' (
      id TEXT NOT NULL,code_hash TEXT NOT NULL,image_hash TEXT NOT NULL,
      priority INTEGER NOT NULL,route TEXT NOT NULL,reason TEXT NOT NULL,
      updated_at TEXT NOT NULL,PRIMARY KEY(id,code_hash,image_hash))''')
    db.execute('CREATE INDEX IF NOT EXISTS auto_quality_candidates_v1_route_priority ON '
               + TABLE + '(route,priority DESC,id)')
    commit(db)


def refresh(root=ROOT, expected_total=131904):
    started = time.monotonic()
    root = Path(root)
    work = root / 'conversion'
    path = work / 'auto_quality_inventory.json'
    previous = None
    if path.exists():
        try:
            previous = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    db = sqlite3.connect(work / 'jobs.sqlite', timeout=2)
    db.execute('PRAGMA busy_timeout=2000')
    # One read transaction produces a consistent corpus snapshot.  It is released
    # before any writer transaction, so conversion workers remain unblocked.
    db.execute('BEGIN')
    total_jobs = db.execute('SELECT count(*) FROM jobs').fetchone()[0]
    if total_jobs != expected_total:
        db.rollback()
        db.close()
        raise AssertionError('Scope differs from expected total: %d != %d' % (total_jobs, expected_total))
    rows = db.execute('SELECT id,format,state,worker_pid,output_record FROM jobs')
    observed = utcnow()
    totals = collections.Counter(total_jobs=total_jobs)
    states = collections.Counter()
    routes = collections.Counter()
    reasons = collections.Counter()
    formats = collections.Counter()
    methods = collections.Counter()
    eligible = []
    for identifier, fmt, state, owner, raw in rows:
        states[state] += 1
        record = None
        malformed = False
        if raw is not None:
            totals['candidates_with_output_record'] += 1
            try:
                record = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                malformed = True
        route, reason = classify(fmt, state, owner, record, malformed)
        routes[route] += 1
        reasons[(route, reason)] += 1
        formats[(fmt, route)] += 1
        method = record.get('conversion_method', 'unknown') if isinstance(record, dict) else 'no_valid_output_record'
        if not isinstance(method, str):
            method = 'invalid_method_metadata'
        methods[(fmt, method, route)] += 1
        if state == 'accepted':
            totals['accepted'] += 1
        if owner is not None:
            totals['worker_owned'] += 1
        if (route in ('graph', 'vector', 'native', 'repair') and isinstance(record, dict)
                and state in IDLE_STATES and owner is None
                and HASH.fullmatch(str(record.get('code_sha256', '')))
                and HASH.fullmatch(str(record.get('image_sha256', '')))):
            eligible.append((identifier, record['code_sha256'], record['image_sha256'],
                             priority(record), route, reason, observed, state))
    db.rollback()
    # Preserve zero counts so snapshot throughput remains well-defined.
    for key in ('candidates_with_output_record', 'accepted', 'worker_owned'):
        totals[key] += 0
    initialize(db)
    inserted = 0
    # Each conditional INSERT compares the exact XML/PNG revision.  A conversion
    # that changes after the read snapshot will be seen on the next invocation.
    statement = '''INSERT INTO ''' + TABLE + '''
      (id,code_hash,image_hash,priority,route,reason,updated_at)
      SELECT ?,?,?,?,?,?,? WHERE EXISTS (
       SELECT 1 FROM jobs WHERE id=? AND state=? AND worker_pid IS NULL
       AND CASE WHEN json_valid(output_record) THEN json_extract(output_record,'$.code_sha256') END=?
       AND CASE WHEN json_valid(output_record) THEN json_extract(output_record,'$.image_sha256') END=?)
      ON CONFLICT(id,code_hash,image_hash) DO UPDATE SET
      priority=excluded.priority,route=excluded.route,reason=excluded.reason,updated_at=excluded.updated_at'''
    for offset in range(0, len(eligible), 500):
        begin(db)
        for row in eligible[offset:offset + 500]:
            identifier, code_hash, image_hash, score, route, reason, at, state = row
            inserted += db.execute(statement, (identifier, code_hash, image_hash, score, route, reason,
                                               at, identifier, state, code_hash, image_hash)).rowcount
        commit(db)
    begin(db)
    # This table describes current work, not archival history.  Audit outcomes
    # belong in the verifier's separate revision-keyed audit table.
    retired = db.execute('''DELETE FROM ''' + TABLE + ''' AS q WHERE NOT EXISTS (
      SELECT 1 FROM jobs AS j WHERE j.id=q.id AND j.worker_pid IS NULL
      AND j.state IN ('rendered','needs_quality_repair','harness_review_pending','harness_rendered','needs_fallback')
      AND CASE WHEN json_valid(j.output_record) THEN json_extract(j.output_record,'$.code_sha256') END=q.code_hash
      AND CASE WHEN json_valid(j.output_record) THEN json_extract(j.output_record,'$.image_sha256') END=q.image_hash)''').rowcount
    commit(db)
    actual_queue = dict(db.execute('SELECT route,count(*) FROM ' + TABLE + ' GROUP BY route'))
    db.close()
    report = {'schema_version': 1, 'observed_at_utc': observed,
              'root': str(root), 'expected_total': expected_total, 'totals': dict(totals),
              'states': dict(sorted(states.items())), 'routes': dict(sorted(routes.items())),
              'by_format_and_route': _summary(formats, ('format', 'route')),
              'by_method_and_route': _summary(methods, ('format', 'method', 'route')),
              'by_reason': _summary(reasons, ('route', 'reason')),
              'candidate_index': {'table': TABLE,
                                  'snapshot_idle_valid_revisions': len(eligible),
                                  'upserted_current_revisions': inserted,
                                  'stale_revisions_removed': retired,
                                  'current_rows_by_route': actual_queue},
              'policy': {'no_jobs_or_existing_queue_mutations': True,
                         'no_quality_acceptance_by_inventory': True,
                         'all_input_jobs_accounted_for': sum(routes.values()) == expected_total,
                         'low_similarity_candidates_retained': True,
                         'worker_ownership_not_reset': True},
              'elapsed_seconds': round(time.monotonic() - started, 3),
              'goal_complete': False}
    report['throughput'] = throughput(previous, report)
    temporary = path.with_name(path.name + '.%d.tmp' % os.getpid())
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--expected-total', type=int, default=131904)
    args = parser.parse_args()
    report = refresh(args.root, args.expected_total)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
