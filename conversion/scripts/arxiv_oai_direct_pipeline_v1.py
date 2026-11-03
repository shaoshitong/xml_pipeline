"""OAI-PMH discovery and direct HKUST3 source acquisition, existing importer.

Keeps the existing paper/PDF ledgers and the unchanged official XML importer,
renderer and QA. Network failures stay pending outside conversion once claims.
No VPS, Mac data relay, model calls, global proxy or routing changes.
"""
from pathlib import Path
import argparse
import calendar
import collections
import concurrent.futures as cf
import datetime as dt
import email.utils
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import threading
import urllib.parse
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
S = R / 'conversion/scripts'
sys.path.insert(0, str(S))
import arxiv_parallel_pipeline_v3_1 as previous

engine = previous.engine
engine.PROXY = None
P = engine.P
D = P / 'oai_direct_pipeline_v1'
SOURCE = P / 'recent_ai_source_expansion_v2'
NS = {'o': 'http://www.openarchives.org/OAI/2.0/', 'a': 'http://arxiv.org/OAI/arXivRaw/'}
CATEGORIES = {'cs.CL', 'cs.CV', 'cs.LG', 'cs.AI'}
STOP = False


def put(path, value):
    engine.native.atomic(path, value)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_page(blob):
    root = ET.fromstring(blob)
    assert root.tag == '{' + NS['o'] + '}OAI-PMH'
    errors = root.findall('o:error', NS)
    if errors:
        code = errors[0].get('code')
        if code == 'noRecordsMatch':
            return [], None
        raise ValueError('OAI_error:' + str(code))
    container = root.find('o:ListRecords', NS)
    assert container is not None, 'missing_ListRecords'
    papers = []
    for record in container.findall('o:record', NS):
        header = record.find('o:header', NS)
        if header is None or header.get('status') == 'deleted':
            continue
        raw = record.find('o:metadata/a:arXivRaw', NS)
        if raw is None:
            continue
        ident = raw.findtext('a:id', '', NS)
        if not re.fullmatch(r'\d{4}\.\d{4,5}', ident):
            continue
        categories = raw.findtext('a:categories', '', NS).split()
        versions = raw.findall('a:version', NS)
        if not set(categories) & CATEGORIES or not versions:
            continue
        versions = sorted(versions, key=lambda v: int(v.get('version', 'v0')[1:]))
        first = email.utils.parsedate_to_datetime(versions[0].findtext('a:date', '', NS))
        if first.year < 2023 or first.date() > dt.date(2026, 11, 2):
            continue
        last = versions[-1]
        version = int(last.get('version')[1:])
        sizes = [v.findtext('a:size', '', NS) for v in versions]
        size = next((s for s in reversed(sizes) if s), '')
        match = re.fullmatch(r'\s*([\d.]+)\s*([kmg]?)b?\s*', size, re.I)
        estimate = int(float(match[1]) * (1024 ** ('kmg'.find(match[2].lower()) + 1) if match[2] else 1)) if match else None
        if estimate == 0:
            continue  # Declared zero-sized/withdrawn source; not a transport retry.
        license_url = raw.findtext('a:license', '', NS)
        papers.append(dict(versioned_id=ident + 'v' + str(version), arxiv_id=ident, version=version, title=raw.findtext('a:title', '', NS), publication_date=first.isoformat(), updated=email.utils.parsedate_to_datetime(last.findtext('a:date', '', NS)).isoformat(), categories=categories, license_urls=[license_url] if license_url else [], abs_url='https://arxiv.org/abs/' + ident + 'v' + str(version), discovery='official_OAI_PMH_arXivRaw', OAI_modified_date=header.findtext('o:datestamp', '', NS), source_size_estimate_bytes=estimate, size_is_estimate_not_download_measurement=True))
    return papers, container.findtext('o:resumptionToken', '', NS) or None


def transient(result):
    text = result.get('error', '')
    return result.get('network_failure') or any(s in text for s in ['HTTPError:403', 'HTTPError:429', 'HTTPError:500', 'HTTPError:502', 'HTTPError:503', 'HTTPError:504', 'ReadTimeout', 'ConnectionError', 'bounded_source_download_attempts_exhausted', 'source_network_budget', 'resource_'])


