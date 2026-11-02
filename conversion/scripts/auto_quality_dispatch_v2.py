"""Transaction-local, revision-deduplicated model dispatch after real QA failures.

The caller owns BEGIN/COMMIT/ROLLBACK and its jobs CAS. This module changes only
its dispatch ledger and eligible Harness queue states, and returns metadata for
the caller to publish. It never opens a model session or writes XML/PNG/jobs.
"""
import base64
import copy
import datetime
import hashlib
import json
import math
import re
import urllib.parse
import xml.etree.ElementTree as E
import zlib
from decimal import Decimal, InvalidOperation
from pathlib import Path

R = Path('/backup/shaoshitong/img2code_20261029')
TABLE = 'auto_quality_model_dispatch_v2'
KEY_VERSION = 'source_bound_native_semantic_revision_v2'
HASH = re.compile(r'^[0-9a-f]{64}$')
NUMERIC = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def initialize(db):
    """No implicit transaction management; caller chooses its schema transaction."""
    db.execute('CREATE TABLE IF NOT EXISTS ' + TABLE + ''' (
      id TEXT NOT NULL, semantic_revision_key TEXT NOT NULL,
      source_code_sha256 TEXT NOT NULL,source_image_sha256 TEXT NOT NULL,
      source_data_sha256 TEXT, code_sha256 TEXT NOT NULL,image_sha256 TEXT,
      dispatched INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL,
      queue_state_before TEXT,queue_state_after TEXT,
      baseline_code_sha256 TEXT,baseline_semantic_revision_key TEXT,
      policy TEXT,feedback TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
      PRIMARY KEY(id,semantic_revision_key))''')


def _number(value):
    if not NUMERIC.fullmatch(value):
        return value
    try:
        number = Decimal(value)
        if not number.is_finite():
            return value
        return '0' if not number else format(number.normalize(), 'f')
    except InvalidOperation:
        return value


def _uri(value):
    if not value.startswith('data:') or ',' not in value:
        return value
    header, payload = value.split(',', 1)
    header = header.replace('\x00', ';')
    try:
        raw = urllib.parse.unquote_to_bytes(payload)
        # drawio's image style commonly omits the literal ;base64 marker.
        if ';base64' in header or header.startswith('data:image/'):
            raw = base64.b64decode(raw, validate=True)
        return 'data-sha256:' + header.split(';', 1)[0].lower() + ':' + sha(raw)
    except (ValueError, TypeError):
        return 'opaque-data-sha256:' + sha(value.encode())


def _style(value):
    # Preserve data-URI header semicolons while splitting the outer style list.
    value = re.sub(r'((?:image|fontSource)=data:[^,]*,)',
                   lambda match: match.group(0).replace(';', '\x00'), value)
    reset = value.startswith(';')
    segments, properties = [], {}
    def flush():
        if properties:
            segments.append({'properties': sorted(properties.items())})
            properties.clear()
    for token in value.split(';'):
        if not token:
            continue
        if '=' not in token:
            flush()
            segments.append({'named_style': token})
            continue
        key, item = token.split('=', 1)
        item = item.replace('\x00', ';')
        if item.startswith('data:'):
            item = _uri(item)
        elif key == 'shape' and item.startswith('stencil(') and item.endswith(')'):
            try:
                stencil = zlib.decompress(base64.b64decode(item[8:-1]), -15).decode()
                item = 'stencil-semantic-sha256:' + sha(json.dumps(_tree(E.fromstring(stencil)), separators=(',', ':'), ensure_ascii=False).encode())
            except Exception:
                item = 'opaque-stencil-sha256:' + sha(item.encode())
        else:
            item = _number(item)
        properties[key] = item  # Native style properties use the final assignment.
    flush()
    return {'reset_default_style': reset, 'ordered_style_segments': segments}


def _tree(element):
    attributes = {}
    geometry = element.tag in ('mxGeometry', 'mxPoint', 'mxRectangle')
    if geometry:
        for key in ('x', 'y'):
            attributes[key] = _number(element.get(key, '0'))
        if element.tag != 'mxPoint':
            for key in ('width', 'height'):
                attributes[key] = _number(element.get(key, '0'))
    for key, value in element.attrib.items():
        if key == 'style':
            attributes[key] = _style(value)
        elif geometry and key in ('x', 'y', 'width', 'height'):
            attributes[key] = _number(value)
        elif geometry and key == 'relative':
            if value not in ('0', 'false'):
                attributes[key] = value
        elif key == 'extFonts':
            fonts = []
            for entry in value.split('|'):
                if not entry:
                    continue
                family, separator, uri = entry.partition('^')
                fonts.append([family, _uri(uri) if separator else ''])
            attributes[key] = fonts
        elif element.tag == 'mxGraphModel' and key in ('pageWidth', 'pageHeight', 'pageScale', 'dx', 'dy'):
            attributes[key] = _number(value)
        else:
            # Keep every visible text byte, parent/terminal/id, geometry, custom
            # resource and native style. XML attribute order alone is irrelevant.
            attributes[key] = value
    text = element.text if element.text and element.text.strip() else None
    tail = element.tail if element.tail and element.tail.strip() else None
    return [element.tag, sorted(attributes.items()), text,
            [_tree(child) for child in element], tail]


