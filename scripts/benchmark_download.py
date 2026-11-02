#!/usr/bin/env python3
"""Read at most the first 4MiB per probe into memory; never save dataset bytes.
Runs <=4 probes concurrently, each with a 20s deadline and short socket timeouts.
Only hostnames (never signed URLs) are included in results.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import time
from urllib.parse import quote, urlparse
import requests

FILES = [('sxy1620348809/VCG-Bench', 'train.parquet', 'vcg'),
         ('DocTron-Hub/VinciCoder-1.6M-SFT', 'chart2code_1.parquet', 'vinci')]
ROUTES = [('hf_proxy', 'https://huggingface.co', True),
          ('mirror_direct', 'https://hf-mirror.com', False),
          ('mirror_proxy', 'https://hf-mirror.com', True)]


def probe(task):
    start = time.monotonic()
    deadline = start + 20
    record = {k: task[k] for k in ('repo_id', 'path', 'revision', 'route', 'range_start', 'range_end')}
    record.update(bytes_read=0, http_status=None, first_byte_seconds=None, redirect_hosts=[])
    payload = bytearray()
    def deadline_alarm(signum, frame):
        raise TimeoutError('probe hard deadline 20s')
    signal.signal(signal.SIGALRM, deadline_alarm)
    signal.setitimer(signal.ITIMER_REAL, 20)
    try:
        with requests.Session() as session:
            session.trust_env = False
            session.max_redirects = 5
            session.headers['User-Agent'] = 'img2code-network-prefix-benchmark/1.0'
            if task['proxy']:
                session.proxies = {'http': task['proxy_url'], 'https': task['proxy_url']}
            url = task['host'] + '/datasets/' + task['repo_id'] + '/resolve/' + task['revision'] + '/' + quote(task['path'], safe='/') + '?download=true'
            with session.get(url, headers={'Range': f'bytes={task["range_start"]}-{task["range_end"]}'},
                             stream=True, timeout=(5, 5)) as response:
                record['http_status'] = response.status_code
                record['headers_seconds'] = round(time.monotonic() - start, 4)
                record['redirect_hosts'] = [urlparse(x.url).hostname for x in response.history] + [urlparse(response.url).hostname]
                record['content_range'] = response.headers.get('Content-Range')
                record['range_supported'] = response.status_code == 206
                response.raise_for_status()
                limit = task['range_end'] - task['range_start'] + 1
                for chunk in response.iter_content(16 * 1024):
                    if time.monotonic() > deadline:
                        record['error'] = 'DeadlineExceeded20s'
                        break
                    if not chunk:
                        continue
                    if record['first_byte_seconds'] is None:
                        record['first_byte_seconds'] = round(time.monotonic() - start, 4)
                    payload.extend(chunk[:limit - len(payload)])
                    if len(payload) >= limit:
                        break
        record['bytes_read'] = len(payload)
        record['prefix_sha256'] = hashlib.sha256(payload).hexdigest()
        record['complete_prefix'] = len(payload) == task['range_end'] - task['range_start'] + 1
    except Exception as exc:
        record['error'] = type(exc).__name__
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            record['http_status'] = exc.response.status_code
        record['bytes_read'] = len(payload)
    signal.setitimer(signal.ITIMER_REAL, 0)
    record['elapsed_seconds'] = round(time.monotonic() - start, 4)
    record['mib_per_second'] = round(record['bytes_read'] / (1024**2) / max(record['elapsed_seconds'], .001), 4)
    # Return only tiny metrics. The prefix buffer is discarded on return.
    return record


def find_revisions(root):
    found = {}
    paths = [root / 'download_inventory.json', *root.glob('runs/*/download_inventory.json')]
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for record in data:
            for task in record.get('files', []):
                for repo, name, label in FILES:
                    if task.get('repo_id') == repo and task.get('path') == name:
                        found[label] = task['revision']
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--proxy-url', default='http://127.0.0.1:7890')
    parser.add_argument('--vcg-revision')
    parser.add_argument('--vinci-revision')
    parser.add_argument('--segmented', action='store_true', help='Also compare four concurrent 1MiB ranges over fastest working route')
    args = parser.parse_args()
    revisions = find_revisions(args.root)
    for label in ('vcg', 'vinci'):
        if getattr(args, label + '_revision'):
            revisions[label] = getattr(args, label + '_revision')
    if any(label not in revisions for _, _, label in FILES):
        parser.error('Fixed revisions missing from inventory; pass --vcg-revision and --vinci-revision')
    tasks = []
    for repo, path, label in FILES:
        for route, host, proxy in ROUTES:
            tasks.append({'repo_id': repo, 'path': path, 'revision': revisions[label], 'route': route,
                          'host': host, 'proxy': proxy, 'proxy_url': args.proxy_url,
                          'range_start': 0, 'range_end': 4 * 1024**2 - 1})
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(probe, task) for task in tasks]):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
    segmented = []
    if args.segmented:
        for repo, path, label in FILES:
            candidates = [x for x in results if x['repo_id'] == repo and x.get('complete_prefix') and x.get('range_supported')]
            if not candidates:
                continue
            best = max(candidates, key=lambda x: x['mib_per_second'])
            original = next(x for x in tasks if x['repo_id'] == repo and x['route'] == best['route'])
            pieces = [{**original, 'range_start': i * 1024**2, 'range_end': (i + 1) * 1024**2 - 1} for i in range(4)]
            started = time.monotonic()
            with ProcessPoolExecutor(max_workers=4) as pool:
                records = list(pool.map(probe, pieces))
            elapsed = time.monotonic() - started
            item = {'repo_id': repo, 'route': best['route'], 'segments': records,
                    'elapsed_seconds': round(elapsed, 4),
                    'mib_per_second': round(sum(x['bytes_read'] for x in records) / 1024**2 / max(elapsed, .001), 4),
                    'all_ranges_supported': all(x.get('range_supported') and x.get('complete_prefix') for x in records)}
            segmented.append(item)
            print(json.dumps({'segmented_result': item}), flush=True)
    aria = shutil.which('aria2c')
    aria_version = None
    if aria:
        try:
            aria_version = subprocess.run([aria, '--version'], capture_output=True, text=True, timeout=3).stdout.splitlines()[0]
        except Exception as exc:
            aria_version = type(exc).__name__
    output = {'results': results, 'segmented': segmented, 'aria2c_path': aria, 'aria2c_version': aria_version,
              'note': 'Only bounded range prefixes were read and discarded in memory. No proxy or global configuration was changed.'}
    dest = args.root / 'network_prefix_benchmark.json'
    dest.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'report': str(dest), 'aria2c_path': aria, 'aria2c_version': aria_version}), flush=True)


if __name__ == '__main__':
    main()
