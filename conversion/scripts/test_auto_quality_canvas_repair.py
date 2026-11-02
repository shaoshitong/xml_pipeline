"""Page-only transforms preserve every object; publication respects ownership."""
import copy
import json
import sqlite3
import xml.etree.ElementTree as E

import auto_quality_canvas_repair as c


def fixture(page=True):
    root = E.Element('mxfile')
    m = E.SubElement(E.SubElement(root, 'diagram'), 'mxGraphModel',
                     **({'pageWidth': '200', 'pageHeight': '100'} if page else {}))
    cells = E.SubElement(m, 'root')
    E.SubElement(cells, 'mxCell', id='0')
    E.SubElement(cells, 'mxCell', id='1', parent='0')
    a = E.SubElement(cells, 'mxCell', id='a', parent='1', vertex='1', value='Alpha', style='shape=rectangle;fillColor=#eeeeee;')
    g = E.SubElement(a, 'mxGeometry', x='-3', y='20', width='50', height='30', **{'as': 'geometry'})
    E.SubElement(g, 'mxRectangle', x='-3', y='20', width='100', height='60', **{'as': 'alternateBounds'})
    child = E.SubElement(cells, 'mxCell', id='child', parent='a', vertex='1', value='nested')
    E.SubElement(child, 'mxGeometry', x='2', y='3', width='20', height='10', **{'as': 'geometry'})
    b = E.SubElement(cells, 'mxCell', id='b', parent='1', vertex='1', value='Beta')
    E.SubElement(b, 'mxGeometry', x='150', y='20', width='40', height='30', **{'as': 'geometry'})
    e = E.SubElement(cells, 'mxCell', id='edge', parent='1', edge='1', source='a', target='b', style='endArrow=block;')
    g = E.SubElement(e, 'mxGeometry', relative='1', **{'as': 'geometry'})
    points = E.SubElement(g, 'Array', **{'as': 'points'})
    E.SubElement(points, 'mxPoint', x='80', y='40')
    E.SubElement(g, 'mxPoint', x='7', y='8', **{'as': 'offset'})
    label = E.SubElement(cells, 'mxCell', id='edge_label', parent='edge', vertex='1', value='follows edge')
    E.SubElement(label, 'mxGeometry', x='0.25', y='0', width='50', height='14', relative='1', **{'as': 'geometry'})
    return E.tostring(root, encoding='unicode')


checks = []
missing = fixture(False)
normalized, meta = c.page_metadata(missing, (200, 100))
assert meta['missing_attributes_filled'] == ['pageWidth', 'pageHeight']
assert c.verify_metadata(missing, normalized, meta)
new, metadata, geometry = c.transform(missing, (200, 100), {'dx': 0, 'dy': 0, 'width': 200, 'height': 100})
assert c.verify_transform(missing, new, metadata, geometry)
assert geometry['translation'] == [0, 0]
assert geometry['new_page'] == [200, 100]
checks.append('missing metadata binds reference size without moving graph')

old = fixture()
new, metadata, geometry = c.transform(old, (200, 100), {'dx': 4, 'dy': 2, 'width': 204, 'height': 102})
assert c.verify_transform(old, new, metadata, geometry)
a = {cell.get('id'): cell for cell in E.fromstring(old).iter('mxCell')}
b = {cell.get('id'): cell for cell in E.fromstring(new).iter('mxCell')}
assert set(a) == set(b)
assert b['a'].find('mxGeometry').get('x') == '1'
assert b['a'].find('mxGeometry/mxRectangle').get('x') == '1'
assert E.tostring(a['child']) == E.tostring(b['child'])
assert E.tostring(a['edge_label']) == E.tostring(b['edge_label'])
assert b['edge'].get('source') == 'a' and b['edge'].get('target') == 'b'
assert b['edge'].find("mxGeometry/mxPoint[@as='offset']").get('x') == '7'
assert b['edge'].find('mxGeometry/Array/mxPoint').get('x') == '84'
assert geometry['new_page'][0] >= geometry['old_page'][0] + geometry['translation'][0]
checks.append('all objects/IDs/text/topology retained; only top-level geometry translates once')

