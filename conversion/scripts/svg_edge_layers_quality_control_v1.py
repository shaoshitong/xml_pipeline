"""Read-only regression or genuine XML/PNG negative intervention; no normal."""
from pathlib import Path
import argparse
from decimal import Decimal
import hashlib
import io
import json
import sqlite3
import sys
import uuid
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
sys.path.insert(0, str(W / 'scripts'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def asset(path):
    return {'file': str(path.relative_to(R)), 'sha256': sha(path.read_bytes())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--role', choices=['positive', 'negative_text', 'negative_geometry', 'negative_opacity', 'negative_order'], required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    from PIL import Image
    import compiler_svg_general_guard_v11 as compiler
    import compiler_svg_scene_quality_ro_v17 as quality
    import svg_analytic_iteration_controls_v6 as controls
    from compiler_svg_source_viewport_iteration_case_v2 import quality_database
    from compiler_svg_general_iteration_case_v2 import publish
    from svg_source_group_nesting_v1 import _world_rectangles
    configuration = compiler.configuration()
    before_record = args.record.read_bytes()
    original = json.loads(before_record)
    identifier = original['id']
    before_xml = (R / original['code_file']).read_bytes()
    assert sha(before_xml) == original['code_sha256']
    before_png = (R / original['image_file']).read_bytes()
    assert sha(before_png) == original['image_sha256']
    reference = Image.open(io.BytesIO((R / original['original_reference']).read_bytes()))
    size = reference.size
    with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as db:
        job = db.execute('select * from jobs where id=?', (identifier,)).fetchone()
    assert job is not None
    source = json.loads(job[4])
    tree = ET.fromstring(before_xml)
    mutated = None
    cells = {c.get('id'): c for c in tree.iter('mxCell')}
    if args.role == 'negative_text':
        for cell in cells.values():
            if cell.get('vertex') == '1' and 'shape=text;' in cell.get('style', '') and cell.get('value'):
                cell.set('value', cell.get('value') + cell.get('value'))
                mutated = cell.get('id')
                break
    elif args.role == 'negative_order':
        from collections import defaultdict
        children=defaultdict(list)
        for c in tree.find('.//mxGraphModel/root'):
            if c.get('parent'):children[c.get('parent')].append(c)
        order=[]
        def visit(c):
            order.append(c)
            for child in reversed(children[c.get('id')]):visit(child)
        visit(cells['0']);assert len(order)==len(cells)
        tree.find('.//mxGraphModel/root')[:]=order
        mutated='all_native_sibling_paint_orders_reversed_geometry_preserved'
    elif args.role == 'negative_opacity':
        from svg_convert_v3 import unpack,pack
        for cell in cells.values():
            st=unpack(cell.get('style',''))
            if st.get('opacity')=='80':
                st['opacity']='30';cell.set('style',pack(st));mutated=cell.get('id');break
    elif args.role == 'negative_geometry':
        boxes = _world_rectangles(cells)
        for identifier_, cell in cells.items():
            if cell.get('vertex') != '1' or 'shape=stencil(' not in cell.get('style', ''):
                continue
            x, y, w, h = boxes[identifier_]
            if x > 20 and y > 20 and x + w < size[0] - 25 and y + h < size[1] - 25:
                geometry = cell.find('mxGeometry')
                geometry.set('x', str(Decimal(geometry.get('x', '0')) + 17))
                mutated = identifier_
                break
    if args.role != 'positive':
        assert mutated is not None, 'no_actual_native_intervention_selected'
    xml = before_xml.decode() if args.role == 'positive' else ET.tostring(tree, encoding='unicode')
    native = compiler.frontend._native(xml, size)
    fresh_png = native['png']
    a = Image.open(io.BytesIO(before_png)).convert('RGBA')
    b = Image.open(io.BytesIO(fresh_png)).convert('RGBA')
    pixels_changed = a.size != b.size or a.tobytes() != b.tobytes()
    assert pixels_changed == (args.role != 'positive'), 'control_intervention_RGBA_contract_failed'
    destination = R / 'clean/svg_edge_layers_quality_controls_v1' / args.role / uuid.uuid4().hex
    destination.mkdir(parents=True)
    code_file = destination / 'candidate.drawio'
    image_file = destination / 'candidate.png'
    code_file.write_text(xml)
    image_file.write_bytes(fresh_png)
    record = {**original, 'code_file': str(code_file.relative_to(R)), 'code_sha256': sha(xml.encode()),
              'image_file': str(image_file.relative_to(R)), 'image_sha256': sha(fresh_png),
              'accepted': False, 'quality_state': 'development_control_pending_current_independent_QA',
              'control_role': args.role}
    proposal = destination / 'record.json'
    proposal.write_text(json.dumps(record, indent=2) + '\n')
    qa_database, owner_proof, owner_audit = quality_database(job, args.work)
    directory = W / 'prototype/candidate_quality_ro_v1' / ('SVG_actual_shadow_' + args.role + '_' + uuid.uuid4().hex)
    report = quality.verify(identifier, proposal, R, Path(compiler.__file__), directory, database=qa_database)
    row = {'id': identifier, 'name': args.role, 'source_code_sha256': source['code_sha256'],
           'source_image_sha256': source['image_sha256'], 'candidate': asset(proposal),
           'qa': asset(directory / 'report.json'), 'native_render': asset(directory / 'native_render.json') if (directory / 'native_render.json').exists() else None, 'fresh_png': asset(image_file),
           'code_and_image_rehashed': True, 'actual_rerendered_pixels_changed': pixels_changed,
           'normal_conversion_calls': 0, 'original_candidate_preserved': str(args.record),
           'mutated_source_cell': mutated}
    role = 'positive' if args.role == 'positive' else 'negative'
    controls.check_control_case(row, role, configuration)
    output = {'control': row, 'quality_ok': report['ok'], 'quality_failures': report.get('failures'),
              'checks': list(report.get('checks', {})), 'normal_conversion_calls': 0,
              'canonical_unchanged': True, 'control_contract_passed': True, 'new_model_calls': 0}
    if role == 'positive':
        output['qualified_manifest'] = publish(record, source, report, directory)
    with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as db:
        assert db.execute('select * from jobs where id=?', (identifier,)).fetchone() == job
    assert args.record.read_bytes() == before_record
    assert (R / original['code_file']).read_bytes() == before_xml
    assert (R / original['image_file']).read_bytes() == before_png
    assert compiler.configuration() == configuration
    (args.work / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output), flush=True)


if __name__ == '__main__':
    main()
