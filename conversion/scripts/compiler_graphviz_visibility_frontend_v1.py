"""Fresh capture-bound Graphviz lowering with explicit nonpainting constraints."""
import copy
import ast
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='compiler_graphviz_visibility_frontend_v1'
UNIT='python_graphviz_explicit_nonpainting_constraints_v1'
sha=lambda data:hashlib.sha256(data).hexdigest()
MODULES=('scene','backend','text','reproduction','domain','quality','case','frontend','quality_ro')


def configuration(data_root=R):
    if Path(data_root).resolve()!=R.resolve():raise ValueError('visibility_requires_HKUST_root')
    import fixed_batch_pipeline_v1 as base
    from round2_font_canvas_registration_v1 import configuration as registration
    pins={**base.pins(),**registration()['pins']}
    pending=[]
    for name in MODULES:
        p=W/'scripts'/('compiler_graphviz_visibility_'+name+'_v1.py');pending.append(p)
    for name in ('svg_convert_v5.py','round2_canvas_repair_v1.py','compiler_capture_snapshot_v1.py'):
        pending.append(W/'scripts'/name)
    scanned=set()
    while pending:
        p=pending.pop().resolve()
        if p in scanned:continue
        scanned.add(p);blob=p.read_bytes();pins[str(p)]=sha(blob)
        for node in ast.walk(ast.parse(blob)):
            imports=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
            for module in imports:
                local=W/'scripts'/(module+'.py')
                if local.is_file() and local.resolve() not in scanned:pending.append(local)
    runtime=W/'runtime/graphviz'
    for folder in (runtime/'bin',runtime/'lib',runtime/'lib/graphviz'):
        for path in folder.iterdir():
            if path.is_file():pins[str(path)]=sha(path.read_bytes())
    for name in ('provenance.json','manifest.json'):
        p=runtime/name
        if p.is_file():pins[str(p)]=sha(p.read_bytes())
    for path in (Path('/home/shaoshitong/anaconda3/bin/python').resolve(),
                 Path('/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome')):
        pins[str(path)]=sha(path.read_bytes())
    return dict(unit=UNIT,policy=VERSION+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20],pins=pins)


def job_tuple(given):
    identifier=given['id'] if isinstance(given,dict) else given[0]
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30) as database:
        job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
    if not job or job[2]!='python' or not job[9]:raise ValueError('visibility_requires_existing_python_graphviz_capture')
    return job


