"""Ordinary captured Graphviz through the exact official CoSyn forward frame."""
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='compiler_python_cosyn_frontend_v1'
UNIT='Python_CoSyn_official_forward_frame_Graphviz_v1'
sha=lambda value:hashlib.sha256(value).hexdigest()


def configuration(data_root=R):
    if Path(data_root).resolve()!=R.resolve():raise ValueError('CoSyn_requires_HKUST_root')
    import compiler_graphviz_visibility_frontend_v1 as frozen
    import compiler_cosyn_image_postprocess_v1 as official
    pins={**frozen.configuration()['pins'],**official.configuration()['pins']}
    for name in ('compiler_python_cosyn_frame_v1.py','compiler_python_cosyn_frontend_v1.py','compiler_python_cosyn_quality_ro_v1.py'):
        p=W/'scripts'/name;pins[str(p)]=sha(p.read_bytes())
    # Read and pin the existing physical-font environment; nothing is installed
    # or changed. Fresh Pango resolution is separately matched to SOURCE faces.
    files={Path(value).resolve()for value in subprocess.check_output(['fc-list','--format=%{file}\n'],text=True).splitlines()if value}
    files.update(path.resolve()for path in Path('/etc/fonts').rglob('*')if path.is_file())
    for path in sorted(files):pins[str(path)]=sha(path.read_bytes())
    return dict(unit=UNIT,policy=VERSION+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20],pins=pins,
                official_source_postprocess=official.configuration()['policy'],native_core_rebuilt=False,
                original_intrinsic_glyph_shape_and_full_source_frame_required=True)


def original(record,given):
    from compiler_graphviz_visibility_frontend_v1 import original as captured
    seed,job=captured(record,given)
    if seed['source']!='allenai--CoSyn-400K':raise ValueError('requires_original_CoSyn_Python')
    return seed,job


def ordinary_queue_status(identifier):
    path=R/'release/compiler_v2/graphviz_batch_20261101_v2_renderdomain/status.sqlite'
    if not path.is_file():raise RuntimeError('infrastructure_missing_ordinary_Graphviz_v2_ledger')
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=30)as database:
        found=database.execute('select status from samples where id=?',(identifier,)).fetchone()
    return dict(ledger=str(path),status=found[0]if found else None,active=bool(found and found[0]in ('queued','running')),read_only=True)


def static_support(given):
    result=dict(supported=False,unit=UNIT,reasons=[],source_only=True)
    try:
        from compiler_graphviz_visibility_scene_v1 import static_support as source_support
        seed,_=original(None,given);support=source_support(seed)
        if not support['supported']:raise ValueError('CoSyn_source_grammar:'+json.dumps(support['reasons']))
        result.update(supported=True,source_capture_snapshot=seed['compiler_source_capture_snapshot'],
                      source_code_sha256=seed['source_code_sha256'],source_image_sha256=seed['source_image_sha256'],
                      ordinary_queue_guard=ordinary_queue_status(seed['id']))
    except Exception as error:result['reasons']=[str(error)[:2500]]
    return result


def convert(record,given,work):
    import compiler_python_cosyn_frame_v1 as frame
    import compiler_graphviz_visibility_text_v1 as text
    from strict_canvas_gate import require_declared_page
    try:
        identifier=given['id']if isinstance(given,dict)else given[0]
        queue=ordinary_queue_status(identifier)
        if queue['active']:return dict(ok=False,reason='deferred_current_ordinary_Graphviz_v2_queue',ordinary_queue_guard=queue,infrastructure_failure=False,model_calls=0)
        work=Path(work).resolve()
        if not work.is_relative_to(W.resolve()):raise ValueError('CoSyn_native_work_outside_conversion')
        work.mkdir(parents=True,exist_ok=False)
        seed,job=original(record,given)
        source=frame.source(seed,work/'source_forward_frame')
        destination=R/'clean'/VERSION/seed['id'][:2]/seed['id']/uuid.uuid4().hex
        destination.mkdir(parents=True,exist_ok=False)
        xml,stats,fonts,shapes,carrier=frame.native(seed,source,destination)
        width,height=source['canvas'];baseline,baseline_info=text._render_observed(xml,width,height)
        frame.save(destination/'baseline.drawio',xml.encode());frame.save(destination/'baseline.png',baseline)
        frame.save(destination/'baseline_native_info.json',frame.raw(baseline_info))
        frame.save(work/'intrinsic_shape_baseline.json',frame.raw(dict(directory=str(destination),source_frame_proof=source['proof_asset'],
                          baseline_code_sha256=sha(xml.encode()),baseline_image_sha256=sha(baseline),source_text_shapes=shapes)))
        # Baseline text anchors are not a released pair. The frozen renderer
        # observes every grapheme at scale=1/translate=0 before its tight-image
        # diagnostic. Anchor correction uses those SOURCE-domain observations;
        # the final PNG still must pass the complete strict declared-page gate.
        if baseline_info.get('scale')!=1 or baseline_info.get('translate')!={'x':0,'y':0}:
            raise ValueError('CoSyn_baseline_observation_not_original_declared_frame')
        # Exactly one bounded whole-run anchor correction, from fresh SOURCE
        # graphemes to fresh native graphemes. No target pixels select anything.
        try:corrections=text.offsets(source['replay']['positions'],baseline_info)
        except Exception:
            import compiler_graphviz_visibility_domain_v1 as domain
            frame.save(work/'intrinsic_shape_glyph_diagnostic.json',frame.raw(domain.glyph_check(source['replay']['positions'],baseline_info)))
            raise
        final=frame.apply_anchors(xml,shapes,corrections)
        png,info=text._render_observed(final,width,height);require_declared_page(info,width,height)
        frame.save(destination/'diagram.drawio',final.encode());frame.save(destination/'image.png',png)
        frame.save(destination/'source_anchor_offsets.json',frame.raw(corrections))
        out={**seed,'code_file':str((destination/'diagram.drawio').relative_to(R)),'code_sha256':sha(final.encode()),
             'image_file':str((destination/'image.png').relative_to(R)),'image_sha256':sha(png),'render':info,
             'native_embedded_fonts':fonts,'svg_conversion':stats,'conversion_method':VERSION,
             'ordinary_queue_guard':queue,
             'compiler_python_cosyn_frame_v1':dict(policy=frame.POLICY,source_frame_proof=source['proof_asset'],
                   registered_SOURCE_SVG=source['proof']['registered_SOURCE_SVG'],mapping=source['proof']['mapping'],
                   native_frame_carrier=carrier,source_anchor_offsets=frame.asset(destination/'source_anchor_offsets.json'),
                   original_intrinsic_glyph_shapes=shapes,final_fresh_drawio_png=True,requires_independent_full_quality=True),
             'quality_state':'pending_independent_CoSyn_source_frame_native_quality', 'model':None}
        frame.save(work/'candidate_record.json',frame.raw(out))
        return dict(ok=True,record=out,record_file=str(work/'candidate_record.json'),work=str(work),model_calls=0)
    except Exception as error:
        return dict(ok=False,reason=str(error).split(':',1)[0],detail=str(error)[:6000],error_type=type(error).__name__,model_calls=0,
                    infrastructure_failure=isinstance(error,(ImportError,ModuleNotFoundError))or str(error).startswith('infrastructure_'))
