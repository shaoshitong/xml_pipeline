"""Short-transaction SVG failure outcomes for the current verified program.

No generation, model call, job/queue/history update or success publication.
Complete fresh source failure certificates and all current route receipts are
required. New research cohorts stay pending. A later verified deterministic
revision may recover an abandoned input; no intrinsic drawio limit is claimed.
"""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time

import svg_failure_closure_v1 as collector
import program_terminal_outcomes_v2 as shared
from bounded_sqlite_transaction_v1 import BusyBudget

POLICY = 'svg_current_verified_program_registry_only_terminal_v1'
DIRECTORY = Path('conversion/svg_program_terminal_outcomes_v1')
MARKER = 'svg_program_terminal_outcome_v1'
RESERVATION = Path('conversion/prototype/svg_marker_composition_v2/research_cohort_manifest.json')
RESERVATION_SHA = '85ae48fc00597c3d86e7d5db2b52d5234050d7d0b4b87f3fe43c4f4a79943bb8'
TAXONOMY_REVIEW = Path('conversion/svg_current_program_failure_taxonomy_review.json')
TAXONOMY_REVIEW_SHA = '372b6fc6d6ce92b5f26a2a507603d8cff4172615b4407239ac2dab61a076b5f1'
SEMANTIC_ISSUES = frozenset(('filter', 'clipPath', 'maskImage', 'fill_paint_server', 'stroke_paint_server',
    'mix_blend_mode', 'evenodd_requires_review', 'textPath', 'text_transform', 'marker_mid',
    'image_transform_requires_review', 'use_symbol_aspect_requires_review',
    'scene_use_symbol_viewport_clip_unproven', 'scene_marker_viewport_clip_unproven',
    'scene_marker_slice_mapping_unproven', 'scene_marker_percent_ref_unproven',
    'scene_vector_image_requires_editable_expansion', 'scene_animated_raster_asset_unproven',
    'scene_image_aspect_mapping_unproven', 'scene_image_axis_flip_not_in_base_mapping',
    'scene_text_descendant_opacity_not_in_base_mapping'))
REGISTRY_COLUMNS = shared.REGISTRY_COLUMNS
JOB_COLUMNS = ('id', 'category', 'format', 'source', 'input_record', 'state', 'route', 'attempts',
               'updated_at', 'output_record', 'error', 'input_manifest', 'worker_pid')
canonical = shared.canonical
require = shared.require
sha = shared.sha
_SEAL = object()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def configuration(root):
    root = Path(root).resolve()
    closure = collector.configuration(root)
    path = root / RESERVATION
    raw = path.read_bytes()
    require(sha(raw) == RESERVATION_SHA, 'reviewed_research_reservation_changed')
    reserved = json.loads(raw)
    require(reserved.get('no_current_program_terminal_publish_authorized_for_this_research_cohort') is True,
            'missing_research_pending_contract')
    identifiers = reserved['ids']
    require(len(identifiers) == len(set(identifiers)) == 16
            and all(re.fullmatch('[0-9a-f]{64}', item) for item in identifiers), 'invalid_research_cohort')
    policy_path = root / 'conversion/model_usage_policy_v2.json'
    model_policy = json.loads(policy_path.read_text())
    require(model_policy['legacy_sdk_disabled'] is True
            and model_policy['model_calls_per_original_sample_lifetime_limit'] == 2
            and model_policy['count_history_across_versions_and_sessions'] is True,
            'user_model_lifetime_or_bulk_dispatch_policy_changed')
    pins = {**closure['pins'], str(path): sha(raw), str(policy_path): sha(policy_path.read_bytes())}
    review = root / TAXONOMY_REVIEW
    require(sha(review.read_bytes()) == TAXONOMY_REVIEW_SHA, 'reviewed_source_failure_taxonomy_changed')
    pins[str(review)] = TAXONOMY_REVIEW_SHA
    for module in (collector, shared, __import__(BusyBudget.__module__)):
        source = Path(module.__file__).resolve()
        pins[str(source)] = sha(source.read_bytes())
    pins[str(Path(__file__).resolve())] = sha(Path(__file__).read_bytes())
    owner = root / 'conversion/auto_quality_owner.json'
    pins[str(owner)] = sha(owner.read_bytes())
    return {'root': str(root), 'closure': closure, 'pins': pins,
            'research_reserved_ids': sorted(identifiers),
            'authorized_model_ids': sorted(model_policy['authorized_model_sample_ids']),
            'writer_begin_seconds': 180, 'writer_commit_seconds': 30,
            'scope': 'Current frozen verified production routes only. Independent research prototypes are not production routes; their reviewed cohort is reserved. No intrinsic drawio inexpressibility is claimed.'}


