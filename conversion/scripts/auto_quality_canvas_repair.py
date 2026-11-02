"""Versioned deterministic page repair for automatic-QA canvas exceptions.

Two supported transformations: fill missing single-page size from the immutable
reference, or add bounded integer padding while translating the complete native
graph. Every repair preserves original-page pixels, complete native paint, all
source objects/text/topology/fonts, and requires later independent batch QA.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import io
import json
import os
import sqlite3
import time
import xml.etree.ElementTree as E
from pathlib import Path

from durable_sqlite import begin, commit
from native_page_padding import shift

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
TABLE = 'auto_quality_canvas_repairs_v1'
STATE = 'auto_quality_canvas_repairing_v1'
IDLE = ('rendered', 'needs_quality_repair', 'harness_review_pending')
RENDERER = W / 'rendering_canvas_padding_proof/remote_render.py'
POLICY = 'reference_registered_integer_canvas_repair_v1'
sha = lambda value: hashlib.sha256(value).hexdigest()
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()


def model(xml):
    root = E.fromstring(xml)
    models = list(root.iter('mxGraphModel'))
    assert len(models) == 1, 'One uncompressed native page required'
    if root.tag == 'mxfile':
        assert len(root.findall('diagram')) == 1, 'Multiple source pages require separate handling'
    return root, models[0]


def page_metadata(xml, reference_size):
    """Restore only absent page dimensions; explicit mismatches are not guessed."""
    root, graph = model(xml)
    width, height = reference_size
    assert all(isinstance(v, int) and 0 < v <= 8192 for v in (width, height))
    assert width * height <= 64000000, 'Reference page exceeds supported area'
    before = {key: graph.get(key) for key in ('pageWidth', 'pageHeight')}
    for key, expected in (('pageWidth', width), ('pageHeight', height)):
        value = graph.get(key)
        if value is None:
            graph.set(key, str(expected))
        else:
            assert float(value) == expected, 'Explicit page size differs from immutable reference'
    out = E.tostring(root, encoding='unicode')
    proof = {'original_attributes': before,
             'normalized_attributes': {'pageWidth': str(width), 'pageHeight': str(height)},
             'missing_attributes_filled': [key for key, value in before.items() if value is None],
             'reference_page': [width, height], 'all_other_xml_unchanged': True}
    verify_metadata(xml, out, proof)
    return out, proof


def verify_metadata(before, after, proof):
    a, am = model(before)
    b, bm = model(after)
    assert {key: am.get(key) for key in ('pageWidth', 'pageHeight')} == proof['original_attributes']
    assert {key: bm.get(key) for key in ('pageWidth', 'pageHeight')} == proof['normalized_attributes']
    assert proof['missing_attributes_filled'] == [key for key, value in proof['original_attributes'].items() if value is None]
    assert [int(float(proof['normalized_attributes'][key])) for key in ('pageWidth', 'pageHeight')] == proof['reference_page']
    for key, value in proof['original_attributes'].items():
        if value is None:
            bm.attrib.pop(key, None)
        else:
            bm.set(key, value)
    assert E.tostring(a) == E.tostring(b), 'Page metadata repair altered other XML content'
    return True


def transform(xml, reference_size, canvas):
    normalized, metadata = page_metadata(xml, reference_size)
    dx, dy = canvas['dx'], canvas['dy']
    width, height = canvas['width'], canvas['height']
    if dx or dy or [width, height] != list(reference_size):
        candidate, geometry = shift(normalized, dx, dy, width, height)
    else:
        candidate = normalized
        geometry = {'translation': [0, 0], 'old_page': list(reference_size),
                    'new_page': list(reference_size), 'translated_top_level_cells': [],
                    'text_style_topology_and_child_geometry_unchanged': True}
    verify_transform(xml, candidate, metadata, geometry)
    return candidate, metadata, geometry


def verify_transform(before, after, metadata, geometry):
    normalized, expected = page_metadata(before, tuple(metadata['reference_page']))
    assert expected == metadata, 'Page metadata proof was altered'
    if geometry['translation'] == [0, 0] and geometry['new_page'] == geometry['old_page']:
        assert not geometry['translated_top_level_cells'], 'Unexpected graph movement on metadata-only repair'
        assert E.tostring(E.fromstring(normalized)) == E.tostring(E.fromstring(after)), 'Metadata-only repair changed graph'
    else:
        generated, expected_geometry = shift(normalized, *geometry['translation'], *geometry['new_page'])
        assert generated == after and expected_geometry == geometry, 'Unverified whole-graph transformation'
    return True


def checked_file(root, value, digest=None, clean=True):
    path = (root / value).resolve()
    assert path.is_relative_to(root / ('clean' if clean else 'conversion')), 'Resource outside owned data root'
    data = path.read_bytes()
    if digest:
        assert sha(data) == digest, 'File hash mismatch: ' + str(value)
    return path, data


def owned_work(root, value):
    path = (root / value).resolve()
    assert path.is_relative_to(root / 'conversion/auto_quality_canvas_repair_v1'), 'Unowned canvas proof'
    return path


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.%d.tmp' % os.getpid())
    temporary.write_bytes(data)
    temporary.replace(path)


def _json(path, value):
    _write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def repair(identifier, raw):
    """Nonpublishing conversion; all writes are versioned data/proof artifacts."""
    from PIL import Image
    from native_padding_proof import render, plan_from_pixels, exact_pixel_proof
    from strict_canvas_gate import require_declared_page
    from harness_source_provenance import validate_source_record
    old = json.loads(raw)
    _, xml_bytes = checked_file(R, old['code_file'], old['code_sha256'])
    _, old_png = checked_file(R, old['image_file'], old['image_sha256'])
    _, reference = checked_file(R, old['original_reference'], old['source_image_sha256'])
    source_checks = validate_source_record(old)
    assert 'original_source_code' in source_checks, 'Immutable source code is required'
    xml = xml_bytes.decode()
    reference_size = Image.open(io.BytesIO(reference)).size
    normalized, metadata = page_metadata(xml, reference_size)
    token = old['code_sha256'] + '_' + old['image_sha256'][:16]
    work = W / 'auto_quality_canvas_repair_v1' / identifier / token
    work.mkdir(parents=True, exist_ok=True)
    _json(work / 'before_record.json', old)
    _write(work / 'baseline.drawio', xml_bytes)
    _write(work / 'baseline.png', old_png)
    # Both before/after are rendered with the same pinned profile. The baseline
    # receives reference dimensions as renderer fallback when XML lacks them.
    baseline_png, before_info = render(xml, *reference_size, work / 'baseline')
    assert before_info['canvas'] == list(reference_size), 'Reference/renderer page registration mismatch'
    assert before_info['renderer_profile'] == 'native_page_padding_strict_v1'
    assert before_info['renderer_module_sha256'] == sha(RENDERER.read_bytes()), 'Pinned renderer changed'
    boundary = before_info['outside_page_pixel_audit']
    assert boundary['white_threshold'] == 255, 'Strict outside-page pixel audit required'
    if boundary['nonwhite_outside_pixels']:
        canvas = plan_from_pixels((work / 'baseline/render.padded.png').read_bytes(), before_info)
        kind = 'bounded_native_paint_overflow'
    else:
        assert metadata['missing_attributes_filled'], 'No current native overflow or missing page metadata'
        canvas = {'dx': 0, 'dy': 0, 'width': reference_size[0], 'height': reference_size[1],
                  'original_page_in_probe': [*boundary['offset'],
                        boundary['offset'][0] + reference_size[0], boundary['offset'][1] + reference_size[1]]}
        kind = 'missing_reference_page_metadata'
    new_xml, metadata, geometry = transform(xml, reference_size, canvas)
    width, height = geometry['new_page']
    new_png, after_info = render(new_xml, width, height, work / 'candidate')
    require_declared_page(after_info, width, height)
    assert after_info['renderer_module_sha256'] == before_info['renderer_module_sha256'], 'Renderer changed between proof captures'
    exact = exact_pixel_proof(work / 'baseline', work / 'candidate', before_info, after_info, canvas)
    # Font workers may later rewrite the live clean code_file in place. Keep
    # independent immutable proof copies in this module's private audit folder.
    _write(work / 'candidate.drawio', new_xml.encode())
    _write(work / 'candidate.png', new_png)
    # Immutable before/after XML/PNG and source pointers remain below clean.
    data = (R / old['code_file']).parent / 'canvas_repair_v1' / token
    _write(data / 'baseline/diagram.drawio', xml_bytes)
    _write(data / 'baseline/image.png', old_png)
    _json(data / 'baseline/conversion.json', old)
    _write(data / 'diagram.drawio', new_xml.encode())
    _write(data / 'image.png', new_png)
    proof = {'version': 1, 'policy': POLICY, 'id': identifier, 'at': now(), 'kind': kind,
             'source_code_sha256': old['source_code_sha256'],
             'source_image_sha256': old['source_image_sha256'],
             'source_hash_checks': source_checks,
             'old_code_sha256': old['code_sha256'], 'old_image_sha256': old['image_sha256'],
             'new_code_sha256': sha(new_xml.encode()), 'new_image_sha256': sha(new_png),
             'baseline_record': str((data / 'baseline/conversion.json').relative_to(R)),
             'baseline_code': str((data / 'baseline/diagram.drawio').relative_to(R)),
             'baseline_image': str((data / 'baseline/image.png').relative_to(R)),
             'candidate_code': str((data / 'diagram.drawio').relative_to(R)),
             'candidate_image': str((data / 'image.png').relative_to(R)),
             'frozen_baseline_record': str((work / 'before_record.json').relative_to(R)),
             'frozen_baseline_record_sha256': sha((work / 'before_record.json').read_bytes()),
             'frozen_baseline_code': str((work / 'baseline.drawio').relative_to(R)),
             'frozen_baseline_image': str((work / 'baseline.png').relative_to(R)),
             'frozen_candidate_code': str((work / 'candidate.drawio').relative_to(R)),
             'frozen_candidate_image': str((work / 'candidate.png').relative_to(R)),
             'metadata': metadata, 'geometry': geometry, 'canvas_plan': canvas,
             'exact_pixel_proof': exact,
             'old_outside_page_pixels': boundary['nonwhite_outside_pixels'],
             'new_outside_page_pixels': after_info['outside_page_pixel_audit']['nonwhite_outside_pixels'],
             'renderer_profile': after_info['renderer_profile'],
             'renderer_module_sha256': after_info['renderer_module_sha256'],
             'reference_registration': {'reference_page': list(reference_size),
                   'output_page': geometry['new_page'], 'original_page_offset': geometry['translation'],
                   'scale': 1, 'original_reference_hash': old['source_image_sha256'],
                   'no_reference_crop': True}, 'accepted': False}
    proof_path = work / 'proof.json'
    _json(proof_path, proof)
    proof_link = {'proof': str(proof_path.relative_to(R)), 'proof_sha256': sha(proof_path.read_bytes())}
    out = {**old, 'code_file': proof['candidate_code'], 'image_file': proof['candidate_image'],
           'code_sha256': proof['new_code_sha256'], 'image_sha256': proof['new_image_sha256'],
           'render': after_info, 'auto_quality_canvas_repair': proof_link,
           'quality_state': 'pending_fixed_batch_source_native_quality_checks',
           'converted_at_utc': now()}
    _json(data / 'conversion.json', out)
    _json(work / 'candidate_record.json', out)
    validate_registration(out, reference, new_xml)
    report = {'at': now(), 'id': identifier, 'kind': kind, 'geometry': geometry,
              'old_outside_pixels': proof['old_outside_page_pixels'], 'new_outside_pixels': 0,
              'code_sha256': out['code_sha256'], 'image_sha256': out['image_sha256'],
              'proof': proof_link, 'accepted': False}
    _json(work / 'report.json', report)
    return work, out, report


def validate_registration(record, reference, xml, root=R):
    """Recompute a frozen page transformation; never trust an offset alone."""
    from PIL import Image
    from native_padding_proof import exact_pixel_proof
    from strict_canvas_gate import require_declared_page
    root = Path(root)
    link = record['auto_quality_canvas_repair']
    proof_path = owned_work(root, link['proof'])
    proof_raw = proof_path.read_bytes()
    assert sha(proof_raw) == link['proof_sha256'], 'Canvas proof hash changed'
    proof = json.loads(proof_raw)
    assert proof['policy'] == POLICY and proof['version'] == 1
    assert all(record[key] == proof[key] for key in ('id', 'source_code_sha256', 'source_image_sha256')), 'Canvas source identity changed'
    assert sha(reference) == proof['source_image_sha256'], 'Reference image changed'
    assert sha(xml.encode() if isinstance(xml, str) else xml) == proof['new_code_sha256'] == record['code_sha256'], 'Current XML differs from proven transformation'
    baseline_raw = owned_work(root, proof['frozen_baseline_record']).read_bytes()
    assert sha(baseline_raw) == proof['frozen_baseline_record_sha256'], 'Frozen baseline metadata changed'
    baseline = json.loads(baseline_raw)
    assert all(baseline[key] == record[key] for key in ('id', 'source_code_sha256', 'source_image_sha256'))
    before_xml = owned_work(root, proof['frozen_baseline_code']).read_bytes()
    assert sha(before_xml) == proof['old_code_sha256'], 'Frozen baseline XML changed'
    assert sha(owned_work(root, proof['frozen_baseline_image']).read_bytes()) == proof['old_image_sha256'], 'Frozen baseline PNG changed'
    candidate_xml = owned_work(root, proof['frozen_candidate_code']).read_bytes()
    assert sha(candidate_xml) == proof['new_code_sha256'], 'Frozen candidate XML changed'
    assert sha(owned_work(root, proof['frozen_candidate_image']).read_bytes()) == proof['new_image_sha256'], 'Frozen candidate PNG changed'
    # Baseline clean copies are private backups; the live candidate file can
    # legitimately acquire a later font-only revision and is checked by QA.
    checked_file(root, proof['baseline_record'])
    checked_file(root, proof['baseline_code'], proof['old_code_sha256'])
    checked_file(root, proof['baseline_image'], proof['old_image_sha256'])
    assert baseline['code_sha256'] == proof['old_code_sha256'] and baseline['image_sha256'] == proof['old_image_sha256']
    assert candidate_xml == (xml.encode() if isinstance(xml, str) else xml)
    reference_size = list(Image.open(io.BytesIO(reference)).size)
    assert reference_size == proof['metadata']['reference_page'] == proof['geometry']['old_page']
    verify_transform(before_xml.decode(), candidate_xml.decode(), proof['metadata'], proof['geometry'])
    folder = proof_path.parent
    origin_raw = (folder / 'candidate_record.json').read_bytes()
    origin = json.loads(origin_raw)
    assert all(origin[key] == record[key] for key in ('id', 'source_code_sha256', 'source_image_sha256', 'code_sha256'))
    assert origin['auto_quality_canvas_repair'] == link
    assert origin['image_sha256'] == proof['new_image_sha256']
    assert origin['code_file'] == proof['candidate_code'] and origin['image_file'] == proof['candidate_image']
    old_info = json.loads((folder / 'baseline/native_render.json').read_text())
    new_info = json.loads((folder / 'candidate/native_render.json').read_text())
    require_declared_page(new_info, *proof['geometry']['new_page'])
    assert old_info['canvas'] == reference_size
    assert old_info['outside_page_pixel_audit']['white_threshold'] == 255
    assert old_info['outside_page_pixel_audit']['nonwhite_outside_pixels'] == proof['old_outside_page_pixels']
    assert new_info['outside_page_pixel_audit']['nonwhite_outside_pixels'] == proof['new_outside_page_pixels'] == 0
    renderer = root / 'conversion/rendering_canvas_padding_proof/remote_render.py'
    assert sha(renderer.read_bytes()) == old_info['renderer_module_sha256'] == new_info['renderer_module_sha256'] == proof['renderer_module_sha256'], 'Pinned native renderer changed'
    assert old_info['renderer_profile'] == new_info['renderer_profile'] == proof['renderer_profile'] == 'native_page_padding_strict_v1'
    exact = exact_pixel_proof(folder / 'baseline', folder / 'candidate', old_info, new_info, proof['canvas_plan'])
    assert exact == proof['exact_pixel_proof'], 'Native paint/page proof changed'
    for name, check in proof['source_hash_checks'].items():
        checked_file(root, check['file'], check['sha256'])
    registration = {'reference_page': reference_size, 'output_page': proof['geometry']['new_page'],
                    'original_page_offset': proof['geometry']['translation'], 'scale': 1,
                    'no_reference_crop': True}
    assert proof['reference_registration'] == {**registration, 'original_reference_hash': proof['source_image_sha256']}, 'Registration contract changed'
    return {'version': 1, **registration, 'source_image_sha256': proof['source_image_sha256'],
            'source_code_sha256': proof['source_code_sha256'],
            'origin_code_sha256': proof['new_code_sha256'], 'origin_image_sha256': proof['new_image_sha256'],
            'origin_record': str((folder / 'candidate_record.json').relative_to(root)),
            'origin_record_sha256': sha(origin_raw),
            'baseline_record': proof['baseline_record'],
            'baseline_record_sha256': sha((root / proof['baseline_record']).read_bytes()),
            'baseline_code': proof['baseline_code'],
            'baseline_code_sha256': proof['old_code_sha256'],
            'baseline_image': proof['baseline_image'],
            'baseline_image_sha256': proof['old_image_sha256'],
            'frozen_baseline_record': proof['frozen_baseline_record'],
            'frozen_baseline_record_sha256': proof['frozen_baseline_record_sha256'],
            'frozen_baseline_code': proof['frozen_baseline_code'],
            'frozen_baseline_image': proof['frozen_baseline_image'],
            'frozen_origin_code': proof['frozen_candidate_code'],
            'frozen_origin_image': proof['frozen_candidate_image'],
            'proof': link['proof'], 'proof_sha256': link['proof_sha256'],
            'renderer_profile': proof['renderer_profile'], 'renderer_module_sha256': proof['renderer_module_sha256'],
            'scope': 'Frozen source-reference page registration and exact graph/page preservation. Source semantics, fonts, fresh native rendering and original-reference fidelity require independent batch QA.'}


def validate_registration_origin(record, reference, root=R):
    """Validate an inherited frozen origin; caller must prove a font-only delta.

    This deliberately does not certify the current XML. It permits a later QA
    adapter to compare that XML against the separately frozen canvas origin.
    """
    root = Path(root)
    link = record['auto_quality_canvas_repair']
    proof_path = owned_work(root, link['proof'])
    assert sha(proof_path.read_bytes()) == link['proof_sha256'], 'Canvas proof hash changed'
    proof = json.loads(proof_path.read_text())
    origin = json.loads((proof_path.parent / 'candidate_record.json').read_text())
    assert origin['auto_quality_canvas_repair'] == link
    assert all(origin[key] == record[key] for key in ('id', 'source_code_sha256', 'source_image_sha256')), 'Inherited canvas source identity changed'
    origin_xml = owned_work(root, proof['frozen_candidate_code']).read_text()
    contract = validate_registration(origin, reference, origin_xml, root)
    return {**contract, 'current_revision_verified': record['code_sha256'] == origin['code_sha256'],
            'inherited_font_or_graph_revision_needs_independent_delta_validation': record['code_sha256'] != origin['code_sha256']}


def initialize(db):
    begin(db)
    db.execute('CREATE TABLE IF NOT EXISTS ' + TABLE + ''' (
      id TEXT,code_hash TEXT,image_hash TEXT,state TEXT,owner_pid INTEGER,
      prior_state TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,code_hash,image_hash))''')
    commit(db)


def claim(db, identifier, state, raw, owner_pid):
    old = json.loads(raw)
    begin(db)
    if state not in IDLE or db.execute('SELECT state,output_record,worker_pid FROM jobs WHERE id=?', (identifier,)).fetchone() != (state, raw, None):
        db.rollback()
        return False
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='harness_queue_v3'").fetchone():
        queue=db.execute('SELECT state FROM harness_queue_v3 WHERE id=?',(identifier,)).fetchone()
        if queue and queue[0]=='running':
            db.rollback()
            return False
    if db.execute('SELECT 1 FROM ' + TABLE + ' WHERE id=? AND code_hash=? AND image_hash=?', (identifier, old['code_sha256'], old['image_sha256'])).fetchone():
        db.rollback()
        return False
    if not db.execute("SELECT 1 FROM auto_quality_exceptions_v1 WHERE id=? AND code_hash=? AND image_hash=? AND route='deterministic_canvas_repair' AND state='pending'", (identifier, old['code_sha256'], old['image_sha256'])).fetchone():
        db.rollback()
        return False
    db.execute('INSERT INTO ' + TABLE + ' VALUES(?,?,?,"running",?,?,NULL,?)',
               (identifier, old['code_sha256'], old['image_sha256'], owner_pid, state, now()))
    db.execute('UPDATE jobs SET state=?,worker_pid=?,updated_at=? WHERE id=?', (STATE, owner_pid, now(), identifier))
    commit(db)
    return True


def finish(db, identifier, prior_state, raw, owner_pid, out, report, publish):
    old = json.loads(raw)
    begin(db)
    owned = db.execute('SELECT state,output_record,worker_pid FROM jobs WHERE id=?', (identifier,)).fetchone()
    assert owned == (STATE, raw, owner_pid), 'Canvas revision ownership changed'
    stage = 'published_pending_batch_qa' if out and publish else 'verified_nonpublishing' if out else 'retained_prior_candidate'
    if out and publish:
        checked_file(R, old['code_file'], old['code_sha256'])
        checked_file(R, old['image_file'], old['image_sha256'])
        checked_file(R, out['code_file'], out['code_sha256'])
        checked_file(R, out['image_file'], out['image_sha256'])
        state = 'needs_quality_repair'
        db.execute('UPDATE jobs SET state=?,worker_pid=NULL,output_record=?,updated_at=? WHERE id=?',
                   (state, json.dumps(out, ensure_ascii=False), now(), identifier))
        db.execute("UPDATE auto_quality_exceptions_v1 SET state='repaired_pending_batch_qa',updated_at=? WHERE id=? AND code_hash=? AND image_hash=? AND route='deterministic_canvas_repair' AND state='pending'",
                   (now(), identifier, old['code_sha256'], old['image_sha256']))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='harness_queue_v3'").fetchone():
            db.execute("INSERT OR IGNORE INTO harness_queue_v3(id,state,attempts,priority) VALUES(?,'held_for_quality_v2',0,1000)",(identifier,))
            db.execute("UPDATE harness_queue_v3 SET state='held_for_quality_v2',worker_pid=NULL,heartbeat=? WHERE id=? AND state!='running'",(now(),identifier))
    else:
        db.execute('UPDATE jobs SET state=?,worker_pid=NULL,updated_at=? WHERE id=?', (prior_state, now(), identifier))
    db.execute('UPDATE ' + TABLE + ' SET state=?,owner_pid=NULL,record=?,updated_at=? WHERE id=? AND code_hash=? AND image_hash=?',
               (stage, json.dumps(report, ensure_ascii=False), now(), identifier, old['code_sha256'], old['image_sha256']))
    commit(db)
    return stage


def worker(index, limit, selected, publish):
    db = sqlite3.connect(W / 'jobs.sqlite', timeout=2)
    done = 0
    counts = {}
    while not limit or done < limit:
        selection = ' AND e.id IN (' + ','.join('?' for _ in selected) + ')' if selected else ''
        rows = db.execute('''WITH chosen AS MATERIALIZED (
          SELECT e.id,e.code_hash,e.image_hash FROM auto_quality_exceptions_v1 e
          JOIN jobs initial ON initial.id=e.id
          WHERE e.route='deterministic_canvas_repair' AND e.state='pending'
          AND initial.state IN ('rendered','needs_quality_repair','harness_review_pending')
          AND initial.worker_pid is NULL
          AND NOT EXISTS(SELECT 1 FROM ''' + TABLE + ''' t WHERE t.id=e.id AND t.code_hash=e.code_hash AND t.image_hash=e.image_hash)
          ''' + selection + ''' ORDER BY e.updated_at,e.id LIMIT 64)
          SELECT j.id,j.state,j.output_record,c.code_hash,c.image_hash FROM chosen c JOIN jobs j ON j.id=c.id
          WHERE j.state IN ('rendered','needs_quality_repair','harness_review_pending') AND j.worker_pid IS NULL''',
          selected).fetchall()
        row = None
        stale = 0
        for identifier, state, raw, code_hash, image_hash in rows:
            record = json.loads(raw)
            if record['code_sha256'] == code_hash and record['image_sha256'] == image_hash:
                if claim(db, identifier, state, raw, os.getpid()):
                    row = identifier, state, raw
                    break
            else:
                begin(db)
                db.execute("UPDATE auto_quality_exceptions_v1 SET state='stale_revision',updated_at=? WHERE id=? AND code_hash=? AND image_hash=? AND route='deterministic_canvas_repair' AND state='pending'", (now(), identifier, code_hash, image_hash))
                commit(db)
                stale += 1
        if row is None:
            if stale:
                continue
            if limit or selected:
                break
            time.sleep(15)
            continue
        identifier, state, raw = row
        out = None
        try:
            work, out, report = repair(identifier, raw)
        except Exception as exc:
            report = {'id': identifier, 'at': now(), 'error': repr(exc), 'accepted': False,
                      'prior_candidate_retained': True}
        stage = finish(db, identifier, state, raw, os.getpid(), out, report, publish)
        done += 1
        counts[stage] = counts.get(stage, 0) + 1
        print(json.dumps({'at': now(), 'id': identifier, 'worker': index, 'stage': stage,
                          'kind': report.get('kind'), 'error': report.get('error')}), flush=True)
    return {'worker': index, 'processed': done, 'counts': counts}


def smoke(identifier):
    """Read current revision, write only new proof artifacts; never claim/publish."""
    db = sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True)
    state, owner, raw = db.execute('SELECT state,worker_pid,output_record FROM jobs WHERE id=?', (identifier,)).fetchone()
    db.close()
    assert state in IDLE and owner is None, 'Smoke requires an idle unaccepted revision'
    work, out, report = repair(identifier, raw)
    print(json.dumps({**report, 'work': str(work.relative_to(R)), 'publishing': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--limit', type=int, default=0, help='Per worker; zero watches for new exceptions')
    parser.add_argument('--id', dest='selected', action='append', default=[])
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--smoke-id')
    args = parser.parse_args()
    if args.smoke_id:
        smoke(args.smoke_id)
        return
    if not args.publish:
        parser.error('Use --smoke-id for a nonpublishing check, or --publish to run the repair queue')
    db = sqlite3.connect(W / 'jobs.sqlite', timeout=2)
    initialize(db)
    db.close()
    _json(W / 'auto_quality_canvas_repair_owner.json', {'pid': os.getpid(), 'workers': args.workers,
          'publish': args.publish, 'at': now(), 'policy': POLICY})
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(worker, range(args.workers), [args.limit] * args.workers,
                                [args.selected] * args.workers, [args.publish] * args.workers))
    _json(W / 'auto_quality_canvas_repair_summary.json', {'at': now(), 'results': results,
                                                        'goal_complete': False})


if __name__ == '__main__':
    main()