def download_direct_source(self, paper):
    """Versioned HTTP transport from v3: keep all prior attempts, allow retriable network outages; official import/QA unchanged."""
    ident = paper['versioned_id']
    target = self.D / 'papers' / ident
    target.mkdir(parents=True, exist_ok=True)
    archive = target / 'source.archive'
    if archive.exists():
        return {'archive': str(archive), 'cached': True}
    t = time.perf_counter()
    try:
        metadata = target / 'provenance.json'
        if not metadata.exists():
            with self.request(paper['abs_url']) as response:
                body = response.content
            if len(body) > 2 * 1024 ** 2:
                raise ValueError('abstract_metadata_over2MiB')
            (target / 'abstract.html').write_bytes(body)
            resolved = engine.native.metadata_from_abs(body.decode(errors='replace'), ident)
            engine.native.once(metadata, dict(paper, **{k: v for (k, v) in resolved.items() if k not in paper or k == 'license_urls'}))
        part = target / 'source.archive.part'
        offset = part.stat().st_size if part.exists() else 0
        assert offset <= 128 * 1024 ** 2, 'prior_partial_above128MiB'
        overlap = min(65536, offset)
        expected = b''
        if overlap:
            with part.open('rb') as f:
                f.seek(offset - overlap)
                expected = f.read(overlap)
        start = offset - overlap
        journal = target / 'source_attempt.json'
        if not journal.exists():
            engine.native.once(journal, {'url': 'https://arxiv.org/src/' + ident, 'at_utc': now(), 'source_attempts': 1, 'version': 'parallel_v3'})
        attempts = target / 'download_attempts.v3.jsonl'
        prior = attempts.read_text().splitlines() if attempts.exists() else []
        assert len(prior) < 1000, 'bounded_source_download_attempts_exhausted_1000'
        with attempts.open('a') as f:
            f.write(engine.native.enc({'at_utc': now(), 'attempt': len(prior) + 1, 'preserved_offset': offset, 'overlap_verified_before_append': overlap, 'transport': 'HKUST_DIRECT_no_proxy'}) + '\n')
        headers = {'Range': 'bytes=' + str(start) + '-'} if offset else None
        with self.request('https://arxiv.org/src/' + ident, stream=True, headers=headers) as response:
            ct = response.headers.get('Content-Type', '').lower()
            engine.native.once(target / ('source_response_headers.v3.' + str(len(prior) + 1) + '.json'), {'content_type': ct, 'content_length': response.headers.get('Content-Length'), 'content_range': response.headers.get('Content-Range'), 'response_url': response.url, 'at_utc': now()})
            if 'application/pdf' in ct:
                raise ValueError('typed_skip_src_endpoint_PDF_content_type_before_body')
            if offset:
                match = re.fullmatch('bytes (\\d+)-(\\d+)/(\\d+)', response.headers.get('Content-Range', ''))
                assert response.status_code == 206 and match and (int(match[1]) == start), 'range_resume_not_confirmed'
                total = int(match[3])
            else:
                total = int(response.headers.get('Content-Length') or 0)
            if total > 128 * 1024 ** 2:
                raise ValueError('typed_skip_source_ContentLength_above128MiB')
            skip = overlap
            verified = 0
            received = 0
            net_seconds = 0.0
            stream_start = time.perf_counter()
            iterator = response.iter_content(256 * 1024)
            with part.open('ab' if offset else 'wb') as out:
                while True:
                    tick = time.perf_counter()
                    try:
                        block = next(iterator)
                    except StopIteration:
                        break
                    elapsed = time.perf_counter() - tick
                    net_seconds += elapsed
                    self.metric('source_HTTP_body_receive', elapsed)
                    if not block:
                        continue
                    received += len(block)
                    with self.mu:
                        self.net_bytes += len(block)
                        if self.net_bytes > engine.BUDGET:
                            raise ValueError('source_network_budget_reached')
                    if offset == 0 and received == len(block) and block.startswith(b'%PDF-'):
                        raise ValueError('typed_skip_src_endpoint_PDF_only_first_chunk')
                    if skip:
                        size = min(len(block), skip)
                        assert block[:size] == expected[verified:verified + size], 'resume_overlap_does_not_match_original'
                        verified += size
                        skip -= size
                        block = block[size:]
                    if block:
                        out.write(block)
                    if out.tell() > 128 * 1024 ** 2:
                        raise ValueError('typed_skip_source_above128MiB')
                    wall = time.perf_counter() - stream_start
                    if wall > 90 and received / wall < 64 * 1024:
                        raise engine.requests.exceptions.ConnectionError('network_source_below64KiB_s_for90s')
                out.flush()
                os.fsync(out.fileno())
            assert not skip, 'short_resume_overlap'
            if total:
                assert part.stat().st_size == total, 'incomplete_source_content_length'
        os.replace(part, archive)
        engine.native.once(target / 'source_receipt.json', {'url': 'https://arxiv.org/src/' + ident, 'sha256': engine.sha(archive.read_bytes()), 'bytes': archive.stat().st_size, 'at_utc': now(), 'resumed_prior_bytes': offset, 'new_transport': 'HKUST3_DIRECT_no_proxy'})
        self.metric('source_archives_downloaded', time.perf_counter() - t)
        self.emit('source_download_complete', paper=ident, bytes=archive.stat().st_size, new_bytes=received, preserved_prior_bytes=offset, seconds=time.perf_counter() - t, body_receive_seconds=net_seconds)
        self.save()
        return {'archive': str(archive), 'cached': False}
    except Exception as e:
        self.metric('source_download_failures', time.perf_counter() - t)
        reason = type(e).__name__ + ':' + str(e)[:1000]
        self.emit('source_download_failed', paper=ident, reason=reason)
        self.save()
        return {'error': reason, 'network_failure': isinstance(e, (engine.requests.ConnectionError, engine.requests.Timeout))}


