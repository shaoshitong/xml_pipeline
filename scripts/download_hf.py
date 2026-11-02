#!/usr/bin/env python3
"""Download public img2code datasets directly on a destination server.

Only requests is required. No Hugging Face token is read or sent.
Example: python download_hf.py --sources dataset_sources.json --root /data/.../img2code
"""
from __future__ import annotations
import argparse
import fcntl
from contextlib import nullcontext
from collections import defaultdict, deque
import concurrent.futures as futures
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlparse
import requests

API = 'https://huggingface.co'
METADATA = re.compile(r'(^|/)(readme[^/]*|licen[cs]e[^/]*|copying[^/]*|notice[^/]*|dataset[_-]summary\.json|manifest\.json|sha256sums)$', re.I)
HF_IDS = {
    'sxy1620348809/VCG-Bench': 'all_data',
    'MiliLab/Omni-I2C': 'all_data',
    'ahazimeh/slide2svg': 'all_data',
    'yashengsun/SciDiagramRevision': 'all_data',
    'Baustex/drawio-to-xml': 'all_data',
    'Baustex/BrokenXML-and-Image-To-drawio': 'all_data',
    'miracle10/DwT_drawio': 'all_data',
    'nllg/DaTikZ-V4': 'all_data',
    'VincentHancoder/RAP': 'rap',
    'nllg/datikz': 'all_data',
    'nllg/datikz-v3': 'all_data',
    'nllg/DaEdiTikZ': 'all_data',
    'nllg/DaEdiTikZ-Bench': 'all_data',
    'Presto-Design/svg_basic_benchmark_v0': 'all_data',
    'Y36521478Y/omnidiagram_train_sft': 'omni',
    'Y36521478Y/omnidiagram_test': 'omni',
    'QijiaHe/VFIG-Data': 'all_data',
    'QijiaHe/VFIG-Bench': 'all_data',
    'DocTron-Hub/VinciCoder-1.6M-SFT': 'vinci_sft',
    'DocTron-Hub/VinciCoder-42k-RL': 'vinci_rl',
    'ChartMimic/ChartMimic': 'chartmimic',
    'TencentARC/Plot2Code': 'all_data',
    'CSU-JPG/Chart2Code': 'csu',
    'allenai/CoSyn-400K': 'cosyn',
    'starvector/svg-diagrams': 'all_data',
    'zjj1233/RealChart2Code': 'realchart',
    'caopu/DrawAI-Bench-Lite': 'auxiliary',
    'BleachNick/CraftBench': 'auxiliary',
}
VINCI_SFT = {
    'chart2code_1.parquet', 'chart2code_2.parquet', 'chart2code_refine.parquet',
    'plot2code_diagram.parquet', 'plot2code_mmd.parquet',
    'plot2code_graphic.parquet', 'img2svg_1.parquet', 'img2svg_refine.parquet',
}
DATA_SUFFIXES = ('.parquet', '.json', '.jsonl', '.csv', '.tsv', '.zip', '.tar.gz', '.tgz',
                 '.tar', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.xml', '.drawio',
                 '.py', '.r', '.txt', '.tex', '.mmd', '.puml', '.xlsx', '.xls', '.pdf',
                 '.otf', '.ttf', '.woff', '.woff2', '.js', '.html', '.css', '.yaml', '.yml')


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def api_json(session, path):
    """Bound retries without disclosing signed download URLs in error records."""
    url = path if path.startswith('https:') else API + path
    last = None
    for attempt in range(5):
        try:
            response = session.get(url, timeout=(20, 120))
            response.raise_for_status()
            return response.json(), response
        except (requests.RequestException, ValueError) as exc:
            last = type(exc).__name__
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                last += ':' + str(exc.response.status_code)
                if exc.response.status_code in (400, 401, 403, 404):
                    break
            time.sleep(min(2 ** attempt, 15))
    raise RuntimeError('public HF API failed: ' + str(last))


