#!/usr/bin/env python3
"""Destination-only downloads for two existing source supplements.
Fetch Omni-I2C ground-truth tar and official drawio-diagrams ZIP. Prefer immutable
GitHub commit URLs; if public commit API fails, record an explicitly unpinned
branch snapshot with retrieval time and the downloaded byte SHA256.
No archive extraction and no downloaded code execution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import zipfile
import json
import os
from pathlib import Path
import re
import time
import requests

SPECS = [
    {'repo': 'MiliLab/Omni-I2C', 'branch': 'main', 'path': 'eval_pipeline/gt_data/gt_data.tar.gz',
     'destination': 'raw/MiliLab--Omni-I2C/gt_data.tar.gz', 'kind': 'gzip',
     'purpose': 'Join Image2Code_Full.tsv answer filenames to ground-truth source files and supporting data'},
    {'repo': 'jgraph/drawio-diagrams', 'branch': 'dev', 'destination': 'raw/jgraph--drawio-diagrams/source.zip',
     'kind': 'zip', 'purpose': 'Official diagram/template examples, some with provided native-source image pairs'},
]


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            result.update(chunk)
    return result.hexdigest()


def pin_commit(repo, branch):
    try:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'img2code-existing-source-supplements/1.0'
            response = session.get('https://api.github.com/repos/' + repo + '/commits/' + branch, timeout=(15, 30))
            response.raise_for_status()
            commit = response.json()['sha']
            if not re.fullmatch(r'[a-f0-9]{40}', commit):
                raise ValueError('unexpected commit identifier')
            return commit, None
    except Exception as exc:
        reason = type(exc).__name__
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            reason += ':' + str(exc.response.status_code)
        return None, reason


def download(url, path, stall_seconds=600):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = Path(str(path) + '.part')
    last_progress = time.monotonic()
    attempt = 0
    final_headers = {}
    while time.monotonic() - last_progress < stall_seconds:
        attempt += 1
        have = part.stat().st_size if part.exists() else 0
        try:
            with requests.Session() as session:
                session.headers['User-Agent'] = 'img2code-existing-source-supplements/1.0'
                headers = {'Range': f'bytes={have}-'} if have else {}
                if attempt > 1:
                    headers['Cache-Control'] = 'no-cache'
                with session.get(url, headers=headers, stream=True, timeout=(20, 45)) as response:
                    response.raise_for_status()
                    skip = 0
                    if have and response.status_code == 206:
                        match = re.match(r'bytes (\d+)-', response.headers.get('Content-Range', ''))
                        if not match or int(match.group(1)) != have:
                            raise ValueError('invalid resume Content-Range')
                    elif have:
                        skip = have  # Preserve saved prefix if the server ignores Range.
                    with part.open('ab' if have else 'wb') as output:
                        for chunk in response.iter_content(1024**2):
                            if not chunk:
                                continue
                            if skip:
                                discard = min(skip, len(chunk));skip -= discard;chunk = chunk[discard:]
                            if time.monotonic() - last_progress >= stall_seconds:
                                raise TimeoutError('no saved-byte progress within stall window')
                            if chunk:
                                output.write(chunk);output.flush();last_progress = time.monotonic()
                    final_headers = {'content_type': response.headers.get('Content-Type'),
                                     'etag': response.headers.get('ETag')}
            os.replace(part, path)
            return {'bytes': path.stat().st_size, 'sha256': sha256(path), 'attempts': attempt, **final_headers}
        except Exception as exc:
            error = type(exc).__name__
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                error += ':' + str(exc.response.status_code)
                if exc.response.status_code in (401, 404):
                    raise RuntimeError('public asset unavailable: ' + error)
            print(json.dumps({'event': 'supplement_retry', 'file': path.name, 'attempt': attempt,
                              'partial_bytes': part.stat().st_size if part.exists() else 0, 'error': error}), flush=True)
            time.sleep(min(10, max(0, stall_seconds - (time.monotonic() - last_progress))))
    raise RuntimeError('supplement stalled without saved-byte progress for ' + str(stall_seconds) + ' seconds')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--stall-seconds', type=int, default=600)
    args = parser.parse_args()
    root = args.root.resolve()
    reports = root / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in SPECS:
        target = root / spec['destination']
        manifest_path = target.parent / 'extra_asset_manifest.json'
        old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        record = {**spec, 'retrieval_started_at': now()}
        try:
            if target.is_file() and old.get('status') == 'complete' and old.get('sha256') == sha256(target):
                results.append({**old, 'reused_verified_asset': True})
                continue
            if old.get('commit'):
                commit, pin_error = old['commit'], old.get('pin_error')
            else:
                commit, pin_error = pin_commit(spec['repo'], spec['branch'])
            reference = commit or spec['branch']
            if spec['kind'] == 'zip':
                url = ('https://codeload.github.com/' + spec['repo'] + '/zip/' + commit) if commit else (
                    'https://codeload.github.com/' + spec['repo'] + '/zip/refs/heads/' + spec['branch'])
            else:
                url = 'https://raw.githubusercontent.com/' + spec['repo'] + '/' + reference + '/' + spec['path']
            record.update(commit=commit, pin_error=pin_error, source_url=url,
                          reproducibility_status='pinned_commit' if commit else 'unpinned_branch_snapshot')
            atomic_json(manifest_path, {**record, 'status': 'downloading'})
            record.update(download(url, target, args.stall_seconds))
            # Raw GitHub can return a Git-LFS pointer; fetch its actual immutable media.
            prefix = target.open('rb').read(300)
            if prefix.startswith(b'version https://git-lfs.github.com/spec/v1'):
                pointer = prefix.decode()
                expected_sha = re.search(r'oid sha256:([0-9a-f]{64})', pointer)
                expected_size = re.search(r'size (\d+)', pointer)
                if not spec.get('path') or not expected_sha or not expected_size:
                    raise ValueError('unrecognized LFS pointer')
                pointer_path = Path(str(target) + '.lfs-pointer')
                os.replace(target, pointer_path)
                media = 'https://media.githubusercontent.com/media/' + spec['repo'] + '/' + reference + '/' + spec['path']
                record.update(download(media, target, args.stall_seconds))
                record.update(lfs_sha256=expected_sha.group(1), lfs_size=int(expected_size.group(1)), media_source_url=media)
                if record['sha256'] != record['lfs_sha256'] or record['bytes'] != record['lfs_size']:
                    raise ValueError('LFS object checksum or size mismatch')
                prefix = target.open('rb').read(4)
            if spec['kind'] == 'zip' and not prefix.startswith(b'PK'):
                raise ValueError('expected ZIP magic missing')
            if spec['kind'] == 'gzip' and not prefix.startswith(b'\x1f\x8b'):
                raise ValueError('expected gzip magic missing')
            if spec['kind'] == 'zip':
                with zipfile.ZipFile(target) as archive:
                    bad_member = archive.testzip()
                    if bad_member:
                        raise ValueError('ZIP CRC validation failed')
            else:
                with gzip.open(target, 'rb') as stream:
                    while stream.read(8 * 1024**2):
                        pass  # validate gzip CRC, discard decompressed bytes
            record.update(status='complete', archive_integrity_checked=True, retrieved_at=now())
        except Exception as exc:
            record.update(status='failed', error=type(exc).__name__ + ':' + str(exc)[:180], failed_at=now())
        atomic_json(manifest_path, record)
        results.append(record)
        print(json.dumps(record), flush=True)
    atomic_json(reports / 'extra_assets.json', {'updated_at': now(), 'assets': results})
    return 1 if any(x['status'] != 'complete' for x in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