class DirectState(previous.UnicodeSafeState):
    def __init__(self, *args, **kwargs):
        self.access_denied = False
        super().__init__(*args, **kwargs)
        for index in range(len(self.workers), 8):
            thread = threading.Thread(target=self.worker_loop, name="native-" + str(index))
            thread.start()
            self.workers.append(thread)
        self.emit('direct_thread_pool_ready', download_threads=8, native_import_workers=len(self.workers))

    def emit(self, event, **fields):
        if 'route' in fields:
            fields['route'] = 'arxiv -> HKUST3 DIRECT'
        super().emit(event, **fields)

    def save(self, finished=False):
        # Keep both the parent write and route correction inside the same RLock.
        # Downloads call save concurrently; releasing it between writes races
        # the fixed .tmp path against another thread's os.replace.
        with self.mu:
            super().save(finished=finished)
            path = engine.CONTROL / (self.profile + '.performance.json')
            value = json.loads(path.read_text())
            value.update(route='arxiv -> HKUST3 DIRECT', VPS_used=False, Mac_in_data_path=False, download_threads=8, native_import_workers=8)
            put(path, value)

    def download(self, paper):
        value = download_direct_source(self, paper)
        if value.get('archive') and not value.get('cached'):
            receipt = self.D / 'papers' / paper['versioned_id'] / 'source_receipt.json'
            data = json.loads(receipt.read_text())
            data['new_transport'] = 'HKUST3_DIRECT_no_proxy'
            put(receipt, data)
        return value

    def direct_batch(self, papers):
        broker_config = os.environ.get('ARXIV_CLUSTER_CONFIG')
        if broker_config:
            config = json.loads(Path(broker_config).read_text())
            session = engine.requests.Session()
            session.trust_env = False
            response = session.post(config['url'] + '/enqueue', json={'papers': papers}, headers={'Authorization': 'Bearer ' + config['token']}, timeout=(8, 120))
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                raise RuntimeError('cluster_enqueue_pending:' + result['error'])
            self.emit('cluster_source_batch_durably_enqueued', papers=len(papers), newly_enqueued=result['enqueued'])
            return 0, []
        terminal = {r[0] for r in self.db.execute("select id from papers where status!='attempt_started'")}
        selected = [p for p in papers if p['versioned_id'] not in terminal and p['arxiv_id'] not in self.inherited_ids]
        selected.sort(key=lambda p: (p.get('source_size_estimate_bytes') is None, p.get('source_size_estimate_bytes') or 0, p['versioned_id']))
        pending, done = [], 0
        # Download concurrency is unchanged; conversion/PDF hash once guards are reused.
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {i: pool.submit(self.download, p) for i, p in enumerate(selected[:16])}
            next_job = len(futures)
            consecutive = 0
            for i, paper in enumerate(selected):
                result = futures.pop(i).result()
                if transient(result):
                    pending.append(dict(paper=paper, reason=result.get('error'), status='pending_network_retry', at_utc=now()))
                    self.emit('source_pending_network_retry', paper=paper['versioned_id'], reason=result.get('error'), conversion_claim_created=False)
                    consecutive += 1
                    if 'HTTPError:403' in result.get('error', ''):
                        self.access_denied = True
                        consecutive = 3
                else:
                    self.process_paper(paper, result)
                    done += 1
                    consecutive = 0
                if next_job < len(selected) and not self.access_denied:
                    futures[next_job] = pool.submit(self.download, selected[next_job])
                    next_job += 1
                if STOP or consecutive >= 3:
                    # Drain prefetched downloads without losing their durable partials.
                    for j, f in futures.items():
                        v = f.result()
                        pending.append(dict(paper=selected[j], reason=v.get('error') or 'prefetch_preserved_for_resume', status='pending_network_retry', at_utc=now()))
                    for j in range(next_job, len(selected)):
                        pending.append(dict(paper=selected[j], reason='deferred_after_transport_circuit', status='pending_network_retry', at_utc=now()))
                    break
        return done, pending


