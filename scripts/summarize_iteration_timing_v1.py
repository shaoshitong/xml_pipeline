"""Read actual queue timestamps; never start, resume, or modify a run.

Execute on HKUST through stdin. Wall duration is not CPU usage or model thinking.
"""
from pathlib import Path
import collections
import datetime
import json
import sqlite3
import time

R = Path('/backup/shaoshitong/img2code_20261029')
RUN = 'svg_complex_semantic_admission_unseen_20261102_v8'


def timestamp(value):
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def phase(name):
    path = R / 'release/compiler_iterations/runs' / (RUN + '_' + name) / 'status.sqlite'
    if not path.exists():
        return None
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(
            'select id,status,started_at,finished_at,result from samples order by seq')]
    started = [timestamp(row['started_at']) for row in rows if row['started_at']]
    ended = [timestamp(row['finished_at']) for row in rows if row['finished_at']]
    durations = sorted(timestamp(row['finished_at']) - timestamp(row['started_at'])
                       for row in rows if row['started_at'] and row['finished_at'])
    reasons = collections.Counter()
    infrastructure = 0
    for row in rows:
        if not row['result']:
            continue
        result = json.loads(row['result'])
        infrastructure += result.get('infrastructure_failure') is True
        if row['status'] != 'qualified':
            details = result.get('quality_failures') or result.get('detail') or []
            if isinstance(details, list) and details and isinstance(details[0], dict):
                reason = details[0].get('reason') or result.get('reason', 'unknown')
            else:
                reason = result.get('reason', 'unknown')
            reasons[str(reason)[:240]] += 1
    counts = dict(collections.Counter(row['status'] for row in rows))
    finished = bool(rows) and len(ended) == len(rows)
    wall = ((max(ended) if finished else time.time()) - min(started)) if started else 0
    return dict(
        total=len(rows), counts=counts, finished=finished,
        measured_completed=len(durations),
        measured_wall_seconds=round(wall, 2),
        per_case_wall_seconds_mean=round(sum(durations) / len(durations), 2) if durations else None,
        per_case_wall_seconds_p50=round(durations[len(durations) // 2], 2) if durations else None,
        per_case_wall_seconds_p95=round(durations[min(len(durations) - 1, int(len(durations) * .95))], 2) if durations else None,
        infrastructure_failures=infrastructure,
        failure_reasons=dict(reasons.most_common(8)),
        elapsed_measures_remote_work_not_HTTP_or_model_thinking=True,
    )


def main():
    started = time.monotonic()
    program = R / 'release/compiler_iterations/programs' / RUN
    handle = json.loads((program / 'launch.json').read_text()) if (program / 'launch.json').exists() else None
    state = json.loads((program / 'state.json').read_text())
    stages = {name: phase(name) for name in ('B', 'C', 'mass')}
    print(json.dumps(dict(
        at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        program=str(program), handle=handle, state=state, phases=stages,
        query_processing_seconds=round(time.monotonic() - started, 4),
        read_only=True, goal_complete=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
