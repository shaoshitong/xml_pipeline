#!/usr/bin/env python3
"""Fetch only official draw.io templates and licenses, directly on HKUST.
Uses GitHub tree API with a pinned commit. API403 falls back to shallow sparse
Git checkout; never clones a full blob history or downloads the full repository.
Requires requests and, for fallback, Git. No credentials are read or sent.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import time
from urllib.parse import quote
import requests

REPO = 'jgraph/drawio'
PREFIX = 'src/main/webapp/templates'
API = 'https://api.github.com/repos/' + REPO
RAW = 'https://raw.githubusercontent.com/' + REPO


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


class APIForbidden(Exception):
    pass


def api_json(session, url):
    response = session.get(url, timeout=(15, 60))
    if response.status_code == 403:
        raise APIForbidden('GitHub public API403')
    response.raise_for_status()
    return response.json()


def safe_relative(name):
    parts = PurePosixPath(name).parts
    return bool(parts and not PurePosixPath(name).is_absolute() and '..' not in parts and '\\' not in name)


def api_inventory(session, revision):
    commit = api_json(session, API + '/commits/' + revision)['sha']
    tree_sha = commit
    repository_license = None
    for component in PREFIX.split('/'):
        tree = api_json(session, API + '/git/trees/' + tree_sha)
        if repository_license is None:
            repository_license = next((x for x in tree['tree'] if x['path'] == 'LICENSE' and x['type'] == 'blob'), None)
        item = next((x for x in tree['tree'] if x['path'] == component and x['type'] == 'tree'), None)
        if item is None:
            raise ValueError('official templates directory missing at pinned commit')
        tree_sha = item['sha']
    tree = api_json(session, API + '/git/trees/' + tree_sha + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('templates subtree API result truncated; do not silently omit data')
    tasks = []
    for item in tree['tree']:
        if item['type'] != 'blob' or item.get('mode') == '120000' or not safe_relative(item['path']):
            continue
        tasks.append({'source_path': PREFIX + '/' + item['path'], 'path': 'templates/' + item['path'],
                      'expected_size': item['size'], 'git_blob_sha1': item['sha']})
    if repository_license:
        tasks.append({'source_path': 'LICENSE', 'path': 'repository_LICENSE',
                      'expected_size': repository_license['size'], 'git_blob_sha1': repository_license['sha']})
    return commit, tasks


def fetch_one(task, commit, destination):
    output = destination / task['path']
    output.parent.mkdir(parents=True, exist_ok=True)
    public_url = RAW + '/' + commit + '/' + quote(task['source_path'], safe='/')
    result = {**task, 'commit': commit, 'source_url': public_url}
    if output.is_file():
        data = output.read_bytes()
        if len(data) == task['expected_size'] and git_blob_sha(data) == task['git_blob_sha1']:
            return {**result, 'sha256': hashlib.sha256(data).hexdigest(), 'status': 'already_complete'}
    error = None
    for attempt in range(3):
        try:
            with requests.Session() as session:
                session.headers['User-Agent'] = 'img2code-official-template-collector/1.0'
                response = session.get(public_url, timeout=(15, 60))
                response.raise_for_status()
                data = response.content
            if len(data) != task['expected_size'] or git_blob_sha(data) != task['git_blob_sha1']:
                raise ValueError('pinned Git blob content verification failed')
            temporary = Path(str(output) + '.part')
            temporary.write_bytes(data)
            os.replace(temporary, output)
            return {**result, 'sha256': hashlib.sha256(data).hexdigest(), 'status': 'complete'}
        except Exception as exc:
            error = type(exc).__name__
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                error += ':' + str(exc.response.status_code)
            time.sleep(2 ** attempt)
    return {**result, 'status': 'failed', 'error': error}


def git_command(args, cwd=None):
    response = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    if response.returncode:
        raise RuntimeError('git ' + args[0] + ' failed, exit=' + str(response.returncode) + '; ' + response.stderr[-300:])
    return response.stdout.strip()


def sparse_fallback(root, revision, destination):
    if not shutil.which('git'):
        raise RuntimeError('GitHub API403 and Git is unavailable for sparse fallback')
    checkout = root / 'work' / 'drawio_templates_sparse_checkout'
    checkout.parent.mkdir(parents=True, exist_ok=True)
    if not checkout.exists():
        git_command(['clone', '--filter=blob:none', '--depth', '1', '--no-checkout', '--sparse',
                     '--branch', 'dev', 'https://github.com/jgraph/drawio.git', str(checkout)])
    origin = git_command(['remote', 'get-url', 'origin'], checkout)
    if origin != 'https://github.com/jgraph/drawio.git':
        raise RuntimeError('existing sparse checkout has unexpected origin; preserved')
    git_command(['sparse-checkout', 'set', '--cone', PREFIX], checkout)
    if re.fullmatch(r'[0-9a-f]{40}', revision):
        git_command(['fetch', '--depth', '1', 'origin', revision], checkout)
        commit = revision
    else:
        git_command(['fetch', '--depth', '1', 'origin', revision], checkout)
        commit = git_command(['rev-parse', 'FETCH_HEAD'], checkout)
    git_command(['checkout', '--detach', commit], checkout)
    lines = git_command(['ls-tree', '-r', '-l', '--full-name', commit, '--', PREFIX, 'LICENSE'], checkout).splitlines()
    results = []
    for line in lines:
        meta, source_path = line.split('\t', 1)
        mode, kind, sha1, size = meta.split()
        if kind != 'blob' or mode == '120000' or not safe_relative(source_path):
            continue
        relative = 'repository_LICENSE' if source_path == 'LICENSE' else 'templates/' + source_path[len(PREFIX) + 1:]
        data = (checkout / source_path).read_bytes()
        if len(data) != int(size) or git_blob_sha(data) != sha1:
            raise ValueError('sparse checkout blob verification failed')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(str(target) + '.part')
        temporary.write_bytes(data)
        os.replace(temporary, target)
        results.append({'source_path': source_path, 'path': relative, 'expected_size': int(size),
                        'git_blob_sha1': sha1, 'sha256': hashlib.sha256(data).hexdigest(), 'status': 'complete',
                        'commit': commit, 'source_url': RAW + '/' + commit + '/' + quote(source_path, safe='/')})
    return commit, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--ref', default='dev')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    root = args.root.resolve()
    destination = root / 'raw' / 'jgraph--drawio-templates'
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / 'source_manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    revision = old.get('commit') or args.ref
    started = now()
    results = []
    method = 'github_api'
    try:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'img2code-official-template-collector/1.0'
            commit, tasks = api_inventory(session, revision)
        atomic_json(manifest_path, {'started_at': started, 'finished': False, 'commit': commit, 'files': []})
        print(json.dumps({'event': 'templates_pinned', 'commit': commit, 'files': len(tasks),
                          'expected_bytes': sum(x['expected_size'] for x in tasks)}), flush=True)
        with ThreadPoolExecutor(max_workers=max(1, min(8, args.workers))) as pool:
            for future in as_completed([pool.submit(fetch_one, task, commit, destination) for task in tasks]):
                results.append(future.result())
                if len(results) % 25 == 0:
                    atomic_json(manifest_path, {'started_at': started, 'finished': False, 'commit': commit, 'files': results})
                    print(json.dumps({'event': 'template_progress', 'files': len(results), 'total': len(tasks)}), flush=True)
    except APIForbidden:
        method = 'git_shallow_sparse_api403_fallback'
        print(json.dumps({'event': 'api403_sparse_fallback', 'revision': revision}), flush=True)
        commit, results = sparse_fallback(root, revision, destination)
    except Exception as exc:
        atomic_json(destination / 'download_error.json', {'time': now(), 'stage': method,
                    'error': type(exc).__name__ + ':' + str(exc)[:300], 'files_completed': len(results)})
        raise
    pairs = []
    for result in results:
        if result['status'] not in ('complete', 'already_complete') or not result['path'].lower().endswith('.xml'):
            continue
        xml = destination / result['path']
        png = xml.with_suffix('.png')
        if png.is_file():
            pairs.append({'xml': str(xml.relative_to(destination)), 'image': str(png.relative_to(destination)),
                          'category': xml.parent.name, 'image_provenance': 'official_template_thumbnail',
                          'code_provenance': 'official_native_mxgraph_template'})
    failures = [x for x in results if x['status'] == 'failed']
    manifest = {'started_at': started, 'finished_at': now(), 'finished': True, 'method': method,
                'repository': REPO, 'commit': commit, 'scope': PREFIX, 'destination': str(destination),
                'template_license': 'CC-BY-4.0 (templates/LICENSE)',
                'repository_code_license': 'Apache-2.0 (repository_LICENSE)',
                'files': results, 'failed_files': failures, 'same_stem_png_xml_pairs': pairs,
                'paired_count_before_domain_filter': len(pairs),
                'verified_bytes': sum(x['expected_size'] for x in results if x['status'] != 'failed')}
    atomic_json(manifest_path, manifest)
    print(json.dumps({key: value for key, value in manifest.items() if key not in ('files', 'same_stem_png_xml_pairs')}), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
