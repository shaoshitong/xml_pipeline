"""Prioritize new source-execution/Range revisions in the disposable QA index."""
import argparse
import fcntl
import json
import os
import sqlite3
import time
from pathlib import Path
from durable_sqlite import begin, commit
from native_worker import W, now


def refresh():
    db = sqlite3.connect(W / 'jobs.sqlite', timeout=2)
    owner = json.loads((W / 'auto_quality_owner.json').read_text())
    process = Path('/proc') / str(owner['pid']) / 'cmdline'
    assert process.exists() and b'auto_quality_batch_v4b.py' in process.read_bytes(), 'Expected live QA4b coordinator'
    begin(db)
    changed = db.execute('''update auto_quality_candidates_v1 as c set priority=2000
      where c.priority<2000 and exists(select 1 from auto_quality_inventory_rows_v2 r
        where r.id=c.id and r.code_hash=c.code_hash and r.image_hash=c.image_hash
        and (r.method='actual_pgf_execution_named_graph_painted_native_markers_v3'
             or r.method like '%_actual_range_glyph_alignment_v3'
             or r.method like '%_measured_source_space_advances_and_fixed_clip_glyphs_v5'
             or r.format in ('drawio','xml')))
      and not exists(select 1 from auto_quality_audits_v1 a where a.id=c.id
        and a.code_hash=c.code_hash and a.image_hash=c.image_hash and a.policy=?)''', (owner['policy'],)).rowcount
    commit(db)
    db.close()
    result = {'at': now(), 'pid': os.getpid(), 'qa_policy': owner['policy'], 'prioritized_current_revisions': changed,
              'jobs_or_payloads_modified': False, 'acceptance_rules_modified': False}
    (W / 'auto_quality_fastlane_v4b_runtime.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    lock = (W / 'auto_quality_fastlane_v4b.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (W / 'auto_quality_fastlane_v4b_owner.json').write_text(json.dumps({'pid': os.getpid(), 'at': now(), 'watch': args.watch}) + '\n')
    while True:
        print(json.dumps(refresh()), flush=True)
        if not args.watch:
            break
        time.sleep(30)