def _snapshot(db, identifier):
    require(tuple(row[1] for row in db.execute('pragma main.table_info(jobs)')) == JOB_COLUMNS,
            'unknown_full_jobs_schema')
    require(tuple(row[1] for row in db.execute('pragma main.table_info(processing_outcomes_v2)')) == ('id', *REGISTRY_COLUMNS),
            'unknown_full_registry_schema')
    schema = db.execute("select type,name,tbl_name,rootpage,sql from main.sqlite_master where name not like 'sqlite_%' order by type,name").fetchall()
    tables = {}
    for kind, table, _, _, _ in schema:
        if kind != 'table':
            continue
        require(re.fullmatch('[A-Za-z0-9_]+', table), 'unknown_table_identifier')
        info = db.execute('pragma main.table_info(' + table + ')').fetchall()
        columns = [row[1] for row in info]
        if 'id' not in columns:
            continue
        require(all(re.fullmatch('[A-Za-z0-9_]+', name) for name in columns), 'unknown_column_identifier')
        order = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]] or columns
        rows = db.execute('select * from main.' + table + ' where id=? order by ' + ','.join(order), (identifier,)).fetchall()
        tables[table] = {'columns': columns, 'rows': [list(row) for row in rows]}
    return {'schema_version': db.execute('pragma main.schema_version').fetchone()[0],
            'schema': [list(row) for row in schema], 'tables': tables}


def _owners(snapshot):
    for table, value in snapshot['tables'].items():
        for row in value['rows']:
            item = dict(zip(value['columns'], row))
            # No implicit exception for retained historical PIDs. Such a row
            # needs a separate reviewed receipt rule before it can be admitted.
            require(all(item.get(name) is None for name in ('worker_pid', 'owner_pid')),
                    'unknown_or_unverified_owner:' + table)
            state = str(item.get('state', ''))
            require(state not in ('running', 'producing', 'repairing', 'converting', 'rendering')
                    and not state.endswith(('_running', '_producing', '_repairing', '_converting', '_rendering')),
                    'unresolved_active_stage:' + table)


def _scope(snapshot, plan):
    jobs = snapshot['tables'].get('jobs', {})
    require(len(jobs.get('rows', [])) == 1, 'missing_exact_original_job')
    job = dict(zip(jobs['columns'], jobs['rows'][0]))
    source = json.loads(job['input_record'])
    record = json.loads(job['output_record'])
    manifest = json.loads(job['input_manifest'])
    require(job['category'] in ('scientific_diagram', 'poster') and job['format'] == 'svg', 'outside_requested_direct_svg_scope')
    require(job['state'] in collector.IDLE and job['worker_pid'] is None, 'not_idle_completed_svg')
    require(job['id'] == plan['id'] == source['pair_sha256'] == record['id'] == record['source_pair_sha256'], 'wrong_original_pair')
    require(job['source'] == source['source'] == record['source'], 'wrong_original_dataset')
    require(job['category'] == source['category'] == record['category'], 'wrong_original_category')
    require(job['format'] == source['format'] == record['source_format'] == 'svg' and record['format'] == 'drawio', 'wrong_original_or_candidate_format')
    for name in ('code', 'image'):
        require(source[name + '_sha256'] == record['source_' + name + '_sha256'] == plan['source_' + name + '_sha256'], 'wrong_original_' + name)
        require(record[name + '_sha256'] == plan[name + '_sha256'], 'changed_candidate_' + name)
    require(manifest['id'] == plan['id'] and manifest['source_format'] == 'svg'
            and (manifest['code_sha256'], manifest['image_sha256']) == (plan['source_code_sha256'], plan['source_image_sha256']),
            'input_manifest_original_pair_or_hash_mismatch')
    require(all(type(manifest.get(name)) is int and manifest[name] > 0 for name in ('width', 'height')),
            'input_manifest_has_no_positive_original_dimensions')
    for name in ('width', 'height'):
        require(name not in source or source[name] == manifest[name], 'input_manifest_original_dimensions_changed')
    value = snapshot['tables'].get('processing_outcomes_v2', {})
    require(len(value.get('rows', [])) == 1, 'missing_original_processing_record')
    outcome = dict(zip(value['columns'], value['rows'][0]))
    require(outcome['status'] == 'pending' and outcome['category'] == job['category'] and outcome['format'] == 'svg'
            and (outcome['source_code_hash'], outcome['source_image_hash']) == (plan['source_code_sha256'], plan['source_image_sha256']),
            'not_current_matching_pending_original')
    return job, source, manifest, record