for kind in ('text', 'color', 'terminal', 'nested_geometry', 'label_geometry', 'page_size'):
    bad = E.fromstring(new)
    cells = {cell.get('id'): cell for cell in bad.iter('mxCell')}
    if kind == 'text':
        cells['a'].set('value', 'lost text')
    elif kind == 'color':
        cells['a'].set('style', 'fillColor=#ff0000;')
    elif kind == 'terminal':
        cells['edge'].set('target', 'a')
    elif kind == 'nested_geometry':
        cells['child'].find('mxGeometry').set('x', '200')
    elif kind == 'label_geometry':
        cells['edge_label'].find('mxGeometry').set('x', '0.5')
    else:
        bad.find('.//mxGraphModel').set('pageWidth', '205')
    try:
        c.verify_transform(old, E.tostring(bad, encoding='unicode'), metadata, geometry)
    except AssertionError:
        pass
    else:
        raise AssertionError('Mutation passed: ' + kind)
checks.append('changed text/color/terminal/nested label/page rejected')
for plan in ({'dx': 4, 'dy': 0, 'width': 200, 'height': 100},
             {'dx': 0, 'dy': 0, 'width': 400, 'height': 100}):
    try:
        c.transform(old, (200, 100), plan)
    except AssertionError:
        pass
    else:
        raise AssertionError('Cropping or unbounded growth passed')
try:
    c.page_metadata(old, (201, 100))
except AssertionError:
    pass
else:
    raise AssertionError('Explicit page mismatch was guessed')
checks.append('original page cannot be cropped; excessive growth and explicit mismatch rejected')

# Source and exception fixtures, not actual data. Claim/finish are tested against
# a separate database so no production records or files can be mutated.
db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT,output_record TEXT,worker_pid INT,updated_at TEXT)')
db.execute('CREATE TABLE auto_quality_exceptions_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,route TEXT,state TEXT,reason TEXT,updated_at TEXT,PRIMARY KEY(id,code_hash,image_hash,policy))')
c.initialize(db)
record = {'code_sha256': 'a' * 64, 'image_sha256': 'b' * 64}
raw = json.dumps(record)
for identifier, state, owner in [('idle','needs_quality_repair',None), ('done','accepted',None), ('busy','needs_quality_repair',88), ('changed','needs_quality_repair',None), ('no_exception','needs_quality_repair',None)]:
    db.execute('INSERT INTO jobs VALUES(?,?,?,?,NULL)', (identifier,state,raw,owner))
    if identifier != 'no_exception':
        db.execute('INSERT INTO auto_quality_exceptions_v1 VALUES(?,?,?,?,?,?,?,NULL)', (identifier,record['code_sha256'],record['image_sha256'],'policy','deterministic_canvas_repair','pending','fixture'))
db.commit()
assert not c.claim(db, 'done', 'accepted', raw, 12)
assert not c.claim(db, 'busy', 'needs_quality_repair', raw, 12)
assert not c.claim(db, 'no_exception', 'needs_quality_repair', raw, 12)
assert not c.claim(db, 'changed', 'needs_quality_repair', json.dumps({**record,'code_sha256':'c'*64}), 12)
assert c.claim(db, 'idle', 'needs_quality_repair', raw, 12)
assert not c.claim(db, 'idle', 'needs_quality_repair', raw, 13)
try:
    c.finish(db, 'idle', 'needs_quality_repair', raw, 13, None, {'error':'fixture'}, False)
except AssertionError:
    db.rollback()
else:
    raise AssertionError('Foreign owner finished task')
