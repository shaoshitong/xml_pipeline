#!/usr/bin/env python3
"""Supervise only this collection's downloader/curators; never kill any process.
Wait for verified bulk+rap downloads, retry failed files, run both curators in
sequence, and write collection_done.json only after final report acceptance.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def load_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def owned_processes(script_name, root, run_name=None):
    """Match UID + exact script basename + exact --root (+run-name), on Linux."""
    output = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            argv = [x.decode(errors='replace') for x in (proc / 'cmdline').read_bytes().split(b'\0') if x]
            if not any(Path(x).name == script_name for x in argv) or '--root' not in argv:
                continue
            if Path(argv[argv.index('--root') + 1]).resolve() != root:
                continue
            actual_run = argv[argv.index('--run-name') + 1] if '--run-name' in argv else 'default'
            if run_name is not None and actual_run != run_name:
                continue
            output.append(int(proc.name))
        except (OSError, ValueError, IndexError):
            continue
    return sorted(output)


def process_io(pid):
    try:
        stats = dict(x.split(':', 1) for x in Path(f'/proc/{pid}/io').read_text().splitlines())
        return tuple(int(stats.get(x, '0').strip()) for x in ('rchar', 'wchar', 'read_bytes', 'write_bytes'))
    except (OSError, ValueError):
        return ()


def acquire_incremental_lock(state_dir, emit, poll_seconds):
    """Serialize the entire final pipeline against an incremental refresh."""
    handle = (state_dir / 'partial-refresh.lock').open('a+')
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            emit({'status': 'waiting_incremental_pipeline',
                  'action': 'preserve_existing_refresh_before_fresh_final_pass'})
            time.sleep(poll_seconds)


def tail_events(path, max_bytes=512 * 1024):
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            length = stream.tell()
            stream.seek(max(0, length - max_bytes))
            lines = stream.read().splitlines()
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        return events
    except OSError:
        return []


def download_state(root, run_name):
    folder = root / 'runs' / run_name
    manifest = load_json(folder / 'download_manifest.json', {})
    failures = load_json(folder / 'download_failures.json', [])
    files = manifest.get('files', [])
    complete = [x for x in files if x.get('status') in ('complete', 'already_complete')]
    planned = manifest.get('planned_files', 0)
    # Older periodic snapshots omit planned_files; inventory supplies the fixed count.
    if not planned:
        inventory = load_json(folder / 'download_inventory.json', [])
        planned = sum(len(x.get('files', [])) for x in inventory)
    events = tail_events(folder / 'download_progress.jsonl')
    progress = next((x for x in reversed(events) if x.get('event') == 'progress'), {})
    tree = next((x for x in reversed(events) if x.get('event') == 'tree_page'), {})
    completion = next((x for x in reversed(events) if x.get('event') == 'file_complete'), {})
    fingerprint = (progress.get('bytes_written_this_run', progress.get('bytes_this_run', 0)),
                   len(complete), tree.get('repo_id'), tree.get('files_discovered'),
                   completion.get('verified_at'))
    ready = bool(manifest.get('finished') and planned > 0 and len(complete) == planned and not failures
                 and all(x.get('status') in ('complete', 'already_complete') for x in files))
    return {'run_name': run_name, 'ready': ready, 'finished': bool(manifest.get('finished')),
            'planned_files': planned, 'completed_files': len(complete), 'failed_items': len(failures),
            'failed_file_items': sum(bool(x.get('path')) for x in failures),
            'discovery_failures': [x for x in failures if x.get('stage') == 'discovery'],
            'verified_bytes': sum(x.get('expected_size', 0) for x in complete),
            'progress_fingerprint': fingerprint, 'latest_progress': progress,
            'inventory_exists': (folder / 'download_inventory.json').is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--scripts-dir', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--runs', nargs='+', default=['bulk', 'rap'])
    parser.add_argument('--poll-seconds', type=int, default=30)
    parser.add_argument('--stall-seconds', type=int, default=600)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--medium-workers', type=int, default=2)
    parser.add_argument('--large-workers', type=int, default=2)
    parser.add_argument('--endpoint', choices=['https://huggingface.co', 'https://hf-mirror.com'], default='https://huggingface.co')
    args = parser.parse_args()
    if not 1 <= args.poll_seconds <= 60 or args.stall_seconds < 1:
        parser.error('poll must be 1-60s, stall must be positive')
    root = args.root.resolve()
    scripts = args.scripts_dir.resolve()
    sources = (args.sources or scripts / 'dataset_sources.json').resolve()
    state_dir = root / 'supervisor'
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = (state_dir / 'supervisor.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(json.dumps({'status': 'duplicate_supervisor_already_running', 'root': str(root)}), flush=True)
        return 2
    atomic_json(state_dir / 'owner.json', {'pid': os.getpid(), 'uid': os.getuid(), 'hostname': socket.gethostname(), 'root': str(root), 'started_at': now()})
    log = (state_dir / 'progress.jsonl').open('a', buffering=1)
    def emit(event):
        item = {'time': now(), 'supervisor_pid': os.getpid(), **event}
        log.write(json.dumps(item, ensure_ascii=False) + '\n')
        atomic_json(state_dir / 'status.json', item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    fingerprints = {}
    last_progress = {name: time.monotonic() for name in args.runs}
    launches = {}
    child_logs = []
    while True:
        snapshots = []
        for name in args.runs:
            snapshot = download_state(root, name)
            pids = owned_processes('download_hf.py', root, name)
            snapshot['owned_download_pids'] = pids
            fingerprint = snapshot['progress_fingerprint']
            if name not in fingerprints or fingerprint != fingerprints[name]:
                fingerprints[name] = fingerprint
                last_progress[name] = time.monotonic()
            stalled_seconds = time.monotonic() - last_progress[name]
            snapshot['seconds_without_measured_progress'] = round(stalled_seconds, 1)
            if snapshot['ready']:
                snapshots.append(snapshot)
                continue
            if stalled_seconds >= args.stall_seconds:
                emit({'status': 'stalled', 'stage': 'downloads', 'run_name': name,
                      'seconds_without_measured_progress': round(stalled_seconds, 1),
                      'owned_download_pids': pids, 'action': 'goal_attention_required_processes_and_data_preserved'})
                return 3
            if not pids and snapshot['inventory_exists']:
                if snapshot['discovery_failures']:
                    emit({'status': 'needs_attention', 'stage': 'discovery', 'run_name': name,
                          'failures': snapshot['discovery_failures'], 'action': 'goal_must_resolve_missing_repository_inventory'})
                    return 4
                previous = launches.get(name)
                if previous is not None:
                    previous.poll()  # reap only our own child
                # Exact run/root check above prevents duplicate collection downloaders.
                retry_flag = '--retry-failed' if snapshot['finished'] and snapshot['failed_file_items'] else '--resume-inventory'
                command = [args.python, str(scripts / 'download_hf.py'), '--root', str(root),
                           '--sources', str(sources), '--run-name', name, retry_flag,
                           '--workers', str(args.workers), '--medium-workers', str(args.medium_workers),
                           '--large-workers', str(args.large_workers),
                           '--stall-seconds', str(args.stall_seconds), '--endpoint', args.endpoint]
                child_log = (state_dir / (name + '-retries.log')).open('a')
                child_logs.append(child_log)
                launches[name] = subprocess.Popen(command, stdout=child_log, stderr=subprocess.STDOUT, env=os.environ.copy())
                emit({'status': 'retry_started', 'run_name': name, 'mode': retry_flag,
                      'pid': launches[name].pid, 'failed_files': snapshot['failed_file_items']})
            snapshots.append(snapshot)
        if snapshots and all(x['ready'] for x in snapshots):
            emit({'status': 'downloads_verified', 'runs': snapshots})
            break
        emit({'status': 'downloading', 'runs': snapshots})
        time.sleep(args.poll_seconds)

    priority = load_json(root / 'download_manifest.json', {})
    templates = load_json(root / 'raw' / 'jgraph--drawio-templates' / 'source_manifest.json', {})
    extra_assets = load_json(root / 'reports' / 'extra_assets.json', {})
    gates = {
        'priority_downloads': bool(priority.get('finished') and priority.get('completed_files') == priority.get('planned_files') and not priority.get('failed_items')),
        'official_templates': bool(templates.get('finished') and not templates.get('failed_files')),
        'extra_assets': bool(len(extra_assets.get('assets', [])) == 2 and all(x.get('status') == 'complete' and x.get('archive_integrity_checked') for x in extra_assets.get('assets', []))),
    }
    if not all(gates.values()):
        emit({'status': 'needs_attention', 'stage': 'auxiliary_download_verification', 'gates': gates, 'action': 'goal_must_resolve_missing_assets_before_curation'})
        return 7

    # A refresh can advance from the main curator to archives or catalog checks
    # while downloads finish. Waiting only for an identical script would allow
    # the final main pass to rewrite inputs under that refresh's later stages.
    # The refresh uses this same root-local flock for its entire pipeline.
    incremental_lock = acquire_incremental_lock(state_dir, emit, args.poll_seconds)

    def curation_command(script_name):
        command = [args.python, str(scripts / script_name), '--root', str(root)]
        if script_name == 'curate_derived.py':command.extend(['--retry-failed','--rebuild-native'])
        if script_name == 'curate_native_sources.py':command.append('--retry-failed')
        return command

    for script_name, report_name in [('curate_pairs.py', 'summary.json'),
                                     ('curate_archives.py', 'archive_summary.json'),
                                     ('curate_derived.py', 'derived_summary.json'),
                                     ('curate_native_sources.py', 'native_sources_summary.json'),
                                     ('finalize_catalog.py', 'catalog_summary.json'),
                                     ('audit_provenance_qc.py', 'provenance_qc.json'),
                                     ('audit_catalog_content.py', 'content_audit.json')]:
        # Wait for this collection's existing curator, never touch other tasks.
        pids = owned_processes(script_name, root)
        child = None
        started = time.time()
        if not pids:
            child_log = (state_dir / (script_name + '.log')).open('a')
            child_logs.append(child_log)
            child = subprocess.Popen(curation_command(script_name),
                                     stdout=child_log, stderr=subprocess.STDOUT, env=os.environ.copy())
            pids = [child.pid]
            emit({'status': 'curation_started', 'script': script_name, 'pid': child.pid})
        else:
            emit({'status': 'waiting_existing_owned_curator', 'script': script_name, 'pids': pids})
        previous = None
        last_io = time.monotonic()
        while True:
            if child is not None:
                exit_code = child.poll()
                alive = [] if exit_code is not None else [child.pid]
            else:
                alive = owned_processes(script_name, root)
                exit_code = None
            if not alive:
                if child is None:
                    # An earlier incremental run may have started before the last
                    # download finished. Always perform a fresh complete pass.
                    child_log = (state_dir / (script_name + '.log')).open('a')
                    child_logs.append(child_log)
                    started = time.time()
                    child = subprocess.Popen(curation_command(script_name),
                                             stdout=child_log, stderr=subprocess.STDOUT, env=os.environ.copy())
                    previous = None; last_io = time.monotonic()
                    emit({'status': 'curation_started_after_incremental_run', 'script': script_name, 'pid': child.pid})
                    continue
                report = load_json(root / 'reports' / report_name, {})
                errors = {key: value.get('error') for key, value in report.get('sources', {}).items() if value.get('error')}
                fresh = (root / 'reports' / report_name).exists() and (root / 'reports' / report_name).stat().st_mtime >= started - 2
                audit_bad = script_name in ('audit_catalog_content.py','audit_provenance_qc.py') and not report.get('ok')
                if script_name == 'curate_native_sources.py':audit_bad=not report.get('processed_all_eligible_pages')
                if exit_code not in (0, None) or not report.get('finished_at') or not fresh or errors or audit_bad:
                    emit({'status': 'curation_failed', 'script': script_name, 'exit_code': exit_code,
                          'report_fresh': fresh, 'source_errors': errors, 'action': 'goal_attention_required'})
                    return 5
                emit({'status': 'curation_verified', 'script': script_name, 'report': str(root / 'reports' / report_name)})
                break
            fingerprint = tuple((pid, process_io(pid)) for pid in alive)
            if fingerprint != previous:
                previous = fingerprint
                last_io = time.monotonic()
            if time.monotonic() - last_io >= args.stall_seconds:
                emit({'status': 'stalled', 'stage': 'curation', 'script': script_name, 'owned_pids': alive,
                      'action': 'goal_attention_required_processes_and_data_preserved'})
                return 6
            emit({'status': 'curating', 'script': script_name, 'owned_pids': alive,
                  'seconds_without_io_progress': round(time.monotonic() - last_io, 1)})
            time.sleep(args.poll_seconds)
    pairs_report = load_json(root / 'reports' / 'summary.json', {})
    archives_report = load_json(root / 'reports' / 'archive_summary.json', {})
    derived_report = load_json(root / 'reports' / 'derived_summary.json', {})
    catalog_report = load_json(root / 'reports' / 'catalog_summary.json', {})
    content_report = load_json(root / 'reports' / 'content_audit.json', {})
    provenance_report = load_json(root / 'reports' / 'provenance_qc.json', {})
    native_report = load_json(root / 'reports' / 'native_sources_summary.json', {})
    final = {'finished_at': now(), 'status': 'complete', 'root': str(root),
             'runs': [download_state(root, name) for name in args.runs],
             'pair_sources': pairs_report.get('sources', {}),
             'archive_sources': archives_report.get('sources', {}),
             'archive_paired_image_code': archives_report.get('paired_image_code'),
             'derived_pairs': derived_report.get('derived_pairs'),
             'native_source_pages_accepted': native_report.get('accepted_pairs'),
             'catalogs': catalog_report.get('groups', {}),
             'content_hash_audit': content_report,
             'provenance_audit': {'ok':provenance_report.get('ok'),'critical_issues':provenance_report.get('critical_issues'),'issues':provenance_report.get('issues'),'cross_kind':provenance_report.get('cross_kind')},
             'additional_download_gates': gates,
             'raw_auxiliary_sources': ['Presto-Design/svg_basic_benchmark_v0: generic SVG feature cases', 'ahazimeh/slide2svg: raster-dominant slide wrappers', 'jgraph/drawio-diagrams: rejected or unrenderable pages stay auxiliary; accepted target pages are native-code rendered pairs', 'DrawAI/CraftBench: image/task auxiliary data without matching editable gold'],
             'validation': 'All selected downloads complete with file hashes; all curation and catalog stages exited successfully with fresh reports. Provided and source-rendered pairs are counted separately. Structural completeness does not imply every provided source code was executed/rendered.'}
    atomic_json(root / 'collection_done.json', final)
    emit({'status': 'complete', 'collection_done': str(root / 'collection_done.json')})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
