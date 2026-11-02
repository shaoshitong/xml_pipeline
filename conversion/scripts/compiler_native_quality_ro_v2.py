"""Independent complete native-source QA with explicit export viewport.

Adapts the frozen native verifier's report schema; does not relax its source,
font, whole-paint, reference-image or actual-editing checks.
"""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
VERSION = 'independent_original_native_full_paint_and_free_endpoints_quality_v2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def complete_source(coverage, record, source, xml):
    require(coverage.get('supported') is True and coverage.get('ok') is True and not coverage.get('failures'),
            'underlying_native_source_not_verified')
    from native_worker import normalize
    original, pages, _ = normalize(source)
    require(pages == 1, 'native_source_pages_changed')
    evidence = coverage.get('evidence', {})
    exact = original == xml
    proven_fonts = (evidence.get('normalized_original_exactly_equals_frozen_before_xml') is True
                    and evidence.get('font_only_delta_independently_verified') is True
                    and evidence.get('unchanged_source_objects_except_portable_font_styles') is True)
    require(exact or proven_fonts, 'native_original_complete_geometry_or_font_delta_unproven')
    out = copy.deepcopy(coverage)
    out.setdefault('evidence', {}).update(complete_source_coverage=True,
            complete_original_normalized_graph_or_verified_font_only_delta=True)
    return out


def verify(identifier, record_file, data_root, plugin_file, work, database=W/'jobs.sqlite'):
    from fixed_batch_case_v1 import checked, save, raw
    from native_quality_v4 import verify as underlying
    from native_export_reference_v4 import configuration
    import compiler_native_source_frontend_v2 as frontend
    record_file, work = Path(record_file).resolve(strict=True), Path(work).resolve()
    require(Path(data_root).resolve() == R.resolve(), 'native_quality_requires_HKUST_root')
    require(work.is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve()), 'native_quality_work_outside_owner')
    require(not work.exists(), 'native_quality_work_already_exists')
    work.mkdir(parents=True)
    report = dict(version=VERSION, id=identifier, checks={}, failures=[], ok=False, accepted=False,
                  canonical_mutations=0, model_calls=0)
    blob = record_file.read_bytes()
    record = json.loads(blob)
    pins = frontend.configuration()['pins']
    pins[str(Path(__file__).resolve())] = sha(Path(__file__).read_bytes())
    import auto_quality_batch_v4b as qa
    for name, digest in qa.IMPLEMENTATION.items():
        path = Path(name) if Path(name).is_absolute() else Path(qa.__file__).parent/name
        require(str(path) not in pins or pins[str(path)] == digest, 'native_quality_pin_conflict')
        pins[str(path)] = digest
    report.update(implementation_pins=pins, input_record_sha256=sha(blob))
    try:
        require(Path(plugin_file).resolve() == Path(frontend.__file__).resolve(), 'wrong_native_source_plugin')
        require(all(sha(Path(p).read_bytes()) == h for p,h in pins.items()), 'native_quality_implementation_changed')
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30) as db:
            job = db.execute('select * from jobs where id=?',(identifier,)).fetchone()
        require(job is not None and job[12] is None, 'original_native_job_missing_or_owned')
        original = json.loads(job[4])
        require((record['id'],record['source_pair_sha256'],record['source_format'],record['category'],record['source'],
                 record['source_code_sha256'],record['source_image_sha256']) ==
                (identifier,identifier,'drawio',original['category'],original['source'],original['code_sha256'],original['image_sha256']),
                'native_quality_source_identity_changed')
        xml = checked(record['code_file'],record['code_sha256']).decode()
        source = checked(record['original_source_code'],record['source_code_sha256']).decode()
        checked(record['original_reference'],record['source_image_sha256'])
        checked(record['image_file'],record['image_sha256'])
        original_report, out, directory = underlying(record,job,work/'underlying',0)
        audit = directory/'audit.json'
        require(json.loads(audit.read_bytes()) == original_report, 'native_quality_underlying_report_changed')
        report['underlying_quality_report'] = dict(file=str(audit.relative_to(R)),sha256=sha(audit.read_bytes()))
        report['quality_policy'] = VERSION+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20]
        report['checks'] = copy.deepcopy(original_report.get('checks',{}))
        report['failures'] = original_report.get('failures',[])
        if not out or original_report.get('state') != 'qualified':
            raise ValueError('underlying_full_native_quality_failed')
        report['checks']['source'] = complete_source(report['checks']['source'],record,source,xml)
        png = (directory/'fresh.png').read_bytes()
        require(png == checked(record['image_file'],record['image_sha256']), 'native_quality_png_not_exact_fresh_export')
        render = report['checks']['render']
        if record.get('native_export_reference_v4'):
            require(render.get('mode')=='actual_upstream_drawio_tight_export' and
                    render.get('complete_source_paint_and_export_paint_independently_verified') is True and
                    render.get('strict_outside_export_pixels')==0 and render.get('strict_outside_page_pixels')==0,
                    'native_export_complete_paint_contract_missing')
            view=record['native_export_reference_v4']['view']
            require(render.get('full_paint_inspection_viewport')==view.get('full_paint_inspection_viewport') and
                    render.get('full_paint_inspection_translation')==view.get('full_paint_inspection_translation'),
                    'native_complete_source_paint_probe_identity_changed')
            render.pop('strict_outside_page_pixels',None)
            render.update(paint_safety_frame='full_paint_inspection_viewport',
                          strict_outside_inspection_pixels=0,
                          strict_outside_export_pixels=0,
                          original_declared_page_outside_pixels=view.get('original_declared_page_outside_pixels'))
        else:
            require(render.get('strict_outside_page_pixels')==0, 'native_declared_page_paint_not_complete')
        render.update(code_sha256=record['code_sha256'],image_sha256=sha(png))
        report['original_source'] = original
        report['underlying_quality_policy'] = original_report.get('policy')
        require(record_file.read_bytes()==blob, 'native_proposal_changed_during_quality')
        require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()), 'native_quality_implementation_changed')
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30) as db:
            require(db.execute('select * from jobs where id=?',(identifier,)).fetchone()==job, 'native_original_job_changed')
        save(work/'fresh.png',png)
        report['ok'] = True
    except Exception as error:
        report['failures'] = [*report.get('failures',[]),dict(type=type(error).__name__,reason=str(error)[:6000])]
    report['evidence_file'] = str(work/'report.json')
    save(work/'report.json',raw(report))
    return report
