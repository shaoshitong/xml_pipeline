"""Dirty versions: same/backdated timestamp, rollback, writers and snapshot race."""
import json
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

from auto_quality_inventory_v2 import (CACHE, DIRTY, TABLE, TRIGGERS, initialize,
                                       refresh)


def record(n, text_size=0):
    return json.dumps({'source_format': 'mermaid', 'conversion_method': 'fixture',
       'code_sha256': '%064x' % n, 'image_sha256': '%064x' % (n + 100),
       'metrics': {'original_reference_ssim_512': 0.0},
       'font_payload_fixture': 'X' * text_size})


def make(root, n=3, text_size=0):
    (root / 'conversion').mkdir()
    db = sqlite3.connect(root / 'conversion/jobs.sqlite')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,format TEXT,state TEXT,worker_pid INT,updated_at TEXT,output_record TEXT)')
    db.executemany('INSERT INTO jobs VALUES(?,"mermaid","needs_quality_repair",NULL,"2026-10-31T00:00:00+00:00",?)',
                   [(str(i), record(i + 1, text_size)) for i in range(n)])
    db.commit()
    return db


checks = []
with tempfile.TemporaryDirectory(prefix='inventory_v2_test_') as directory:
    root = Path(directory)
    db = make(root, text_size=256 * 1024)
    original_jobs = db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
    first = refresh(root, 3)
    assert first['incremental']['large_payloads_parsed'] == 3
    assert first['candidate_index']['current_rows_by_route'] == {'graph': 3}
    assert original_jobs == db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
    second = refresh(root, 3)
    assert second['incremental']['large_payloads_parsed'] == 0
    assert second['incremental']['large_payloads_reused'] == 3
    assert second['candidate_index']['upserted_current_revisions'] == 0
    checks += ['bootstrap scope complete', 'jobs unchanged', 'unchanged large payloads not reparsed']
    # Claim and release with the same timestamp; no large JSON needs decoding.
    db.execute('UPDATE jobs SET state="repair_running",worker_pid=88 WHERE id="0"')
    db.commit()
    report = refresh(root, 3)
    assert report['incremental']['large_payloads_parsed'] == 0
    assert report['routes']['defer'] == 1
    assert not db.execute('SELECT 1 FROM ' + TABLE + ' WHERE id="0"').fetchone()
    db.execute('UPDATE jobs SET state="needs_quality_repair",worker_pid=NULL WHERE id="0"')
    db.commit()
    assert refresh(root, 3)['candidate_index']['current_rows_by_route'] == {'graph': 3}
    checks += ['same timestamp claim/release detected without payload parse']
    # Same timestamp, same length, same state: changed XML/PNG revision still seen.
    before = db.execute('SELECT length(CAST(output_record AS BLOB)) FROM jobs WHERE id="1"').fetchone()[0]
    db.execute('UPDATE jobs SET output_record=? WHERE id="1"', (record(44, 256 * 1024),))
    db.commit()
    assert db.execute('SELECT length(CAST(output_record AS BLOB)) FROM jobs WHERE id="1"').fetchone()[0] == before
    report = refresh(root, 3)
    assert report['incremental']['large_payloads_parsed'] == 1
    assert report['incremental']['same_timestamp_dirty_rows'] == 1
    assert db.execute('SELECT code_hash FROM ' + TABLE + ' WHERE id="1"').fetchone()[0] == '%064x' % 44
    # Backdating a publication cannot bypass monotone dirty version.
    db.execute('UPDATE jobs SET output_record=?,updated_at="2000-01-01T00:00:00+00:00" WHERE id="1"', (record(45, 256 * 1024),))
    db.commit()
    assert refresh(root, 3)['incremental']['large_payloads_parsed'] == 1
    assert db.execute('SELECT code_hash FROM ' + TABLE + ' WHERE id="1"').fetchone()[0] == '%064x' % 45
    checks += ['same timestamp same-length revision detected', 'backdated publication detected']
    # Trigger writes are in the writer's transaction, not irreversible side effects.
    version = db.execute('SELECT * FROM ' + DIRTY + ' WHERE id="1"').fetchone()
    db.execute('UPDATE jobs SET output_record=? WHERE id="1"', (record(46, 256 * 1024),))
    assert db.execute('SELECT * FROM ' + DIRTY + ' WHERE id="1"').fetchone() != version
    db.rollback()
    assert db.execute('SELECT * FROM ' + DIRTY + ' WHERE id="1"').fetchone() == version
    assert refresh(root, 3)['incremental']['large_payloads_parsed'] == 0
    checks += ['writer rollback restores journal exactly']
    # A concurrent writer commits after inventory's read snapshot but before its
    # cache/queue publication. Old revision must not be queued, nor dirty lost.
    errors = []
    def publish_new_revision():
        def writer():
            try:
                writer_db = sqlite3.connect(root / 'conversion/jobs.sqlite', timeout=10)
                writer_db.execute('UPDATE jobs SET output_record=? WHERE id="2"', (record(61, 256 * 1024),))
                writer_db.commit()
                writer_db.close()
            except Exception as exc:
                errors.append(repr(exc))
        thread = threading.Thread(target=writer)
        thread.start()
        thread.join(10)
        assert not thread.is_alive()
    refresh(root, 3, _after_snapshot=publish_new_revision)
    assert not errors
    assert not db.execute('SELECT 1 FROM ' + TABLE + ' WHERE id="2"').fetchone()
    report = refresh(root, 3)
    assert report['incremental']['large_payloads_parsed'] == 1
    assert db.execute('SELECT code_hash FROM ' + TABLE + ' WHERE id="2"').fetchone()[0] == '%064x' % 61
    checks += ['snapshot-late concurrent writer cannot enqueue stale revision', 'new dirty version survives cache publication']
    # Deletion/replacement with unchanged total scope retires the old cache key.
    db.execute('DELETE FROM jobs WHERE id="2"')
    db.execute('INSERT INTO jobs VALUES("new","mermaid","needs_quality_repair",NULL,"2000-01-01",?)', (record(71),))
    db.commit()
    report = refresh(root, 3)
    assert report['incremental']['deleted_cache_rows'] == 1
    assert not db.execute('SELECT 1 FROM ' + CACHE + ' WHERE id="2"').fetchone()
    assert db.execute('SELECT 1 FROM ' + TABLE + ' WHERE id="new"').fetchone()
    checks += ['same-count ID replacement detected']
    db.close()

