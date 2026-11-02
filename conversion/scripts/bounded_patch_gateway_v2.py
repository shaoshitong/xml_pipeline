"""Bounded patch gateway with live canonical jobs/outcomes admission.

Historical usage supplies lifetime counts, never current admission. Both budget
reservation and dispatch re-read the canonical registry, source/revision files,
qualification, owners and all legacy model queues. No legacy SDK is imported.
There is no default transport, model worker, queue consumer or automatic sender.
"""
import copy
import json
import sqlite3
from pathlib import Path

import bounded_patch_gateway_v1 as core

ROOT=Path('/backup/shaoshitong/img2code_20261029')
LIVE_DB=ROOT/'conversion/jobs.sqlite'
EXPECTED={'scientific_diagram':107161,'poster':24743}
IDLE={'rendered','needs_quality_repair','harness_review_pending'}
MODEL_TABLES=('harness_queue','harness_queue_v2','harness_queue_v3')
initialize=core.initialize
finish=core.finish
validate_and_apply=core.validate_and_apply
lookup_sample_budget_adapter=core.lookup_sample_budget_adapter
POLICY_PATH=core.POLICY_PATH
TABLE=core.TABLE
ADMISSION_KEY='current_admission_v2'


def _binding(record):
    identity=core._identity(record)
    if not core.HASH.fullmatch(str(record.get('image_sha256',''))):
        raise ValueError('gateway_live_base_image_identity_required')
    return {'identity':identity,'base_code_sha256':record['code_sha256'],
            'base_image_sha256':record['image_sha256'],'base_code_file':record['code_file'],
            'base_image_file':record['image_file'],'base_record_sha256':core.sha(core.encoded(record))}


def prepare(record,xml,target_cells,**kwargs):
    result=core.prepare(record,xml,target_cells,**kwargs)
    result.update(_binding(record))
    result['gateway_version']=2
    return result


def prepare_followup(first,first_request_key,first_response,record,xml,target_cells,**kwargs):
    result=core.prepare_followup(first,first_request_key,first_response,record,xml,target_cells,**kwargs)
    result.update(_binding(record))
    result['gateway_version']=2
    return result


def _columns(db,table):
    return {row[1] for row in db.execute('PRAGMA table_info('+table+')')}


def _clean_hash(root,relative,digest):
    if not relative or not core.HASH.fullmatch(str(digest or '')):
        raise ValueError('gateway_live_file_identity_missing')
    path=(root/relative).resolve()
    if not path.is_relative_to((root/'clean').resolve()):
        raise ValueError('gateway_live_candidate_or_source_outside_clean')
    if core.sha(path.read_bytes())!=digest:
        raise ValueError('gateway_live_file_hash_changed: '+relative)
    return str(path.relative_to(root))