def original(record,given):
    from compiler_capture_snapshot_v1 import seal_snapshot,check_snapshot
    from compiler_graphviz_visibility_scene_v1 import _read
    job=job_tuple(given);source=json.loads(job[4]);capture=json.loads(job[9])
    if (capture['id'],capture['source_code_sha256'],capture['source_image_sha256'])!=(source['pair_sha256'],source['code_sha256'],source['image_sha256']):
        raise ValueError('visibility_canonical_source_identity_changed')
    seed=dict(id=source['pair_sha256'],source_pair_sha256=source['pair_sha256'],category=source['category'],
              source_format='python',source=source['source'],format='drawio',model=None,
              source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
    for key in ('source_render_dot','source_render_svg','source_render_svg_sha256','execution_audit',
                'original_source_data','source_data_sha256'):
        if key in capture:seed[key]=copy.deepcopy(capture[key])
    manifest=json.loads(job[11]) if job[11] else None
    for key,manifest_key,digest in [('original_source_code','source_code',source['code_sha256']),
                                    ('original_reference','reference_image',source['image_sha256'])]:
        choices=[(record or {}).get(key),capture.get(key),(manifest or {}).get(manifest_key)]
        for locator in choices:
            if not locator:continue
            try:_read(locator,digest)
            except (OSError,ValueError):continue
            seed[key]=locator;break
        else:raise ValueError('visibility_original_clean_payload_missing:'+key)
    frozen=(record or {}).get('compiler_source_capture_snapshot')
    snapshot=copy.deepcopy(frozen) if frozen else seal_snapshot(seed)
    check_snapshot(seed,snapshot)
    seed['compiler_source_capture_snapshot']=snapshot
    return seed,job


def static_support(given):
    result=dict(supported=False,unit=UNIT,reasons=[],source_only=True)
    try:
        from compiler_graphviz_visibility_scene_v1 import static_support as source_support,_read
        seed,_=original(None,given);predicate=source_support(seed)
        if not predicate['supported']:raise ValueError('visibility_source_profile:'+json.dumps(predicate['reasons']))
        dot=_read(seed['source_render_dot'],predicate['source_dot_sha256']).decode()
        if not re.search(r'\bstyle\s*=\s*(?:"[^"\n]*\binvis\b[^"\n]*"|invis\b)',dot):
            raise ValueError('visibility_unit_requires_explicit_source_invis_style')
        result.update(supported=True,source_code_sha256=seed['source_code_sha256'],
                      source_image_sha256=seed['source_image_sha256'],source_capture_snapshot=seed['compiler_source_capture_snapshot'])
    except Exception as exc:result['reasons']=[str(exc)[:2000]]
    return result


def convert(record,given,work):
    from fixed_batch_case_v1 import save,raw
    from compiler_graphviz_visibility_reproduction_v1 import check
    from compiler_graphviz_visibility_text_v1 import convert as lower
    try:
        work=Path(work).resolve()
        if not work.is_relative_to(W.resolve()):raise ValueError('visibility_work_outside_conversion')
        work.mkdir(parents=True,exist_ok=False)
        seed,job=original(record,given)
        reproduced=check(seed,work/'source_reproduction');save(work/'source_reproduction.json',raw(reproduced))
        if not reproduced.get('ok'):
            return dict(ok=False,reason='source_reference_pending:'+str(reproduced.get('reason')),
                        detail=reproduced,infrastructure_failure=reproduced.get('infrastructure_failure') is True,model_calls=0)
        from compiler_graphviz_visibility_scene_v1 import _read
        ref=reproduced['assets']['source_scene'];scene=json.loads(_read(ref['file'],ref['sha256']))
        if not scene.get('layout_constraints'):raise ValueError('visibility_unit_requires_actual_explicit_nonpainting_source_constraints')
        attempt=lower(seed,job,work/'lowering')
        if not attempt.get('ok'):return attempt
        out=attempt['record'];out['compiler_source_reproduction']=reproduced['evidence']
        out['compiler_quality_phase_visibility_v1']='candidate'
        out['conversion_method']=VERSION
        # One deterministic source/native-paint padding proof, without target
        # pixel fitting or repeated variants. The unchanged final QA still
        # verifies original-page preservation, all paint and registration.
        from round2_canvas_repair_v1 import repair as canvas_repair
        padding=work/'native_paint_padding';padding.mkdir()
        normalized=canvas_repair(out,job,padding)
        save(work/'native_paint_padding_result.json',raw(normalized))
        if normalized.get('ok'):
            out=normalized['record']
        elif normalized.get('detail')!='no_current_overflow_or_missing_page_metadata':
            return dict(ok=False,reason='visibility_native_paint_padding_pending',detail=normalized,model_calls=0)
        # The padding renderer's PNG is a geometry/page-preservation witness.
        # The dataset pair uses an actual fresh render from the unchanged strict
        # qualification painter. These profiles can differ in antialias pixels;
        # the immutable padding witness and all final fidelity gates stay intact.
        from compiler_graphviz_visibility_text_v1 import _render_observed
        from strict_canvas_gate import require_declared_page
        xml=_read(out['code_file'],out['code_sha256']).decode()
        model=ET.fromstring(xml).find('.//mxGraphModel')
        width,height=[int(round(float(model.get(k)))) for k in ('pageWidth','pageHeight')]
        png,info=_render_observed(xml,width,height);require_declared_page(info,width,height)
        destination=R/'clean'/VERSION/out['id'][:2]/out['id']/uuid.uuid4().hex
        destination.mkdir(parents=True,exist_ok=False);save(destination/'image.png',png)
        provenance=dict(policy='actual_strict_native_final_pair_png_v1',code_sha256=out['code_sha256'],
                        auxiliary_paint_proof_image=dict(file=out['image_file'],sha256=out['image_sha256']),
                        final_image=dict(file=str((destination/'image.png').relative_to(R)),sha256=sha(png)),
                        actual_upstream_drawio=True,geometry_changed=False,source_and_original_reference_quality_required=True)
        save(destination/'actual_native_png.json',raw(provenance))
        out={**out,'image_file':provenance['final_image']['file'],'image_sha256':sha(png),'render':info,
             'compiler_graphviz_visibility_final_png':provenance}
        save(work/'candidate_record.json',raw(out))
        return dict(ok=True,record=out,record_file=str(work/'candidate_record.json'),work=str(work),model_calls=0)
    except Exception as exc:
        return dict(ok=False,reason=str(exc)[:5000],error_type=type(exc).__name__,
                    infrastructure_failure=isinstance(exc,(ImportError,ModuleNotFoundError)) or str(exc).startswith('infrastructure_'),model_calls=0)