def list_tree(session, repo, revision, progress=None):
    url = f'{API}/api/datasets/{quote(repo, safe="/")}/tree/{revision}?recursive=true&limit=1000'
    entries, seen = [], set()
    while url:
        if url in seen:
            raise RuntimeError('tree pagination loop')
        seen.add(url)
        try:
            data, response = api_json(session, url)
        except RuntimeError as exc:
            if 'HTTPError:400' in str(exc) and 'limit=1000' in url:
                url = url.replace('limit=1000', 'limit=100')
                continue
            raise
        if not isinstance(data, list):
            raise RuntimeError('HF tree is not a list')
        entries.extend(item for item in data if item.get('type') == 'file')
        if progress:
            progress({'event': 'tree_page', 'repo_id': repo, 'page': len(seen),
                      'files_discovered': len(entries), 'last_path': data[-1].get('path') if data else None})
        nxt = response.links.get('next', {}).get('url')
        if nxt and urlparse(urljoin(url, nxt)).netloc != 'huggingface.co':
            raise RuntimeError('unexpected pagination host')
        url = urljoin(url, nxt) if nxt else None
    return entries


def selected_paths(repo, entries):
    """Keep source assets plus attribution, with explicit domain selection."""
    mode = HF_IDS[repo]
    candidates = []
    for item in entries:
        p = item['path']
        lower, name = p.lower(), Path(p).name.lower()
        if '..' in Path(p).parts or Path(p).is_absolute():
            continue
        if METADATA.search(p):
            candidates.append(item)
            continue
        if name == '.gitattributes':
            candidates.append(item)
            continue
        if any(x in lower for x in ('web2html', 'checkpoint', '.safetensors', '.bin', '.pt', '.pth', 'optimizer')):
            continue
        if mode == 'vinci_sft':
            keep = name in VINCI_SFT
        elif mode == 'vinci_rl':
            keep = name == 'chart2code.parquet'
        elif mode == 'omni':
            keep = name.startswith('dia2code_') and name.endswith('.parquet')
        elif mode == 'chartmimic':
            keep = name == 'dataset-iclr.tar.gz'
        elif mode == 'cosyn':
            keep = bool(re.search(r'(^|[/_\-])(chart|diagram|svg|graphic)([/_\-.]|$)', lower)) and lower.endswith(DATA_SUFFIXES)
        elif mode == 'rap':
            keep = (lower.startswith(('posters/', 'templates/', 'annotations/')) and lower.endswith(DATA_SUFFIXES)) or name in ('manifest.tsv', 'lowres_restored.txt')
        elif mode == 'realchart':
            keep = name.startswith('benchmark_data.tar.gz.') or name == 'benchmark_data.tar.gz'
        else:
            keep = lower.endswith(DATA_SUFFIXES)
            # Evaluation outputs / model generations are not source data.
            if any(re.search(r'(^|/)' + term + r'([^/]*)(/|$)', lower) for term in ('results', 'predictions', 'model_outputs', 'outputs')):
                keep = False
            if mode == 'csu' and (name in ('asset_audit_report.json', 'upload_to_hf.py') or lower.startswith('assets/')):
                keep = False
        if keep:
            candidates.append(item)
    if mode == 'omni':
        # Whole parquet and numbered parts coexist for some languages.
        # Prefer complete family of parts; global row dedup occurs during cleaning.
        families = {re.sub(r'_part\d+(?=\.parquet$)', '', x['path'])
                    for x in candidates if re.search(r'_part\d+\.parquet$', x['path'])}
        candidates = [x for x in candidates if x['path'] not in families]
    return sorted(candidates, key=lambda x: x['path'])


def medium_round_robin(tasks):
    """Offer one medium file per repository per round, prioritizing schema samples."""
    grouped = defaultdict(list)
    for task in tasks:
        grouped[task['repo_id']].append(task)
    def priority(repo):
        ordered = ('qijiahe/vfig-bench', 'qijiahe/vfig-data', 'chartmimic/chartmimic',
                   'nllg/datikz-v4', 'y36521478y/omnidiagram', 'allenai/cosyn')
        lower = repo.lower()
        return (next((i for i, prefix in enumerate(ordered) if lower.startswith(prefix)), len(ordered)), repo)
    def asset_priority(task):
        p=task['path'].lower()
        if p.startswith('annotations/') or 'manifest' in Path(p).name:return (0,task['expected_size'],p)
        if task['repo_id']=='VincentHancoder/RAP' and p.startswith('templates/'):
            return (1,task['expected_size'],p)
        return (2,task['expected_size'],p)
    queues = {repo: deque(sorted(items, key=asset_priority))
              for repo, items in grouped.items()}
    repos = sorted(queues, key=priority)
    result = []
    while repos:
        for repo in repos:
            result.append(queues[repo].popleft())
        repos = [repo for repo in repos if queues[repo]]
    return result


