"""Original native XML -> observed physical fonts -> actual drawio export.

Always starts from authoritative original geometry, never a clipped cached
candidate. One-page source-declared named and explicit-coordinate connectors
are supported; complete source paint is inspected before actual native export.
"""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import uuid
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
VERSION = 'compiler_native_source_frontend_v2'
UNIT = 'original_native_bound_and_explicit_coordinates_complete_export_v2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def configuration(data_root=R):
    from native_export_reference_v4 import configuration as export_configuration
    if Path(data_root).resolve() != R.resolve():
        raise ValueError('native_frontend_requires_HKUST_root')
    pins = export_configuration()
    for name in (VERSION + '.py', 'compiler_native_quality_ro_v2.py', 'native_source_font_profile_v4.py',
                 'native_source_editing_v4.py', 'portable_native_fonts.py', 'auto_quality_font_repair.py',
                 'compiler_types_source_ir_v1.py'):
        path = W / 'scripts' / name
        pins[str(path)] = sha(path.read_bytes())
    return dict(unit=UNIT, policy=VERSION + ':' + sha(json.dumps(pins, sort_keys=True).encode())[:20], pins=pins)


def source_inputs(given):
    identifier = given['id'] if isinstance(given, dict) else given[0]
    with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30) as db:
        row = db.execute('select input_record,input_manifest,format,category from jobs where id=?', (identifier,)).fetchone()
    if not row or not row[1] or row[2] != 'drawio' or row[3] not in ('scientific_diagram', 'poster'):
        raise ValueError('native_source_manifest_or_scope_unsupported')
    source, manifest = json.loads(row[0]), json.loads(row[1])
    if source['pair_sha256'] != identifier:
        raise ValueError('native_source_identity_mismatch')
    paths = [(R / manifest[name]).resolve(strict=True) for name in ('source_code', 'reference_image')]
    if not all(p.is_relative_to(R.resolve()) for p in paths):
        raise ValueError('native_source_outside_HKUST_root')
    code, reference = (p.read_bytes() for p in paths)
    if sha(code) != source['code_sha256'] or sha(reference) != source['image_sha256']:
        raise ValueError('native_original_payload_hash_changed')
    return source, code.decode('utf-8'), reference


def normalize_source(code):
    from native_worker import normalize
    xml, pages, _ = normalize(code)
    if pages != 1:
        raise ValueError('native_multiple_pages_pending')
    root = ET.fromstring(xml)
    model = root.find('.//mxGraphModel') if root.tag != 'mxGraphModel' else root
    if model is None:
        raise ValueError('native_missing_model')
    size = [float(model.get(key, 0)) for key in ('pageWidth', 'pageHeight')]
    if any(not 0 < n <= 8192 or n != round(n) for n in size):
        raise ValueError('native_original_declared_page_unsupported')
    from native_source_font_profile_v4 import _cells
    cells = _cells(root)
    if not cells:
        raise ValueError('native_original_cell_identity_invalid')
    from native_free_edges_v4 import structure_checks
    # This is a source-only grammar inventory, not a qualification proof. Its
    # exact normalized-source identity is established directly above; the RO
    # quality adapter independently replays source/fonts/rendering/editability.
    structure_checks(xml, record={'source_format':'drawio','code_sha256':sha(xml.encode())},
        source_profile={'supported':True,'ok':True,'profile':'original_native_xml',
                        'evidence':{'unchanged_source_objects_except_portable_font_styles':True,'source_pages':1}})
    vertices = [c for c in cells.values() if c.get('vertex') == '1']
    if not vertices or len(vertices) == 1 and any('image=' in c.get('style', '') or 'shape=image' in c.get('style', '') for c in vertices):
        raise ValueError('native_no_editable_graph_or_whole_image_wrapper')
    return xml, list(map(int, size))


def static_support(given):
    result = dict(supported=False, unit=UNIT, reasons=[])
    try:
        from PIL import Image
        _, code, reference = source_inputs(given)
        xml, size = normalize_source(code)
        reference_size = Image.open(io.BytesIO(reference)).size
        if not all(0 < n <= 8192 for n in reference_size):
            raise ValueError('native_reference_size_unsupported')
        result.update(supported=True, source_declared_page=size, reference_size=reference_size,
                      source_geometry_complete=True, source_only=True)
    except Exception as error:
        result['reasons'] = [str(error)[:1500]]
    return result


def convert(record, job, work):
    from fixed_batch_case_v1 import checked, raw, save
    try:
        work = Path(work).resolve()
        if not work.is_relative_to((W / VERSION).resolve()):
            raise ValueError('native_frontend_work_outside_owner')
        work.mkdir(parents=True, exist_ok=False)
        source, code, _ = source_inputs(job)
        if (record.get('id'),record.get('source_pair_sha256'),record.get('source_code_sha256'),record.get('source_image_sha256')) != (source['pair_sha256'],source['pair_sha256'],source['code_sha256'],source['image_sha256']):
            raise ValueError('native_prepared_original_identity_changed')
        xml, size = normalize_source(code)
        for key, digest in [('original_source_code', 'source_code_sha256'), ('original_reference', 'source_image_sha256')]:
            if not (R/record[key]).resolve(strict=True).is_relative_to((R/'clean').resolve()):
                raise ValueError('native_prepared_original_not_in_clean')
            checked(record[key], record[digest])
        from native_worker import native
        rendered = native.native_job(xml, *size, 180, W / 'rendering_paintbounds_strict/remote_render.py',
                                     8192, R / 'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
        if not rendered.get('ok'):
            raise ValueError('native_original_seed_render_failed:' + str(rendered.get('error'))[:1200])
        identifier = source['pair_sha256']
        dest = R / 'clean' / VERSION / identifier[:2] / identifier / uuid.uuid4().hex
        dest.mkdir(parents=True)
        save(dest / 'diagram.drawio', xml.encode())
        save(dest / 'image.png', rendered['png'])
        seed = dict(id=identifier, source_pair_sha256=identifier, category=source['category'], source=source['source'],
                    source_format='drawio', format='drawio', source_code_sha256=source['code_sha256'],
                    source_image_sha256=source['image_sha256'], original_reference=record['original_reference'],
                    original_source_code=record['original_source_code'], code_file=str((dest/'diagram.drawio').relative_to(R)),
                    code_sha256=sha(xml.encode()), image_file=str((dest/'image.png').relative_to(R)),
                    image_sha256=sha(rendered['png']), conversion_method=VERSION,
                    render=rendered['native_render'], model=None, model_configuration={'external_model_calls': 0})
        save(work / 'seed_record.json', raw(seed))
        from native_compiler_v4 import repair
        attempt = repair(seed, job, work / 'font_and_export')
        save(work / 'repair_result.json', raw(attempt))
        if not attempt.get('ok'):
            return attempt
        out = attempt['record']
        if not out.get('native_export_reference_v4'):
            return dict(ok=False, reason='native_source_export_pending',detail=attempt.get('export_refusal'))
        save(work / 'candidate_record.json', raw(out))
        return dict(ok=True, record=out, record_file=str(work/'candidate_record.json'),
                    source_geometry_seed='exact_original_normalized_native_XML', model_calls=0)
    except Exception as error:
        return dict(ok=False, reason='native_original_source_conversion_pending', error_type=type(error).__name__,
                    detail=str(error)[:5000], infrastructure_failure=isinstance(error, (ImportError, ModuleNotFoundError)))
