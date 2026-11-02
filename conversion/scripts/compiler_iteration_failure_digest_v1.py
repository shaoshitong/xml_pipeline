"""Batch failure taxonomy from one readonly run ledger; no case generation."""
import argparse
import collections
import datetime
import json
from pathlib import Path
import re
import sqlite3


def reasons(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('reason', 'error', 'error_type', 'diagnostic_stage') and isinstance(item, str):
                yield item
            elif key in ('failures', 'detail', 'quality_failures', 'issues'):
                yield from reasons(item)
    elif isinstance(value, list):
        for item in value:
            yield from reasons(item)
    elif isinstance(value, str):
        yield value


def signature(text):
    text = re.sub(r'[a-f0-9]{32,64}', '<HASH>', text)
    text = re.sub(r'/backup/\S+', '<PATH>', text)
    text = re.sub(r'[-+]?\b\d+(?:\.\d+)?(?:e[-+]?\d+)?\b', '<N>', text)
    return text[:900]


def digest(run, output):
    path = run / 'status.sqlite'
    db = sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True, timeout=30)
    db.execute('begin')
    counts = dict(db.execute('select status,count(*) from samples group by status'))
    phases, diagnostic, source_reasons, primary = (collections.Counter() for _ in range(4))
    errors = collections.Counter()
    examples = collections.defaultdict(list)
    infra = 0
    for identifier, text in db.execute("select id,result from samples where status='abandoned'"):
        row = json.loads(text)
        phases[str(row.get('phase'))] += 1
        diagnostic[str(row.get('diagnostic_stage'))] += 1
        source_reasons[str(row.get('source_reproduction_reason'))] += 1
        primary[str(row.get('reason'))] += 1
        infra += row.get('infrastructure_failure') is True
        observed = set()
        for field in ('quality_failures', 'detail', 'last_normalization_failure'):
            observed.update(signature(x) for x in reasons(row.get(field)) if x)
        for reason in observed:
            errors[reason] += 1
            if len(examples[reason]) < 3:
                examples[reason].append(identifier)
    db.close()
    result = dict(schema='compiler_iteration_failure_digest_v1', at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  run=str(run), ledger_counts=counts, failure_rows=counts.get('abandoned', 0),
                  phases=dict(phases), diagnostic_stages=dict(diagnostic), source_reproduction_reasons=dict(source_reasons),
                  primary_reasons=dict(primary), infrastructure_failure_rows=infra,
                  failure_signatures=[dict(reason=k, affected_rows=v, example_ids=examples[k]) for k,v in errors.most_common(30)],
                  interpretation='All failure rows remain pending repair, not irrecoverable inputs. Signatures can overlap within a sample.',
                  source_or_image_payloads_read=False, model_calls=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('failure_digest_snapshot_exists')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    digest(args.run, args.output)