def _logical_source_witnesses(snapshot, plan, root):
    """Bind the actual locators, including aliases outside resolved inventory."""
    job, source, manifest, record = _scope(snapshot, plan)
    expected = [(record['code_file'], record['code_sha256']),
                (record['image_file'], record['image_sha256']),
                (record['original_source_code'], record['source_code_sha256']),
                (record['original_reference'], record['source_image_sha256']),
                (manifest['source_code'], manifest['code_sha256']),
                (manifest['reference_image'], manifest['image_sha256'])]
    root = Path(root).resolve()
    result = {}
    for logical, digest in expected:
        relative = Path(logical)
        require(not relative.is_absolute() and '..' not in relative.parts, 'invalid_authoritative_payload_locator')
        path = root / relative
        require(path.resolve(strict=True).is_relative_to(root), 'authoritative_payload_outside_registered_root')
        result[str(path)] = digest
    return result, (job, source, manifest, record)


def _config_signature(config):
    return canonical({key: value for key, value in config.items() if not key.startswith('_')})


def _source_failure_taxonomy(plan):
    folder = Path(plan['evidence_directory'])
    scene = json.loads((folder / 'scene_checker.json').read_bytes())
    dom = json.loads((folder / 'scene_dom.json').read_bytes())
    require(str(folder / 'base_dom.json') in plan['files'], 'missing_complete_original_base_dom')
    base_dom = json.loads((folder / 'base_dom.json').read_bytes())
    capture = dom.get('sceneCapture', {})
    require(capture.get('completeOfflineSource') is True and capture.get('sourcePayloadHashesRecheckedAfterCapture') is True
            and capture.get('blockedResources') == [] and capture.get('objectIdsV6Compatible') is True,
            'source_capture_or_source_payload_recheck_incomplete')
    for name, key in (('svg_dom_source_scene_v1.js', 'extractorSha256'), ('auto_quality_svg_closed_scene_v1.py', 'moduleSha256')):
        pins = [digest for path, digest in plan['pins'].items() if Path(path).name == name]
        require(len(pins) == 1 and capture.get(key) == pins[0], 'source_capture_author_pin_mismatch:' + name)

    def issue(value):
        require(isinstance(value, dict) and not collector.nested_evidence_errors(value), 'nested_source_capture_or_resource_error')
        reason = value.get('reason')
        if reason in ('scene_geometry_sampling_capped', 'scene_geometry_sampling_failed') and value.get('severity') == 'informational':
            # Informational browser sampling is not the topology parser. The
            # latter must independently retain every source operation.
            shapes = [obj for obj in dom.get('objects', []) if obj.get('type') == 'shape']
            require(shapes, 'informational_sampling_has_no_source_shape_inventory')
            for obj in shapes:
                topology = obj.get('sceneGeometry', {}).get('topology', {})
                require(topology.get('parser') == 'fontTools.svgLib.path.parse_path/RecordingPen'
                        and isinstance(topology.get('subpaths'), list)
                        and topology.get('subpath_count') == len(topology['subpaths'])
                        and all(part.get('operations') for part in topology['subpaths']),
                        'informational_sampling_has_no_complete_independent_source_topology')
            return
        require(reason in SEMANTIC_ISSUES or reason == 'unsupported_visible_element' and value.get('tag') == 'foreignObject',
                'unknown_or_capture_or_clone_source_issue:' + str(reason))

    require(scene.get('failures'), 'missing_source_failure_taxonomy')
    for failure in scene['failures']:
        require(isinstance(failure, dict) and failure.get('reason') in collector.SEMANTIC_REASONS,
                'unknown_or_nonsemantic_scene_failure')
        if failure['reason'] == 'unresolved_source_feature':
            issue(failure.get('issue'))
    for name in ('full_base_issues.json', 'full_scene_issues.json', 'full_scene_additional_issues.json'):
        path = folder / name
        require(str(path) in plan['files'], 'missing_complete_source_issue_inventory:' + name)
        values = json.loads(path.read_bytes())
        require(isinstance(values, list), 'invalid_complete_source_issue_inventory')
        expected = base_dom.get('issues', []) if name == 'full_base_issues.json' else dom.get('issues', []) if name == 'full_scene_issues.json' else dom.get('sceneIssues', [])
        require(values == expected, 'complete_source_issue_inventory_differs_from_original_dom:' + name)
        for value in values:
            issue(value)
    return scene


