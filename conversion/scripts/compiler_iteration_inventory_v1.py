"""Snapshot full-scope accepted data and retryable backlog; no model/conversion.

Historical ``abandoned`` is an attempt outcome, never an irrecoverable input.
All indexes and assets remain on HKUST. Sources are read without changing a run.
"""
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

ROOT = Path('/backup/shaoshitong/img2code_20261029')
CATEGORIES = {'scientific_diagram', 'poster'}
SOURCES = [
    ('initial_screen', 'jsonl', 'release/fixed_batch_v1/initial_screen_20261031_1717/processed.jsonl'),
    ('graphviz_v1_C', 'db', 'release/compiler_v1/graphviz_unseen_20261101_v1_C/status.sqlite'),
    ('round2', 'db', 'release/round2_fixed_v1/repair_pass_20261101_0627/status.sqlite'),
    ('other_formats', 'jsonl', 'release/compiler_types_v1/programs/other_formats_20261101_v2/failed_attempts.jsonl'),
    ('other_formats_accepted', 'manifests', 'release/compiler_types_v1/programs/other_formats_20261101_v2/qualified_merged.jsonl'),
    ('graphviz_v2_prior', 'wrapped', 'release/compiler_v2/preparation_graphviz_batch_20261101_v2_renderdomain/prior_results.jsonl'),
    ('graphviz_live_v2', 'db', 'release/compiler_v2/graphviz_batch_20261101_v2_renderdomain/status.sqlite'),
]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def read_scope(root):
    path = root / 'release/manifest.jsonl'
    scope, counts, manifest_rows, duplicates = {}, collections.Counter(), 0, 0
    h = hashlib.sha256()
    with path.open('rb') as f:
        for line in f:
            h.update(line)
            if not line.strip():
                continue
            manifest_rows += 1
            x = json.loads(line)
            if x.get('category') not in CATEGORIES:
                continue
            identifier = x['pair_sha256']
            item = {k: x.get(k) for k in ('category', 'format', 'source', 'code_sha256', 'image_sha256')}
            if identifier in scope:
                if scope[identifier] != item:
                    raise ValueError('conflicting_scope_identity:' + identifier)
                duplicates += 1
                continue
            scope[identifier] = item
            counts[item['category']] += 1
    expected = {'scientific_diagram': 107161, 'poster': 24743}
    if dict(counts) != expected:
        raise ValueError('scope_changed_requires_explicit_reconciliation:' + compact_json(dict(counts)))
    return scope, dict(manifest_rows=manifest_rows, unique_scope=len(scope), duplicate_scope_rows=duplicates,
                       categories=dict(counts), manifest_sha256=h.hexdigest())


def read_results(root, kind, rel):
    path = root / rel
    if not path.exists():
        raise FileNotFoundError(path)
    if kind == 'db':
        db = sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True, timeout=30)
        try:
            db.execute('begin')
            for identifier, status, text in db.execute('select id,status,result from samples order by seq'):
                x = json.loads(text) if text else {'id': identifier, 'status': status}
                if x.get('id') != identifier or x.get('status') != status:
                    raise ValueError('ledger_result_identity_mismatch:' + identifier)
                yield x
        finally:
            db.close()
    else:
        with path.open() as f:
            for line in f:
                if line.strip():
                    x = json.loads(line)
                    if kind == 'wrapped':
                        x = x['result']
                    elif kind == 'manifests':
                        x = dict(id=x['id'], status='qualified', manifest=x)
                    yield x


def failure_family(result):
    text = compact_json({k: result.get(k) for k in ('phase', 'reason', 'detail', 'quality_failures')}).lower()
    for family, words in [
        ('runtime_or_environment', ('infrastructure_', 'page.capturescreenshot', 'modulenotfounderror', 'importerror')),
        ('font_and_text', ('font', 'glyph', 'textcoverage', 'text_coverage')),
        ('canvas_and_coordinates', ('canvas', 'clipping', 'viewport', 'outside_reference')),
        ('nodes_edges_and_arrows', ('dangling', 'terminal', 'arrow', 'edge', 'geometry')),
        ('source_coverage_or_reproduction', ('source', 'coverage', 'profile', 'unsupported')),
        ('visual_alignment', ('pixel', 'ssim', 'alignment', 'visual')),
        ('input_or_conversion', ('convert', 'parse', 'xml', 'syntax')),
    ]:
        if any(word in text for word in words):
            return family
    return 'needs_diagnosis'


def live_owner(directory):
    """A historical queued row is active only with its actual live owner."""
    try:
        owner = json.loads((directory / 'owner.json').read_bytes())
        process = Path('/proc') / str(owner['pid'])
        fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        command = (process / 'cmdline').read_bytes().split(b'\0')
        if fields[0] == 'Z' or int(fields[19]) != owner['start_ticks']:
            return False
        return any(str(directory).encode() in part or directory.name.encode() in part for part in command)
    except (OSError, ValueError, KeyError, IndexError):
        return False


