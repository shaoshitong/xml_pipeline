"""Finite real positive/negative controls on consumed cases, without new cohort reads."""
import copy
import json
from pathlib import Path
import sqlite3
import uuid
import xml.etree.ElementTree as ET

import compiler_mermaid_alpha_layers_v1 as compiler
from compiler_mermaid_iteration_case_v1 import full_quality, publish
from deterministic_candidate_quality_ro_v1 import verify
from native_worker import native
from svg_convert_v3 import unpack, pack

R, W, raw, sha = compiler.R, compiler.W, compiler.raw, compiler.sha
CONTROL = R / 'release/compiler_iterations/controls/mermaid_alpha_layers_controls_20261101_v1'
INITIAL = R / 'clean/compiler_mermaid_alpha_layers_v1/32/324876415e8ade1f940521d340fe8e0a291bccf186368c53eb8d9d4789c6d171/a5400b5a52af465f85174ca53f800748/record.json'
INITIAL_QA = W / 'prototype/candidate_quality_ro_v1/mermaid_alpha_dev_324876415e8a_1d83f69791a9457b92ea70ee5535a98b/report.json'
MORE = ('ece79572f7682704fb3e4f651bc92f72e6ce66596eb15013e8baae6d6842a318',
        '885573ee7a921000a96c21877a1299ee2053284ba59cc5df8bc5a7873b45b9f2')


def asset(path):
    path = Path(path)
    return {'file': str(path.relative_to(R)), 'sha256': sha(path.read_bytes())}


def source_record(identifier):
    with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as db:
        return json.loads(db.execute('select input_record from jobs where id=?', (identifier,)).fetchone()[0])


def control_row(record_file, qa_file, name):
    record = json.loads(Path(record_file).read_bytes())
    return {'id': record['id'], 'name': name, 'candidate': asset(record_file), 'qa': asset(qa_file),
            'source_code_sha256': record['source_code_sha256'], 'source_image_sha256': record['source_image_sha256']}


def positive(identifier):
    with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as db:
        columns = [x[1] for x in db.execute('pragma table_info(jobs)')]
        snapshot = db.execute('select * from jobs where id=?', (identifier,)).fetchone()
        job = dict(zip(columns, snapshot))
        previous = json.loads(job['output_record']) if job['output_record'] else {}
        work = W / compiler.VERSION / 'controls' / CONTROL.name / identifier
        result = compiler.convert(previous, job, work)
        compiler.require(result.get('ok'), 'additional_positive_not_converted:' + json.dumps(result.get('detail')))
        directory = W / 'prototype/candidate_quality_ro_v1' / ('mermaid_alpha_control_' + identifier[:12] + '_' + uuid.uuid4().hex)
        quality = verify(identifier, result['record_file'], R, Path(compiler.__file__), directory)
        full_quality(quality, result['record'])
        compiler.require(snapshot == db.execute('select * from jobs where id=?', (identifier,)).fetchone(), 'canonical_job_changed')
        row = control_row(result['record_file'], directory / 'report.json', 'consumed_full_quality_positive')
        print(json.dumps({'positive': identifier, 'ok': True, 'qa': row['qa']}), flush=True)
        return row


def mutate_alpha(root):
    cell = next(c for c in root.iter('mxCell') if c.get('sourceCssBackgroundAlpha') and float(c.get('sourceCssBackgroundAlpha')) < 1)
    style = unpack(cell.get('style'))
    style['fillOpacity'] = '100'
    cell.set('style', pack(style))


def mutate_layer(root):
    container = root.find('.//mxGraphModel/root')
    cell = next(c for c in container if c.get('sourceCssBackgroundAlpha'))
    container.remove(cell)


def mutate_terminal(root):
    edge = next(c for c in root.iter('mxCell') if c.get('edge') == '1')
    edge.set('target', edge.get('source'))


def mutate_label(root):
    next(c for c in root.iter('mxCell') if c.get('value', '').strip()).set('value', '')


