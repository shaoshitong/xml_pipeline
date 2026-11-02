"""Read-only negative-index adapter for legacy and program-terminal v1/v2 rows.

The existing exporter row shape is retained. Program-terminal markers require
hash-bound canonical decisions and explicitly frozen writer/planner identities;
legacy explicit outcomes retain the exporter's generic source identity checks.
No database, exporter, planner or writer entry point is invoked by this module.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT=Path('/backup/shaoshitong/img2code_20261029')
OUTCOME_COLUMNS=('id','category','format','source_code_hash','source_image_hash','reason','record')
REGISTRY_COLUMNS=('category','format','source_code_hash','source_image_hash','status','reason','record','updated_at')
VERSIONS={1:{'marker':'program_terminal_outcome_v1','directory':'conversion/program_terminal_outcomes_v1','policy':'bounded_program_terminal_outcome_registry_only_v1','writer':'program_terminal_outcomes_v1.py'},2:{'marker':'program_terminal_outcome_v2','directory':'conversion/program_terminal_outcomes_v2','policy':'bounded_program_terminal_outcome_registry_only_v2','writer':'program_terminal_outcomes_v2.py'}}
PLANNER='bounded_program_terminal_planner_v1.py'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


class Refused(ValueError):pass


def require(condition,reason):
    if not condition:raise Refused(reason)


def canonical(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()


def json_sha(value):
    return sha(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())


def _digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def _row(row):
    if isinstance(row,dict):
        require(row.get('status','abandoned')=='abandoned','negative_index_requires_abandoned_row')
        require(all(key in row for key in OUTCOME_COLUMNS),'negative_row_fields_missing')
        return {key:row[key] for key in OUTCOME_COLUMNS}
    require(isinstance(row,(tuple,list)) and len(row)==len(OUTCOME_COLUMNS),'negative_row_shape_changed')
    return dict(zip(OUTCOME_COLUMNS,row))


def _expected_pins(root,version,pins):
    """Explicit pins are authoritative, including a historical writer revision.

    ``pins`` is ``{1: {'writer_sha256': ..., 'planner_sha256': ...}, 2: ...}``.
    If supplied, a missing version is a refusal. Otherwise current canonical
    script bytes supply defaults; callers exporting older revisions can freeze
    their archived source hashes explicitly rather than trusting today's file.
    """
    if pins is None:
        scripts=Path(root)/'conversion/scripts';expected={'writer_sha256':sha((scripts/VERSIONS[version]['writer']).read_bytes()),'planner_sha256':sha((scripts/PLANNER).read_bytes())}
    else:
        require(isinstance(pins,dict) and version in pins,'missing_frozen_receipt_author_pins')
        expected=pins[version]
    require(isinstance(expected,dict) and all(_digest(expected.get(key)) for key in ('writer_sha256','planner_sha256')),'invalid_frozen_receipt_author_pins')
    return expected


def read_decision(root,receipt,version,identifier):
    """Read only a canonical immutable decision below its exact owned prefix."""
    require(version in VERSIONS,'unsupported_terminal_receipt_version')
    require(isinstance(receipt,dict) and _digest(receipt.get('sha256')) and _digest(receipt.get('plan_sha256')),'invalid_decision_digests')
    require(isinstance(receipt.get('file'),str),'invalid_decision_locator')
    relative=Path(receipt['file']);prefix=Path(VERSIONS[version]['directory']);expected=prefix/identifier/('decision.'+receipt['sha256']+'.json')
    require(relative==expected and not relative.is_absolute() and '..' not in relative.parts,'invalid_decision_locator')
    root=Path(root).resolve(strict=True);directory=os.open(root,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0));fd=None
    try:
        # Do not follow intermediate symlinks, even if their final target would
        # happen to lie elsewhere within the program's receipt directory.
        for name in relative.parts[:-1]:
            child=os.open(name,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0),dir_fd=directory);os.close(directory);directory=child
        fd=os.open(relative.name,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0),dir_fd=directory);before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode),'decision_not_regular_file');require(before.st_mode&0o222==0,'decision_not_immutable_readonly_file');chunks=[]
        while True:
            chunk=os.read(fd,1024*1024)
            if not chunk:break
            chunks.append(chunk)
        after=os.fstat(fd)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns,before.st_mode)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns,after.st_mode),'decision_changed_while_reading')
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)
    payload=b''.join(chunks);require(sha(payload)==receipt['sha256'],'decision_hash_mismatch')
    try:document=json.loads(payload)
    except (ValueError,UnicodeDecodeError) as error:raise Refused('decision_not_json') from error
    require(isinstance(document,dict) and canonical(document)==payload,'decision_not_canonical_json')
    return document,payload


def validate_outcome(row,root=ROOT,pins=None):
    """Validate one abandoned exporter row without changing any file or DB.

    A seven-column row matches the frozen exporter's existing SQL projection.
    A mapping may additionally include status, which must be ``abandoned``.
    Full current job/QA/outcome CAS remains the responsibility of the writer.
    """
    row=_row(row);identifier=row['id'];require(_digest(identifier),'invalid_original_identifier');require(_digest(row['source_code_hash']) and _digest(row['source_image_hash']),'invalid_source_digests');require(isinstance(row['reason'],str) and bool(row['reason'].strip()) and bool(row['record']),'missing_negative_reason_or_evidence')
    try:evidence=json.loads(row['record']) if isinstance(row['record'],str) else copy.deepcopy(row['record'])
    except (ValueError,TypeError) as error:raise Refused('negative_evidence_not_json') from error
    require(isinstance(evidence,dict),'negative_evidence_not_object');require((evidence.get('id'),evidence.get('source_code_sha256'),evidence.get('source_image_sha256'))==(identifier,row['source_code_hash'],row['source_image_hash']),'negative_source_identity_mismatch')
    markers=[key for key in evidence if key.startswith('program_terminal_outcome_v')]
    if not markers:return {'id':identifier,'kind':'legacy_explicit','receipt_verified':False,'source_identity_verified':True,'accepted':False,'abandonment_is_not_conversion_success':True}
    require(len(markers)==1 and markers[0] in {spec['marker'] for spec in VERSIONS.values()},'ambiguous_or_unknown_program_terminal_marker')
    version=next(version for version,spec in VERSIONS.items() if spec['marker']==markers[0]);spec=VERSIONS[version];marker=evidence[spec['marker']];require(isinstance(marker,dict) and marker.get('policy')==spec['policy'],'terminal_marker_policy_mismatch');receipt=marker.get('decision');document,payload=read_decision(root,receipt,version,identifier);expected=_expected_pins(root,version,pins)
    require(type(document.get('version')) is int and document['version']==version,'terminal_document_version_mismatch');require(document.get('writer_policy')==spec['policy'],'terminal_document_policy_mismatch');require(document.get('writer_sha256')==expected['writer_sha256'],'terminal_writer_sha256_mismatch');require(document.get('planner_sha256')==expected['planner_sha256'],'terminal_planner_sha256_mismatch')
    plan=document.get('plan');require(isinstance(plan,dict) and plan.get('id')==identifier,'terminal_plan_identifier_mismatch');require(document.get('plan_sha256')==receipt['plan_sha256']==sha(canonical(plan)),'terminal_plan_digest_mismatch');require(isinstance(document.get('created_at'),str) and bool(document['created_at']) and document['created_at']==receipt.get('created_at'),'terminal_creation_timestamp_mismatch')
    require(document.get('deterministic_recovery_permitted') is True and document.get('abandonment_is_not_conversion_success') is True and document.get('new_model_calls')==0,'terminal_recovery_nonsuccess_or_model_contract_missing');require(evidence.get('deterministic_recovery_permitted') is True and evidence.get('abandonment_is_not_conversion_success') is True and evidence.get('new_model_calls')==0,'negative_recovery_nonsuccess_or_model_contract_missing')
    base=copy.deepcopy(evidence);base.pop(spec['marker']);require(canonical(base)==canonical(plan.get('evidence')),'terminal_plan_evidence_differs_from_outcome')
    cas=plan.get('cas');require(isinstance(cas,dict) and marker.get('prior_registry_snapshot_sha256')==cas.get('registry_snapshot_sha256') and _digest(cas.get('registry_snapshot_sha256')),'terminal_prior_registry_digest_mismatch');require(marker.get('active_quality_policy')==cas.get('active_policy') and isinstance(cas.get('active_policy'),str) and bool(cas['active_policy']),'terminal_active_quality_policy_mismatch')
    prior=document.get('prior_outcome');require(isinstance(prior,dict) and all(key in prior for key in REGISTRY_COLUMNS),'terminal_prior_registry_fields_missing');require(prior['status']=='pending' and (prior['category'],prior['format'],prior['source_code_hash'],prior['source_image_hash'])==(row['category'],row['format'],row['source_code_hash'],row['source_image_hash']),'terminal_prior_registry_source_or_status_mismatch');require(json_sha(tuple(prior[key] for key in REGISTRY_COLUMNS))==cas['registry_snapshot_sha256'],'terminal_prior_registry_snapshot_mismatch')
    require(isinstance(document.get('historical_terminal_receipt_owners'),list),'terminal_historical_owner_provenance_missing');require(isinstance(evidence.get('reason_code'),str) and isinstance(evidence.get('reason_detail'),str) and row['reason']=='current_frozen_program:'+evidence['reason_code']+'; '+evidence['reason_detail'],'terminal_reason_differs_from_decision')
    if version==2:
        nonce=document.get('commit_nonce');require(isinstance(nonce,str) and re.fullmatch('[0-9a-f]{32}',nonce) is not None and nonce==receipt.get('commit_nonce')==marker.get('commit_nonce'),'terminal_commit_nonce_mismatch');preparation=document.get('preparation');require(isinstance(preparation,dict) and isinstance(preparation.get('db_cas_snapshots'),dict) and isinstance(preparation.get('file_witnesses'),(dict,list)),'terminal_preparation_proof_missing')
    return {'id':identifier,'kind':'program_terminal_v'+str(version),'version':version,'receipt_verified':True,'source_identity_verified':True,'writer_policy':spec['policy'],'writer_sha256':document['writer_sha256'],'planner_sha256':document['planner_sha256'],'decision':copy.deepcopy(receipt),'commit_nonce':document.get('commit_nonce'),'accepted':False,'deterministic_recovery_permitted':True,'abandonment_is_not_conversion_success':True}


def manifest_row(row,root=ROOT,pins=None):
    """Retain exactly the existing exporter's manifest shape after validation."""
    normalized=_row(row);validate_outcome(normalized,root,pins);evidence=json.loads(normalized['record']) if isinstance(normalized['record'],str) else copy.deepcopy(normalized['record'])
    return {'id':normalized['id'],'category':normalized['category'],'source_format':normalized['format'],'status':'abandoned','reason':normalized['reason'],'source_code_sha256':normalized['source_code_hash'],'source_image_sha256':normalized['source_image_hash'],'decision':evidence}