def check_manifest(root, identifier, item, row, hash_cache):
    identity = (row.get('id'), row.get('source_format'), row.get('category'),
                row.get('source_code_sha256'), row.get('source_image_sha256'))
    expected = (identifier, item['format'], item['category'], item['code_sha256'], item['image_sha256'])
    if (identity != expected or row.get('source_pair_sha256') != identifier or
            row.get('format') != 'drawio' or row.get('status') != 'qualified'):
        raise ValueError('accepted_manifest_source_identity_mismatch:' + row['id'])
    clean = (root / 'clean').resolve(strict=True)
    for field, hash_field in [('code_file', 'code_sha256'), ('image_file', 'image_sha256'),
                              ('metadata_file', 'metadata_sha256'), ('original_source_code', 'source_code_sha256'),
                              ('original_reference', 'source_image_sha256')]:
        p = (root / row[field]).resolve(strict=True)
        if not p.is_file() or not p.is_relative_to(clean):
            raise ValueError('accepted_asset_not_actual_clean_file:' + row[field])
        if p not in hash_cache:
            hash_cache[p] = digest(p)
        if hash_cache[p] != row[hash_field]:
            raise ValueError('accepted_asset_hash_mismatch:' + row[field])


def snapshot(root, output):
    output.mkdir(parents=True, exist_ok=False)
    scope, scope_info = read_scope(root)
    accepted, latest_failures, seen_attempts, live_states = {}, {}, collections.Counter(), {}
    source_counts, conflicts, cache = [], [], {}
    event_file = output / 'attempts.jsonl'
    with event_file.open('w') as out:
        discovered = [('iteration_' + p.parent.name, 'db', str(p.relative_to(root)))
                      for p in sorted((root / 'release/compiler_iterations/runs').glob('*/status.sqlite'))]
        discovered += [('iteration_control_' + p.parent.name, 'manifests', str(p.relative_to(root)))
                       for p in sorted((root / 'release/compiler_iterations/controls').glob('*/qualified.jsonl'))]
        for name, kind, rel in SOURCES + discovered:
            counts = collections.Counter()
            active = kind == 'db' and live_owner((root / rel).parent)
            for result in read_results(root, kind, rel):
                identifier, status = result['id'], result['status']
                if identifier not in scope:
                    raise ValueError('attempt_outside_scope:' + identifier)
                counts[status] += 1
                if status in ('queued', 'running'):
                    if active:
                        live_states[identifier] = status
                    continue
                if kind != 'manifests':
                    seen_attempts[identifier] += 1
                manifest = result.get('manifest')
                if status == 'qualified' and manifest:
                    accepted[identifier] = manifest
                elif status != 'qualified':
                    latest_failures[identifier] = dict(run=name, reason=result.get('reason'),
                                                       family=failure_family(result),
                                                       evidence=result.get('quality_report') or result.get('evidence_directory'))
                out.write(compact_json(dict(id=identifier, run=name, status=status,
                                            reason=result.get('reason'),
                                            family=failure_family(result) if status != 'qualified' else None,
                                            quality_report=result.get('quality_report'))) + '\n')
            source_counts.append(dict(run=name, path=rel, counts=dict(counts), live_owner_verified=active))
    # A newer accepted revision may legitimately replace a prior revision.
    # Verify current selected assets, not superseded historical paths/hashes.
    for identifier, manifest in list(accepted.items()):
        try:
            check_manifest(root, identifier, scope[identifier], manifest, cache)
        except Exception as error:
            conflicts.append(dict(id=identifier, reason=str(error)))
            del accepted[identifier]
    by_format = collections.defaultdict(collections.Counter)
    backlog = collections.defaultdict(collections.Counter)
    with (output / 'qualified.jsonl').open('w') as q, (output / 'dispositions.jsonl').open('w') as d:
        for identifier, item in sorted(scope.items()):
            if identifier in accepted:
                state = 'qualified'
                q.write(compact_json(accepted[identifier]) + '\n')
            elif identifier in live_states:
                state = live_states[identifier]
            elif identifier in latest_failures:
                state = 'pending_retry'
            else:
                state = 'pending_conversion'
            by_format[item['format']][state] += 1
            row = dict(id=identifier, source_format=item['format'], category=item['category'], state=state,
                       recorded_attempt_events=seen_attempts[identifier], irrecoverable=False)
            if identifier in latest_failures and state != 'qualified':
                row['latest_failure'] = latest_failures[identifier]
                backlog[item['format']][latest_failures[identifier]['family']] += 1
            d.write(compact_json(row) + '\n')
    summary = dict(schema='compiler_iteration_inventory_v1', at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   inventory_program_sha256=digest(Path(__file__).resolve()),
                   scope=scope_info, qualified_total=len(accepted), by_format=dict(by_format),
                   remaining=len(scope) - len(accepted), final_irrecoverable=0,
                   failure_families_by_format=dict(backlog), sources=source_counts,
                   accepted_integrity_errors=conflicts, checked_distinct_clean_asset_hashes=len(cache),
                   interpretation='All historical abandoned outcomes remain retryable. No format stopped; no conversion dispatched by this snapshot.')
    for filename in ('qualified.jsonl', 'dispositions.jsonl', 'attempts.jsonl'):
        summary.setdefault('files', {})[filename] = dict(sha256=digest(output / filename), bytes=(output / filename).stat().st_size)
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    current = root / 'release/compiler_iterations/current.json'
    current.parent.mkdir(parents=True, exist_ok=True)
    pointer = dict(goal_complete=False, overall_state='active_converter_repair',
                   inventory=str((output / 'summary.json').relative_to(root)),
                   inventory_sha256=digest(output / 'summary.json'),
                   qualified_manifest=str((output / 'qualified.jsonl').relative_to(root)),
                   qualified_total=len(accepted), at_utc=summary['at_utc'],
                   snapshot_kind='all_five_current_clean_asset_hashes_verified',
                   accepted_integrity_errors=len(conflicts))
    temporary = current.with_name(current.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(current)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if conflicts:
        raise SystemExit('Accepted asset integrity errors require repair; see summary, no data was deleted.')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    snapshot(args.root, args.output)
