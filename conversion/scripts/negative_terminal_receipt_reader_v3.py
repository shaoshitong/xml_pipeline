"""Read-only strict negative-index adapter, including SVG program receipts.

Existing v1/v2 receipt rules remain unchanged. SVG markers cannot silently fall
through to legacy evidence. No writer, planner, database or exporter is invoked.
"""
import copy
import json
import os
from pathlib import Path
import re
import stat

import negative_terminal_receipt_reader_v2 as prior

ROOT = prior.ROOT
DIRECTORY = Path('conversion/svg_program_terminal_outcomes_v1')
MARKER = 'svg_program_terminal_outcome_v1'
POLICY = 'svg_current_verified_program_registry_only_terminal_v1'
canonical = prior.canonical
sha = prior.sha
require = prior.require


def _read(root, receipt, identifier):
    require(isinstance(receipt, dict) and prior._digest(receipt.get('sha256'))
            and prior._digest(receipt.get('plan_sha256')), 'invalid_svg_decision_digests')
    relative = Path(receipt.get('file', ''))
    require(relative == DIRECTORY / identifier / ('decision.' + receipt['sha256'] + '.json'), 'invalid_svg_decision_locator')
    directory = os.open(Path(root).resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fd = None
    try:
        for name in relative.parts[:-1]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_mode & 0o222 == 0, 'svg_decision_not_immutable_regular_file')
        parts = []
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            parts.append(block)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')
        require(tuple(getattr(before, key) for key in fields) == tuple(getattr(after, key) for key in fields), 'svg_decision_changed_during_read')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)
    payload = b''.join(parts)
    require(sha(payload) == receipt['sha256'], 'svg_decision_digest_mismatch')
    document = json.loads(payload)
    require(canonical(document) == payload, 'svg_decision_not_canonical')
    return document


def _evidence(plan, receipt):
    reason = 'current_verified_program_source_role_or_feature_unverifiable: ' + ','.join(plan['source_construct_classes'])
    value = {name: plan[name] for name in ('id', 'source_code_sha256', 'source_image_sha256', 'code_sha256', 'image_sha256', 'source_construct_classes')}
    value.update(reason_code='svg_current_program_complete_source_feature_or_role_failure', reason_detail=reason,
                 accepted=False, abandonment_is_not_conversion_success=True, deterministic_recovery_permitted=True,
                 new_model_calls=0, certificate={'file': str(Path(plan['evidence_directory']) / 'report.json'),
                                               'certificate_sha256': plan['certificate_sha256']},
                 active_quality_policy=plan['policy'], route_catalog_sha256=plan['catalog_sha256'],
                 scope='Unsupported by the current frozen verified production program; not intrinsic drawio inexpressibility.')
    value[MARKER] = {'policy': POLICY, 'decision': receipt, 'commit_nonce': receipt['commit_nonce']}
    return reason, value


