"""Resume failed metadata partitions without resetting any paper/PDF once claim.

Uses the unchanged v3.1 import/render procedure and the existing VPS transport.
Only metadata discovery is repartitioned into days and transient API failures
receive bounded backoff. The existing cumulative resource guard remains active.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

R = Path('/backup/shaoshitong/img2code_20261029')
sys.path.insert(0, str(R / 'conversion/scripts'))
import arxiv_parallel_pipeline_v3_1 as prior

engine = prior.engine
D = engine.P / 'recent_ai_source_expansion_v2'
C = engine.CONTROL


def repartition(cursor):
    changed = []
    keys = {u['key'] for u in cursor['units']}
    for unit in list(cursor['units']):
        if unit['state'] != 'typed_failure' or len(unit['key']) != 6:
            continue
        unit['state'] = 'partitioned_for_metadata_recovery_v3_2'
        unit['prior_failure_count_preserved'] = unit['failures']
        added = []
        for day in engine.inventory.split_days(unit):
            if day['key'] not in keys:
                day['origin_failed_month'] = unit['key']
                cursor['units'].append(day)
                keys.add(day['key'])
                added.append(day['key'])
        changed.append({'month': unit['key'], 'new_daily_partitions': len(added)})
    if changed:
        cursor['position'] = next(i for i, u in enumerate(cursor['units']) if u['state'] == 'pending')
    return changed


class RetryMetadataState(prior.UnicodeSafeState):
    def request(self, url, stream=False, headers=None, api=False):
        if not api:
            return super().request(url, stream=stream, headers=headers, api=api)
        for attempt in range(4):
            try:
                return super().request(url, stream=stream, headers=headers, api=True)
            except engine.requests.RequestException as error:
                response = getattr(error, 'response', None)
                status = getattr(response, 'status_code', None)
                transient = status in (429, 500, 502, 503, 504) or isinstance(error, (engine.requests.Timeout, engine.requests.ConnectionError))
                if not transient or attempt == 3:
                    raise
                retry = response.headers.get('Retry-After', '') if response is not None else ''
                delay = max(30 * 2 ** attempt, min(900, int(retry)) if retry.isdigit() else 0)
                self.emit('metadata_transient_backoff_v3_2', http_status=status, attempt=attempt + 1, delay_seconds=delay)
                time.sleep(delay)


def main():
    lock = (C / 'program.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = D / 'cursor.parallel_v3.json'
    original = path.read_bytes()
    cursor = json.loads(original)
    proof = C / 'metadata_recovery_v3_2'
    proof.mkdir(exist_ok=True)
    backup = proof / ('cursor_before_' + hashlib.sha256(original).hexdigest() + '.json')
    if not backup.exists():
        backup.write_bytes(original)
    changes = repartition(cursor)
    if changes:
        engine.native.atomic(path, cursor)
    engine.native.atomic(proof / 'repartition.json', {'at_utc': engine.now(), 'old_cursor_sha256': hashlib.sha256(original).hexdigest(), 'failed_months_repartitioned': changes, 'pending_daily_partitions': sum(u['state'] == 'pending' for u in cursor['units']), 'paper_and_PDF_once_ledgers_unchanged': True, 'official_import_render_code_unchanged': True, 'route_unchanged': True})
    fcntl.flock(lock, fcntl.LOCK_UN)
    lock.close()
    engine.State = RetryMetadataState
    engine.run()


if __name__ == '__main__':
    main()