class WorkerSessions:
    def __init__(self, user_agent='img2code-dataset-collector/1.0'):
        self.local = threading.local()
        self.lock = threading.Lock()
        self.sessions = []
        self.user_agent = user_agent

    def get(self, route_key='primary_env', *, trust_env=True, proxies=None):
        # Configuration is part of the key: no existing Session is ever repointed.
        configuration = (route_key, bool(trust_env), tuple(sorted((proxies or {}).items())))
        cache = getattr(self.local, 'cache', None)
        if cache is None:
            cache = self.local.cache = {}
        if configuration not in cache:
            session = requests.Session()
            session.trust_env = trust_env
            session.headers['User-Agent'] = self.user_agent
            if proxies:
                session.proxies = dict(proxies)
            cache[configuration] = session
            with self.lock:
                self.sessions.append(session)
        return cache[configuration]

    def close(self):
        # Caller guarantees no in-flight workers remain.
        with self.lock:
            sessions, self.sessions = self.sessions, []
        for session in sessions:
            session.close()

    def preferred_route(self, fallback_enabled):
        # A successful route is worker-local, just like its requests.Session.
        # Do not pay two dead-primary timeouts again for every small poster.
        return getattr(self.local, 'verified_route', 'primary_env') if fallback_enabled else 'primary_env'

    def verified_route(self, route):
        self.local.verified_route = route

