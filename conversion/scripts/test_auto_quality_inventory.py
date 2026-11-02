"""Exercise routing, revision replacement, ownership and unchanged source jobs."""
import json
import sqlite3
import tempfile
from pathlib import Path

from auto_quality_inventory import TABLE, classify, refresh, throughput


def record(fmt, n, **extra):
    return {'source_format': fmt, 'code_sha256': '%064x' % n,
            'image_sha256': '%064x' % (n + 100), **extra}


with tempfile.TemporaryDirectory(prefix='inventory_test_') as directory:
    root = Path(directory)
    (root / 'conversion').mkdir()
    database = root / 'conversion/jobs.sqlite'
    db = sqlite3.connect(database)
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,format TEXT,state TEXT,worker_pid INT,output_record TEXT)')
    cases = [
        ('low_score', 'mermaid', 'needs_quality_repair', None,
         record('mermaid', 1, metrics={'original_reference_ssim_512': 0.0})),
        ('owned', 'svg', 'rendered', 123456, record('svg', 2)),
        ('done', 'svg', 'accepted', None, record('svg', 3)),
        ('no_payload', 'html', 'queued_html_v3', None, None),
        ('failed_empty', 'tikz', 'needs_fallback', None, None),
        ('literal', 'tikz', 'needs_quality_repair', None,
         record('tikz', 4, connectivity={'complete': True},
                conversion_method='source_named_tikz_nodes_and_native_bound_paths_v1')),
        ('unbound', 'tikz', 'needs_quality_repair', None, record('tikz', 5)),
        ('native', 'drawio', 'rendered', None, record('drawio', 6)),
        ('vector', 'python', 'harness_review_pending', None, record('python', 7)),
        ('malformed', 'svg', 'rendered', None, '{broken'),
        ('running_without_owner', 'svg', 'svg_converting', None, record('svg', 8)),
    ]
    values = [(i, f, s, o, json.dumps(r) if isinstance(r, dict) else r)
              for i, f, s, o, r in cases]
    db.executemany('INSERT INTO jobs VALUES(?,?,?,?,?)', values)
    db.commit()
    before = db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
    first = refresh(root, len(cases))
    assert first['totals']['total_jobs'] == len(cases)
    assert first['totals']['accepted'] == 1
    assert first['policy']['all_input_jobs_accounted_for']
    assert first['routes'] == {'graph': 2, 'defer': 2, 'accepted': 1, 'wait': 1, 'repair': 3, 'native': 1, 'vector': 1}
    queue = dict(db.execute('SELECT id,route FROM ' + TABLE))
    assert queue == {'low_score': 'graph', 'literal': 'graph', 'unbound': 'repair',
                     'native': 'native', 'vector': 'vector'}
    assert before == db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
    # Once another worker owns an indexed revision, inventory removes its own
    # stale row without resetting that owner or modifying the candidate.
    db.execute('UPDATE jobs SET worker_pid=77 WHERE id="low_score"')
    # A replacement revision retires the old key and inserts the new current key.
    new = record('drawio', 22)
    db.execute('UPDATE jobs SET output_record=? WHERE id="native"', (json.dumps(new),))
    db.commit()
    snapshot_before_second = db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
    second = refresh(root, len(cases))
    assert snapshot_before_second == db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
    assert not db.execute('SELECT 1 FROM ' + TABLE + ' WHERE id="low_score"').fetchone()
    assert db.execute('SELECT code_hash FROM ' + TABLE + ' WHERE id="native"').fetchone() == (new['code_sha256'],)
    assert second['candidate_index']['stale_revisions_removed'] == 2
    assert second['throughput']['native_candidate_net_change'] == 0
    assert second['throughput']['accepted_net_change'] == 0
    # Full scope mismatch is an error, not silent truncation or passing subset.
    try:
        refresh(root, len(cases) + 1)
    except AssertionError:
        pass
    else:
        raise AssertionError('scope mismatch accepted')
    db.close()

rate = throughput({'observed_at_utc': '2026-10-31T00:00:00+00:00',
                   'totals': {'candidates_with_output_record': 100, 'accepted': 3}},
                  {'observed_at_utc': '2026-10-31T00:01:00+00:00',
                   'totals': {'candidates_with_output_record': 110, 'accepted': 4}})
assert rate['native_candidate_net_pairs_per_hour'] == 600
assert rate['accepted_net_pairs_per_hour'] == 60
print(json.dumps({'ok': True, 'checks': ['scope complete', 'low score retained',
      'owned and nonidle deferred', 'accepted not requeued', 'malformed tracked',
      'unbound TikZ repaired', 'jobs unchanged', 'stale revisions retired',
      'replacement exact revision', 'net throughput']}))
