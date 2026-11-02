"""Compact, read-only progress and failure telemetry for the fixed SVG program."""
from pathlib import Path
import collections
import datetime
import json
import sqlite3
import statistics

R = Path('/backup/shaoshitong/img2code_20261029')
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='svg_complex_symbol_viewport_unseen100_20261102_v7');NAME=parser.parse_args().run_id
assert NAME and all(c.isalnum()or c in '-_'for c in NAME)
P = R / 'release/compiler_iterations/programs' / NAME

def read(path):
    return json.loads(path.read_text()) if path.exists() else None

def identity(owner):
    if not owner:
        return None
    proc = Path('/proc') / str(owner['pid'])
    try:
        fields = (proc / 'stat').read_text().rsplit(') ', 1)[1].split()
        return dict(pid=owner['pid'], same_birth=int(fields[19]) == owner['start_ticks'],
                    live=fields[0] != 'Z', state=fields[0])
    except FileNotFoundError:
        return dict(pid=owner['pid'], live=False, missing=True)

def main():
    out = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               state=read(P / 'state.json'), process=identity(read(P / 'owner.json')),
               failure=read(P / 'failure.json'))
    for phase in ('B', 'C', 'mass'):
        run = R / 'release/compiler_iterations/runs' / (NAME + '_' + phase)
        if not (run / 'status.sqlite').exists():
            continue
        with sqlite3.connect((run / 'status.sqlite').as_uri() + '?mode=ro', uri=True, timeout=5) as db:
            counts = dict(db.execute('select status,count(*) from samples group by status'))
            results = [json.loads(row[0]) for row in db.execute('select result from samples where result is not null')]
        reasons = collections.Counter()
        source_reasons = collections.Counter()
        seconds = []
        for result in results:
            reasons.update([str(result.get('detail') or result.get('reason'))])
            if result.get('quality_report'):
                report = read(R / result['quality_report'])
                if report:
                    seconds.append(report['seconds'])
                    source = report.get('checks', {}).get('source', {})
                    source_reasons.update(str(row.get('reason')) for row in source.get('failures', []))
        out[phase] = dict(evaluation='old_baseline' if phase == 'B' else 'new_frontend',
            counts=counts, completed=len(results), reasons=dict(reasons), source_reasons=dict(source_reasons),
            infrastructure_failures=sum(r.get('infrastructure_failure') is True for r in results),
            cleanup_complete=sum(r.get('case_cleanup_complete') is True for r in results),
            quality_seconds=dict(mean=round(statistics.mean(seconds), 3), total=round(sum(seconds), 3)) if seconds else None,
            process=identity(read(run / 'owner.json')), infrastructure_stop=read(run / 'infrastructure_stop.json'))
    print(json.dumps(out))

if __name__ == '__main__':
    main()
