"""Read-only, birth-bound live Python batch and frozen-manifest exclusions.

A stale queued row alone is never a live owner. No foreign ledger is mutated.
"""
import hashlib
import json
from pathlib import Path
import sqlite3

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda data:hashlib.sha256(data).hexdigest()


def live_owner(path,freeze):
    from initial_conversion_process_v1 import identity
    path=Path(path)
    try:
        owner=json.loads(path.read_bytes());current=identity(int(owner['pid']))
        if not current or current.get('state')=='Z'or str(current['start_ticks'])!=str(owner['start_ticks']):return None
        args=[v.decode()for v in Path('/proc',str(owner['pid']),'cmdline').read_bytes().split(b'\0')if v]
        pins=freeze.get('pins',{})
        scripts=[Path(v).resolve()for v in args if v.endswith('.py')and Path(v).is_absolute()]
        matching=[str(p)for p in scripts if any(Path(raw).resolve()==p and p.is_file()and sha(p.read_bytes())==digest for raw,digest in pins.items())]
        if not matching:return None
        return dict(owner_file=str(path),pid=owner['pid'],start_ticks=owner['start_ticks'],actual_cmdline=args,actual_frozen_entrypoints=matching,live=True)
    except (OSError,ValueError,KeyError,TypeError):return None


def _freeze(path):
    try:return json.loads(Path(path).read_bytes())
    except (OSError,ValueError):return {}


def frozen_ids(manifest,freeze):
    blob=Path(manifest).read_bytes()
    if sha(blob)!=freeze.get('input_sha256'):raise RuntimeError('infrastructure_live_overlap_manifest_not_frozen:'+str(manifest))
    return {row['id']for line in blob.splitlines()if line and (row:=json.loads(line))}


def snapshot(ignore_runs=(),root=R,identifier=None):
    root=Path(root);ignore=set(ignore_runs);active={};ledgers=[];programs=[];program_owners={}
    def ignore_run(name):return any(name==value or name.startswith(value+'_')for value in ignore)
    for directory in sorted((root/'release/compiler_iterations/programs').glob('*')):
        if not directory.is_dir()or ignore_run(directory.name):continue
        freeze=_freeze(directory/'implementation.json');owner=live_owner(directory/'owner.json',freeze)
        if not owner:continue
        program_owners[directory.name]=owner;programs.append(owner)
        for phase in ('B','C','mass'):
            manifest=directory/(phase+'.jsonl');phasefreeze=_freeze(directory/(phase+'.freeze.json'))
            if manifest.is_file()and phasefreeze:
                ids=frozen_ids(manifest,phasefreeze)
                if identifier is not None:ids&={identifier}
                if not ids:continue
                # A phase still needs to be queued/running. Completed rows are
                # preserved separately, not held hostage by a live supervisor.
                ledger=root/'release/compiler_iterations/runs'/(directory.name+'_'+phase)/'status.sqlite'
                pending=ids
                if ledger.is_file():
                    with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True,timeout=30)as db:
                        pending={i for i,status in (db.execute('select id,status from samples where id=?',(identifier,))if identifier is not None else db.execute('select id,status from samples'))if status in ('queued','running')}
                for identifier in pending:active.setdefault(identifier,[]).append(dict(kind='live_program_frozen_pending_manifest',manifest=str(manifest),manifest_sha256=sha(manifest.read_bytes()),owner=owner))
    for ledger in sorted((root/'release').rglob('status.sqlite')):
        directory=ledger.parent
        if ignore_run(directory.name):continue
        freeze=_freeze(directory/'freeze.json');owner=live_owner(directory/'owner.json',freeze)
        if not owner:continue
        try:
            with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True,timeout=30)as db:
                tables={x[0]for x in db.execute("select name from sqlite_master where type='table'")}
                if 'samples'not in tables:continue
                pending=[i for i,status in (db.execute('select id,status from samples where id=?',(identifier,))if identifier is not None else db.execute('select id,status from samples'))if status in ('queued','running')]
        except sqlite3.DatabaseError as error:raise RuntimeError('infrastructure_live_overlap_ledger_unreadable:'+str(ledger))from error
        record=dict(ledger=str(ledger),owner=owner,pending_rows=len(pending));ledgers.append(record)
        for identifier in pending:active.setdefault(identifier,[]).append(dict(kind='live_controller_queued_or_running',ledger=str(ledger),owner=owner))
    return dict(schema='birth_bound_active_conversion_overlap_v1',active=active,live_ledgers=ledgers,live_programs=programs,dead_or_unowned_queued_rows_not_deferred=True,read_only=True)


def guard(identifier,ignore_runs=()):
    state=snapshot(ignore_runs=ignore_runs,identifier=identifier);return dict(id=identifier,active=identifier in state['active'],owners=state['active'].get(identifier,[]),read_only=True,birth_checked=True)
