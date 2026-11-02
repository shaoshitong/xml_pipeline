"""Conservative, transactional reservations for unseen compiler validation.

Reserved is not consumed. Reservations are never released or reused by this
helper, including after a failed preparation; existing audit files stay intact.
"""
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

SCHEMA='compiler_validation_reservation_v1'


def raw(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()


def sha(value):return hashlib.sha256(value).hexdigest()


def cohort_identity(selected):
    rows=[];all_keys=set()
    for item in selected:
        source=item['source'];identifier=item['id'];cluster=item['audit_cluster']
        if not isinstance(cluster,str) or not cluster or not item.get('cluster_keys'):
            raise ValueError('reservation_missing_stable_cluster_keys')
        hashes=[identifier,source['code_sha256'],source['image_sha256']]
        if any(not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in hashes):
            raise ValueError('reservation_invalid_source_identity')
        hard=item['cluster_keys']
        if not isinstance(hard,list) or any(not isinstance(k,str) or not k for k in hard):
            raise ValueError('reservation_invalid_cluster_keys')
        keys={('id',identifier),('code',source['code_sha256']),('image',source['image_sha256']),
              ('audit_cluster',cluster)}|{('hard_cluster',key) for key in hard}
        if keys & all_keys:
            raise ValueError('reservation_cohort_has_duplicate_identity_or_cluster')
        all_keys.update(keys)
        rows.append(dict(id=identifier,code_sha256=source['code_sha256'],
                         image_sha256=source['image_sha256'],audit_cluster=cluster,
                         hard_cluster_keys=sorted(set(hard))))
    if not rows:raise ValueError('reservation_empty_cohort')
    return dict(schema=SCHEMA,rows=sorted(rows,key=lambda row:row['id'])),sorted(all_keys)


def reserve(registry,selected,*,audit,run_prefix,implementation_identity_sha256,
            phase_runs,selected_manifest_sha256,protocol_sha256,controls_proof_sha256):
    identity,keys=cohort_identity(selected);cohort_sha256=sha(raw(identity))
    if set(phase_runs)!=set(('B','C')) or len(set(phase_runs.values()))!=2:
        raise ValueError('reservation_requires_one_bound_B_C_pair')
    path=Path(registry);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=30,isolation_level=None)
    try:
        db.execute('pragma foreign_keys=ON');db.execute('pragma journal_mode=WAL')
        db.execute('pragma synchronous=FULL')
        db.execute('''create table if not exists reservations(
          reservation_id text primary key,cohort_sha256 text unique not null,
          run_prefix text unique not null,state text not null check(state='reserved'),
          record text not null)''')
        db.execute('''create table if not exists reservation_keys(
          kind text not null,value text not null,reservation_id text not null,
          primary key(kind,value),foreign key(reservation_id) references reservations(reservation_id))''')
        db.execute('BEGIN IMMEDIATE')
        for kind,value in keys:
            found=db.execute('select reservation_id from reservation_keys where kind=? and value=?',
                             (kind,value)).fetchone()
            if found:raise ValueError('unseen_validation_identity_already_reserved:'+kind+':'+value)
        if db.execute('select 1 from reservations where run_prefix=? or cohort_sha256=?',
                      (run_prefix,cohort_sha256)).fetchone():
            raise ValueError('unseen_validation_reservation_not_reusable')
        record=dict(schema=SCHEMA,reservation_id=uuid.uuid4().hex,state='reserved',
                    consumed=False,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    audit=str(Path(audit).resolve()),cohort_sha256=cohort_sha256,
                    run_prefix=run_prefix,phase_runs=phase_runs,
                    implementation_identity_sha256=implementation_identity_sha256,
                    selected_manifest_sha256=selected_manifest_sha256,protocol_sha256=protocol_sha256,
                    controls_proof_sha256=controls_proof_sha256,source_ids=[r['id'] for r in identity['rows']],
                    reserved_identity_keys=len(keys),safe_automatic_preparation_retry=False)
        db.execute('insert into reservations values(?,?,?,?,?)',
                   (record['reservation_id'],cohort_sha256,run_prefix,'reserved',raw(record).decode()))
        db.executemany('insert into reservation_keys values(?,?,?)',
                       [(kind,value,record['reservation_id']) for kind,value in keys])
        db.commit();return record
    except BaseException:
        if db.in_transaction:db.rollback()
        raise
    finally:db.close()
