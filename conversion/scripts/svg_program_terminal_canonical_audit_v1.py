"""Read-only, repeatable audit of committed SVG program-terminal receipts.

No writer/planner is imported. Data/media stay on the machine that runs this
script. A coherent SQLite read snapshot is released before any file hashing.
Later same-source candidate or job metadata changes are reported as superseded,
not attributed to the terminal writer. Reports use a new owned timestamp path.
"""
import argparse
import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import uuid

LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ROOT = Path('/backup/shaoshitong/img2code_20261029')
MARKER = 'svg_program_terminal_outcome_v1'
PINS = {'writer_sha256': 'f892477e6d7069c844e63f353e75798d1ced0b807e4a97f793b64a5857175c8a',
        'collector_sha256': 'f7a0aca39833513aa660a7b3bf39639649aeae01069436dac23b759ec8b44e60'}
READER_SHA = '2cfe22ab23ba04dccb8940e6782582a1ace9c0e6e8c1d495adfdcdab165f486c'
PRIOR_READER_SHA = '1fa069a7c2983f2b284d378f0e788bc8f693ab8069840d1de451edb75fbe68e9'
RESERVATION = 'conversion/prototype/svg_marker_composition_v2/research_cohort_manifest.json'
RESERVATION_SHA = '85ae48fc00597c3d86e7d5db2b52d5234050d7d0b4b87f3fe43c4f4a79943bb8'
TAXONOMY = 'conversion/svg_current_program_failure_taxonomy_review.json'
TAXONOMY_SHA = '372b6fc6d6ce92b5f26a2a507603d8cff4172615b4407239ac2dab61a076b5f1'
REPORT_DIRECTORY = 'conversion/audit/svg_program_terminal_canonical_audit_v1'
JOB_COLUMNS = ('id', 'category', 'format', 'source', 'input_record', 'state', 'route', 'attempts',
               'updated_at', 'output_record', 'error', 'input_manifest', 'worker_pid')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def file_digest(root, logical, expected, cache=None, clean=True):
    relative = Path(logical)
    require(not relative.is_absolute() and '..' not in relative.parts, 'nonrelative_payload_locator')
    path = Path(root) / relative
    target = path.resolve(strict=True)
    owned = Path(root).resolve() if clean is None else Path(root).resolve() / ('clean' if clean else 'conversion')
    require(target.is_relative_to(owned), 'payload_outside_owned_data_root')
    before = target.stat()
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
    require(stat.S_ISREG(before.st_mode), 'payload_not_regular')
    key = (str(target), fields(before))
    actual = cache.get(key) if cache is not None else None
    if actual is None:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            require(fields(os.fstat(stream.fileno())) == fields(before), 'payload_changed_before_read')
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
            require(fields(os.fstat(stream.fileno())) == fields(before), 'payload_changed_during_read')
        actual = digest.hexdigest()
        if cache is not None:
            cache[key] = actual
    require(path.resolve(strict=True) == target and fields(target.stat()) == fields(before), 'payload_path_changed_during_read')
    require(actual == expected, 'payload_digest_mismatch:' + str(relative))
    return {'file': str(relative), 'sha256': actual, 'bytes': before.st_size}


def four(record):
    return tuple(record[name] for name in ('source_code_sha256', 'source_image_sha256', 'code_sha256', 'image_sha256'))


def source_identity(identifier, job, record, plan):
    original = json.loads(job['input_record'])
    require(job['id'] == identifier == record['id'] == record['source_pair_sha256'] == original['pair_sha256'], 'original_pair_identity_mismatch')
    require(job['category'] == original['category'] == record['category'] and job['category'] in ('scientific_diagram', 'poster'), 'original_category_mismatch')
    require(job['source'] == original['source'] == record['source'], 'original_dataset_mismatch')
    require(job['format'] == original['format'] == record['source_format'] == 'svg' and record['format'] == 'drawio', 'original_format_mismatch')
    require((original['code_sha256'], original['image_sha256']) == four(record)[:2]
            == (plan['source_code_sha256'], plan['source_image_sha256']), 'original_source_hash_mismatch')
    manifest = json.loads(job['input_manifest'])
    require(manifest['id'] == identifier and manifest['source_format'] == 'svg'
            and (manifest['code_sha256'], manifest['image_sha256']) == four(record)[:2], 'original_manifest_identity_mismatch')
    return original, manifest


def revision_kind(before, current, prior_job, current_job):
    require(four(before)[:2] == four(current)[:2], 'source_identity_changed_after_decision')
    if four(before)[2:] != four(current)[2:]:
        return 'superseded_candidate_same_original_source'
    if prior_job != current_job:
        return 'superseded_job_metadata_same_candidate'
    return 'exact_committed_job_and_revision_preserved'