def _identity(record):
    identity = {key: record.get(key) for key in ('id', 'source_code_sha256', 'source_image_sha256')}
    if not identity['id'] or not all(HASH.fullmatch(str(identity[key] or '')) for key in ('source_code_sha256', 'source_image_sha256')):
        raise ValueError('dispatch_source_identity_missing_or_invalid')
    if record.get('source_pair_sha256') not in (None, record['id']):
        raise ValueError('dispatch_source_pair_identity_mismatch')
    source_record = record.get('source_record')
    if isinstance(source_record, dict):
        for source, target in (('image_sha256', 'source_image_sha256'), ('code_sha256', 'source_code_sha256')):
            if source_record.get(source) and source_record[source] != record[target]:
                raise ValueError('dispatch_original_source_record_identity_mismatch')
    return identity


def semantic_revision_key(record, xml):
    identity = _identity(record)
    root = E.fromstring(xml)
    models = list(root.iter('mxGraphModel'))
    if len(models) != 1 or root.tag == 'mxfile' and len(root.findall('diagram')) != 1:
        raise ValueError('dispatch_requires_one_uncompressed_native_page')
    assets = []
    for key in ('source_assets', 'original_vector_assets'):
        for asset in record.get(key) or []:
            if not isinstance(asset, dict):
                continue
            for field in ('sha256', 'source_sha256', 'original_sha256', 'embedded_sha256'):
                if asset.get(field):
                    assets.append((key, field, asset[field]))
    auxiliary = record.get('source_data_sha256')
    if auxiliary and not HASH.fullmatch(str(auxiliary)):
        raise ValueError('dispatch_original_data_digest_invalid')
    canonical = {'version': KEY_VERSION, 'identity': identity,
                 'original_data_sha256': auxiliary, 'original_asset_digests': sorted(set(assets)),
                 'native_graph': _tree(models[0])}
    return sha(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def _read_clean(root, path, digest):
    target = (root / path).resolve()
    if not target.is_relative_to((root / 'clean').resolve()):
        raise ValueError('dispatch_candidate_outside_clean')
    data = target.read_bytes()
    if sha(data) != digest:
        raise ValueError('dispatch_current_xml_hash_changed')
    return data.decode()


def _genuine_failure(report):
    if report.get('accepted') or report.get('state') not in ('repair_required', 'failed'):
        return False, 'report_is_not_a_failed_quality_revision'
    failures = report.get('failures') or []
    source = (report.get('checks') or {}).get('source') or {}
    visual = (report.get('checks') or {}).get('visual') or {}
    raster = bool(visual.get('ok') is False and visual.get('failures'))
    raster = raster or any(str(value).startswith('raster_anomaly:') for value in failures)
    concrete_source = []
    if source.get('supported') is True and source.get('ok') is False:
        for failure in source.get('failures') or []:
            reason = failure.get('reason', '') if isinstance(failure, dict) else str(failure)
            if not reason or reason.startswith(('unsupported', 'source_profile_not_',
                    'source_capture_', 'source_parser_', 'reference_parse_', 'missing_runtime',
                    'profile_', 'source_profile_validation_error','source_graph_validation_error','independent_source_coverage_pending')):
                continue
            concrete_source.append(failure)
    return bool(raster or concrete_source), 'real_visual_or_source_mismatch' if raster or concrete_source else 'no_concrete_source_or_visual_mismatch'


def _feedback(record, report, revision_key):
    boxes = []
    visual = (report.get('checks') or {}).get('visual') or {}
    for region in visual.get('worst_text_regions') or []:
        box = region.get('box')
        if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in box):
            continue
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        boxes.append({key: region[key] for key in ('cell', 'box', 'ssim', 'unregistered_ssim', 'registration_shift') if key in region})
        if len(boxes) == 20:
            break
    source = (report.get('checks') or {}).get('source') or {}
    feedback = {'source': 'automatic_quality', 'reviewer': 'fixed_batch_quality_program',
                'at': report.get('at') or now(), 'policy': report.get('policy'),
                'checked_code_sha256': record['code_sha256'],
                'checked_image_sha256': record.get('image_sha256'),
                'semantic_revision_key': revision_key,
                'failures': [str(value)[:2500] for value in (report.get('failures') or [])[:20]],
                'source_failures': (source.get('failures') or [])[:20],
                'local_text_boxes': boxes,
                'interpretation': 'Machine diagnostic, not a human review or acceptance. Preserve correct source content; repair the specific failures and independently recheck the resulting XML and render.'}
    prior = record.get('root_review')
    if isinstance(prior, dict):
        review = copy.deepcopy(prior)
    elif prior is not None:
        review = {'preserved_prior_review': copy.deepcopy(prior)}
    else:
        review = {}
    review['automatic_quality'] = feedback
    return {**record, 'root_review': review}, feedback