# Measure short existing-style state writers with a large output record, both
# without and with the journal. This is a diagnostic, not a brittle speed test.
benchmarks = {}
for with_journal in (False, True):
    with tempfile.TemporaryDirectory(prefix='inventory_v2_writer_bench_') as directory:
        root = Path(directory)
        db = make(root, n=8, text_size=256 * 1024)
        if with_journal:
            initialize(db)
        db.close()
        errors = []
        def writer(offset):
            try:
                connection = sqlite3.connect(root / 'conversion/jobs.sqlite', timeout=20)
                connection.execute('PRAGMA busy_timeout=20000')
                for i in range(80):
                    identifier = str(offset + i % 4)
                    connection.execute('UPDATE jobs SET state=?,worker_pid=?,updated_at=? WHERE id=?',
                         ('repair_running' if i % 2 else 'needs_quality_repair',
                          100 + offset if i % 2 else None, '2026-10-31T00:00:00+00:00', identifier))
                    if i % 11:
                        connection.commit()
                    else:
                        connection.rollback()
                connection.close()
            except Exception as exc:
                errors.append(repr(exc))
        start = time.monotonic()
        threads = [threading.Thread(target=writer, args=(offset,)) for offset in (0, 4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
            assert not thread.is_alive(), 'writer stalled'
        elapsed = time.monotonic() - start
        assert not errors, errors
        db = sqlite3.connect(root / 'conversion/jobs.sqlite')
        if with_journal:
            # 8 seeded rows plus 2*72 committed UPDATEs, and no payload writes.
            assert db.execute('SELECT sum(version) FROM ' + DIRTY).fetchone()[0] == 8 + 2 * 72
            assert db.execute('SELECT sum(payload_version) FROM ' + DIRTY).fetchone()[0] == 8
        db.close()
        benchmarks['journal' if with_journal else 'baseline'] = {
            'writer_threads': 2, 'attempted_updates': 160, 'committed_updates': 144,
            'rolled_back_updates': 16, 'payload_bytes_per_job': 256 * 1024,
            'elapsed_seconds': round(elapsed, 6), 'errors': errors}
checks += ['two concurrent existing-style writers finish without lock failure',
           'journal counts only committed writes', 'state writes do not mark payload dirty']
print(json.dumps({'ok': True, 'checks': checks, 'writer_benchmark': benchmarks}))