def negative(name, mutation):
    record = json.loads(INITIAL.read_bytes())
    root = ET.fromstring((R / record['code_file']).read_bytes())
    mutation(root)
    xml = ET.tostring(root, encoding='unicode')
    canvas = json.loads(INITIAL_QA.read_bytes())['checks']['render']['canvas']
    width, height = (canvas['width'], canvas['height']) if isinstance(canvas, dict) else canvas
    rendered = native.native_job(xml, width, height, 180, W / 'rendering_paintbounds_strict/remote_render.py', 8192,
                                 R / 'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    compiler.require(rendered.get('ok'), 'negative_actual_native_render_failed')
    directory = R / 'clean/compiler_mermaid_alpha_controls_v1' / name / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    code_file, image_file = directory / 'candidate.drawio', directory / 'candidate.png'
    code_file.write_text(xml)
    image_file.write_bytes(rendered['png'])
    record = copy.deepcopy(record)
    record.update(code_file=str(code_file.relative_to(R)), code_sha256=sha(code_file.read_bytes()),
                  image_file=str(image_file.relative_to(R)), image_sha256=sha(image_file.read_bytes()))
    record[compiler.FIELD]['candidate_code_sha256'] = record['code_sha256']
    proposal = directory / 'record.json'
    proposal.write_bytes(raw(record))
    qdir = W / 'prototype/candidate_quality_ro_v1' / ('mermaid_alpha_negative_' + name + '_' + uuid.uuid4().hex)
    report = verify(record['id'], proposal, R, Path(compiler.__file__), qdir)
    compiler.require(report.get('ok') is False and bool(report.get('failures')), 'negative_false_acceptance:' + name)
    compiler.require(any(f.get('stage') in ('source_preliminary', 'source') for f in report['failures']),
                     'negative_not_rejected_by_independent_source:' + name)
    row = control_row(proposal, qdir / 'report.json', name)
    row.update(actual_XML_and_PNG_rehashed=True, mutation_rejected=True)
    print(json.dumps({'negative': name, 'rejected': True, 'failures': report['failures']}), flush=True)
    return row


def main():
    CONTROL.mkdir(parents=True, exist_ok=False)
    config = compiler.configuration()
    first = json.loads(INITIAL.read_bytes())
    full_quality(json.loads(INITIAL_QA.read_bytes()), first)
    positives = [control_row(INITIAL, INITIAL_QA, 'consumed_new_alpha_full_quality_positive')]
    positives += [positive(identifier) for identifier in MORE]
    negatives = [negative(name, mutation) for name, mutation in (
        ('opaque_source_alpha_layer', mutate_alpha), ('deleted_source_background_layer', mutate_layer),
        ('changed_bound_terminal', mutate_terminal), ('deleted_source_label', mutate_label))]
    compiler.require(config == compiler.configuration(), 'control_implementation_changed')
    qualified = []
    for row in positives:
        record = json.loads((R / row['candidate']['file']).read_bytes())
        quality_path = R / row['qa']['file']
        report = json.loads(quality_path.read_bytes())
        qualified.append(publish(record, source_record(row['id']), report, quality_path.parent))
    manifest = CONTROL / 'qualified.jsonl'
    manifest.write_bytes(b''.join(raw(row) for row in qualified))
    proof = {'schema': 'compiler_mermaid_alpha_controls_v1', 'frozen_frontend': config,
             'producer': asset(Path(__file__).resolve()), 'positive_cases': positives, 'negative_cases': negatives,
             'positives': [row['qa'] for row in positives], 'negatives': [row['qa'] for row in negatives],
             'qualified_manifest': asset(manifest), 'source_policy': 'one_editable_rectangle_per_actual_CSS_layer_same_source_order_and_alpha',
             'new_unseen_samples_read': 0, 'model_calls': 0, 'goal_complete': False}
    (CONTROL / 'proof.json').write_bytes(raw(proof))
    print(json.dumps({'proof': asset(CONTROL / 'proof.json'), 'positive': len(positives), 'negative': len(negatives)}), flush=True)


if __name__ == '__main__':
    main()
