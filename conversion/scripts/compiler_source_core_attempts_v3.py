"""Read-only once-per-source-core history across production and development.

The source frontend configuration identifies the core. Case/controller/pool/
program versions never enter this identity. Explicit manual development receipts
are immutable history, never source eligibility or quality-score filters.
"""
import functools
import hashlib
import json
from pathlib import Path
import sqlite3

R=Path('/backup/shaoshitong/img2code_20261029')
CATALOG='release/compiler_iterations/source_core_attempts/manual_catalog_20261101_v3.json'
PRECALL=('deferred_birth_verified_active_', 'deferred_current_ordinary_Graphviz_v2_queue',
         'deferred_live_or_unproved_canonical_worker_claim',
         'already_qualified_complete_original_preserved',
         'same_source_core_already_attempted_preserved')


def raw(value):return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def error(reason):return RuntimeError('infrastructure_source_core_attempt_history:'+reason)


def _read_errors(function):
    @functools.wraps(function)
    def checked(*args,**kwargs):
        try:return function(*args,**kwargs)
        except Exception as exception:
            if isinstance(exception,RuntimeError)and str(exception).startswith('infrastructure_'):raise
            raise error(type(exception).__name__+':'+str(exception))from exception
    return checked


def core_identity(configuration):
    pins=configuration.get('pins');unit=configuration.get('unit');policy=configuration.get('policy')
    if not isinstance(pins,dict)or not pins or not isinstance(unit,str)or not isinstance(policy,str):raise ValueError('source_core_requires_frozen_frontend_configuration')
    return dict(schema='frozen_source_core_identity_v3',unit=unit,policy=policy,
                key=sha(raw(dict(unit=unit,policy=policy,pins=pins))))


def _read(reference,root):
    path=(Path(root)/reference['file']).resolve(strict=True)
    if not path.is_relative_to(Path(root).resolve()):raise error('evidence_outside_root:'+str(path))
    body=path.read_bytes()
    if sha(body)!=reference['sha256']:raise error('immutable_evidence_changed:'+str(path))
    return path,body


def _source(source,identifier):
    if not isinstance(source,dict)or source.get('pair_sha256')!=identifier:raise error('request_original_ID_changed:'+str(identifier))
    for key in ('code_sha256','image_sha256','format','category','source'):
        if not isinstance(source.get(key),str)or not source[key]:raise error('request_original_identity_incomplete:'+identifier)
    return {key:source[key]for key in ('code_sha256','image_sha256','format','category','source')}


def normal_was_called(request,result,attempt):
    if (request.get('evaluation_phase')in ('baseline','control_positive','control_failure_replay')
        or request.get('existing_development_candidate')or request.get('existing_development_failure')
        or request.get('negative_control')):return False
    if attempt is not None:
        if attempt.get('normal_source_conversion_called')is False:return False
        return True
    if result.get('phase')=='input':return False
    if result.get('error_type')=='ValueError'and result.get('reason')=='retryable_iteration_case_failure'and any(str(result.get('detail','')).startswith(prefix)for prefix in PRECALL):return False
    # A claimed/interrupted source attempt with no definitive pre-call evidence
    # cannot be silently reexecuted just because its owner died.
    return True


