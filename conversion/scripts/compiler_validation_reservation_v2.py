"""Atomic fresh cohort selection and alias-aware validation reservation.

The selector runs once under BEGIN IMMEDIATE against current canonicalized
keys. Its binding callback computes bytes/hashes in memory. No release, retry,
source rendering or source-normal conversion is provided by this module.
"""
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from compiler_validation_identity_alias_v1 import normalize_keys, request_keys, storage_keys, POLICY, HASH

SCHEMA = 'compiler_validation_reservation_v2'


def raw(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


class ReservationConflict(ValueError):
    def __init__(self, conflicts):
        self.conflicts = [list(key) for key in sorted(conflicts)]
        super().__init__('unseen_validation_identity_already_reserved:' + ':'.join(self.conflicts[0]))


def cohort_identity(selected):
    entries, all_keys = [], set()
    for item in selected:
        if not item.get('audit_cluster') or not item.get('cluster_keys'):
            raise ValueError('reservation_missing_stable_cluster_keys')
        keys = request_keys(item)
        if keys & all_keys:
            raise ValueError('reservation_cohort_has_duplicate_canonical_identity_or_cluster')
        all_keys.update(keys)
        entries.append(dict(id=item['id'], code_sha256=item['source']['code_sha256'],
                            image_sha256=item['source']['image_sha256'],
                            audit_cluster=item['audit_cluster'],
                            hard_cluster_keys=sorted(set(item['cluster_keys']))))
    if not entries:
        raise ValueError('reservation_empty_cohort')
    return dict(schema=SCHEMA, identity_alias_policy=POLICY,
                rows=sorted(entries, key=lambda row:row['id'])), frozenset(all_keys)


def _open(registry):
    path = Path(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30, isolation_level=None)
    db.execute('pragma foreign_keys=ON')
    db.execute('pragma journal_mode=WAL')
    db.execute('pragma synchronous=FULL')
    db.execute("""create table if not exists reservations(
      reservation_id text primary key,cohort_sha256 text unique not null,
      run_prefix text unique not null,state text not null check(state='reserved'),
      record text not null)""")
    db.execute("""create table if not exists reservation_keys(
      kind text not null,value text not null,reservation_id text not null,
      primary key(kind,value),foreign key(reservation_id) references reservations(reservation_id))""")
    return db


def reserve_fresh(registry, selector, *, bind_selected, audit, run_prefix,
                  implementation_identity_sha256, phase_runs, controls_proof_sha256):
    if set(phase_runs) != {'B','C'} or len(set(phase_runs.values())) != 2:
        raise ValueError('reservation_requires_one_bound_B_C_pair')
    db = _open(registry)
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('select 1 from reservations where run_prefix=?', (run_prefix,)).fetchone():
            raise ValueError('unseen_validation_reservation_not_reusable')
        existing_raw = db.execute('select kind,value from reservation_keys').fetchall()
        existing = normalize_keys(existing_raw)
        choice = selector(existing, tuple(existing_raw))
        if not isinstance(choice, dict) or not isinstance(choice.get('selected'), list):
            raise ValueError('reservation_selector_requires_selected_list_and_metadata')
        selected = choice['selected']
        identity, keys = cohort_identity(selected)
        if keys & existing:
            raise ReservationConflict(keys & existing)
        binding = bind_selected(selected, {k:v for k,v in choice.items() if k != 'selected'})
        if not isinstance(binding, dict) or not {'selected_manifest_sha256','protocol_sha256'} <= binding.keys():
            raise ValueError('reservation_selected_binding_missing')
        if any(not isinstance(binding[k], str) or not HASH.fullmatch(binding[k])
               for k in ('selected_manifest_sha256','protocol_sha256')):
            raise ValueError('reservation_binding_hash_invalid')
        cohort_sha256 = sha(raw(identity))
        if db.execute('select 1 from reservations where cohort_sha256=?', (cohort_sha256,)).fetchone():
            raise ValueError('unseen_validation_reservation_not_reusable')
        record = dict(schema=SCHEMA, identity_alias_policy=POLICY,
                      reservation_id=uuid.uuid4().hex, state='reserved', consumed=False,
                      created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      audit=str(Path(audit).resolve()), cohort_sha256=cohort_sha256,
                      run_prefix=run_prefix, phase_runs=phase_runs,
                      implementation_identity_sha256=implementation_identity_sha256,
                      controls_proof_sha256=controls_proof_sha256,
                      source_ids=[row['id'] for row in identity['rows']],
                      registry_snapshot_canonical_sha256=sha(raw(sorted(existing))),
                      selection_sha256=sha(raw({k:v for k,v in choice.items() if k != 'selected'})),
                      selection_under_same_write_transaction=True,
                      selection_attempts=1, automatic_retry=False,
                      safe_automatic_preparation_retry=False, **binding)
        stored = storage_keys(selected)
        record['reserved_identity_keys'] = len(stored)
        db.execute('insert into reservations values(?,?,?,?,?)',
                   (record['reservation_id'],cohort_sha256,run_prefix,'reserved',raw(record).decode()))
        db.executemany('insert into reservation_keys values(?,?,?)',
                       [(kind,value,record['reservation_id']) for kind,value in stored])
        db.commit()
        return dict(reservation=record, selected=selected,
                    selection={k:v for k,v in choice.items() if k != 'selected'}, binding=binding)
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def reserve(registry, selected, *, audit, run_prefix, implementation_identity_sha256,
            phase_runs, selected_manifest_sha256, protocol_sha256, controls_proof_sha256):
    result = reserve_fresh(registry, lambda *_:dict(selected=list(selected)),
        bind_selected=lambda *_:dict(selected_manifest_sha256=selected_manifest_sha256,
                                    protocol_sha256=protocol_sha256),
        audit=audit,run_prefix=run_prefix,implementation_identity_sha256=implementation_identity_sha256,
        phase_runs=phase_runs,controls_proof_sha256=controls_proof_sha256)
    return result['reservation']