class DownloadRun:
    def __init__(self, root, run_name="default", large_workers=4, stall_seconds=600, download_base=API, fallback_proxy=""):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.stall_seconds = stall_seconds
        self.download_base = download_base.rstrip("/")
        self.fallback_proxy = fallback_proxy.strip()
        self.worker_sessions = WorkerSessions()
        self.state_root = self.root / "runs" / run_name
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.run_lock = (self.state_root / "download.lock").open("a+")
        try:
            fcntl.flock(self.run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.run_lock.close()
            raise RuntimeError("another downloader already holds this run lock")
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.large = threading.Semaphore(large_workers)
        self.files = {}
        self.started = time.monotonic()
        self.logfile = (self.state_root / 'download_progress.jsonl').open('a', buffering=1)
        self.active = {}

    def close(self):
        self.worker_sessions.close()
        self.logfile.close()
        self.run_lock.close()

    def emit(self, event):
        with self.lock:
            self.logfile.write(json.dumps({'time': now(), **event}, ensure_ascii=False) + '\n')

    def report(self):
        while not self.stop.wait(5):
            with self.lock:
                details = list(self.active.values())
                complete = sum(1 for x in self.files.values() if x.get('status') in ('complete', 'already_complete'))
                failed = sum(1 for x in self.files.values() if x.get('status') == 'failed')
                downloaded = sum(x.get('bytes_this_run', 0) for x in self.files.values())
                written = sum(x.get('bytes_written_this_run', 0) for x in self.files.values())
                elapsed = time.monotonic() - self.started
                event = {'time': now(), 'event': 'progress', 'completed_files': complete,
                         'failed_files': failed, 'active_files': details,
                         'bytes_this_run': downloaded, 'bytes_written_this_run': written, 'elapsed_seconds': round(elapsed, 1),
                         'mean_bytes_per_second': round(downloaded / max(elapsed, .001))}
                self.logfile.write(json.dumps(event) + '\n')
            print(json.dumps(event), flush=True)

    def hash_file(self, path):
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    def download(self, task):
        key = task['repo_id'] + '/' + task['path']
        dest = self.root / 'raw' / task['repo_id'].replace('/', '--') / task['path']
        part = Path(str(dest) + '.part')
        dest.parent.mkdir(parents=True, exist_ok=True)
        expected = task['expected_size']
        result = {**task, 'destination': str(dest), 'bytes_this_run': 0, 'bytes_written_this_run': 0, 'status': 'pending',
                  'zero_length_source': expected == 0}
        with self.lock:
            self.files[key] = result
        sem = None  # independent pools enforce their own concurrency without cross-pool starvation
        if sem:
            sem.acquire()
        try:
            if dest.is_file() and dest.stat().st_size == expected:
                digest = self.hash_file(dest)
                if not task['lfs_sha256'] or digest == task['lfs_sha256']:
                    result.update(status='already_complete', sha256=digest, verified_at=now())
                    self.emit({'event': 'file_complete', **result})
                    return result
            if dest.exists():
                # Never silently overwrite an unexpected preexisting file.
                bad = dest.with_name(dest.name + '.invalid-' + str(int(time.time())))
                os.replace(dest, bad)
            attempt = 0
            no_progress_attempts = 0
            integrity_failures = 0
            no_progress_network_errors = 0
            active_route = self.worker_sessions.preferred_route(bool(self.fallback_proxy))
            fallback_active = active_route == 'control_relay'
            last_progress = time.monotonic()
            while time.monotonic() - last_progress < self.stall_seconds:
                attempt += 1
                result['attempts'] = attempt
                attempt_route = active_route
                result['download_route'] = attempt_route
                have = part.stat().st_size if part.exists() else 0
                before_attempt = have
                if have > expected:
                    # A partial larger than the pinned file is invalid, retain it for diagnosis.
                    os.replace(part, part.with_name(part.name + '.oversize-' + str(int(time.time()))))
                    have = 0
                with self.lock:
                    self.active[key] = {'repo_id': task['repo_id'], 'path': task['path'],
                                        'bytes_on_disk': have, 'expected_size': expected,
                                        'phase': 'download', 'attempt': attempt, 'route': attempt_route}
                try:
                    if expected == 0 and have == 0:
                        part.touch(exist_ok=True)
                    if have != expected:
                        relay_proxies = {'http': self.fallback_proxy, 'https': self.fallback_proxy} if attempt_route == 'control_relay' else None
                        with nullcontext(self.worker_sessions.get(
                                attempt_route, trust_env=attempt_route == 'primary_env',
                                proxies=relay_proxies)) as session:
                            session.headers['User-Agent'] = 'img2code-dataset-collector/1.0'
                            headers = {'Range': f'bytes={have}-'} if have else {}
                            if attempt > 1:
                                headers['Cache-Control'] = 'no-cache'
                            url = f'{self.download_base}/datasets/{task["repo_id"]}/resolve/{task["revision"]}/{quote(task["path"], safe="/")}?download=true'
                            if attempt > 1:
                                url += '&collector_retry=' + str(int(time.time()))
                            with session.get(url, headers=headers, stream=True, timeout=(20, 45)) as response:
                                response.raise_for_status()
                                skip_prefix = 0
                                if response.status_code == 206:
                                    match = re.match(r'bytes (\d+)-\d+/(\d+|\*)', response.headers.get('Content-Range', ''))
                                    if not match or int(match.group(1)) != have:
                                        raise ValueError('invalid resume Content-Range; partial preserved')
                                elif have > 0:
                                    # Never discard a growing partial if a CDN ignores Range.
                                    # Replay and discard only the already saved prefix, then append.
                                    skip_prefix = have
                                    with self.lock:
                                        self.active[key]['phase'] = 'replay_saved_prefix'
                                    self.emit({'event': 'range_ignored_prefix_preserved',
                                               'repo_id': task['repo_id'], 'path': task['path'],
                                               'saved_bytes': have, 'route': attempt_route})
                                with part.open('ab' if have else 'wb') as stream:
                                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                                        if not chunk:
                                            continue
                                        with self.lock:
                                            result['bytes_this_run'] += len(chunk)
                                        if skip_prefix:
                                            skipped = min(skip_prefix, len(chunk))
                                            skip_prefix -= skipped
                                            chunk = chunk[skipped:]
                                        if time.monotonic() - last_progress >= self.stall_seconds:
                                            raise TimeoutError('no saved-byte progress for stall window')
                                        if not chunk:
                                            continue
                                        stream.write(chunk)
                                        stream.flush()  # preserve progress on disconnect; no fsync per chunk
                                        have += len(chunk)
                                        last_progress = time.monotonic()
                                        no_progress_attempts = 0
                                        no_progress_network_errors = 0
                                        with self.lock:
                                            result['bytes_written_this_run'] = result.get('bytes_written_this_run', 0) + len(chunk)
                                            self.active[key]['bytes_on_disk'] = have
                                            self.active[key]['phase'] = 'download'
                                        if have > expected:
                                            raise ValueError('received more bytes than repository expected size')
                    if part.stat().st_size != expected:
                        raise ValueError('downloaded size differs from repository expected size')
                    with self.lock:
                        self.active[key]['phase'] = 'sha256'
                    digest = self.hash_file(part)
                    if task['lfs_sha256'] and digest != task['lfs_sha256']:
                        part.unlink()
                        integrity_failures += 1
                        if integrity_failures >= 3:
                            result['terminal_reason'] = 'three_full_download_integrity_failures'
                            result.update(status='failed', failed_at=now())
                            return result
                        raise ValueError('LFS SHA256 mismatch; invalid partial removed before retry')
                    os.replace(part, dest)
                    if result['bytes_written_this_run']:
                        self.worker_sessions.verified_route(attempt_route)
                    result.update(status='complete', sha256=digest, verified_at=now())
                    self.emit({'event': 'file_complete', **result})
                    return result
                except Exception as exc:
                    error = type(exc).__name__
                    if isinstance(exc, requests.HTTPError) and exc.response is not None:
                        error += ':' + str(exc.response.status_code)
                    elif isinstance(exc, (ValueError, TimeoutError)):
                        error += ':' + str(exc)[:180]
                    after_attempt = part.stat().st_size if part.exists() else 0
                    made_progress = after_attempt > before_attempt
                    no_progress_attempts = 0 if made_progress else no_progress_attempts + 1
                    if made_progress:
                        no_progress_network_errors = 0
                    elif self.fallback_proxy and isinstance(exc, (requests.ReadTimeout, requests.ConnectionError)):
                        no_progress_network_errors += 1
                        if fallback_active or no_progress_network_errors >= 2:
                            fallback_active = True
                            active_route = 'control_relay' if attempt_route == 'primary_env' else 'primary_env'
                    stalled = time.monotonic() - last_progress
                    result['last_error'] = error
                    result['seconds_without_saved_progress'] = round(stalled, 1)
                    self.emit({'event': 'file_retry', 'repo_id': task['repo_id'], 'path': task['path'],
                               'attempt': attempt, 'error': error, 'partial_bytes': after_attempt,
                               'seconds_without_saved_progress': round(stalled, 1),
                               'consecutive_attempts_without_progress': no_progress_attempts,
                               'consecutive_network_errors_without_progress': no_progress_network_errors,
                               'route': attempt_route, 'next_route': active_route})
                    if stalled < self.stall_seconds:
                        time.sleep(min(2 ** min(no_progress_attempts + 1, 5), 30,
                                       max(0, self.stall_seconds - stalled)))
            result.update(status='failed', failed_at=now(), terminal_reason='no_saved_byte_progress_for_stall_window')
            return result
        finally:
            with self.lock:
                self.active.pop(key, None)
            if sem:
                sem.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--repos', nargs='*', help='Optional exact HF repo IDs to limit this run')
    parser.add_argument('--run-name', default='default', help='State folder root/runs/NAME; raw remains shared')
    parser.add_argument('--workers', type=int, default=8, help='Concurrent files <=1MiB, independently of large pool (default 8)')
    parser.add_argument('--medium-workers', type=int, default=2, help='Concurrent files >1MiB and <1GiB, with repository round robin (default 2)')
    parser.add_argument('--large-workers', type=int, default=2, help='Concurrent files >=1GiB, largest first (default 2)')
    parser.add_argument('--stall-seconds', type=int, default=600, help='Fail only after this many seconds without saved-byte progress (default 600)')
    parser.add_argument('--download-base', '--endpoint', dest='download_base', choices=['https://huggingface.co', 'https://hf-mirror.com'], default=API, help='Pinned files are fetched through this host; API discovery stays on HF')
    parser.add_argument('--fallback-proxy', default=os.environ.get('IMG2CODE_FALLBACK_PROXY', ''), help='Optional task-only HTTP proxy used after two zero-progress network failures; empty disables fallback')
    parser.add_argument('--retry-failed', action='store_true', help='Resume pinned inventory and retry all noncomplete files, including interrupted pending records; preserve completed entries')
    parser.add_argument('--resume-inventory', action='store_true', help='Load pinned tasks from this run inventory, skip API discovery')
    parser.add_argument('--plan-only', action='store_true', help='Discover and save pinned inventory, do not download dataset assets')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', args.run_name):
        parser.error('--run-name must be a safe single directory name')
    if args.workers < 1 or args.medium_workers < 1 or args.large_workers < 1 or args.stall_seconds < 1:
        parser.error('worker counts must be positive')
    root = Path(args.root).expanduser().resolve()
    sources = json.loads(Path(args.sources).read_text())
    source_map = {x['id']: x for x in sources['datasets']}
    repos = args.repos or [repo for repo in HF_IDS if repo in source_map]
    unknown = set(repos) - set(HF_IDS)
    if unknown:
        parser.error('unsupported repo IDs: ' + ', '.join(sorted(unknown)))
    run = DownloadRun(root, args.run_name, args.large_workers, args.stall_seconds, args.download_base, args.fallback_proxy)
    state = run.state_root
    inventory = []
    failures = []
    tasks = []
    previous_complete = []
    total_inventory_tasks = 0
    if args.resume_inventory or args.retry_failed:
        inventory_path = state / 'download_inventory.json'
        if not inventory_path.exists():
            parser.error('--resume-inventory needs ' + str(inventory_path))
        inventory = json.loads(inventory_path.read_text())
        if args.repos:
            inventory = [x for x in inventory if x['repo_id'] in repos]
        tasks = [task for record in inventory for task in record['files']]
        total_inventory_tasks = len(tasks)
        failure_path = state / 'download_failures.json'
        old_failures = json.loads(failure_path.read_text()) if failure_path.exists() else []
        failures = [x for x in old_failures if x.get('stage') == 'discovery']
        if args.retry_failed:
            prior_path = state / 'download_manifest.json'
            prior = json.loads(prior_path.read_text()).get('files', []) if prior_path.exists() else []
            inventory_keys = {(x['repo_id'],x['path']) for x in tasks}
            previous_complete = [{**x, 'retained_from_previous_run': True} for x in prior
                if x.get('status') in ('complete', 'already_complete') and (x['repo_id'],x['path']) in inventory_keys]
            complete_keys={(x['repo_id'],x['path']) for x in previous_complete}
            tasks = [x for x in tasks if (x['repo_id'], x['path']) not in complete_keys]
            run.emit({'event': 'retry_noncomplete_inventory', 'noncomplete_files_to_retry': len(tasks), 'completed_files_retained': len(previous_complete)})
        run.emit({'event': 'inventory_resumed', 'repositories': len(inventory), 'files': len(tasks)})
        print(json.dumps({'event': 'inventory_resumed', 'repositories': len(inventory), 'files': len(tasks)}), flush=True)
    else:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'img2code-dataset-collector/1.0'
            for repo in repos:
                try:
                    data, _ = api_json(session, '/api/datasets/' + quote(repo, safe='/'))
                    if data.get('private') or data.get('gated') not in (False, None):
                        raise RuntimeError('repository private or gated; no access acceptance attempted')
                    sha = data['sha']
                    entries = list_tree(session, repo, sha, run.emit)
                    chosen = selected_paths(repo, entries)
                    record = {'repo_id': repo, 'revision': sha, 'discovered_at': now(),
                              'license_hf_card': (data.get('cardData') or {}).get('license'),
                              'source_research': source_map.get(repo), 'repository_file_count': len(entries),
                              'selected_file_count': len(chosen), 'files': []}
                    for item in chosen:
                        lfs = item.get('lfs') or {}
                        digest = lfs.get('oid') or lfs.get('sha256')
                        if digest:
                            digest = digest.removeprefix('sha256:')
                        task = {'repo_id': repo, 'revision': sha, 'path': item['path'],
                                'expected_size': item.get('size', lfs.get('size', 0)),
                                'git_blob_oid': item.get('oid'), 'lfs_sha256': digest,
                                'source_url': f'{API}/datasets/{repo}/resolve/{sha}/{quote(item["path"], safe="/")}',
                                'license_hf_card': record['license_hf_card'],
                                'auxiliary_only': HF_IDS[repo] == 'auxiliary'}
                        tasks.append(task)
                        record['files'].append(task)
                    inventory.append(record)
                    run.emit({'event': 'repository_pinned', 'repo_id': repo, 'revision': sha,
                              'selected_file_count': len(chosen), 'expected_bytes': sum(x['size'] for x in chosen)})
                    print(json.dumps({'repo': repo, 'revision': sha, 'selected_files': len(chosen),
                                      'expected_bytes': sum(x['size'] for x in chosen)}), flush=True)
                    atomic_json(state / 'download_inventory.json', inventory)
                except Exception as exc:
                    failure = {'repo_id': repo, 'stage': 'discovery', 'error': type(exc).__name__ + ':' + str(exc)[:180], 'time': now()}
                    failures.append(failure)
                    run.emit({'event': 'repository_failed', **failure})
    atomic_json(state / 'download_inventory.json', inventory)
    atomic_json(state / 'source_research.json', sources)
    atomic_json(state / 'download_failures.json', failures)
    if args.plan_only:
        print(json.dumps({'status': 'planned', 'files': len(tasks), 'expected_bytes': sum(x['expected_size'] for x in tasks), 'failed_repositories': len(failures)}), flush=True)
        run.close()
        return 1 if failures else 0
    reporter = threading.Thread(target=run.report, daemon=True)
    reporter.start()
    # Separate small, medium and large pools: long shards cannot starve new sources.
    small_tasks = sorted((x for x in tasks if x['expected_size'] <= 1024**2), key=lambda x: x['expected_size'])
    medium_tasks = medium_round_robin([x for x in tasks if 1024**2 < x['expected_size'] < 1024**3])
    large_tasks = sorted((x for x in tasks if x['expected_size'] >= 1024**3), key=lambda x: x['expected_size'], reverse=True)
    results = list(previous_complete)
    last_manifest_write = 0.0
    try:
        with futures.ThreadPoolExecutor(max_workers=args.workers) as small_pool, futures.ThreadPoolExecutor(max_workers=args.medium_workers) as medium_pool, futures.ThreadPoolExecutor(max_workers=args.large_workers) as large_pool:
            pending = [large_pool.submit(run.download, task) for task in large_tasks]
            pending += [medium_pool.submit(run.download, task) for task in medium_tasks]
            pending += [small_pool.submit(run.download, task) for task in small_tasks]
            for future in futures.as_completed(pending):
                result = future.result()
                results.append(result)
                if result['status'] == 'failed':
                    failures.append(result)
                # JSONL records every completion; batch the growing snapshot to avoid O(N^2) disk writes.
                if time.monotonic() - last_manifest_write >= 5 or len(results) == len(tasks):
                    atomic_json(state / 'download_manifest.json', {'updated_at': now(), 'finished': False, 'files': results})
                    atomic_json(state / 'download_failures.json', failures)
                    last_manifest_write = time.monotonic()
    finally:
        run.stop.set()
        reporter.join(timeout=6)
    completed = sum(x['status'] in ('complete', 'already_complete') for x in results)
    summary = {'updated_at': now(), 'finished': True, 'planned_files': total_inventory_tasks or len(tasks),
               'completed_files': completed, 'failed_items': len(failures),
               'verified_bytes': sum(x['expected_size'] for x in results if x['status'] in ('complete', 'already_complete')),
               'bytes_downloaded_this_run': sum(x['bytes_this_run'] for x in results if not x.get('retained_from_previous_run')),
               'files': results}
    atomic_json(state / 'download_manifest.json', summary)
    atomic_json(state / 'download_failures.json', failures)
    run.emit({'event': 'run_finished', **{k: v for k, v in summary.items() if k != 'files'}})
    run.close()
    print(json.dumps({k: v for k, v in summary.items() if k != 'files'}), flush=True)
    return 1 if failures or completed != summary['planned_files'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