def _owned_json(root, path, prefix):
    target = (root / path).resolve()
    if not target.is_relative_to((root / prefix).resolve()):
        raise ValueError('unowned_deterministic_repair_proof')
    return target, json.loads(target.read_text())


def _deterministic_current(record, root):
    digest = record['code_sha256']
    proof = record.get('html_source_repair_v2') or {}
    if (proof.get('output_code_sha256') == digest and
            all(proof.get(key) == record[key] for key in ('source_code_sha256', 'source_image_sha256'))):
        return {'ok': True, 'method': 'deterministic_html_source_v2'}
    link = record.get('auto_quality_canvas_repair') or {}
    if link.get('proof') and link.get('proof_sha256'):
        try:
            path, proof = _owned_json(root, link['proof'], 'conversion/auto_quality_canvas_repair_v1')
            if sha(path.read_bytes()) == link['proof_sha256'] and proof.get('new_code_sha256') == digest and all(proof.get(key) == record.get(key) for key in ('id', 'source_code_sha256', 'source_image_sha256')):
                return {'ok': True, 'method': 'deterministic_registered_canvas_v1'}
        except (OSError, ValueError, TypeError):
            pass
    proof = record.get('native_font_validation') or {}
    if proof.get('output_code_sha256') == digest and proof.get('native_pixels_unchanged') is True and proof.get('audit'):
        try:
            path, stored = _owned_json(root, proof['audit'], 'conversion/auto_quality_font_repair_v1')
            if stored == proof and path.parent.name == proof.get('input_code_sha256') and path.parent.parent.name == record['id']:
                return {'ok': True, 'method': 'deterministic_actual_font_embedding_v2'}
        except (OSError, ValueError, TypeError):
            pass
    if record.get('conversion_method') == 'source_named_tikz_nodes_and_native_bound_paths_v1' and record.get('native_binding_validation'):
        try:
            _, proof = _owned_json(root, record['native_binding_validation'], 'conversion/tikz_literal_binding_pilot')
            if proof.get('ok') is True and proof.get('id') == record['id'] and proof.get('output_code_sha256') == digest:
                return {'ok': True, 'method': 'deterministic_literal_source_binding_v1'}
        except (OSError, ValueError, TypeError):
            pass
    return {'ok': False, 'reason': 'current_revision_has_no_matching_deterministic_repair_proof'}


def _session_baseline(root, session, record):
    if not session:
        return None, None, {'reason': 'finished_attempt_has_no_session_baseline'}
    folder = (root / session).resolve()
    if not folder.is_relative_to((root / 'conversion/harness_sessions').resolve()):
        return None, None, {'reason': 'finished_session_outside_owned_harness_sessions'}
    try:
        baseline = json.loads((folder / 'baseline/conversion.json').read_text())
        if _identity(baseline) != _identity(record):
            return None, None, {'reason': 'finished_session_source_identity_mismatch'}
        choices = [folder / 'baseline' / Path(baseline['code_file']).name,
                   folder / 'baseline/diagram.drawio']
        path = next((path for path in choices if path.is_file() and sha(path.read_bytes()) == baseline['code_sha256']), None)
        if path is None:
            return None, None, {'reason': 'finished_session_baseline_xml_missing_or_hash_mismatched'}
        xml = path.read_text()
        revision = semantic_revision_key(baseline, xml)
        return baseline, revision, {'baseline_code_sha256': baseline['code_sha256'],
                                    'baseline_semantic_revision_key': revision,
                                    'session': session}
    except (OSError, ValueError, KeyError, TypeError, E.ParseError) as exc:
        return None, None, {'reason': 'finished_session_baseline_unverifiable', 'error': str(exc)[:500]}


