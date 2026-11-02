"""Finite offline initial TikZ compile/native supervisor; default is private smoke.

Production publication requires --publish. Existing converter mains/owners and
queues are untouched. Logical stage/source/PDF keys survive implementation
version changes. A deadline creates a recovery-tier receipt, never abandonment.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from durable_sqlite import begin,commit

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';OWNER='conversion/initial_conversion_supervisor_v1'
TABLE='initial_conversion_stage_attempts_v1';RECOVERY='initial_conversion_recovery_v1';RUNS='initial_conversion_runs_v1'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
STATES={'compile':'initial_tikz_compile_v1_running','native':'initial_tikz_native_v1_running'}
INPUT_STATES={'compile':'queued','native':'tikz_source_rendered'}
TERMINAL=('validated_nonpublishing','published_pending_native','published_pending_quality','deferred_recovery_tier','stale_revision')
DRAIN=False
sha=lambda raw:hashlib.sha256(raw).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.initial.tmp');tmp.write_bytes(raw);tmp.replace(path)


def raw_json(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()


def exists(db,table):return db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone() is not None


def birth(pid):
    try:raw=Path('/proc/'+str(pid)+'/stat').read_text();return int(raw[raw.rindex(')')+2:].split()[19])
    except (OSError,ValueError,IndexError):return None


def implementation():
    scripts=Path(__file__).resolve().parent
    paths=[scripts/name for name in ['initial_conversion_supervisor_v1.py','initial_conversion_case_v1.py','initial_conversion_process_v1.py','durable_sqlite.py','sandbox_runner.py','pdf_to_native.py','svg_convert_v2.py','tikz_connectivity.py','native_worker.py','svg_batch.py']]
    paths += [R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',W/'scripts/svg_dom_pdf.js',W/'rendering_fonts/remote_render.py',W/'runtime/tectonic/tectonic',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
    pins={str(path.resolve()):sha(path.read_bytes()) for path in paths}
    return 'bounded_offline_initial_tikz_v1:'+sha(raw_json(pins))[:20],pins


def check_pins(pins):
    for path,digest in pins.items():
        if sha(Path(path).read_bytes())!=digest:raise RuntimeError('Frozen initial implementation changed: '+path)


def init(db):
    if tuple(row[1] for row in db.execute('PRAGMA table_info(jobs)'))!=JOB_COLUMNS:raise RuntimeError('Unknown jobs schema; full-column CAS review required')
    begin(db,seconds=5)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(id TEXT,stage TEXT,source_code_hash TEXT,source_image_hash TEXT,stage_input_hash TEXT,state TEXT,owner_pid INT,owner_start_ticks INT,claim_token TEXT,policy TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,stage,source_code_hash,source_image_hash,stage_input_hash))')
        db.execute('CREATE TABLE IF NOT EXISTS '+RECOVERY+'(id TEXT,stage TEXT,source_code_hash TEXT,source_image_hash TEXT,stage_input_hash TEXT,reason TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,stage,source_code_hash,source_image_hash,stage_input_hash))')
        db.execute('CREATE TABLE IF NOT EXISTS '+RUNS+'(run_id TEXT,stage TEXT,quota INT,claimed INT DEFAULT 0,policy TEXT,publish INT,created_at TEXT,PRIMARY KEY(run_id,stage))')
        commit(db,seconds=5)
    except BaseException:db.rollback();raise


def create_run(db,run_id,policy,publish,quotas):
    begin(db,seconds=5)
    try:
        for stage,quota in quotas.items():db.execute('INSERT INTO '+RUNS+' VALUES(?,?,?,0,?,?,?)',(run_id,stage,quota,policy,int(publish),now()))
        commit(db,seconds=5)
    except BaseException:db.rollback();raise


def snapshot(db,identifier):return db.execute('SELECT '+','.join(JOB_COLUMNS)+' FROM jobs WHERE id=?',(identifier,)).fetchone()
def as_job(row):return dict(zip(JOB_COLUMNS,row))


def execution_snapshot(db,identifier):
    if not exists(db,'tikz_renders'):return None
    return db.execute('SELECT id,state,record,error,updated_at FROM tikz_renders WHERE id=?',(identifier,)).fetchone()


def pointer_path(identifier):
    path=(R/'clean/drawio_unified'/identifier[:2]/identifier/'conversion.json').resolve()
    if not path.is_relative_to((R/'clean').resolve()):raise ValueError('Canonical initial metadata outside clean')
    return path


def pointer_snapshot(identifier):
    path=pointer_path(identifier);return sha(path.read_bytes()) if path.exists() else None


def outcome_snapshot(db,identifier):
    if not exists(db,'processing_outcomes_v2'):return None
    return db.execute('SELECT id,category,format,source_code_hash,source_image_hash,status,reason,record,updated_at FROM processing_outcomes_v2 WHERE id=?',(identifier,)).fetchone()


def model_busy(db,identifier):
    for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
        if not exists(db,table):continue
        cols={row[1] for row in db.execute('PRAGMA table_info('+table+')')};predicate="state='running'"+(' OR worker_pid IS NOT NULL' if 'worker_pid' in cols else '')
        if db.execute('SELECT 1 FROM '+table+' WHERE id=? AND ('+predicate+')',(identifier,)).fetchone():return True
    return False


def admission(db,row,stage):
    job=as_job(row);outcome=outcome_snapshot(db,job['id'])
    if (stage not in INPUT_STATES or job['format']!='tikz' or job['state']!=INPUT_STATES[stage] or job['worker_pid'] is not None
            or job['output_record'] is not None or not job['input_manifest'] or not outcome or outcome[5]!='pending' or model_busy(db,job['id'])):return None
    try:
        source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest'])
        if (source['pair_sha256']!=job['id'] or manifest['id']!=job['id'] or source['format']!='tikz' or manifest['source_format']!='tikz'
            or source['source']!=job['source'] or source['category']!=job['category'] or outcome[1:3]!=(job['category'],'tikz')
            or outcome[3:5]!=(source['code_sha256'],source['image_sha256'])
            or (manifest['code_sha256'],manifest['image_sha256'])!=(source['code_sha256'],source['image_sha256'])):return None
        execution=execution_snapshot(db,job['id']);stage_input=source['code_sha256']
        if stage=='native':
            if not execution or execution[1]!='tikz_source_rendered' or not execution[2]:return None
            info=json.loads(execution[2])
            if info['source_code_sha256']!=source['code_sha256'] or info['id']!=job['id']:return None
            stage_input=info['pdf_sha256']
        return (job['id'],stage,source['code_sha256'],source['image_sha256'],stage_input)
    except (ValueError,KeyError,TypeError):return None


def quota_available(db,run_id,stage):
    row=db.execute('SELECT quota,claimed FROM '+RUNS+' WHERE run_id=? AND stage=?',(run_id,stage)).fetchone()
    return bool(row and (row[0]==0 or row[1]<row[0]))


def select_candidate(db,run_id,stage,ids=()):
    if not quota_available(db,run_id,stage):return None
    restriction=' AND j.id IN ('+','.join('?' for _ in ids)+')' if ids else ''
    sql='''SELECT j.id FROM jobs j JOIN processing_outcomes_v2 o ON o.id=j.id
      WHERE j.format='tikz' AND j.state=? AND j.worker_pid IS NULL AND j.output_record IS NULL AND j.input_manifest IS NOT NULL AND o.status='pending'
      AND NOT EXISTS(SELECT 1 FROM '''+TABLE+''' a WHERE a.id=j.id AND a.stage=? AND a.source_code_hash=o.source_code_hash AND a.source_image_hash=o.source_image_hash
        AND a.stage_input_hash='''+("o.source_code_hash" if stage=='compile' else "(SELECT json_extract(r.record,'$.pdf_sha256') FROM tikz_renders r WHERE r.id=j.id)")+')'+restriction+' ORDER BY j.id LIMIT 128'
    for identifier, in db.execute(sql,[INPUT_STATES[stage],stage,*ids]).fetchall():
        row=snapshot(db,identifier)
        if row and admission(db,row,stage):return tuple(row)
    return None


def owner_valid(context):
    if context is None:return True  # Direct isolated state tests have no launcher.
    try:
        path=Path(context['file']);raw=path.read_bytes();owner=json.loads(raw)
        return (sha(raw)==context['sha256'] and owner['run_id']==context['run_id'] and owner['policy']==context['policy']
            and owner['pid']==context['pid'] and owner['pid_start_ticks']==context['pid_start_ticks'] and birth(context['pid'])==context['pid_start_ticks'])
    except (OSError,ValueError,KeyError,TypeError):return False


def claim(db,prior,stage,run_id,policy,pid=None,pid_start=None,owner_context=None):
    pid=pid or os.getpid();pid_start=birth(pid) if pid_start is None else pid_start
    if pid_start is None:raise RuntimeError('Cannot prove slot process birth identity')
    begin(db,seconds=5)
    try:
        key=admission(db,prior,stage)
        if (not owner_valid(owner_context) or snapshot(db,prior[0])!=prior or not key or not quota_available(db,run_id,stage)
                or db.execute('SELECT 1 FROM '+TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone()):db.rollback();return None
        token=uuid.uuid4().hex;stamp=now();job=as_job(prior);owned=list(prior);owned[5]=STATES[stage];owned[7]=job['attempts']+1;owned[8]=stamp;owned[12]=pid
        current={'id':job['id'],'key':list(key),'stage':stage,'run_id':run_id,'policy':policy,'pid':pid,'pid_start_ticks':pid_start,'token':token,
            'prior_snapshot':list(prior),'owned_snapshot':owned,'prior_execution':list(execution_snapshot(db,job['id'])) if execution_snapshot(db,job['id']) else None,
            'main_owner_context':owner_context,'prior_outcome':list(outcome_snapshot(db,job['id'])),'prior_conversion_metadata_sha256':pointer_snapshot(job['id']),'claimed_at':stamp,'accepted':False,'model_calls':0}
        db.execute('INSERT INTO '+TABLE+' VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(*key,'running',pid,pid_start,token,policy,json.dumps(current),stamp))
        db.execute('UPDATE '+RUNS+' SET claimed=claimed+1 WHERE run_id=? AND stage=?',(run_id,stage))
        db.execute('UPDATE jobs SET state=?,attempts=?,updated_at=?,worker_pid=? WHERE id=?',(STATES[stage],owned[7],stamp,pid,job['id']));commit(db,seconds=5);return current
    except BaseException:db.rollback();raise


def source_files(claim_record):
    job=as_job(claim_record['prior_snapshot']);source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest']);checks={}
    for field,digest in [('source_code','code_sha256'),('reference_image','image_sha256')]:
        path=(R/manifest[field]).resolve()
        if not path.is_relative_to(R.resolve()) or sha(path.read_bytes())!=source[digest]:raise ValueError('Authoritative initial source file changed: '+field)
        checks[field]={'file':manifest[field],'sha256':source[digest]}
    return checks


def _owned(path,work=None):
    path=(R/path).resolve()
    if not path.is_relative_to((R/OWNER).resolve()) or work is not None and not path.is_relative_to(Path(work).resolve()):raise ValueError('Initial artifact outside owned attempt')
    return path


def _checked(entry,work):
    raw=_owned(entry['file'],work).read_bytes()
    if sha(raw)!=entry['sha256']:raise ValueError('Initial proposal artifact hash changed')
    return raw


def validate_result(current,result,work):
    if (result.get('id'),result.get('stage'),result.get('code_sha256'),result.get('image_sha256'),result.get('stage_input_hash'))!=(current['id'],current['stage'],*current['key'][2:]):raise ValueError('Isolated stage result/source identity mismatch')
    if result.get('partial_artifact_inventory'):_checked(result['partial_artifact_inventory'],work)
    if not result.get('ok'):return None
    source_files(current)
    record=json.loads(_checked(result['record_file'],work))
    if record!=result['record'] or record['id']!=current['id'] or record['source_code_sha256']!=current['key'][2]:raise ValueError('Stage candidate record identity mismatch')
    for entry in result['artifacts'].values():_checked(entry,work)
    if current['stage']=='compile':
        if record.get('source_image_sha256')!=current['key'][3] or _checked({'file':record['pdf_file'],'sha256':record['pdf_sha256']},work)[:4]!=b'%PDF':raise ValueError('Compiled PDF source/hash mismatch')
    else:
        if record['source_pair_sha256']!=current['id'] or record['source_image_sha256']!=current['key'][3] or record.get('model') is not None or not record['quality_state'].startswith('pending_') or record.get('automatic_quality_policy'):raise ValueError('Initial native candidate cannot be accepted/model-generated')
        if record.get('source_format')!='tikz' or record.get('format')!='drawio' or record.get('source_record')!=json.loads(current['prior_snapshot'][4]) or record.get('source_render_pdf_sha256')!=current['key'][4]:raise ValueError('Native proposal lost the original source/PDF identity')
        for locator,entry in result['publish_files'].items():
            if not (R/locator).resolve().is_relative_to((R/'clean').resolve()):raise ValueError('Native target outside clean')
            _checked(entry,work)
        for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_svg','source_render_svg_sha256')]:
            if result['publish_files'][record[field]]['sha256']!=record[digest]:raise ValueError('Native candidate source/payload binding mismatch')
    return record


def _restore(db,prior):db.execute('UPDATE jobs SET '+','.join(name+'=?' for name in JOB_COLUMNS[1:])+' WHERE id=?',(*prior[1:],prior[0]))


def publish_native(current,result,record,work):
    for locator,entry in result['publish_files'].items():
        path=(R/locator).resolve();raw=_checked(entry,work);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=raw:raise ValueError('Immutable initial clean candidate differs')
        else:
            with path.open('xb') as stream:stream.write(raw)
    pointer=pointer_path(current['id']);before=pointer.read_bytes() if pointer.exists() else None
    atomic(Path(work)/'publication_intent.json',raw_json({'token':current['token'],'id':current['id'],'source_code_sha256':current['key'][2],'source_image_sha256':current['key'][3],'record':record,'accepted':False}))
    if before is not None:atomic(Path(work)/'prior_conversion_metadata.bin',before)
    replacement=raw_json(record);atomic(pointer,replacement);return pointer,before,replacement


def finish(db,current,result,work,publish=False,artifact_writer=publish_native,deadline=None):
    key=tuple(current['key']);prior=tuple(current['prior_snapshot']);owned=tuple(current['owned_snapshot']);pointer=None;before=replacement=None
    record=validate_result(current,result,work)
    begin(db,seconds=5)
    try:
        owner=db.execute('SELECT state,owner_pid,owner_start_ticks,claim_token FROM '+TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone()
        expected=('running',current['pid'],current['pid_start_ticks'],current['token'])
        if owner!=expected or snapshot(db,current['id'])!=owned or birth(current['pid'])!=current['pid_start_ticks']:
            report={**result,'state':'stale_revision','published':False,'accepted':False,'model_calls':0}
        elif (not owner_valid(current.get('main_owner_context')) or outcome_snapshot(db,current['id'])!=tuple(current['prior_outcome']) or execution_snapshot(db,current['id'])!=(tuple(current['prior_execution']) if current['prior_execution'] else None) or model_busy(db,current['id']) or current['stage']=='native' and pointer_snapshot(current['id'])!=current.get('prior_conversion_metadata_sha256')):
            _restore(db,prior);report={**result,'state':'stale_revision','published':False,'accepted':False,'reason':'Source/outcome/execution/model admission changed'}
        elif not result.get('ok') or deadline is not None and time.monotonic()>=deadline:
            if result.get('ok'):result={**result,'ok':False,'reason':'whole_case_deadline_before_publication','prepared_proposal_retained':True}
            reason=result.get('reason','typed_runtime_failure');report={**result,'state':'deferred_recovery_tier','published':False,'accepted':False,'model_calls':0,'larger_or_recovery_tier_required':True}
            db.execute('INSERT OR REPLACE INTO '+RECOVERY+' VALUES(?,?,?,?,?,?,?,?)',(*key,reason,json.dumps({'claim':current,'result':report,'work':str(Path(work).relative_to(R))}),now()))
            db.execute('UPDATE jobs SET state=?,worker_pid=NULL,error=?,updated_at=? WHERE id=?',('initial_conversion_deferred_v1','Initial '+current['stage']+' deferred to recovery/larger tier: '+reason,now(),current['id']))
        elif not publish:
            _restore(db,prior);report={**result,'state':'validated_nonpublishing','published':False,'accepted':False,'model_calls':0}
        elif current['stage']=='compile':
            db.execute('INSERT OR REPLACE INTO tikz_renders VALUES(?,?,?,?,?)',(current['id'],'tikz_source_rendered',json.dumps(record),None,now()))
            db.execute('UPDATE jobs SET state=?,worker_pid=NULL,error=NULL,updated_at=? WHERE id=?',('tikz_source_rendered',now(),current['id']))
            report={**result,'state':'published_pending_native','published':True,'accepted':False,'model_calls':0}
        else:
            pointer=pointer_path(current['id']);before=pointer.read_bytes() if pointer.exists() else None;replacement=raw_json(record)
            artifact_writer(current,result,record,work)
            if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('Initial publication deadline exceeded; frozen proposal retained')
            target='needs_quality_repair' if result['requires_quality_repair'] else 'rendered'
            db.execute('UPDATE jobs SET state=?,output_record=?,worker_pid=NULL,error=?,updated_at=? WHERE id=?',(target,json.dumps(record,ensure_ascii=False),'Pending full native/source quality validation',now(),current['id']))
            report={**result,'state':'published_pending_quality','published':True,'accepted':False,'model_calls':0}
        if owner==expected:db.execute('UPDATE '+TABLE+' SET state=?,record=?,updated_at=? WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',(report['state'],json.dumps(report,ensure_ascii=False),now(),*key))
        commit(db,seconds=5)
    except BaseException:
        db.rollback()
        if pointer is not None and replacement is not None and snapshot(db,current['id'])==owned and pointer.exists() and pointer.read_bytes()==replacement:
            if before is None:pointer.unlink()
            else:atomic(pointer,before)
        raise
    try:atomic(Path(work)/'supervisor_result.json',raw_json(report))
    except OSError:pass
    return report


def make_request(current,work,pins,timeout,max_side):
    job=as_job(current['prior_snapshot']);request={'id':current['id'],'stage':current['stage'],'stage_input_hash':current['key'][4],'source':json.loads(job['input_record']),'manifest':json.loads(job['input_manifest']),
        'execution':json.loads(current['prior_execution'][2]) if current['stage']=='native' else None,'pins':pins,'phase_timeout_seconds':min(150,timeout),'max_side':max_side,
        'proposed_clean_directory':str(Path('clean/drawio_unified')/current['id'][:2]/current['id']),'artifact_version':current['token'][:24]}
    atomic(Path(work)/'request.json',raw_json(request));return request


def partial_inventory(work):
    rows=[];hashed=0
    for path in sorted(Path(work).rglob('*')):
        if not path.is_file():continue
        if len(rows)>=256:break
        size=path.stat().st_size;row={'file':str(path.relative_to(R)),'bytes':size}
        if size<=8*1024**2 and hashed+size<=64*1024**2:row['sha256']=sha(path.read_bytes());hashed+=size
        else:row['sha256']=None;row['reason']='retained_on_remote_hash_budget_exceeded'
        rows.append(row)
    path=Path(work)/'partial_artifacts.json';atomic(path,raw_json({'files':rows,'total_hashed_bytes':hashed,'artifacts_deleted':False}))
    return {'file':str(path.relative_to(R)),'sha256':sha(path.read_bytes())}


def run_case(current,pins,timeout,max_side,deadline=None):
    check_pins(pins);work=R/OWNER/current['id']/current['stage']/current['key'][4]/current['token'];work.mkdir(parents=True,exist_ok=False)
    request=make_request(current,work,pins,timeout,max_side)
    from initial_conversion_process_v1 import run
    env={key:os.environ[key] for key in ['PATH','HOME','LANG','LC_ALL','TMPDIR'] if key in os.environ};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=str(R/'env'))
    process=run([sys.executable,str(Path(__file__).with_name('initial_conversion_case_v1.py')),str(work/'request.json')],work,max(.001,deadline-time.monotonic()) if deadline is not None else timeout,env)
    atomic(work/'isolation.json',raw_json(process));check_pins(pins)
    if not process.get('cleanup_complete'):reason='owned_subtree_cleanup_incomplete'
    elif process.get('deadline_exceeded'):reason='whole_case_deadline_requires_recovery_tier'
    elif not process.get('ok'):reason='isolated_case_process_failure'
    elif not (work/'result.json').is_file():reason='isolated_case_missing_result'
    else:
        result=json.loads((work/'result.json').read_text());result['partial_artifact_inventory']=partial_inventory(work);return work,result,process
    result={'ok':False,'state':'deferred_recovery_tier','reason':reason,'id':current['id'],'stage':current['stage'],'code_sha256':current['key'][2],'image_sha256':current['key'][3],'stage_input_hash':current['key'][4],'accepted':False,'model_calls':0,'isolation':process}
    result['partial_artifact_inventory']=partial_inventory(work)
    return work,result,process


def draining(control):
    if DRAIN:return True
    if not Path(control).exists():return False
    try:return json.loads(Path(control).read_text()).get('drain') is True
    except (OSError,ValueError,TypeError,AttributeError):return True


def request_drain(*_):
    global DRAIN
    DRAIN=True


def slot(args):
    signal.signal(signal.SIGUSR1,request_drain);db=sqlite3.connect(args.db,timeout=.25);metadata=json.loads(Path(args.run_metadata).read_text());pins=metadata['pins'];counts={};processed=0
    owner_file=Path(metadata['owner_file']);context={'file':str(owner_file),'sha256':sha(owner_file.read_bytes()),**{key:metadata[key] for key in ['run_id','policy','pid','pid_start_ticks']}}
    while not draining(args.control):
        check_pins(pins)
        if not owner_valid(context) or os.getppid()!=metadata['pid']:break
        prior=select_candidate(db,args.run_id,args.stage,metadata.get('authorized_sample_ids',()))
        if prior is None:
            if not args.watch or not quota_available(db,args.run_id,args.stage):break
            time.sleep(5);continue
        current=claim(db,prior,args.stage,args.run_id,metadata['policy'],owner_context=context)
        if current is None:continue
        work=None;deadline=time.monotonic()+args.timeout
        try:
            work,result,isolation=run_case(current,pins,args.timeout,args.max_side,deadline=deadline)
            if not isolation.get('cleanup_complete'):raise RuntimeError('New owned process subtree not fully reaped; halt slot for recovery')
            try:report=finish(db,current,result,work,args.publish,deadline=deadline)
            except TimeoutError:
                deferred={**result,'ok':False,'state':'deferred_recovery_tier','reason':'publication_phase_deadline','prepared_proposal_retained':True}
                report=finish(db,current,deferred,work,args.publish)
        except Exception as exc:
            if db.in_transaction:db.rollback()
            # The new owner remains diagnosable; never guess at foreign state.
            if work is None:work=R/OWNER/current['id']/current['stage']/current['key'][4]/current['token'];work.mkdir(parents=True,exist_ok=True)
            atomic(work/'slot_recovery_required.json',raw_json({'claim':current,'error_type':type(exc).__name__,'error':str(exc)[:2500],'accepted':False,'model_calls':0}));raise
        processed+=1;counts[report['state']]=counts.get(report['state'],0)+1
        event={'at':now(),'id':current['id'],'stage':args.stage,'state':report['state'],'reason':report.get('reason'),'seconds':report.get('seconds'),'code_sha256':report.get('record',{}).get('code_sha256'),'pdf_sha256':report.get('record',{}).get('pdf_sha256'),'published':report['published'],'accepted':False,'model_calls':0}
        fd=os.open(metadata['events_file'],os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
        try:os.write(fd,(json.dumps(event)+'\n').encode())
        finally:os.close(fd)
    db.close();return {'pid':os.getpid(),'stage':args.stage,'processed':processed,'counts':counts}


def bootstrap_private(canonical,destination,limits,ids=()):
    if Path(destination).exists():raise ValueError('Private smoke DB must be new')
    reader=sqlite3.connect('file:'+str(canonical)+'?mode=ro',uri=True,timeout=2);private=sqlite3.connect(destination,timeout=.25)
    for table in ('jobs','processing_outcomes_v2','tikz_renders'):
        ddl=reader.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0];private.execute(ddl)
    selected=[]
    for stage,limit in limits.items():
        # End-of-queue samples avoid racing the existing lexicographic workers.
        restriction=' AND id IN ('+','.join('?' for _ in ids)+')' if ids else ''
        for identifier, in reader.execute('SELECT id FROM jobs WHERE format=? AND state=? AND worker_pid IS NULL AND output_record IS NULL'+restriction+' ORDER BY id DESC',['tikz',INPUT_STATES[stage],*ids]):
            row=snapshot(reader,identifier)
            if not admission(reader,row,stage):continue
            private.execute('INSERT INTO jobs VALUES('+','.join('?' for _ in row)+')',row);outcome=outcome_snapshot(reader,identifier);private.execute('INSERT INTO processing_outcomes_v2 VALUES('+','.join('?' for _ in outcome)+')',outcome);execution=execution_snapshot(reader,identifier)
            if execution:private.execute('INSERT INTO tikz_renders VALUES(?,?,?,?,?)',execution)
            selected.append({'id':identifier,'stage':stage,'canonical_snapshot_sha256':sha(raw_json(row))})
            if sum(x['stage']==stage for x in selected)>=limit:break
    private.commit();scope=dict(reader.execute('SELECT format,count(*) FROM jobs GROUP BY format'));reader.close();private.close()
    return {'selected':selected,'canonical_total':sum(scope.values()),'canonical_input_format_counts':scope,'canonical_opened_read_only':True}


def main(args):
    signal.signal(signal.SIGUSR1,request_drain);policy,pins=implementation();run_id=uuid.uuid4().hex;work=R/OWNER/'runs'/run_id;work.mkdir(parents=True,exist_ok=False)
    lock=(W/'initial_conversion_supervisor_v1.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.publish:database=W/'jobs.sqlite';bootstrap=None
    else:database=work/'private_jobs.sqlite';bootstrap=bootstrap_private(W/'jobs.sqlite',database,{'compile':args.compile_limit,'native':args.native_limit},args.ids)
    db=sqlite3.connect(database,timeout=.25);init(db);quotas={'compile':0 if args.watch else args.compile_limit,'native':0 if args.watch else args.native_limit};create_run(db,run_id,policy,args.publish,quotas);db.close()
    control=(W/'initial_conversion_supervisor_v1_control.json') if args.publish else (work/'control.json');events=work/'events.jsonl';metadata={'pid':os.getpid(),'pid_start_ticks':birth(os.getpid()),'at':now(),'run_id':run_id,'policy':policy,'pins':pins,'publish':args.publish,'private_smoke':not args.publish,'database':str(database),'owner_file':str(W/'initial_conversion_supervisor_v1_owner.json'),'control':str(control),'events_file':str(events),'bootstrap':bootstrap,'authorized_sample_ids':args.ids,'model_calls':0,'accepted':0}
    meta=work/'run.json';atomic(meta,raw_json(metadata));atomic(W/'initial_conversion_supervisor_v1_owner.json',raw_json(metadata));children=[]
    for stage,workers,deadline in [('compile',args.compile_workers,args.compile_timeout),('native',args.native_workers,args.native_timeout)]:
        for index in range(workers):
            output=(work/(stage+'.'+str(index)+'.log')).open('wb');cmd=[sys.executable,str(Path(__file__).resolve()),'--slot','--db',str(database),'--run-id',run_id,'--run-metadata',str(meta),'--control',str(control),'--stage',stage,'--timeout',str(deadline),'--max-side',str(args.max_side)]
            if args.publish:cmd+=['--publish']
            if args.watch:cmd+=['--watch']
            child=subprocess.Popen(cmd,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'});children.append((child,output))
    while any(child.poll() is None for child,_ in children):
        if DRAIN:atomic(control,raw_json({'drain':True,'requested_at':now(),'scope':'Finish current bounded case; no new claims'}))
        time.sleep(.5)
    outcomes=[]
    for child,output in children:output.close();outcomes.append({'pid':child.pid,'returncode':child.returncode})
    db=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=2);states=[dict(zip(['stage','state','count'],row)) for row in db.execute('SELECT stage,state,count(*) FROM '+TABLE+' GROUP BY stage,state')];db.close()
    summary={**{key:metadata[key] for key in ['run_id','policy','publish','private_smoke','database','bootstrap']},'at':now(),'slot_processes':outcomes,'stage_states':states,'events_file':str(events),'model_calls':0,'accepted':0,'production_canonical_claimed':args.publish}
    atomic(work/'summary.json',raw_json(summary));atomic(W/'initial_conversion_supervisor_v1_summary.json',raw_json(summary));print(json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--publish',action='store_true');parser.add_argument('--id',dest='ids',action='append',default=[]);parser.add_argument('--watch',action='store_true');parser.add_argument('--compile-limit',type=int,default=2);parser.add_argument('--native-limit',type=int,default=2);parser.add_argument('--compile-workers',type=int,default=1);parser.add_argument('--native-workers',type=int,default=1);parser.add_argument('--compile-timeout',type=float,default=240);parser.add_argument('--native-timeout',type=float,default=180);parser.add_argument('--max-side',type=int,default=8192)
    parser.add_argument('--slot',action='store_true');parser.add_argument('--db');parser.add_argument('--run-id');parser.add_argument('--run-metadata');parser.add_argument('--control');parser.add_argument('--stage',choices=['compile','native']);parser.add_argument('--timeout',type=float)
    args=parser.parse_args()
    if args.slot:print(json.dumps(slot(args)))
    else:
        if not 1<=args.max_side<=16384:parser.error('max-side must be 1..16384; oversized pages are deferred, never scaled')
        if args.watch and not args.publish:parser.error('Watch requires explicit production --publish; smoke is always finite')
        if any(v<1 or v>64 for v in [args.compile_limit,args.native_limit]) or any(v<1 or v>16 for v in [args.compile_workers,args.native_workers]) or any(not math.isfinite(v) or v<1 or v>3600 for v in [args.compile_timeout,args.native_timeout]):parser.error('Finite limits 1..64, workers 1..16, deadline 1..3600 required')
        main(args)