def _capture(db, plan, config):
    require(not db.in_transaction, 'preparation_requires_no_transaction')
    db.execute('begin')
    try:
        result = collector.revalidate(db, plan, config['closure'], check_files=True)
        require(result.get('current') is True, 'stale_or_invalid_source_certificate:' + str(result.get('reason')))
        snapshot = _snapshot(db, plan['id'])
        _owners(snapshot)
        _scope(snapshot, plan)
        db.rollback()
        return snapshot
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise


def _decision_path(root, receipt):
    relative = Path(receipt['file'])
    require(not relative.is_absolute() and '..' not in relative.parts
            and relative.parent.parent == DIRECTORY and re.fullmatch('[0-9a-f]{64}', relative.parent.name)
            and relative.name == 'decision.' + receipt['sha256'] + '.json', 'invalid_immutable_decision_locator')
    path = Path(root).resolve() / relative
    require(path.resolve(strict=True).is_relative_to(Path(root).resolve() / DIRECTORY), 'decision_outside_owned_directory')
    return path


def read_decision(root, receipt):
    require(re.fullmatch('[0-9a-f]{64}', receipt.get('sha256', '')), 'invalid_decision_digest')
    path = _decision_path(root, receipt)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o444, 'decision_must_be_immutable_regular_file')
    witness = shared.file_witness(root, str(path), receipt['sha256'])
    payload = path.read_bytes()
    require(sha(payload) == receipt['sha256'], 'decision_changed_after_hash_read')
    document = json.loads(payload)
    require(canonical(document) == payload and document['id'] == path.parent.name, 'noncanonical_or_misidentified_decision')
    return document, payload, witness


