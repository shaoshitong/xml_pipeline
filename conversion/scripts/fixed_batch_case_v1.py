"""One bounded, model-free initial-screen case. The canonical jobs DB is read-only."""
import argparse, hashlib, importlib, json, os, sqlite3, sys, traceback, uuid
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029'); W=R/'conversion'
def sha(blob): return hashlib.sha256(blob).hexdigest()
def raw(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
def save(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
def checked(logical,digest):
    path=R/logical; target=path.resolve(strict=True)
    if not target.is_relative_to(R.resolve()):raise ValueError('asset_outside_root:'+str(logical))
    blob=path.read_bytes()
    if sha(blob)!=digest:raise ValueError('asset_sha256_mismatch:'+str(logical))
    return blob
def bootstrap_private(job,path,source_db):
    d=sqlite3.connect(path)
    for table in ['jobs','python_renders','tikz_renders']:
        schema=source_db.execute('select sql from sqlite_master where type="table" and name=?',(table,)).fetchone()
        if not schema:continue
        d.execute(schema[0]); cols=[r[1] for r in source_db.execute('pragma table_info('+table+')')]
        rows=[job] if table=='jobs' else source_db.execute('select * from '+table+' where id=?',(job[0],)).fetchall()
        for row in rows:d.execute('insert into '+table+' values('+','.join('?' for _ in cols)+')',row)
    d.commit();d.close()
def tikz_convert(job,work,execution):
    import initial_conversion_case_v1 as c
    import initial_conversion_case_v1b as adapter
    # Reuse the frozen cache-only compiler and PDF/vector converter. Only its
    # newly-owned output namespace changes, within this isolated child process.
    c.OWNER=str(work.relative_to(R));c.write_json=adapter.write_json
    source=json.loads(job[4]);manifest=json.loads(job[11])
    request={'id':job[0],'source':source,'manifest':manifest,'phase_timeout_seconds':150,'max_side':8192,
             'proposed_clean_directory':str(Path('clean/fixed_batch_candidates_v1')/work.parent.name/job[0]),
             'artifact_version':uuid.uuid4().hex[:24]}
    if execution:
        try:checked(execution['pdf_file'],execution['pdf_sha256'])
        except (OSError,ValueError,KeyError):execution=None
    if not execution:
        stage=work/'compile';stage.mkdir();request['stage']='compile'
        execution=c.compile_case(request,stage)['record']
    stage=work/'native';stage.mkdir();request.update(stage='native',execution=execution)
    result=c.native_case(request,stage)
    for target,entry in result['publish_files'].items():
        if not (R/target).resolve().is_relative_to((R/'clean').resolve()):raise ValueError('candidate_target_outside_clean')
        save(R/target,checked(entry['file'],entry['sha256']))
    return result['record']
def prepare_originals(record,source,manifest,work):
    from native_worker import pair
    if record.get('original_reference') and record.get('original_source_code'):
        image=checked(record['original_reference'],source['image_sha256']);code=checked(record['original_source_code'],source['code_sha256'])
        if all((R/record[k]).resolve().is_relative_to((R/'clean').resolve()) for k in ['original_reference','original_source_code']):return record
    elif manifest:
        image=checked(manifest['reference_image'],source['image_sha256']);code=checked(manifest['source_code'],source['code_sha256'])
    else:image,text=pair(source);code=text.encode()
    dest=R/'clean/fixed_batch_originals_v1'/source['pair_sha256'][:2]/source['pair_sha256']
    save(dest/'reference.bin',image);save(dest/'source.txt',code)
    return {**record,'original_reference':str((dest/'reference.bin').relative_to(R)),'original_source_code':str((dest/'source.txt').relative_to(R))}
def run(request_path):
    request=json.loads(Path(request_path).read_bytes());work=Path(request['work']).resolve();identifier=request['id'];stage='input'
    if not work.is_relative_to((W/'fixed_batch_v1').resolve()):raise ValueError('case_work_outside_owner')
    result={'id':identifier,'seq':request['seq'],'source_code_sha256':request['source']['code_sha256'],
            'source_image_sha256':request['source']['image_sha256'],'model_calls':0,'canonical_jobs_written':False}
    try:
        for path,digest in request['pins'].items():
            if sha(Path(path).read_bytes())!=digest:raise RuntimeError('infrastructure_pinned_implementation_changed:'+path)
        d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
        try:
            job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
            if not job:raise ValueError('missing_authoritative_job')
            source=json.loads(job[4]);manifest=json.loads(job[11]) if job[11] else None
            if source!=request['source'] or (job[1],job[2],job[3])!=(source['category'],source['format'],source['source']):raise ValueError('authoritative_input_identity_changed')
            if manifest:
                checked(manifest['source_code'],source['code_sha256']);checked(manifest['reference_image'],source['image_sha256'])
            else:
                from native_worker import pair
                pair(source)
            private=work/'case.sqlite';bootstrap_private(job,private,d)
            compiled=d.execute('select record from tikz_renders where id=? and state="tikz_source_rendered"',(identifier,)).fetchone() if job[2]=='tikz' else None
        finally:d.close()
        record=json.loads(job[9]) if job[9] else None
        if not record:
            stage='conversion'
            if job[2]=='tikz':record=tikz_convert(job,work,json.loads(compiled[0]) if compiled and compiled[0] else None)
            else:
                from fixed_batch_conversion_adapters_v1 import convert
                converted=convert(job,private,work)
                if not converted.get('ok'):raise ValueError('conversion_failed:'+json.dumps(converted,ensure_ascii=False)[:5000])
                record=converted['record']
        record=prepare_originals(record,source,manifest,work)
        for k,digest in [('code_file','code_sha256'),('image_file','image_sha256')]:checked(record[k],record[digest])
        stage='quality'
        import auto_quality_batch_v4b as qa
        import clip_canvas_render_v4b as clip
        qa.W=work/'qa_evidence';clip.OWNER=str((work/'clip_evidence').relative_to(R))
        import html_actual_text_alignment as glyph
        original_capture=glyph.capture_source
        glyph.capture_source=lambda record,ignored,*a,**kw:original_capture(record,work/'html_capture'/uuid.uuid4().hex,*a,**kw)
        item=(identifier,job[5],json.dumps(record,ensure_ascii=False),job[4],job[6])
        _,report,out,qa_work=qa.verify(item)
        result.update(quality_report=str((Path(qa_work)/'audit.json').relative_to(R)),quality_policy=qa.POLICY,
                      quality_failures=report.get('failures',[]),candidate_code_sha256=record['code_sha256'],candidate_image_sha256=record['image_sha256'])
        if not out or report.get('state')!='qualified':
            result.update(status='abandoned',phase='quality',reason='initial_screen_quality_failed',
                          detail=report.get('failures') or ['quality_did_not_return_a_qualified_candidate'],
                          infrastructure_failure=report.get('exception_type') in ('ImportError','ModuleNotFoundError'))
        else:
            stage='publication'
            fresh=(Path(qa_work)/'fresh.png').read_bytes()
            if sha(fresh)!=out['image_sha256']:raise ValueError('fresh_qualified_png_hash_mismatch')
            save(R/out['image_file'],fresh)
            from qualified_index_v4 import manifest_row,require_source
            require_source(out,source);compact,_=manifest_row(out,R)
            result.update(status='qualified',phase='quality',reason='initial_screen_passed',manifest=compact)
        # All imports/converters operate on per-case files; source jobs remain
        # immutable, and the run's own ledger is the only new outcome authority.
        d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
        try:
            if d.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job:raise RuntimeError('infrastructure_canonical_job_changed_during_case')
        finally:d.close()
    except Exception as e:
        text=str(e);fatal=text.startswith('infrastructure_') or isinstance(e,(ImportError,ModuleNotFoundError))
        result.update(status='abandoned',phase=stage,reason='initial_screen_'+stage+'_failed',error_type=type(e).__name__,detail=text[:8000],infrastructure_failure=fatal)
        save(work/'traceback.txt',traceback.format_exc().encode())
    save(work/'result.json',raw(result));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('request');a=p.parse_args();run(a.request)