def _manual(configuration,root,identifiers,catalog):
    identity=core_identity(configuration);path=(root/(catalog or CATALOG)).resolve(strict=True)
    if not path.is_relative_to(root):raise error('manual_catalog_outside_root')
    body=path.read_bytes();document=json.loads(body)
    if document.get('schema')!='source_core_manual_attempt_catalog_v3'or not isinstance(document.get('entries'),list):raise error('manual_catalog_schema_changed')
    events=[]
    for declaration in document['entries']:
        if declaration['source_core_key']!=identity['key']:continue
        identifier=declaration['id']
        if identifiers is not None and identifier not in identifiers:continue
        _,payload=_read(declaration['receipt'],root);receipt=json.loads(payload)
        row=receipt[declaration['rows_key']][declaration['row_index']]
        if row.get('id')!=identifier or row.get(declaration['normal_count_key'])!=1:raise error('manual_normal_call_binding_changed:'+identifier)
        if declaration.get('requires_unchanged_canonical')and row.get('canonical_unchanged')is not True:raise error('manual_canonical_unchanged_proof_missing:'+identifier)
        _,payload=_read(declaration['frontend'],root);attempt=json.loads(payload)
        if not isinstance(attempt,dict)or not normal_was_called({'evaluation_phase':'manual_normal'}, {},attempt):raise error('manual_receipt_is_not_a_normal_attempt:'+identifier)
        source=declaration['source'];bound=_source(source,identifier)
        if isinstance(attempt.get('record'),dict):
            record=attempt['record']
            if(record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(identifier,bound['code_sha256'],bound['image_sha256']):raise error('manual_candidate_original_identity_changed:'+identifier)
        events.append(dict(id=identifier,source=source,original_identity=bound,source_core=identity,
                           evidence_kind='manual_development',declaration=declaration,
                           catalog=dict(file=str(path),sha256=sha(body)),frontend=declaration['frontend'],
                           normal_attempt_preserved=True,normal_reexecution_allowed=False))
    return events


@_read_errors
def collect(configuration,root=R,identifiers=None,ignore_runs=(),catalog=None):
    """Return real or conservatively ambiguous normal attempts in every mode."""
    from compiler_mermaid_alpha_qualifications_v2 import discover_ledger_paths
    root=Path(root).resolve();identity=core_identity(configuration)
    wanted=None if identifiers is None else set(identifiers)
    if wanted==set():return []
    if wanted is not None and any(not isinstance(x,str)or not x for x in wanted):raise ValueError('attempt_history_requires_exact_ID_strings')
    events=[];ignored=set(ignore_runs)
    for ledger in discover_ledger_paths(root):
        if ledger.parent.name in ignored or str(ledger.parent)in ignored:continue
        freeze=ledger.parent/'freeze.json'
        if not freeze.is_file():continue
        freeze_body=freeze.read_bytes();frozen=json.loads(freeze_body)
        if any(frozen.get('pins',{}).get(path)!=digest for path,digest in configuration['pins'].items()):continue
        with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True,timeout=30)as db:
            db.execute('pragma query_only=ON');db.execute('begin')
            columns={row[1]for row in db.execute('pragma table_info(samples)')}
            if not {'id','status','attempts','source','result'}<=columns:continue
            parts=[None]if wanted is None else[sorted(wanted)[i:i+400]for i in range(0,len(wanted),400)]
            for chunk in parts:
                query='select id,status,attempts,source,result from samples where attempts>0';parameters=()
                if chunk is not None:query+=' and id in ('+','.join('?'for _ in chunk)+')';parameters=tuple(chunk)
                for identifier,status,count,request_body,result_body in db.execute(query,parameters):
                    request=json.loads(request_body);result=json.loads(result_body)if result_body else{}
                    if not isinstance(request,dict)or not isinstance(result,dict):raise error('recognized_ledger_row_schema_changed:'+identifier)
                    if request.get('compiler_unit')!=identity['unit']:continue
                    if not normal_was_called(request,result,None):continue
                    source=request.get('source');bound=_source(source,identifier)
                    if request.get('id')!=identifier or result.get('id',identifier)!=identifier:raise error('ledger_original_ID_changed:'+identifier)
                    if (result.get('source_code_sha256',bound['code_sha256']),result.get('source_image_sha256',bound['image_sha256']))!=(bound['code_sha256'],bound['image_sha256']):raise error('ledger_original_hashes_changed:'+identifier)
                    frontend=None;attempt=None;evidence=result.get('evidence_directory')
                    if evidence:
                        directory=(root/evidence).resolve()
                        if not directory.is_relative_to((root/'conversion').resolve()):raise error('ledger_frontend_evidence_outside_owner')
                        path=directory/'frontend_result.json'
                        if path.is_file():
                            payload=path.read_bytes();attempt=json.loads(payload)
                            if not isinstance(attempt,dict):raise error('frontend_evidence_schema_changed:'+identifier)
                            frontend=dict(file=str(path),sha256=sha(payload))
                    if not normal_was_called(request,result,attempt):continue
                    events.append(dict(id=identifier,source=source,original_identity=bound,source_core=identity,
                        evidence_kind='SQLite_normal_or_ambiguous',ledger=str(ledger),status=status,claimed_attempts=count,
                        freeze=dict(file=str(freeze),sha256=sha(freeze_body)),
                        request_json=request_body,request_sha256=sha(request_body.encode()),
                        result_json=result_body,result_sha256=sha((result_body or'').encode()),frontend=frontend,
                        ambiguity_conservatively_preserved=frontend is None,normal_attempt_preserved=True,normal_reexecution_allowed=False))
    events.extend(_manual(configuration,root,wanted,catalog))
    return events


@_read_errors
def validate(events,configuration,root=R):
    root=Path(root).resolve();identity=core_identity(configuration)
    for event in events:
        if event.get('source_core')!=identity or _source(event['source'],event['id'])!=event['original_identity']:raise error('preserved_attempt_core_or_original_changed')
        if event['evidence_kind']=='manual_development':
            _,body=_read(event['catalog'],root);catalog=json.loads(body)
            if event['declaration']not in catalog['entries']:raise error('manual_declaration_missing')
            matched=_manual(configuration,root,{event['id']},event['catalog']['file'])
            if event not in matched:raise error('manual_preserved_attempt_changed')
        elif event['evidence_kind']=='SQLite_normal_or_ambiguous':
            _,body=_read(event['freeze'],root);freeze=json.loads(body)
            if any(freeze.get('pins',{}).get(p)!=v for p,v in configuration['pins'].items()):raise error('preserved_ledger_source_core_changed')
            if sha(event['request_json'].encode())!=event['request_sha256']or sha((event['result_json']or'').encode())!=event['result_sha256']:raise error('preserved_raw_ledger_evidence_changed')
            request=json.loads(event['request_json']);result=json.loads(event['result_json'])if event['result_json']else{}
            if request.get('id')!=event['id']or request.get('source')!=event['source']:raise error('preserved_ledger_request_changed')
            attempt=json.loads(_read(event['frontend'],root)[1])if event.get('frontend')else None
            if not normal_was_called(request,result,attempt):raise error('preserved_evidence_is_not_normal')
        else:raise error('unknown_preserved_attempt_evidence_kind')
    return True


def guard(identifier,source,configuration,current_run=None,root=R,catalog=None):
    events=collect(configuration,root,{identifier},ignore_runs=(current_run,)if current_run else(),catalog=catalog)
    expected=_source(source,identifier)
    if any(event['original_identity']!=expected for event in events):raise error('original_source_conflicts_with_attempt_history:'+identifier)
    validate(events,configuration,root)
    return dict(id=identifier,source_core=core_identity(configuration),already_attempted=bool(events),events=events,read_only=True)