def _write_decision(root, receipt, payload):
    require(sha(payload) == receipt['sha256'], 'decision_payload_digest_mismatch')
    relative = Path(receipt['file'])
    require(relative.parent.parent == DIRECTORY and re.fullmatch('[0-9a-f]{64}', relative.parent.name)
            and relative.name == 'decision.' + receipt['sha256'] + '.json', 'invalid_decision_locator')
    descriptor = os.open(Path(root).resolve(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.' + relative.name + '.' + secrets.token_hex(16) + '.tmp'
    fd = None
    try:
        for name in (*DIRECTORY.parts, relative.parent.name):
            try:
                os.mkdir(name, 0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.fsync(descriptor)
            os.fsync(child)
            os.close(descriptor)
            descriptor = child
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
        remaining = memoryview(payload)
        while remaining:
            count = os.write(fd, remaining)
            require(count > 0, 'short_decision_write')
            remaining = remaining[count:]
        os.fsync(fd)
        os.fchmod(fd, 0o444)
        os.fsync(fd)
        os.close(fd)
        fd = None
        try:
            os.link(temporary, relative.name, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
        except FileExistsError:
            _, stored, _ = read_decision(root, receipt)
            require(stored == payload, 'immutable_decision_content_conflict')
        os.fsync(descriptor)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temporary, dir_fd=descriptor)
            os.fsync(descriptor)
        except FileNotFoundError:
            pass
        os.close(descriptor)


def _outcome(plan, receipt):
    reason = 'current_verified_program_source_role_or_feature_unverifiable: ' + ','.join(plan['source_construct_classes'])
    evidence = {name: plan[name] for name in ('id', 'source_code_sha256', 'source_image_sha256', 'code_sha256', 'image_sha256', 'source_construct_classes')}
    evidence.update(reason_code='svg_current_program_complete_source_feature_or_role_failure',
                    reason_detail=reason, accepted=False, abandonment_is_not_conversion_success=True,
                    deterministic_recovery_permitted=True, new_model_calls=0,
                    certificate={'file': str(Path(plan['evidence_directory']) / 'report.json'), 'certificate_sha256': plan['certificate_sha256']},
                    active_quality_policy=plan['policy'], route_catalog_sha256=plan['catalog_sha256'],
                    scope='Unsupported by the current frozen verified production program; not intrinsic drawio inexpressibility.')
    evidence[MARKER] = {'policy': POLICY, 'decision': receipt, 'commit_nonce': receipt['commit_nonce']}
    return reason, canonical(evidence).decode()


def prepare_decision(db, plan, config, publish=False):
    require(type(publish) is bool and not db.in_transaction and db.row_factory is None, 'fresh_default_connection_and_explicit_publish_required')
    require(not db.execute('select 1 from sqlite_temp_master limit 1').fetchone(), 'temporary_schema_not_allowed')
    require(all(row[1] in ('main', 'temp') for row in db.execute('pragma database_list')), 'attached_database_not_allowed')
    plan = copy.deepcopy(plan)
    require(re.fullmatch('[0-9a-f]{64}', plan.get('id', '')), 'invalid_original_identifier')
    require(plan.get('proposal') is True and plan.get('source_construct_classes'), 'not_a_semantic_source_failure_proposal')
    require(plan['id'] not in config['research_reserved_ids'], 'reserved_active_deterministic_research')
    require(plan['id'] not in config['authorized_model_ids'], 'reserved_authorized_localized_model_case')
    started = time.monotonic()
    snapshot = _capture(db, plan, config)
    registry = shared._registry(db, plan['id'])
    files = {path: value['sha256'] for path, value in plan['files'].items()}
    certificate = Path(plan['evidence_directory']) / 'report.json'
    require(certificate.resolve().is_relative_to(Path(config['closure']['evidence_root']).resolve()), 'unowned_source_certificate')
    stored = json.loads(certificate.read_bytes())
    require(canonical(stored) == canonical(plan), 'supplied_certificate_differs_from_owned_file')
    scene = _source_failure_taxonomy(plan)
    classes = sorted(collector.source_reasons(scene) & collector.SEMANTIC_REASONS)
    require(plan['source_construct_classes'] == classes and classes,
            'source_failure_classes_do_not_match_complete_frozen_scene_evidence')
    files[str(certificate)] = sha(certificate.read_bytes())
    for path, digest in config['pins'].items():
        require(path not in files or files[path] == digest, 'conflicting_source_or_implementation_witness')
        files[path] = digest
    required_aliases, authorities = _logical_source_witnesses(snapshot, plan, config['root'])
    for path, digest in required_aliases.items():
        require(path not in files or files[path] == digest, 'conflicting_authoritative_logical_payload_digest')
        files[path] = digest
    witnesses = {path: shared.file_witness(config['root'], path, digest) for path, digest in sorted(files.items())}
    resolved = {value['identity']['resolve']: value['sha256'] for value in witnesses.values()}
    for authority in authorities:
        for path, digest in shared._logical_aliases(authority, config['root'], resolved).items():
            if path not in witnesses:
                witnesses[path] = shared.file_witness(config['root'], path, digest)
    require(_capture(db, plan, config) == snapshot, 'complete_database_snapshot_changed_during_preparation')
    shared._check_identities(config['root'], witnesses)
    nonce = secrets.token_hex(16)
    stamp = now()
    document = {'version': 1, 'id': plan['id'], 'created_at': stamp, 'writer_policy': POLICY,
                'writer_sha256': sha(Path(__file__).read_bytes()), 'commit_nonce': nonce,
                'plan': plan, 'plan_sha256': sha(canonical(plan)), 'prior_outcome': dict(zip(REGISTRY_COLUMNS, registry)),
                'complete_database_cas_snapshot': snapshot, 'file_witnesses': witnesses,
                'reviewed_config': config, 'scope': config['scope'], 'accepted': False,
                'deterministic_recovery_permitted': True, 'abandonment_is_not_conversion_success': True, 'new_model_calls': 0}
    payload = canonical(document)
    digest = sha(payload)
    receipt = {'file': str(DIRECTORY / plan['id'] / ('decision.' + digest + '.json')),
               'sha256': digest, 'plan_sha256': document['plan_sha256'], 'commit_nonce': nonce, 'created_at': stamp}
    reason, raw = _outcome(plan, receipt)
    expected = tuple(list(registry[:4]) + ['abandoned', reason, raw, stamp])
    if publish:
        _write_decision(config['root'], receipt, payload)
        stored, stored_payload, witness = read_decision(config['root'], receipt)
        require(stored_payload == payload, 'durable_decision_readback_failed')
        witnesses['decision:' + digest] = witness
    return {'_seal': _SEAL, 'plan': plan, 'snapshot': snapshot, 'registry': registry,
            'expected': expected, 'witnesses': witnesses, 'receipt': receipt, 'document': document,
            'config_signature': _config_signature(config), 'publish': publish,
            'preparation_seconds': time.monotonic() - started}


def apply_prepared(db, prepared, config):
    require(prepared.get('_seal') is _SEAL and not db.in_transaction, 'unverified_or_borrowed_preparation')
    base = {'id': prepared['plan']['id'], 'policy': POLICY, 'applied': False, 'accepted': False, 'decision': prepared['receipt']}
    acquired = None
    committing = False
    updated = False
    try:
        begin = BusyBudget(config.get('writer_begin_seconds', 180), 5)
        if prepared['publish']:
            begin.begin(db)
        else:
            db.execute('begin')
        acquired = time.monotonic()
        require(_config_signature(config) == prepared['config_signature'], 'configuration_changed_after_preparation')
        require(_snapshot(db, base['id']) == prepared['snapshot'], 'full_database_compare_and_swap_changed')
        _owners(prepared['snapshot'])
        shared._check_identities(config['root'], prepared['witnesses'])
        if not prepared['publish']:
            db.rollback()
            return {**base, 'state': 'dry_run_current', 'would_apply': True, 'writer_lock_held_seconds': 0.0}
        reason, raw, stamp = prepared['expected'][5:8]
        changes = db.total_changes
        where = ' and '.join(name + ' is ?' for name in REGISTRY_COLUMNS)
        cursor = db.execute('update processing_outcomes_v2 set status="abandoned",reason=?,record=?,updated_at=? where id=? and ' + where,
                            (reason, raw, stamp, base['id'], *prepared['registry']))
        cursor.fetchall()
        require(cursor.rowcount == 1 and db.total_changes - changes == 1, 'registry_CAS_or_trigger_side_effect_refused')
        updated = True
        require(shared._registry(db, base['id']) == prepared['expected'], 'committed_row_differs_from_exact_decision')
        shared._check_identities(config['root'], prepared['witnesses'])
        committing = True
        end = BusyBudget(config.get('writer_commit_seconds', 30), 5)
        end.commit(db)
        return {**base, 'state': 'abandoned', 'applied': True, 'commit_nonce': prepared['receipt']['commit_nonce'],
                'writer_lock_held_seconds': time.monotonic() - acquired, 'begin_diagnostics': begin.diagnostics(),
                'commit_diagnostics': end.diagnostics(), 'jobs_queues_source_and_histories_unchanged': True}
    except BaseException as error:
        active = db.in_transaction
        if active:
            db.rollback()
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        recovered = False
        if committing and updated and not active:
            try:
                recovered = shared._registry(db, base['id']) == prepared['expected']
            except sqlite3.Error:
                pass
        return {**base, 'state': 'abandoned' if recovered else 'commit_outcome_unknown' if committing and updated and not active else 'failed_rolled_back',
                'applied': bool(recovered), 'commit_receipt_recovered': bool(recovered), 'error': repr(error),
                'writer_lock_held_seconds': time.monotonic() - acquired if acquired is not None else 0.0,
                'may_have_committed': bool(committing and updated and not active and not recovered)}


def apply(db, plan, config, publish=False):
    require(not db.in_transaction and db.row_factory is None and type(publish) is bool, 'fresh_connection_and_boolean_publish_required')
    row = shared._registry(db, plan['id'])
    if row is None or row[4] != 'pending':
        return {'id': plan['id'], 'state': 'preserved_' + str(row[4] if row else 'missing_registry'), 'applied': False, 'accepted': False}
    try:
        prepared = prepare_decision(db, plan, config, publish)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        return {'id': plan['id'], 'state': 'preparation_refused', 'error': repr(error), 'applied': False, 'accepted': False, 'no_writer_transaction_opened': True}
    return apply_prepared(db, prepared, config)