def check_current_admission(prepared,*,db_path=LIVE_DB,expected=EXPECTED,expected_snapshot=None):
    """Read-only fresh admission; missing/unknown/busy/qualified is a hard refusal."""
    target=Path(db_path).resolve()
    root=target.parent.parent
    if target.name!='jobs.sqlite' or target.parent.name!='conversion' or not target.is_file():
        raise ValueError('gateway_live_canonical_jobs_database_missing')
    if not isinstance(expected,dict) or not expected or any(type(n) is not int or n<1 for n in expected.values()):
        raise ValueError('gateway_live_scope_contract_invalid')
    identity=prepared.get('identity') or {}
    if any(not core.HASH.fullmatch(str(identity.get(k,''))) for k in ('id','source_code_sha256','source_image_sha256')):
        raise ValueError('gateway_live_source_identity_missing')
    if not prepared.get('base_image_sha256') or not prepared.get('base_record_sha256'):
        raise ValueError('gateway_live_v2_revision_binding_required')
    db=sqlite3.connect('file:'+str(target)+'?mode=ro',uri=True,timeout=2)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        required={'id','category','format','state','worker_pid','input_record','output_record','input_manifest','updated_at'}
        if not required.issubset(_columns(db,'jobs')) or not {'id','category','format','source_code_hash','source_image_hash','status','reason','record','updated_at'}.issubset(_columns(db,'processing_outcomes_v2')):
            raise ValueError('gateway_live_jobs_or_outcome_registry_schema_missing')
        if dict(db.execute('SELECT category,count(*) FROM jobs GROUP BY category'))!=expected:
            raise ValueError('gateway_live_authoritative_input_scope_changed')
        if db.execute('SELECT count(*) FROM processing_outcomes_v2').fetchone()[0]!=sum(expected.values()):
            raise ValueError('gateway_live_outcome_registry_scope_incomplete')
        if (db.execute('SELECT 1 FROM jobs j WHERE NOT EXISTS(SELECT 1 FROM processing_outcomes_v2 o WHERE o.id=j.id) LIMIT 1').fetchone()
                or db.execute('SELECT 1 FROM processing_outcomes_v2 o WHERE NOT EXISTS(SELECT 1 FROM jobs j WHERE j.id=o.id) LIMIT 1').fetchone()):
            raise ValueError('gateway_live_registered_original_id_set_changed')
        identifier=identity['id']
        job=db.execute('SELECT id,category,format,state,worker_pid,input_record,output_record,input_manifest,updated_at FROM jobs WHERE id=?',(identifier,)).fetchone()
        outcome=db.execute('SELECT id,category,format,source_code_hash,source_image_hash,status,reason,record,updated_at FROM processing_outcomes_v2 WHERE id=?',(identifier,)).fetchone()
        if not job or not outcome:
            raise ValueError('gateway_live_original_not_registered')
        if job[3]=='accepted' or outcome[5]=='qualified':
            raise ValueError('gateway_live_original_already_accepted_or_qualified')
        if outcome[5]!='pending':
            raise ValueError('gateway_live_outcome_is_terminal_or_unknown')
        if job[3] not in IDLE or job[4] is not None or not job[6]:
            raise ValueError('gateway_live_job_busy_owned_or_unknown_state')
        original=json.loads(job[5])
        record=json.loads(job[6])
        if outcome[:3]!=(identifier,job[1],job[2]):
            raise ValueError('gateway_live_registry_category_or_format_mismatch')
        if (outcome[3:5]!=(identity['source_code_sha256'],identity['source_image_sha256'])
                or original.get('code_sha256')!=identity['source_code_sha256']
                or original.get('image_sha256')!=identity['source_image_sha256']
                or core._identity(record)!=identity or record.get('source_pair_sha256')!=identifier
                or record.get('source_format')!=job[2]):
            raise ValueError('gateway_live_authoritative_original_source_identity_changed')
        source_record=record.get('source_record')
        if source_record and (source_record.get('code_sha256')!=identity['source_code_sha256'] or source_record.get('image_sha256')!=identity['source_image_sha256']):
            raise ValueError('gateway_live_embedded_source_record_identity_changed')
        if (record.get('code_sha256')!=prepared['base_code_sha256']
                or record.get('image_sha256')!=prepared['base_image_sha256']
                or record.get('code_file')!=prepared['base_code_file']
                or record.get('image_file')!=prepared['base_image_file']
                or core.sha(core.encoded(record))!=prepared['base_record_sha256']):
            raise ValueError('gateway_live_current_revision_or_metadata_changed')
        plan=prepared.get('repair_plan')
        if not isinstance(plan,dict) or plan.get('base_code_sha256')!=record['code_sha256']:
            raise ValueError('gateway_live_program_repair_plan_base_changed')
        queues={}
        for table in MODEL_TABLES:
            columns=_columns(db,table)
            if not columns:
                continue
            if not {'id','state'}.issubset(columns):
                raise ValueError('gateway_live_unknown_model_queue_schema')
            columns=sorted(columns)
            row=db.execute('SELECT '+','.join(columns)+' FROM '+table+' WHERE id=?',(identifier,)).fetchone()
            values=dict(zip(columns,row)) if row else None
            queues[table]=values
            if values and (values['state']=='running' or values.get('worker_pid') is not None):
                raise ValueError('gateway_live_model_queue_running_or_owned: '+table)
        files={'code':_clean_hash(root,record['code_file'],record['code_sha256']),
               'image':_clean_hash(root,record['image_file'],record['image_sha256'])}
        for path,digest in [('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
            if record.get(path):files[path]=_clean_hash(root,record[path],identity[digest])
        snapshot={'version':2,'database':str(target),'original_id':identifier,
                  'source_identity':identity,'category':job[1],'source_format':job[2],
                  'job_state':job[3],'job_worker_pid':job[4],
                  'input_record_sha256':core.sha(job[5].encode()),
                  'output_record_sha256':core.sha(job[6].encode()),
                  'input_manifest_sha256':core.sha((job[7] or '').encode()),'job_updated_at':job[8],
                  'code_sha256':record['code_sha256'],'image_sha256':record['image_sha256'],
                  'outcome':list(outcome),'model_queues':queues,'verified_clean_files':files,
                  'scope':dict(expected),'expected_inputs':sum(expected.values())}
        digest=core.sha(core.encoded(snapshot))
        if expected_snapshot is not None and (expected_snapshot.get('snapshot_sha256')!=digest or expected_snapshot.get('snapshot')!=snapshot):
            raise ValueError('gateway_live_admission_snapshot_changed_after_reservation')
        return {'snapshot_sha256':digest,'snapshot':snapshot,'checked_at':core.now(),
                'current_admission_verified':True,'read_only':True}
    finally:
        db.close()


def _policy_location(prepared,policy_path,db_path):
    policy=core.require_enabled_policy(prepared,policy_path)
    root=Path(policy.get('input_root',''))
    if not root.is_absolute():
        raise ValueError('gateway_live_policy_input_root_invalid')
    canonical=(root/'conversion/jobs.sqlite').resolve()
    target=canonical if db_path is None else Path(db_path).resolve()
    expected=policy.get('categories')
    if target!=canonical or not isinstance(expected,dict) or sum(expected.values())!=policy.get('expected_input_pairs'):
        raise ValueError('gateway_live_canonical_database_or_policy_scope_mismatch')
    return policy,target,expected


def _budget_only(history):
    """Discard stale quality admission; retain conservative historical cost limits."""
    result=copy.deepcopy(history)
    used=result.get('conservative_budget_used')
    complete=result.get('coverage_complete_for_id') is True
    counts=[result.get(k) for k in ('confirmed_calls','unknown_reservations')]
    valid=(complete and result.get('max_calls')==2 and bool(result.get('history_snapshot_id'))
           and type(used) is int and used>=0 and all(type(v) is int and v>=0 for v in counts)
           and used>=sum(counts) and result.get('unknown_usage') is False)
    result['history_snapshot_eligible_for_new_call']=result.get('eligible_for_new_call')
    result['eligible_for_new_call']=bool(valid and used<2)
    result['eligibility_scope']='Historical lifetime budget only; live jobs/outcomes plus root policy independently control dispatch.'
    return result


def _lookup(db,identifier,history_lookup):
    if history_lookup is not None:
        return _budget_only(history_lookup(identifier))
    keys=[r[0] for r in db.execute('SELECT request_key FROM '+TABLE+' WHERE original_id=?',(identifier,))]
    return _budget_only(core.lookup_sample_budget_adapter(identifier,request_keys=keys))


def reserve(db,prepared,history_lookup=None,*,policy_path=POLICY_PATH,live_db_path=None):
    _,target,expected=_policy_location(prepared,policy_path,live_db_path)
    def history(identifier):
        budget=_lookup(db,identifier,history_lookup)
        # Embedded in the same private-ledger atomic INSERT as the reservation.
        budget[ADMISSION_KEY]=check_current_admission(prepared,db_path=target,expected=expected)
        return budget
    result=core.reserve(db,prepared,history)
    return {**result,'gateway_version':2}


def _locally_block(db,reservation,exc,phase):
    # A pre-send observer must never free another thread's already-sent request.
    expected='reserved' if phase=='before_send' else 'sent_unknown'
    evidence={'source':'canonical_live_admission_v2','phase':phase,'reason':str(exc)[:1000],
              'upstream_send_performed':False,'charged':False}
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('UPDATE '+TABLE+" SET state='blocked_local',finished_at=?,evidence_json=? WHERE request_key=? AND original_id=? AND state=?",
                   (core.now(),json.dumps(evidence,ensure_ascii=False),reservation['request_key'],reservation['original_id'],expected))
        db.commit()
    except BaseException:
        db.rollback()
        raise


def send_once(db,prepared,reservation,transport=None,*,policy_path=POLICY_PATH,history_lookup=None,live_db_path=None):
    if transport is None:
        raise RuntimeError('gateway_transport_not_enabled_no_api_was_sent')
    _,target,expected=_policy_location(prepared,policy_path,live_db_path)
    row=db.execute('SELECT original_id,request_sha256,state,evidence_json FROM '+TABLE+' WHERE request_key=?',(reservation['request_key'],)).fetchone()
    if not row or row[:3]!=(prepared['identity']['id'],prepared['request_sha256'],'reserved'):
        raise ValueError('gateway_live_reservation_identity_or_state_mismatch')
    admission=json.loads(row[3]).get('history',{}).get(ADMISSION_KEY)
    if not isinstance(admission,dict) or not admission.get('current_admission_verified'):
        raise ValueError('gateway_live_reservation_has_no_canonical_admission')
    try:
        check_current_admission(prepared,db_path=target,expected=expected,expected_snapshot=admission)
    except Exception as exc:
        _locally_block(db,reservation,exc,'before_send')
        raise
    def history(identifier):
        return _lookup(db,identifier,history_lookup)
    def guarded(request,key):
        # This is called after core marks sent_unknown but BEFORE any transport.
        try:
            _,fresh_target,fresh_expected=_policy_location(prepared,policy_path,live_db_path)
            fresh=check_current_admission(prepared,db_path=fresh_target,expected=fresh_expected,expected_snapshot=admission)
        except Exception as exc:
            _locally_block(db,reservation,exc,'immediately_before_transport')
            raise
        result=transport(request,key)
        if not isinstance(result,dict):
            raise ValueError('gateway_transport_returned_no_response_object')
        evidence=result.get('evidence') or {}
        if not isinstance(evidence,dict):
            raise ValueError('gateway_transport_evidence_is_not_an_object')
        return {**result,'evidence':{**evidence,ADMISSION_KEY:fresh,
                'root_policy_and_live_current_revision_checked_before_transport':True}}
    return core.send_once(db,prepared,reservation,guarded,policy_path=policy_path,history_lookup=history)
