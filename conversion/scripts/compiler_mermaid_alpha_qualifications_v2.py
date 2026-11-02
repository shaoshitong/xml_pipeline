"""Read authoritative qualified SQLite rows, including live unfinished runs.

No exports, worker claims, conversion, publication or canonical writes. Every
find_qualified candidate is source-bound and checked against all five actual
clean assets; corrupt/conflicting evidence stops reuse rather than reconversion.
"""
import hashlib
import json
from pathlib import Path
import sqlite3

R=Path('/backup/shaoshitong/img2code_20261029')


def _failure(reason,detail):
    return RuntimeError('infrastructure_qualified_ledger_'+reason+':'+str(detail))


def _identifier_filter(identifiers):
    if identifiers is None:return None
    if isinstance(identifiers,(str,bytes)):raise ValueError('identifiers_must_be_a_collection_of_complete_IDs')
    result=set(identifiers)
    if any(not isinstance(value,str)or not value for value in result):raise ValueError('identifiers_must_be_nonempty_strings')
    return result


def discover_ledger_paths(root=R):
    """Discover the authoritative ledger floor without recursive tree walking.

    Legacy DBs come from inventory.SOURCES. Every current fixed-program ledger
    is exactly release/compiler_iterations/runs/*/status.sqlite. The current
    inventory may explicitly register additional DB paths; it is a catalog,
    never a source of qualification statuses or an owner-liveness filter.
    """
    from compiler_iteration_inventory_v1 import SOURCES
    root=Path(root).resolve();release=(root/'release').resolve()
    if not release.exists():return []
    candidates=[root/relative for _,kind,relative in SOURCES if kind=='db']
    try:
        candidates.extend((release/'compiler_iterations/runs').glob('*/status.sqlite'))
        pointer=release/'compiler_iterations/current.json'
        if pointer.exists()or pointer.is_symlink():
            pointer_path=pointer.resolve(strict=True)
            if not pointer_path.is_relative_to(release):raise _failure('catalog_outside_release',pointer)
            current=json.loads(pointer_path.read_bytes())
            if not isinstance(current,dict)or not isinstance(current.get('inventory'),str):raise _failure('invalid_current_inventory_pointer',pointer)
            inventory_path=(root/current['inventory']).resolve(strict=True)
            if not inventory_path.is_relative_to(release)or not inventory_path.is_file():raise _failure('catalog_outside_release',inventory_path)
            payload=inventory_path.read_bytes()
            if current.get('inventory_sha256')is not None and hashlib.sha256(payload).hexdigest()!=current['inventory_sha256']:raise _failure('catalog_inventory_hash_mismatch',inventory_path)
            inventory=json.loads(payload)
            if not isinstance(inventory,dict)or not isinstance(inventory.get('sources',[]),list):raise _failure('invalid_inventory_catalog',inventory_path)
            for item in inventory.get('sources',[]):
                if not isinstance(item,dict):raise _failure('invalid_inventory_source_entry',inventory_path)
                relative=item.get('path')
                if isinstance(relative,str)and(item.get('kind')=='db'or(item.get('kind')is None and Path(relative).name=='status.sqlite')):candidates.append(root/relative)
        discovered=set()
        for candidate in candidates:
            if not candidate.exists()and not candidate.is_symlink():continue
            path=candidate.resolve(strict=True)
            if not path.is_relative_to(release)or not path.is_file():raise _failure('path_outside_release',candidate)
            discovered.add(path)
        return sorted(discovered)
    except RuntimeError:raise
    except (OSError,ValueError,TypeError)as error:raise _failure('catalog_discovery_failed',error)from error


def ledger_manifests(root=R,identifiers=None):
    """Return every qualified manifest from recognized release SQLite ledgers.

    Filtering is done in SQL, in bounded chunks, so find_qualified does not
    deserialize an entire dataset. Each DB has one coherent read transaction;
    no final/in-progress export or owner/PID state is used for qualification.
    Multiple valid versions of an ID are retained for complete asset validation.
    """
    root=Path(root).resolve();release=(root/'release').resolve();wanted=_identifier_filter(identifiers)
    if wanted==set()or not release.exists():return []
    result=[];visited=set()
    paths=discover_ledger_paths(root)
    for named_path in paths:
        try:
            path=named_path.resolve(strict=True)
            if not path.is_relative_to(release)or not path.is_file():raise _failure('path_outside_release',named_path)
            if path in visited:continue
            visited.add(path)
            connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=30)
            try:
                connection.execute('pragma query_only=ON');connection.execute('begin')
                tables={row[0]for row in connection.execute("select name from sqlite_master where type='table'")}
                if 'samples'not in tables:continue
                columns={row[1]for row in connection.execute('pragma table_info(samples)')}
                if not {'id','status','result'}<=columns:continue
                if wanted is None:
                    queries=[("select id,status,result from samples where status='qualified' order by id",())]
                else:
                    values=sorted(wanted);queries=[]
                    for offset in range(0,len(values),500):
                        chunk=values[offset:offset+500];queries.append(("select id,status,result from samples where status='qualified' and id in ("+','.join('?'for _ in chunk)+') order by id',tuple(chunk)))
                for query,parameters in queries:
                    for identifier,status,payload in connection.execute(query,parameters):
                        location=str(named_path)+'#'+str(identifier)
                        if not isinstance(identifier,str)or not identifier:raise _failure('invalid_row_ID',location)
                        try:value=json.loads(payload)
                        except (TypeError,ValueError)as error:raise _failure('invalid_qualified_result_JSON',location)from error
                        if not isinstance(value,dict)or value.get('id')!=identifier or value.get('status')!=status or status!='qualified':raise _failure('result_identity_conflict',location)
                        manifest=value.get('manifest')
                        if not isinstance(manifest,dict)or manifest.get('id')!=identifier:raise _failure('manifest_identity_conflict',location)
                        if manifest.get('status')!='qualified':raise _failure('manifest_status_conflict',location)
                        result.append(manifest)
            finally:connection.close()
        except RuntimeError:raise
        except (OSError,sqlite3.Error)as error:raise _failure('unreadable_database',str(named_path)+':'+str(error))from error
    return result


def find_qualified(identifier,source,root=R):
    """Return one verified qualification, validating all observed versions first.

    Different qualified versions may have different immutable code/image paths.
    They remain legitimate when they match the same original identity and all
    five clean payload hashes. A conflicting claim to a path, source identity
    or damaged payload is an infrastructure error, even if another row is good.
    """
    from compiler_iteration_inventory_v1 import check_manifest
    if not isinstance(identifier,str)or not identifier:raise ValueError('qualified_lookup_requires_complete_ID')
    if not isinstance(source,dict):raise ValueError('qualified_lookup_requires_original_source_record')
    if source.get('pair_sha256',identifier)!=identifier:raise _failure('caller_source_identity_conflict',identifier)
    root=Path(root).resolve();manifests=ledger_manifests(root,identifiers={identifier});cache={};verified=[]
    for manifest in manifests:
        try:
            if source.get('source')is not None and manifest.get('source')!=source['source']:raise ValueError('accepted_manifest_original_dataset_mismatch')
            check_manifest(root,identifier,source,manifest,cache)
        except Exception as error:raise _failure('asset_or_source_conflict',identifier+':'+str(error))from error
        verified.append(manifest)
    return verified[0]if verified else None