def validate_outcome(row, root=ROOT, pins=None):
    row = prior._row(row)
    evidence = json.loads(row['record']) if isinstance(row['record'], str) else copy.deepcopy(row['record'])
    require(isinstance(evidence, dict), 'negative_evidence_not_object')
    svg_markers = [key for key in evidence if key.startswith('svg_program_terminal_outcome_v')]
    if not svg_markers:
        return prior.validate_outcome(row, root, pins)
    require(svg_markers == [MARKER] and not any(key.startswith('program_terminal_outcome_v') for key in evidence),
            'ambiguous_or_unknown_svg_terminal_marker')
    identifier = row['id']
    require(prior._digest(identifier) and row['category'] in ('scientific_diagram', 'poster') and row['format'] == 'svg', 'invalid_svg_original_scope')
    require(prior._digest(row['source_code_hash']) and prior._digest(row['source_image_hash']), 'invalid_svg_original_source_digests')
    require((evidence.get('id'), evidence.get('source_code_sha256'), evidence.get('source_image_sha256'))
            == (identifier, row['source_code_hash'], row['source_image_hash']), 'svg_negative_source_identity_mismatch')
    marker = evidence[MARKER]
    require(isinstance(marker, dict) and marker.get('policy') == POLICY, 'svg_terminal_policy_mismatch')
    receipt = marker['decision']
    document = _read(root, receipt, identifier)
    require(pins is None or isinstance(pins, dict), 'invalid_frozen_svg_pin_mapping')
    expected = pins.get('svg') if pins is not None else {
        'writer_sha256': sha((Path(root) / 'conversion/scripts/svg_program_terminal_outcomes_v1.py').read_bytes()),
        'collector_sha256': sha((Path(root) / 'conversion/scripts/svg_failure_closure_v1.py').read_bytes())}
    require(isinstance(expected, dict) and all(prior._digest(expected.get(name)) for name in ('writer_sha256', 'collector_sha256')),
            'missing_or_invalid_frozen_svg_author_pins')
    require(type(document.get('version')) is int and document['version'] == 1
            and document.get('id') == identifier and document.get('writer_policy') == POLICY
            and document.get('writer_sha256') == expected['writer_sha256'], 'svg_decision_author_or_version_mismatch')
    plan = document['plan']
    require(plan.get('schema') == 'svg_failure_only_finite_program_closure_v1' and plan.get('proposal') is True
            and plan.get('id') == identifier and isinstance(plan.get('source_construct_classes'), list)
            and bool(plan['source_construct_classes']), 'svg_source_failure_plan_missing')
    require(all(prior._digest(plan.get(name)) for name in ('source_code_sha256', 'source_image_sha256', 'code_sha256', 'image_sha256')),
            'invalid_svg_source_or_candidate_digests')
    require(sha(canonical(plan)) == document.get('plan_sha256') == receipt['plan_sha256'], 'svg_source_plan_digest_mismatch')
    body = {key: value for key, value in plan.items() if key != 'certificate_sha256'}
    require(sha(canonical(body)) == plan.get('certificate_sha256'), 'svg_source_certificate_body_mismatch')
    nonce = document.get('commit_nonce')
    require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce)
            and nonce == receipt.get('commit_nonce') == marker.get('commit_nonce'), 'svg_terminal_commit_nonce_mismatch')
    require(document.get('created_at') == receipt.get('created_at') and bool(receipt.get('created_at')), 'svg_terminal_timestamp_mismatch')
    require(document.get('accepted') is False and document.get('deterministic_recovery_permitted') is True
            and document.get('abandonment_is_not_conversion_success') is True and document.get('new_model_calls') == 0,
            'svg_terminal_nonsuccess_or_recovery_contract_missing')
    config = document['reviewed_config']
    require(Path(config['root']).resolve() == Path(root).resolve() and identifier not in config['research_reserved_ids']
            and identifier not in config['authorized_model_ids'], 'svg_terminal_reserved_research_or_model_case')
    author_pins = [value for key, value in config['pins'].items() if Path(key).name == 'svg_failure_closure_v1.py']
    require(author_pins == [expected['collector_sha256']], 'svg_source_collector_author_mismatch')
    writer_pins = [value for key, value in config['pins'].items() if Path(key).name == 'svg_program_terminal_outcomes_v1.py']
    require(writer_pins == [expected['writer_sha256']], 'svg_reviewed_writer_pin_mismatch')
    require(config['closure']['catalog_sha256'] == plan['catalog_sha256']
            and config['closure']['pins'] == plan['pins'], 'svg_source_catalog_or_pin_set_mismatch')
    require(isinstance(document.get('file_witnesses'), dict) and document['file_witnesses'], 'svg_terminal_file_preparation_missing')
    snapshot = document['complete_database_cas_snapshot']
    value = snapshot['tables']['processing_outcomes_v2']
    require(len(value['rows']) == 1, 'svg_prior_registry_snapshot_missing')
    prior_row = dict(zip(value['columns'], value['rows'][0]))
    prior_outcome = document['prior_outcome']
    require(prior_row['id'] == identifier and prior_outcome == {name: prior_row[name] for name in prior.REGISTRY_COLUMNS},
            'svg_prior_registry_row_mismatch')
    require(prior_outcome['status'] == 'pending'
            and (prior_outcome['category'], prior_outcome['format'], prior_outcome['source_code_hash'], prior_outcome['source_image_hash'])
            == (row['category'], row['format'], row['source_code_hash'], row['source_image_hash']), 'svg_prior_original_or_status_mismatch')
    reason, expected_evidence = _evidence(plan, receipt)
    require(row['reason'] == reason and canonical(evidence) == canonical(expected_evidence), 'svg_outcome_differs_from_exact_decision')
    return {'id': identifier, 'kind': 'svg_program_terminal_v1', 'receipt_verified': True,
            'source_identity_verified': True, 'writer_sha256': expected['writer_sha256'],
            'collector_sha256': expected['collector_sha256'], 'decision': receipt, 'commit_nonce': nonce,
            'accepted': False, 'deterministic_recovery_permitted': True, 'abandonment_is_not_conversion_success': True}


def manifest_row(row, root=ROOT, pins=None):
    normalized = prior._row(row)
    validate_outcome(normalized, root, pins)
    evidence = json.loads(normalized['record']) if isinstance(normalized['record'], str) else copy.deepcopy(normalized['record'])
    return {'id': normalized['id'], 'category': normalized['category'], 'source_format': normalized['format'],
            'status': 'abandoned', 'reason': normalized['reason'], 'source_code_sha256': normalized['source_code_hash'],
            'source_image_sha256': normalized['source_image_hash'], 'decision': evidence}