def route_failure(db, record, report, root=R):
    """Return metadata and dispatch summary; caller must atomically publish it."""
    if not db.in_transaction:
        raise RuntimeError('route_failure requires the caller-owned writer transaction')
    root = Path(root)
    genuine, reason = _genuine_failure(report)
    summary = {'source': 'automatic_quality', 'id': record.get('id'), 'dispatched': False,
               'queue_changed': False, 'reason': reason}
    if not genuine:
        return record, summary
    xml = _read_clean(root, record['code_file'], record['code_sha256'])
    key = semantic_revision_key(record, xml)
    updated, feedback = _feedback(record, report, key)
    summary['semantic_revision_key'] = key
    prior = db.execute('SELECT dispatched,state FROM ' + TABLE + ' WHERE id=? AND semantic_revision_key=?', (record['id'], key)).fetchone()
    queue_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='harness_queue_v3'").fetchone()
    queue = db.execute('SELECT state,worker_pid,session_dir FROM harness_queue_v3 WHERE id=?', (record['id'],)).fetchone() if queue_exists else None
    before = queue[0] if queue else None
    after = before
    baseline_code = None
    baseline_key = None
    dispatched = False
    if prior and prior[0]:
        summary['reason'] = 'semantic_revision_already_dispatched'
    elif not queue_exists:
        summary['reason'] = 'harness_queue_not_initialized'
    elif queue and (queue[0] == 'running' or queue[1] is not None):
        summary['reason'] = 'existing_running_or_owned_queue_preserved'
    elif queue is None:
        db.execute('INSERT INTO harness_queue_v3(id,state,attempts,priority) VALUES(?,"held_for_source_v5",0,1000)', (record['id'],))
        after = 'held_for_source_v5'
        dispatched = True
        summary.update(queue_changed=True, reason='new_genuine_failure_queued')
    elif before == 'held_for_quality_v2':
        db.execute("UPDATE harness_queue_v3 SET state='held_for_source_v5' WHERE id=? AND state='held_for_quality_v2' AND worker_pid IS NULL", (record['id'],))
        after = 'held_for_source_v5'
        dispatched = True
        summary.update(queue_changed=True, reason='verified_quality_hold_released')
    elif before == 'held_for_source_v5':
        dispatched = True
        summary['reason'] = 'existing_source_queue_will_consume_current_revision'
    elif before == 'attempt_finished':
        repair = _deterministic_current(record, root)
        summary['deterministic_repair'] = repair
        if not repair['ok']:
            summary['reason'] = repair['reason']
        else:
            baseline, baseline_key, evidence = _session_baseline(root, queue[2], record)
            summary['finished_baseline'] = evidence
            baseline_code = evidence.get('baseline_code_sha256')
            if baseline is None:
                summary['reason'] = evidence['reason']
            elif baseline_code == record['code_sha256'] or baseline_key == key:
                summary['reason'] = 'finished_attempt_has_same_semantic_baseline'
            else:
                db.execute("UPDATE harness_queue_v3 SET state='held_for_source_v5' WHERE id=? AND state='attempt_finished' AND worker_pid IS NULL", (record['id'],))
                after = 'held_for_source_v5'
                dispatched = True
                summary.update(queue_changed=True, reason='new_deterministic_semantic_revision_requeued')
    else:
        summary['reason'] = 'other_existing_queue_state_preserved'
    summary.update(queue_state_before=before, queue_state_after=after, dispatched=dispatched)
    # An observational row (e.g. running queue) does not consume the dispatch key.
    # Only a genuine queued/current revision prevents future duplicate calls.
    created = now()
    db.execute('''INSERT INTO ''' + TABLE + ''' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(id,semantic_revision_key) DO UPDATE SET
      dispatched=max(''' + TABLE + '''.dispatched,excluded.dispatched),
      state=CASE WHEN ''' + TABLE + '''.dispatched THEN ''' + TABLE + '''.state ELSE excluded.state END,
      feedback=excluded.feedback,updated_at=excluded.updated_at''',
      (record['id'], key, record['source_code_sha256'], record['source_image_sha256'],
       record.get('source_data_sha256'), record['code_sha256'], record.get('image_sha256'),
       int(dispatched), summary['reason'], before, after, baseline_code, baseline_key,
       report.get('policy'), json.dumps({'automatic_quality': feedback, 'dispatch_evidence': summary}, ensure_ascii=False), created, created))
    return updated, summary
