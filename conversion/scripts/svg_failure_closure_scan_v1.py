"""Finite, read-only scan of every current direct-SVG source-failure revision.

Each source capture is isolated behind the tested process-tree deadline helper.
Only sidecars/proposals are written. This script has no outcome publication API.
"""
import argparse
import collections
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time
import uuid

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
sys.path.insert(0, str(W / 'scripts'))
STOP = False


def request_stop(*_):
    global STOP
    STOP = True


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def atomic(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(canonical(value))
    temporary.replace(path)


def source_scope(db, identifier):
    row = db.execute('select category,format,source,input_record,output_record from jobs where id=?', (identifier,)).fetchone()
    category, fmt, source_name, raw_source, raw_candidate = row
    source = json.loads(raw_source)
    candidate = json.loads(raw_candidate)
    assert category in ('scientific_diagram', 'poster') and fmt == 'svg'
    assert source['pair_sha256'] == candidate['id'] == candidate['source_pair_sha256'] == identifier
    assert category == source['category'] == candidate['category']
    assert fmt == source['format'] == candidate['source_format']
    assert source_name == source['source'] == candidate['source']


def case(identifier, work):
    import svg_failure_closure_v1 as collector
    config = collector.configuration(R)
    db = sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30, isolation_level=None)
    try:
        source_scope(db, identifier)
        result = collector.prepare(db, identifier, config, Path(work) / 'evidence')
        if result['proposal']:
            result['scan_end_revalidation'] = collector.revalidate(db, result, config, check_files=True)
        # Keep the actual immutable certificate intact; scanner observations are separate.
        atomic(Path(work) / 'case_result.json', result)
    finally:
        db.close()


def isolated_case(item):
    from initial_conversion_process_v1 import run
    identifier, directory, timeout = item
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONPATH=str(R / 'env'))
    result = run([sys.executable, str(Path(__file__).resolve()), '--case', identifier, '--work', str(directory)], directory, timeout, env)
    atomic(directory / 'capture_isolation.json', result)
    output = directory / 'case_result.json'
    if not result.get('cleanup_complete') or result.get('deadline_exceeded') or not result.get('ok') or not output.exists():
        return {'id': identifier, 'state': 'pending_capture_resource_or_deadline', 'work': str(directory), 'isolation': result, 'proposal': False}
    evidence = json.loads(output.read_text())
    current = evidence.get('scan_end_revalidation', {}).get('current', False)
    return {'id': identifier, 'state': 'current_readonly_proposal' if evidence.get('proposal') and current else 'retain_pending',
            'proposal': bool(evidence.get('proposal') and current), 'work': str(directory),
            'certificate_sha256': evidence.get('certificate_sha256'), 'catalog_sha256': evidence.get('catalog_sha256'),
            'deferred_reasons': evidence.get('deferred_reasons', []), 'error': evidence.get('error'),
            'cleanup_complete': result['cleanup_complete'], 'model_calls': 0}


def select_ids(db):
    assert dict(db.execute('select category,count(*) from jobs group by category')) == {'scientific_diagram': 107161, 'poster': 24743}
    return [row[0] for row in db.execute('''select j.id from jobs j join processing_outcomes_v2 o on o.id=j.id
      where j.format='svg' and o.status='pending' and j.worker_pid is null
      and j.state in ('rendered','needs_quality_repair','harness_review_pending','harness_rendered')
      and j.output_record is not null and exists(select 1 from auto_quality_audits_v1 q
        where q.id=j.id and q.code_hash=json_extract(j.output_record,'$.code_sha256')
        and q.image_hash=json_extract(j.output_record,'$.image_sha256') and q.state='repair_required'
        and json_extract(q.record,'$.checks.source.ok')=0
        and json_array_length(json_extract(q.record,'$.checks.source.failures'))>0)
      order by j.id''').fetchall()]


def main(args):
    if args.case:
        return case(args.case, args.work)
    assert 1 <= args.workers <= 2 and 30 <= args.timeout <= 600 and args.limit >= 0
    import svg_failure_closure_v1 as collector
    assert hashlib.sha256(Path(collector.__file__).read_bytes()).hexdigest() == 'f7a0aca39833513aa660a7b3bf39639649aeae01069436dac23b759ec8b44e60'
    config = collector.configuration(R)
    db = sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30, isolation_level=None)
    try:
        identifiers = select_ids(db)
    finally:
        db.close()
    if args.limit:
        identifiers = identifiers[:args.limit]
    scope = W / 'prototype/svg_failure_closure_v1/scans' / uuid.uuid4().hex
    scope.mkdir(parents=True, exist_ok=False)
    manifest = {'at': collector.now(), 'scope_inputs': 131904, 'selected_ids': identifiers, 'selected_count': len(identifiers),
                'selection_scope': 'All current direct-SVG pending revisions with exact-pair recorded source failures.',
                'limit': args.limit, 'finite': True, 'workers': args.workers, 'timeout_seconds': args.timeout,
                'catalog_sha256': config['catalog_sha256'], 'read_only_database': True, 'publish_available': False,
                'source_images_or_XML_downloaded_locally': False, 'model_calls': 0, 'goal_complete': False}
    atomic(scope / 'manifest.json', manifest)
    signal.signal(signal.SIGUSR1, request_stop)
    rows = []
    counts = collections.Counter()
    started = time.monotonic()
    context = multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=context) as pool:
        iterator = iter(identifiers)
        pending = {}
        for _ in range(args.workers):
            identifier = next(iterator, None)
            if identifier:
                future = pool.submit(isolated_case, (identifier, str(scope / identifier), args.timeout))
                pending[future] = identifier
        while pending:
            completed, _ = concurrent.futures.wait(pending, timeout=1, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in completed:
                identifier = pending.pop(future)
                try:
                    row = future.result()
                except Exception as error:
                    row = {'id': identifier, 'state': 'pending_scanner_error', 'proposal': False, 'error': repr(error)}
                rows.append(row)
                counts[row['state']] += 1
                atomic(scope / 'runtime.json', {'pid': os.getpid(), 'at': collector.now(), 'completed': len(rows), 'selected': len(identifiers),
                        'counts': dict(counts), 'scope': str(scope), 'drain_requested': STOP, 'model_calls': 0, 'read_only': True})
                print(json.dumps({'id': identifier, 'state': row['state'], 'completed': len(rows), 'selected': len(identifiers)}), flush=True)
                if not STOP:
                    following = next(iterator, None)
                    if following:
                        future = pool.submit(isolated_case, (following, str(scope / following), args.timeout))
                        pending[future] = following
    report = {**manifest, 'scope': str(scope), 'completed': len(rows), 'counts': dict(counts), 'records': rows,
              'seconds': time.monotonic() - started, 'drained': STOP, 'all_selected_examined': len(rows) == len(identifiers)}
    atomic(scope / 'report.json', report)
    atomic(W / ('svg_failure_closure_scan_v1_smoke.json' if args.limit else 'svg_failure_closure_scan_v1_latest.json'), report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('selected_ids', 'records')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--case')
    parser.add_argument('--work')
    main(parser.parse_args())
