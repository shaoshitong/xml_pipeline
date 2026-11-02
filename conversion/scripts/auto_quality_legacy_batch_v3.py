"""Batch revalidate every legacy acceptance through the current independent QA.

The private ledger claims diagnostics only; it never steals a job/model owner.
Passing pairs upgrade to the automatic policy. Failed pairs retain all payloads
and reenter typed repair queues, rather than remaining falsely accepted.
"""
import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

import auto_quality_batch_v2 as quality
import auto_quality_publication_v3 as publication
from auto_quality_dispatch_v2 import initialize
from durable_sqlite import begin, commit
from native_worker import R, W, now

TABLE = 'auto_quality_legacy_revalidation_v3'
PIN = hashlib.sha256(Path(publication.__file__).read_bytes()).hexdigest()


def initialize_ledger(db):
    begin(db)
    db.execute('create table if not exists ' + TABLE + '''(
      id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,mode TEXT,
      state TEXT,owner_pid INTEGER,record TEXT,updated_at TEXT,
      primary key(id,code_hash,image_hash,policy,mode))''')
    db.execute('create table if not exists auto_quality_audits_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy))')
    db.execute('create table if not exists auto_quality_exceptions_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,route TEXT,state TEXT,reason TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy))')
    initialize(db)
    commit(db)


def select(db, mode):
    guards = ''
    for table in publication.MODEL_TABLES:
        if not db.execute('select 1 from sqlite_master where type=\'table\' and name=?', (table,)).fetchone():
            continue
        columns = {r[1] for r in db.execute('pragma table_info(' + table + ')')}
        condition = "h.state='running'" + (' or h.worker_pid is not NULL' if 'worker_pid' in columns else '')
        guards += ' and not exists(select 1 from ' + table + ' h where h.id=j.id and (' + condition + '))'
    return db.execute('''select j.id,j.state,j.output_record,j.input_record,'native'
      from jobs j where j.state='accepted' and j.worker_pid is NULL
      and json_extract(j.output_record,'$.automatic_quality_policy') is NULL
      ''' + guards + '''
      and not exists(select 1 from ''' + TABLE + ''' l where l.id=j.id
        and l.code_hash=json_extract(j.output_record,'$.code_sha256')
        and l.image_hash=json_extract(j.output_record,'$.image_sha256')
        and l.policy=? and l.mode=? and
        (l.state not in ('worker_error','recovered_abandoned') or
         coalesce(json_extract(l.record,'$.ledger_attempt'),1)>=2)) order by j.id limit 1''', (quality.POLICY, mode)).fetchone()


def recover_dead(db):
    """Recover private claims only after proving the old coordinator has exited."""
    recovered = []
    for row in db.execute('select id,code_hash,image_hash,policy,mode,owner_pid,record from ' + TABLE + " where state='running'").fetchall():
        identifier, code, image, policy, mode, pid, previous_raw = row
        process = Path('/proc') / str(pid) / 'cmdline'
        command = process.read_bytes().replace(b'\0', b' ').decode() if process.exists() else ''
        if 'auto_quality_legacy_batch_v3.py' in command:
            continue
        receipt = db.execute('select state,record from auto_quality_audits_v1 where id=? and code_hash=? and image_hash=? and policy=?', (identifier, code, image, policy)).fetchone()
        previous = json.loads(previous_raw) if previous_raw else {}
        if receipt and mode == 'publish' and receipt[0] in ('accepted', 'repair_required', 'stale_revision'):
            stage, raw = receipt
            report = json.loads(raw)
        else:
            stage = 'recovered_abandoned'
            report = {'id': identifier, 'accepted': False, 'old_owner_pid': pid, 'old_owner_command': command,
                      'old_owner_terminal': True, 'at': now()}
        report['ledger_attempt'] = previous.get('ledger_attempt', 1)
        begin(db)
        db.execute('update ' + TABLE + ' set state=?,record=?,updated_at=? where id=? and code_hash=? and image_hash=? and policy=? and mode=? and state=\'running\' and owner_pid=?', (stage, json.dumps(report), now(), identifier, code, image, policy, mode, pid))
        commit(db)
        recovered.append({'id': identifier, 'state': stage, 'old_owner_pid': pid})
    return recovered


def run(args):
    lock = (W / 'auto_quality_legacy_v3.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = sqlite3.connect(W / 'jobs.sqlite', timeout=2)
    initialize_ledger(db)
    recoveries = recover_dead(db)
    mode = 'publish' if args.publish else 'diagnostic'
    owner = {'pid': os.getpid(), 'workers': 1, 'policy': quality.POLICY, 'publish': args.publish, 'at': now(), 'recovered_private_claims': recoveries}
    (W / 'auto_quality_legacy_v3_owner.json').write_text(json.dumps(owner) + '\n')
    counts = {}
    total = 0
    started = time.monotonic()
    while not args.limit or total < args.limit:
        assert hashlib.sha256(Path(publication.__file__).read_bytes()).hexdigest() == PIN, 'Publication implementation changed'
        quality.ensure_pinned()
        item = select(db, mode)
        if not item:
            break
        identifier, state, raw, input_raw, route = item
        record = json.loads(raw)
        key = (identifier, record['code_sha256'], record['image_sha256'], quality.POLICY, mode)
        begin(db)
        current = db.execute('select state,output_record,input_record,worker_pid from jobs where id=?', (identifier,)).fetchone()
        if current != (state, raw, input_raw, None):
            db.rollback()
            continue
        prior = db.execute('select record from ' + TABLE + ' where id=? and code_hash=? and image_hash=? and policy=? and mode=?', key).fetchone()
        attempt = (json.loads(prior[0]).get('ledger_attempt', 1) if prior and prior[0] else 0) + 1
        db.execute('insert or replace into ' + TABLE + ' values(?,?,?,?,?,\'running\',?,?,?)', (*key, os.getpid(), json.dumps({'ledger_attempt': attempt}), now()))
        commit(db)
        try:
            item, report, out, folder = quality.verify(item)
            if args.publish:
                publication.publish(db, item, report, out, folder, True, quality.POLICY)
            else:
                report['diagnostic_only'] = True
            stage = report['state']
        except Exception as exc:
            if db.in_transaction:
                db.rollback()
            report = {'id': identifier, 'state': 'worker_error', 'accepted': False, 'error': repr(exc), 'at': now()}
            stage = 'worker_error'
        report['ledger_attempt'] = attempt
        begin(db)
        db.execute('update ' + TABLE + ' set state=?,record=?,updated_at=? where id=? and code_hash=? and image_hash=? and policy=? and mode=? and owner_pid=?', (stage, json.dumps(report, ensure_ascii=False), now(), *key, os.getpid()))
        commit(db)
        counts[stage] = counts.get(stage, 0) + 1
        total += 1
        runtime = {**owner, 'at': now(), 'processed': total, 'counts': counts, 'elapsed_seconds': time.monotonic() - started, 'goal_complete': False}
        (W / 'auto_quality_legacy_v3_runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
        print(json.dumps({'at': now(), 'id': identifier, 'stage': stage, 'failures': report.get('failures'), 'error': report.get('error')}, ensure_ascii=False), flush=True)
    print(json.dumps({'at': now(), 'processed': total, 'counts': counts, 'goal_complete': False}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--publish', action='store_true')
    run(parser.parse_args())