def units():
    out = []
    for year in range(2026, 2022, -1):
        for month in range(12, 0, -1):
            if (year, month) > (2026, 11):
                continue
            end = min(dt.date(year, month, calendar.monthrange(year, month)[1]), dt.date(2026, 11, 2))
            for cat in ['CL', 'CV', 'LG', 'AI']:
                out.append(dict(key=f'{year:04}{month:02}_{cat}', params={'verb': 'ListRecords', 'metadataPrefix': 'arXivRaw', 'set': 'cs:cs:' + cat, 'from': f'{year:04}-{month:02}-01', 'until': end.isoformat()}, page=0, generation=0, state='pending', token=None, failures=0))
    out.sort(key=lambda u: (u['key'] != '202610_CL', -int(u['key'][:6]), u['key']))
    return out


def metadata(unit):
    folder = D / 'metadata' / unit['key'] / str(unit['generation'])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (str(unit['page']) + '.xml')
    if not path.exists():
        params = {'verb': 'ListRecords', 'resumptionToken': unit['token']} if unit['token'] else unit['params']
        url = 'https://oaipmh.arxiv.org/oai?' + urllib.parse.urlencode(params)
        tmp = path.with_suffix('.partial')
        probe = engine.CONTROL / 'oai_recovery_v1/probe_listrecords.xml'
        probe_info = probe.with_name('probe_listrecords.json')
        if unit['key'] == '202610_CL' and unit['page'] == 0 and probe.exists() and json.loads(probe_info.read_text()).get('status') == 200:
            blob = probe.read_bytes()
            parse_page(blob)
            path.write_bytes(blob)
            origin = 'preexisting_frozen_official_OAI_response_reused_no_network'
        else:
            a = subprocess.run(['curl', '--noproxy', '*', '--compressed', '-L', '--connect-timeout', '8', '--max-time', '240', '--max-filesize', str(16 * 1024 ** 2), '-sS', '-D', str(path.with_suffix('.headers')), '-o', str(tmp), '-w', '%{http_code}', url], capture_output=True, text=True, timeout=250)
            if a.returncode != 0 or a.stdout not in ['200', '206']:
                raise RuntimeError('OAI_transfer_pending:curl=' + str(a.returncode) + ':HTTP=' + a.stdout)
            blob = tmp.read_bytes()
            parse_page(blob)
            os.replace(tmp, path)
            origin = 'HKUST3_DIRECT_no_proxy'
        put(path.with_suffix('.receipt.json'), dict(at_utc=now(), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size, transfer=origin, params=params))
    return parse_page(path.read_bytes())


