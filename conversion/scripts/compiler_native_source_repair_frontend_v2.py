"""Original native XML with complete-text-node portable physical fonts."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='compiler_native_source_repair_frontend_v2'
UNIT='original_native_materialized_text_node_physical_fonts_complete_export_v2'
sha=lambda data:hashlib.sha256(data).hexdigest()


def configuration(data_root=R):
    if Path(data_root).resolve()!=R.resolve():raise ValueError('native_source_repair_requires_HKUST_root')
    import fixed_batch_pipeline_v1 as base
    from compiler_native_source_frontend_v2 import configuration as original
    pins={**base.pins(),**original()['pins']}
    names=('compiler_native_source_repair_fonts_v2.py','compiler_native_source_repair_frontend_v2.py',
           'compiler_native_source_repair_quality_ro_v2.py','compiler_native_source_repair_editing_v1.py',
           'compiler_native_text_node_cdp_v2.py')
    for name in names:
        path=W/'scripts'/name;pins[str(path)]=sha(path.read_bytes())
    path=W/'scripts/compiler_native_source_repair_editing_v1.js';pins[str(path)]=sha(path.read_bytes())
    for name in ('native_worker.py','portable_native_fonts.py','auto_quality_font_repair.py','pdf_to_native.py','native_source_font_profile_v4.py','compiler_capture_snapshot_v1.py'):
        path=W/'scripts'/name;pins[str(path)]=sha(path.read_bytes())
    files={Path(value).resolve()for value in subprocess.check_output(['fc-list','--format=%{file}\n'],text=True).splitlines()if value}
    files.update(path.resolve()for path in Path('/etc/fonts').rglob('*')if path.is_file())
    for path in files:pins[str(path)]=sha(path.read_bytes())
    return dict(unit=UNIT,policy=VERSION+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20],pins=pins)


def original(record,given):
    from compiler_native_source_frontend_v2 import source_inputs,normalize_source
    identifier=given['id']if isinstance(given,dict)else given[0]
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
    source,code,reference=source_inputs(job);xml,page=normalize_source(code);manifest=json.loads(job[11])
    input_source=(R/manifest['source_code']).resolve(strict=True);input_reference=(R/manifest['reference_image']).resolve(strict=True)
    def locator(field,filename,digest,default):
        choices=[(record or{}).get(field),str(Path('clean/fixed_batch_originals_v1')/identifier[:2]/identifier/filename),str(Path('clean/compiler_native_source_repair_originals_v1')/identifier[:2]/identifier/filename)]
        for name in choices:
            if not name:continue
            path=(R/name).resolve()
            if path.is_relative_to((R/'clean').resolve())and path.is_file()and sha(path.read_bytes())==digest:return path
        return default
    source_path=locator('original_source_code','source.txt',source['code_sha256'],input_source);reference_path=locator('original_reference','reference.bin',source['image_sha256'],input_reference)
    snapshot=dict(schema='native_original_payload_and_normalized_XML_snapshot_v1',id=identifier,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],input_source_code=str(input_source.relative_to(R)),input_reference_image=str(input_reference.relative_to(R)),normalized_source_sha256=sha(xml.encode()),source_declared_page=page,input_record_sha256=sha(job[4].encode()),input_manifest_sha256=sha(job[11].encode()))
    frozen=(record or{}).get('compiler_source_capture_snapshot')
    if frozen and frozen!=snapshot:raise RuntimeError('infrastructure_native_frozen_source_payload_changed')
    seed=dict(id=identifier,source_pair_sha256=identifier,category=source['category'],source=source['source'],source_format='drawio',format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=str(source_path.relative_to(R)),original_reference=str(reference_path.relative_to(R)),compiler_source_capture_snapshot=frozen or snapshot,model=None)
    return seed,job


def static_support(given):
    result=dict(supported=False,unit=UNIT,source_only=True,reasons=[])
    try:
        seed,_=original(None,given);result.update(supported=True,source_capture_snapshot=seed['compiler_source_capture_snapshot'],source_code_sha256=seed['source_code_sha256'],source_image_sha256=seed['source_image_sha256'])
    except Exception as error:result['reasons']=[str(error)[:2000]]
    return result


def convert(record,given,work):
    import compiler_native_source_repair_fonts_v2 as fonts
    from compiler_native_source_frontend_v2 import source_inputs,normalize_source
    from native_export_reference_v4 import repair as export
    from compiler_typed_runtime_failure_v1 import diagnose
    try:
        work=Path(work).resolve()
        if not work.is_relative_to((W/VERSION).resolve()):raise ValueError('native_source_repair_work_outside_owner')
        work.mkdir(parents=True,exist_ok=False);seed,job=original(record,given);source,code,reference=source_inputs(job);xml,page=normalize_source(code)
        original_directory=R/'clean/compiler_native_source_repair_originals_v1'/seed['id'][:2]/seed['id']
        original_directory.mkdir(parents=True,exist_ok=True)
        for field,filename,payload,digest in [('original_source_code','source.txt',code.encode(),source['code_sha256']),('original_reference','reference.bin',reference,source['image_sha256'])]:
            require_path=(R/seed[field]).resolve()
            if not require_path.is_relative_to((R/'clean').resolve()):
                target=original_directory/filename
                if target.exists():
                    if sha(target.read_bytes())!=digest:raise ValueError('native_source_original_clean_copy_changed')
                else:fonts.save(target,payload)
                seed[field]=str(target.relative_to(R))
        result=fonts.compile(xml,page,work/'physical_font_runs')
        destination=R/'clean'/VERSION/seed['id'][:2]/seed['id']/uuid.uuid4().hex;destination.mkdir(parents=True,exist_ok=False)
        fonts.save(destination/'diagram.drawio',result['xml'].encode());fonts.save(destination/'image.png',result['png']);fonts.save(destination/'source_font_runs_proof.json',fonts.raw(result['proof']))
        candidate={**seed,'code_file':str((destination/'diagram.drawio').relative_to(R)),'code_sha256':sha(result['xml'].encode()),'image_file':str((destination/'image.png').relative_to(R)),'image_sha256':sha(result['png']),'render':result['info'],'native_embedded_fonts':result['assets'],'conversion_method':VERSION,'native_source_repair_v1':dict(policy=fonts.POLICY,proof_file=str((destination/'source_font_runs_proof.json').relative_to(R)),proof_sha256=sha(fonts.raw(result['proof'])),source_capture_snapshot=seed['compiler_source_capture_snapshot']),'model_configuration':dict(external_model_calls=0)}
        fonts.save(work/'before_export_record.json',fonts.raw(candidate));attempt=export(candidate,job,work/'complete_export');fonts.save(work/'export_result.json',fonts.raw(attempt))
        if not attempt.get('ok'):return dict(ok=False,reason='native_source_repair_source_reference_export_pending',detail=attempt.get('detail'),infrastructure_failure=False,model_calls=0)
        out=attempt['record'];fonts.save(work/'candidate_record.json',fonts.raw(out));return dict(ok=True,record=out,record_file=str(work/'candidate_record.json'),model_calls=0)
    except Exception as error:
        diagnosis=diagnose(error);return dict(ok=False,reason=str(error).split(':',1)[0],detail=str(error)[:6000],error_type=type(error).__name__,infrastructure_failure=diagnosis['infrastructure_failure'],infrastructure_diagnosis=diagnosis,model_calls=0)
