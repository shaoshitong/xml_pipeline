"""Idempotent launcher for direct acquisition; never resets cumulative budget."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import subprocess

R = Path('/backup/shaoshitong/img2code_20261029')
P = R / 'clean/arxiv_research_figures_v1'
C = P / 'transport_performance_v3'
D = P / 'oai_direct_pipeline_v1'


def birth(pid):
    p = Path('/proc', str(pid), 'stat')
    if not p.exists():
        return None
    fields = p.read_text().rsplit(')', 1)[1].split()
    return fields[19] if fields[0] != 'Z' else None


def main():
    D.mkdir(exist_ok=True)
    receipt = D / 'launch.json'
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if birth(old['pid']) == old['birth_ticks']:
            print(json.dumps(dict(already_running=True, **old)))
            return
    lock = (C / 'program.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pilot = json.loads((D / 'pilot_progress.json').read_text())
    assert pilot['downloaded_bytes'] > 0 and pilot['papers_completed'] == 2 and not pilot['pending_sources']
    assert len(pilot['selected']) == 2
    for paper in pilot['selected']:
        folder = P / 'recent_ai_source_expansion_v2/papers' / paper['versioned_id']
        data = json.loads((folder / 'source_receipt.json').read_text())
        assert hashlib.sha256((folder / 'source.archive').read_bytes()).hexdigest() == data['sha256']
        assert data['new_transport'] == 'HKUST3_DIRECT_no_proxy'
        assert json.loads((folder / 'record.json').read_text())['status'] == 'source_completed'
    for name, expected in json.loads((C / 'procedure_pins.v3_1.json').read_text()).items():
        assert hashlib.sha256((R / name).read_bytes()).hexdigest() == expected, name
    guard_before = json.loads((C / 'resource_guard_v1/state.json').read_text())
    assert not guard_before.get('stop')
    script = R / 'conversion/scripts/arxiv_oai_direct_pipeline_v1.py'
    command = ['/home/shaoshitong/anaconda3/bin/python', '-u', str(script)]
    # Preserve the last launch's telemetry before initializing per-launch counters.
    previous = C / 'recent_AI.performance.json'
    history = D / 'launch_history'
    history.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if previous.exists():
        (history / (stamp + '.prior_performance.json')).write_bytes(previous.read_bytes())
        initial = json.loads(previous.read_text())
        initial.update(new_source_network_bytes=0, route='arxiv -> HKUST3 DIRECT', phase='new_launch_starting')
        previous.write_text(json.dumps(initial, indent=2) + '\n')
    if (C / 'launch.json').exists():
        (history / (stamp + '.prior_launch.json')).write_bytes((C / 'launch.json').read_bytes())
    fcntl.flock(lock, fcntl.LOCK_UN)
    lock.close()
    with (D / 'program.log').open('ab') as log:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONPATH=str(R / 'env')))
    row = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), pid=child.pid, birth_ticks=birth(child.pid), command=command, source_sha256=hashlib.sha256(script.read_bytes()).hexdigest(), route='arxiv -> HKUST3 DIRECT', VPS_used=False, Mac_in_data_path=False, download_workers=8, native_import_workers=8, metadata_connections=1, cumulative_guard_before=guard_before, existing_budget_not_reset=True, external_models=0)
    for path in [receipt, C / 'launch.json']:
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(row, indent=2) + '\n')
        os.replace(tmp, path)
    print(json.dumps({k: v for k, v in row.items() if k != 'cumulative_guard_before'}))


if __name__ == '__main__':
    main()