def publisher_state(root):
    path = Path(root) / 'conversion/svg_program_terminal_finite_cohort_v1_owner.json'
    try:
        raw = path.read_bytes()
        owner = json.loads(raw)
        pid = int(owner['pid'])
        item = {'owner_file': str(path), 'owner_sha256': sha(raw), 'declared_pid': pid,
                'declared_birth': owner['pid_start_ticks'], 'run_id': owner.get('run_id'), 'run': owner.get('run'),
                'selected': owner.get('selected'), 'writer_sha256': owner.get('writer_sha256'),
                'reader_sha256': owner.get('reader_sha256')}
        try:
            tokens = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(') ', 1)[1].split()
            command = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
            item.update(actual_birth=int(tokens[19]), ppid=int(tokens[1]), process_state=tokens[0],
                        command=[part.decode(errors='replace') for part in command if part])
            item['declared_birth_matches_actual'] = item['actual_birth'] == owner['pid_start_ticks']
            item['state'] = 'live_matching_birth' if item['declared_birth_matches_actual'] else 'pid_reused_not_original_owner'
            item['command_script_hashes'] = [{'file': part, 'sha256': sha(Path(part).read_bytes())}
                                             for part in item['command'] if part.endswith('.py') and Path(part).is_absolute() and Path(part).is_file()]
        except (FileNotFoundError, ProcessLookupError):
            item['state'] = 'original_publisher_no_longer_present'
        return item
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'state': 'owner_status_unavailable', 'error': repr(error)}


def snapshot(db, protected):
    require(not db.in_transaction, 'audit_requires_no_existing_transaction')
    require(tuple(row[1] for row in db.execute('pragma main.table_info(jobs)')) == JOB_COLUMNS, 'unexpected_jobs_schema')
    db.execute('begin')
    try:
        rows = db.execute("select id,category,format,source_code_hash,source_image_hash,reason,record,updated_at from processing_outcomes_v2 where status='abandoned' and instr(record,?)>0 order by id", ('"svg_program_terminal_outcome_v',)).fetchall()
        jobs = {}
        for row in rows:
            current = db.execute('select * from jobs where id=?', (row[0],)).fetchone()
            jobs[row[0]] = dict(zip(JOB_COLUMNS, current)) if current else None
        protections = {}
        for identifier in sorted(protected):
            value = db.execute('select category,format,source_code_hash,source_image_hash,status,reason from processing_outcomes_v2 where id=?', (identifier,)).fetchone()
            protections[identifier] = list(value) if value else None
        db.rollback()
        return rows, jobs, protections
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise


def audit_one(row, current_job, reader, root, cache):
    identifier = row[0]
    output = {'id': identifier, 'state': 'audit_failed', 'errors': []}
    try:
        verified = reader.validate_outcome(row[:7], root, {'svg': PINS})
        evidence = json.loads(row[6])
        receipt = evidence[MARKER]['decision']
        document = reader._read(root, receipt, identifier)
        require(row[7] == receipt['created_at'], 'outcome_timestamp_differs_from_nonce_decision')
        require(verified['receipt_verified'] and document['commit_nonce'] == evidence[MARKER]['commit_nonce'] == receipt['commit_nonce'], 'receipt_nonce_not_verified')
        plan = document['plan']
        value = document['complete_database_cas_snapshot']['tables']['jobs']
        require(tuple(value['columns']) == JOB_COLUMNS and len(value['rows']) == 1, 'decision_missing_exact_original_job')
        before_job = dict(zip(value['columns'], value['rows'][0]))
        before = json.loads(before_job['output_record'])
        source_identity(identifier, before_job, before, plan)
        require(four(before) == tuple(plan[name] for name in ('source_code_sha256', 'source_image_sha256', 'code_sha256', 'image_sha256')), 'decision_job_four_hash_mismatch')
        require(current_job is not None and current_job['output_record'], 'current_job_or_candidate_missing')
        current = json.loads(current_job['output_record'])
        _, manifest = source_identity(identifier, current_job, current, plan)
        require((current_job['id'], current_job['category'], current_job['format'], current_job['source'])
                == (before_job['id'], before_job['category'], before_job['format'], before_job['source']), 'current_original_registration_changed')
        kind = revision_kind(before, current, before_job, current_job)
        checks = []
        for locator, digest in (('original_source_code', 'source_code_sha256'), ('original_reference', 'source_image_sha256'),
                                ('code_file', 'code_sha256'), ('image_file', 'image_sha256')):
            checks.append(file_digest(root, current[locator], current[digest], cache))
        for locator, digest in (('source_code', 'code_sha256'), ('reference_image', 'image_sha256')):
            checks.append(file_digest(root, manifest[locator], manifest[digest], cache, clean=None))
        folder = Path(plan['evidence_directory']).resolve(strict=True)
        for name, expected in (('current.drawio', plan['code_sha256']), ('original_source.svg', plan['source_code_sha256'])):
            relative = folder.relative_to(Path(root).resolve()) / name
            checks.append(file_digest(root, relative, expected, cache, clean=False))
        output.update(state='verified', revision_state=kind, receipt=receipt, commit_nonce=receipt['commit_nonce'],
                      baseline_four_hashes=list(four(before)), current_four_hashes=list(four(current)),
                      source_identity_verified=True, current_job_state=current_job['state'], current_worker_pid=current_job['worker_pid'],
                      current_quality_state=current.get('quality_state'), current_conversion_method=current.get('conversion_method'),
                      current_code_file=current['code_file'], current_image_file=current['image_file'],
                      immutable_source_certificate_sha256=plan['certificate_sha256'], artifact_checks=checks,
                      later_job_changes_not_attributed_to_terminal_writer=(kind != 'exact_committed_job_and_revision_preserved'))
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        output['errors'].append(repr(error))
    return output