def run(pilot):
    global STOP
    D.mkdir(exist_ok=True)
    lock = (engine.CONTROL / 'program.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda *_: globals().__setitem__('STOP', True))
    policy = D / 'policy.json'
    if not policy.exists():
        guard = json.loads((engine.CONTROL / 'resource_guard_v1/state.json').read_text())
        put(policy, dict(at_utc=now(), route='arxiv -> HKUST3 DIRECT', initial_cumulative_network_bytes=guard['observed_payload_bytes'], cumulative_budget_bytes=guard['network_payload_limit_bytes'], old_budget_not_reset=True, native_importer_changed=False, initial_papers=int(engine.connect(SOURCE / 'once.sqlite').execute('select count(*) from papers').fetchone()[0]), baseline_pairs=3759))
    cursor_path = D / 'cursor.json'
    cursor = json.loads(cursor_path.read_text()) if cursor_path.exists() else {'units': units(), 'pending_sources': {}, 'completed_metadata_pages': 0}
    state = DirectState(SOURCE, 'recent_AI')
    try:
        while not STOP:
            guard = json.loads((engine.CONTROL / 'resource_guard_v1/state.json').read_text())
            limit = guard['network_payload_limit_bytes'] - guard['observed_payload_bytes']
            if guard.get('stop') or limit <= 0:
                put(D / 'status.json', dict(at_utc=now(), status='blocked_existing_resource_budget', guard=guard, goal_complete=False))
                break
            engine.BUDGET = state.net_bytes + limit
            if state.access_denied:
                put(D / 'status.json', dict(at_utc=now(), status='blocked_remote_access_denied_403', pending_sources=len(cursor['pending_sources']), goal_complete=False))
                break
            ready = [v for v in cursor['pending_sources'].values() if v.get('retry_after_epoch', 0) <= time.time()][:16]
            if ready:
                completed, retry = state.direct_batch([v['paper'] for v in ready])
                for item in ready:
                    cursor['pending_sources'].pop(item['paper']['versioned_id'], None)
                for item in retry:
                    item['retry_after_epoch'] = time.time() + 60
                    cursor['pending_sources'][item['paper']['versioned_id']] = item
                put(cursor_path, cursor)
                if retry and not completed:
                    put(D / 'status.json', dict(at_utc=now(), status='source_transport_pending_retry', pending_sources=len(cursor['pending_sources']), next_retry_seconds=60, goal_complete=False))
                    for _ in range(60):
                        if STOP:
                            break
                        time.sleep(1)
                    continue
            available = [u for u in cursor['units'] if u['state'] == 'pending']
            if not available:
                put(D / 'status.json', dict(at_utc=now(), status='metadata_exhausted_with_pending_sources' if cursor['pending_sources'] else 'metadata_exhausted', pending_sources=len(cursor['pending_sources']), goal_complete=False))
                if cursor['pending_sources']:
                    time.sleep(5)
                    continue
                break
            unit = available[0]
            try:
                papers, next_token = metadata(unit)
                known = {r[0] for r in state.db.execute('select id from papers')}
                fresh = [p for p in papers if p['versioned_id'] not in known and p['arxiv_id'] not in state.inherited_ids]
                fresh.sort(key=lambda p: (p.get('source_size_estimate_bytes') is None, p.get('source_size_estimate_bytes') or 0, p['versioned_id']))
                if pilot:
                    fresh = [p for p in fresh if 65536 <= (p.get('source_size_estimate_bytes') or 0) <= 2 * 1024 ** 2][:2]
                put(D / 'latest_metadata.json', dict(at_utc=now(), unit=unit['key'], papers=len(papers), unseen_papers=len(fresh), cached_official_response=(unit['key'] == '202610_CL' and unit['page'] == 0), route='DIRECT', goal_complete=False))
                completed, pending = state.direct_batch(fresh)
                for item in pending:
                    item['retry_after_epoch'] = time.time() + 60
                    cursor['pending_sources'][item['paper']['versioned_id']] = item
                put(cursor_path, cursor)
                if pilot:
                    put(D / 'pilot_progress.json', dict(at_utc=now(), selected=fresh, papers_completed=completed, pending_sources=pending, downloaded_bytes=state.net_bytes, PDF_states=dict(state.pdf_counts), goal_complete=False))
                    break
                cursor['completed_metadata_pages'] += 1
                unit['page'] += 1
                unit['token'] = next_token
                if not next_token:
                    unit['state'] = 'metadata_exhausted_source_pending' if pending else 'done'
                put(cursor_path, cursor)
                put(D / 'status.json', dict(at_utc=now(), status='running', completed_metadata_pages=cursor['completed_metadata_pages'], pending_sources=len(cursor['pending_sources']), new_download_bytes_this_launch=state.net_bytes, goal_complete=False))
                time.sleep(3.3)
            except Exception as error:
                if not isinstance(error, (RuntimeError, engine.requests.RequestException)) and 'OAI_error:' not in str(error):
                    put(D / 'status.json', dict(at_utc=now(), status='failed_code_error', reason=type(error).__name__ + ':' + str(error), goal_complete=False))
                    raise
                unit['failures'] += 1
                delay = min(900, 30 * 2 ** min(unit['failures'], 5))
                unit['last_error'] = str(error)[:1500]
                if 'badResumptionToken' in str(error):
                    unit.update(token=None, page=0, generation=unit['generation'] + 1)
                put(cursor_path, cursor)
                put(D / 'status.json', dict(at_utc=now(), status='pending_retry', unit=unit['key'], reason=unit['last_error'], delay_seconds=delay, failures_not_counted_complete=True, goal_complete=False))
                print(json.dumps({'event': 'pending_retry', 'reason': unit['last_error'], 'delay': delay}), flush=True)
                if pilot:
                    break
                for _ in range(delay):
                    if STOP:
                        break
                    time.sleep(1)
    finally:
        state.close(finished=False)
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot2', action='store_true')
    args = parser.parse_args()
    run(args.pilot2)
