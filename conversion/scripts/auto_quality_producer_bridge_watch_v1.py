"""Small serialized 60-second queue bridge; never starts a model call."""
import argparse
import fcntl
import hashlib
import json
import os
import signal
import time
from pathlib import Path

import auto_quality_producer_bridge_v1 as bridge

STOP = False


def stop(*_):
    global STOP
    STOP = True


def atomic(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=bridge.R)
    p.add_argument('--interval', type=float, default=60)
    p.add_argument('--limit', type=int, default=10000)
    p.add_argument('--ticks', type=int, default=0, help='0 means watch until signalled')
    p.add_argument('--publish', action='store_true')
    args = p.parse_args(argv)
    if args.interval < 60 or not 1 <= args.limit <= 10000 or args.ticks < 0:
        p.error('interval >= 60, limit 1..10000 and ticks >= 0 required')
    work = args.root / 'conversion'
    lock = (work / 'auto_quality_producer_bridge_watch_v1.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for sig in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    pins = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path(bridge.__file__), Path(bridge.core.__file__))}
    owner = {'pid': os.getpid(), 'started_at_utc': bridge.now(), 'interval_seconds': args.interval,
             'limit': args.limit, 'publish': args.publish, 'pins': pins,
             'scope': 'Idle quality_v3 holds with exact committed current QA3 geometry/visual failure. No model API calls.'}
    atomic(work / 'auto_quality_producer_bridge_v1_owner.json', owner)
    ticks = released = errors = 0
    while not STOP and (not args.ticks or ticks < args.ticks):
        for name, digest in pins.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Bridge implementation changed: ' + name)
        try:
            result = bridge.run_once(root=args.root, limit=args.limit, enabled=args.publish)
            released += result['released']
        except Exception as exc:
            errors += 1
            result = {'at': bridge.now(), 'released': 0, 'error': str(exc)[:1000]}
        ticks += 1
        summary = {**owner, 'at': bridge.now(), 'ticks': ticks, 'total_released': released,
                   'tick_errors': errors, 'last_tick': result, 'model_calls_started_by_bridge': 0}
        atomic(work / 'auto_quality_producer_bridge_v1_summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        deadline = time.monotonic() + args.interval
        while not STOP and time.monotonic() < deadline and (not args.ticks or ticks < args.ticks):
            time.sleep(min(1, deadline - time.monotonic()))
    atomic(work / 'auto_quality_producer_bridge_v1_owner.json', {**owner, 'finished_at_utc': bridge.now(), 'ticks': ticks, 'total_released': released})


if __name__ == '__main__':
    main()