def run(root, reader=None):
    root = Path(root).resolve()
    scripts = root / 'conversion/scripts'
    implementations = {'reader_v3': (scripts / 'negative_terminal_receipt_reader_v3.py', READER_SHA),
                       'reader_v2': (scripts / 'negative_terminal_receipt_reader_v2.py', PRIOR_READER_SHA),
                       'writer': (scripts / 'svg_program_terminal_outcomes_v1.py', PINS['writer_sha256']),
                       'collector': (scripts / 'svg_failure_closure_v1.py', PINS['collector_sha256'])}
    for path, expected in implementations.values():
        require(sha(path.read_bytes()) == expected, 'audit_implementation_pin_changed:' + path.name)
    if reader is None:
        sys.path.insert(0, str(scripts))
        reader = importlib.import_module('negative_terminal_receipt_reader_v3')
        require(Path(reader.__file__).resolve() == implementations['reader_v3'][0].resolve(), 'reader_import_path_mismatch')
    reserved_bytes = (root / RESERVATION).read_bytes()
    taxonomy_bytes = (root / TAXONOMY).read_bytes()
    require(sha(reserved_bytes) == RESERVATION_SHA and sha(taxonomy_bytes) == TAXONOMY_SHA, 'protected_cohort_manifest_pin_changed')
    reserved = set(json.loads(reserved_bytes)['ids'])
    review = json.loads(taxonomy_bytes)['taxonomy_review']
    capture = set(review['clone_context_proposal_unique_ids']) | set(review['switch_proposal_unique_ids'])
    require(len(reserved) == 16 and len(capture) == 24, 'protected_cohort_counts_changed')
    started = now()
    db = sqlite3.connect('file:' + str(root / 'conversion/jobs.sqlite') + '?mode=ro', uri=True, timeout=0)
    try:
        db.execute('pragma query_only=on')
        rows, jobs, protections = snapshot(db, reserved | capture)
    finally:
        db.close()
    snapshot_finished = now()
    cache = {}
    results = [audit_one(row, jobs[row[0]], reader, root, cache) for row in rows]
    protected_errors = [{'id': identifier, 'observed': value, 'error': 'protected_original_not_pending_svg'}
                        for identifier, value in protections.items() if not value or value[1] != 'svg' or value[4] != 'pending']
    counts = {}
    for value in results:
        key = value.get('revision_state', value['state'])
        counts[key] = counts.get(key, 0) + 1
    require(sha(Path(__file__).read_bytes()) == LOADED_SOURCE_SHA256, 'audit_source_changed_during_run')
    return {'schema': 'svg_program_terminal_canonical_audit_v1', 'started_at': started,
            'sqlite_read_snapshot_released_at': snapshot_finished, 'finished_at': now(), 'root': str(root),
            'read_only': True, 'canonical_writer_called': False, 'canonical_mutations': 0, 'model_api_calls': 0,
            'audit_script_sha256': LOADED_SOURCE_SHA256,
            'implementation_sha256': {name: digest for name, (_, digest) in implementations.items()},
            'committed_new_svg_marker_rows_in_snapshot': len(rows),
            'verified_rows': sum(value['state'] == 'verified' for value in results),
            'failed_rows': sum(value['state'] != 'verified' for value in results),
            'revision_counts': counts, 'rows': results, 'publisher': publisher_state(root),
            'protected_research_count': len(reserved), 'protected_capture_clone_count': len(capture),
            'protected_unique_count': len(reserved | capture), 'protected_all_pending': not protected_errors,
            'protected_errors': protected_errors, 'protected_outcomes': protections,
            'scope': 'Only rows committed in this SQLite snapshot are claimed audited. Later writer commits require rerun. Same-source candidate/job changes are superseded, not proof that the terminal writer changed jobs.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = run(args.root)
    directory = args.root.resolve() / REPORT_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '_' + uuid.uuid4().hex[:8] + '.json')
    raw = canonical(result)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({'report': str(path), 'sha256': sha(raw), 'started_at': result['started_at'],
                      'rows': result['committed_new_svg_marker_rows_in_snapshot'], 'verified': result['verified_rows'],
                      'failed': result['failed_rows'], 'revision_counts': result['revision_counts'],
                      'protected_all_pending': result['protected_all_pending'], 'publisher': result['publisher']}, ensure_ascii=False))
    return 0 if not result['failed_rows'] and result['protected_all_pending'] else 2


if __name__ == '__main__':
    sys.exit(main())