assert db.execute('SELECT worker_pid FROM jobs WHERE id="idle"').fetchone()[0] == 12
stage = c.finish(db, 'idle', 'needs_quality_repair', raw, 12, None, {'error':'fixture','accepted':False}, False)
assert stage == 'retained_prior_candidate'
assert db.execute('SELECT state,output_record,worker_pid FROM jobs WHERE id="idle"').fetchone() == ('needs_quality_repair',raw,None)
assert db.execute('SELECT state FROM jobs WHERE id="done"').fetchone()[0] == 'accepted'
checks.append('accepted/busy/changed/no-exception revisions excluded; owner CAS protects finish; failures retain original')
print(json.dumps({'ok':True,'checks':checks,'new_acceptances':0}))

# Optional real remote frozen-provenance checks. This reads only the supplied
# nonpublishing smoke artifacts and removes only its own temporary negative JSON.
if __name__ == '__main__':
    import argparse
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof-id', action='append', default=[])
    args = parser.parse_args()
    if args.proof_id:
        cases = []
        for identifier in args.proof_id:
            files = list((c.W / 'auto_quality_canvas_repair_v1' / identifier).glob('*/candidate_record.json'))
            path = max(files, key=lambda value: value.stat().st_mtime_ns)
            record = json.loads(path.read_text())
            reference = (c.R / record['original_reference']).read_bytes()
            xml = (c.R / record['code_file']).read_text()
            contract = c.validate_registration(record, reference, xml)
            rejected = []
            for kind in ('source_identity', 'reference_bytes', 'xml_bytes', 'proof_hash',
                         'cropped_page', 'registration_offset', 'foreign_frozen_xml'):
                rr = copy.deepcopy(record)
                ref = reference
                xx = xml
                temporary = None
                if kind == 'source_identity':
                    rr['source_code_sha256'] = '0' * 64
                if kind == 'reference_bytes':
                    ref = reference + b'changed'
                if kind == 'xml_bytes':
                    xx = xml.replace('mxGraphModel', 'mxGraphModelChanged')
                if kind == 'proof_hash':
                    rr['auto_quality_canvas_repair']['proof_sha256'] = '0' * 64
                if kind in ('cropped_page', 'registration_offset', 'foreign_frozen_xml'):
                    proof = json.loads((c.R / rr['auto_quality_canvas_repair']['proof']).read_text())
                    if kind == 'cropped_page':
                        proof['geometry']['new_page'][0] -= 1
                    elif kind == 'registration_offset':
                        proof['reference_registration']['original_page_offset'][0] += 1
                    else:
                        proof['frozen_candidate_code'] = record['code_file']
                    temporary = path.parent / ('negative_%d_%s.json' % (os.getpid(), kind))
                    c._json(temporary, proof)
                    rr['auto_quality_canvas_repair'] = {'proof': str(temporary.relative_to(c.R)),
                                                      'proof_sha256': c.sha(temporary.read_bytes())}
                try:
                    c.validate_registration(rr, ref, xx)
                except (AssertionError, ValueError, E.ParseError):
                    rejected.append(kind)
                else:
                    raise AssertionError('Frozen proof negative passed: ' + kind)
                finally:
                    if temporary:
                        temporary.unlink()
            # A later revision does not destroy the original proof. This API
            # explicitly marks the CURRENT revision as unverified, so a caller
            # still needs graph/font-only delta and actual-render checks.
            revision = {**record, 'code_sha256': '0' * 64}
            inherited = c.validate_registration_origin(revision, reference)
            assert inherited['origin_code_sha256'] == record['code_sha256']
            assert not inherited['current_revision_verified']
            assert inherited['inherited_font_or_graph_revision_needs_independent_delta_validation']
            cases.append({'id': identifier, 'contract': contract,
                          'negative_guards_rejected': rejected,
                          'later_revision_does_not_destroy_origin': True,
                          'later_revision_not_accepted_by_origin_validation': True,
                          'accepted': False})
        result = {'at': c.now(), 'ok': True, 'cases': cases, 'jobs_mutated': False,
                  'new_acceptances': 0}
        c._json(c.W / 'auto_quality_canvas_repair_preflight_tests.json', result)
        print(json.dumps(result))
