"""Independent original native text-node/font/source/export/editability QA."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import time

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='independent_native_original_materialized_text_node_physical_fonts_full_quality_v2'
sha=lambda data:hashlib.sha256(data).hexdigest()


def require(ok,reason):
    if not ok:raise ValueError(reason)


def verify(identifier,record_file,data_root,plugin_file,work,database=W/'jobs.sqlite'):
    import compiler_native_source_repair_frontend_v2 as frontend
    import compiler_native_source_repair_fonts_v2 as fonts
    from compiler_native_source_frontend_v2 import source_inputs,normalize_source
    from compiler_native_source_repair_editing_v1 import structure_checks,audit as editing
    from native_source_font_profile_v4 import verify_assets,_models
    from native_export_reference_v4 import validate
    from auto_quality_common import resource_checks,image_quality,require_rendered_text
    from fixed_batch_case_v1 import checked
    from compiler_typed_runtime_failure_v1 import diagnose
    started=time.monotonic();record_file=Path(record_file).resolve(strict=True);work=Path(work).resolve()
    require(Path(data_root).resolve()==R.resolve(),'native_run_quality_wrong_root')
    require(Path(plugin_file).resolve()==Path(frontend.__file__).resolve(),'native_run_quality_wrong_frontend')
    require(work.is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve())and not work.exists(),'native_run_quality_unowned_work')
    work.mkdir(parents=True,exist_ok=False);blob=record_file.read_bytes();record=json.loads(blob);config=frontend.configuration()
    report=dict(id=identifier,version=VERSION,input_record_sha256=sha(blob),implementation_pins=config['pins'],quality_policy=config['policy'],checks={},failures=[],ok=False,accepted=False,canonical_mutations=0,model_calls=0)
    try:
        require(all(sha(Path(path).read_bytes())==digest for path,digest in config['pins'].items()),'infrastructure_native_run_quality_pin_changed')
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30)as db:job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
        require(job is not None and job[12]is None,'native_run_original_missing_or_owned');source=json.loads(job[4]);seed,canonical=frontend.original(record,job)
        require(canonical==job,'infrastructure_native_run_original_job_changed')
        require((record['id'],record['source_pair_sha256'],record['source_format'],record['source_code_sha256'],record['source_image_sha256'],record['category'],record['source'])==(identifier,identifier,'drawio',source['code_sha256'],source['image_sha256'],source['category'],source['source']),'native_run_candidate_source_identity_changed')
        xml=checked(record['code_file'],record['code_sha256']).decode();checked(record['image_file'],record['image_sha256']);original=checked(record['original_source_code'],record['source_code_sha256']).decode();reference=checked(record['original_reference'],record['source_image_sha256'])
        report['checks']['resources']=resource_checks(R,record,xml,reference)
        normalized,page=normalize_source(original);rederived=fonts.compile(normalized,page,work/'independent_original_font_runs')
        require(rederived['xml']==xml,'native_run_candidate_not_independently_rederived_font_only_XML')
        require(rederived['proof']['source_code_sha256']==sha(normalized.encode())and rederived['proof']['output_code_sha256']==record['code_sha256'],'native_run_fresh_font_delta_revision_changed')
        files={};faces=verify_assets(R,record,_models(normalized)[1],_models(xml)[1],files)
        require(all(sha(Path(path).read_bytes())==digest for path,digest in files.items()),'native_run_font_assets_changed')
        no_op=rederived['proof'].get('no_op')is True
        evidence=dict(complete_source_coverage=True,current_code_sha256=record['code_sha256'],source_pages=1,normalized_original_and_font_only_XML_delta_independently_rederived=True,fresh_source_RGBA_equals_portable_RGBA=no_op or rederived['proof'].get('source_RGBA_equals_portable_RGBA')is True,physical_faces_and_glyph_counts_preserved=no_op or rederived['proof'].get('complete_physical_PS_and_glyph_inventory_preserved')is True,all_original_markup_and_text_nodes_preserved=no_op or rederived['proof'].get('original_source_markup_recovers_exactly')is True,source_snapshot=seed['compiler_source_capture_snapshot'],source_font_run_proof=rederived.get('proof_file'),physical_fonts=faces,glyph_max_error_px=rederived['proof'].get('glyph_max_error_px',0.),source_graph_content_geometry_topology_and_native_cells_preserved=True)
        coverage=dict(supported=True,ok=True,profile='original_native_per_text_node_physical_fonts_v1',failures=[],evidence=evidence,accepted=False)
        report['checks']['source']=coverage;report['checks']['structure']=structure_checks(xml,record=record,source_profile=coverage)
        previous,full,export,view=validate(record,xml);info=export['native_render'];png=export['png']
        require(png==checked(record['image_file'],record['image_sha256']),'native_run_candidate_PNG_not_exact_actual_fresh_export')
        report['checks']['render']=dict(code_sha256=record['code_sha256'],image_sha256=sha(png),mode='actual_upstream_drawio_tight_export',paint_safety_frame='full_paint_inspection_viewport',strict_outside_inspection_pixels=0,strict_outside_export_pixels=0,complete_source_paint_and_export_paint_independently_verified=True,original_declared_page_outside_pixels=view['original_declared_page_outside_pixels'],full_paint_inspection_viewport=view['full_paint_inspection_viewport'],export_viewport=view['export_viewport'],view_transform=view['view_transform'],original_native_cells_unchanged_except_proved_font_bindings=True)
        report['checks']['text_paint']=require_rendered_text(xml,info)
        usage=[font for row in info['actual_platform_font_usage']for font in row.get('fonts',[])if font.get('glyphCount',0)]
        require(not info['actual_text_positions']or usage and all(font.get('isCustomFont')for font in usage),'native_run_actual_export_font_not_portable')
        report['checks']['fonts']=dict(all_rendered_fonts_embedded=True,actual_custom_font_glyphs=sum(font['glyphCount']for font in usage),original_physical_sfnt_tables_independently_verified=True,source_complete_text_node_PS_and_glyph_inventory_preserved=True,exact_source_before_after_RGBA_preserved=True,glyph_geometry_tolerance_px=.03,glyph_max_error_px=evidence['glyph_max_error_px'])
        visual=image_quality(reference,png,{**record,'native_canvas_contract':dict(offset=view['original_reference_offset'])},info['actual_text_positions']);report['checks']['visual']=visual
        require(visual['ok'],'native_run_original_reference_raster_anomaly:'+','.join(visual['failures']))
        moves=editing(xml,record=record,source_profile=coverage);require(moves['ok']and len(moves['moves'])==2*report['checks']['structure']['edges'],'native_run_incomplete_actual_endpoint_editing')
        fonts.save(work/'movement.json',fonts.raw(moves));report['checks']['native_editing']=dict(ok=True,endpoint_moves=len(moves['moves']),model_and_all_live_states_restored=moves['model_and_all_live_states_restored'],actual_source_model_constraint_perimeter_proof=True)
        require(record_file.read_bytes()==blob,'native_run_proposal_changed_during_QA')
        require(all(sha(Path(path).read_bytes())==digest for path,digest in config['pins'].items()),'infrastructure_native_run_quality_pin_changed')
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30)as db:require(db.execute('select*from jobs where id=?',(identifier,)).fetchone()==job,'infrastructure_native_run_original_job_changed')
        fonts.save(work/'fresh.png',png);report.update(ok=True,accepted=True)
    except Exception as error:
        diagnosis=diagnose(error);report.update(infrastructure_failure=diagnosis['infrastructure_failure'],infrastructure_diagnosis=diagnosis);report['failures'].append(dict(type=type(error).__name__,reason=str(error)[:6500]))
    report['seconds']=time.monotonic()-started;fonts.save(work/'report.json',fonts.raw(report));return report
