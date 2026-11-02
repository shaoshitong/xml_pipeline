"""Bounded DB-admission hardening for the frozen initial TikZ conversion helpers.

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

from bounded_sqlite_transaction_v1 import BusyBudget,BusyBudgetExceeded,is_busy

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';OWNER='conversion/initial_conversion_supervisor_v1'
TABLE='initial_conversion_stage_attempts_v1';RECOVERY='initial_conversion_recovery_v1';RUNS='initial_conversion_runs_v1'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
STATES={'compile':'initial_tikz_compile_v1b_running','native':'initial_tikz_native_v1b_running'}
INPUT_STATES={'compile':'queued','native':'tikz_source_rendered'}
TERMINAL=('validated_nonpublishing','published_pending_native','published_pending_quality','deferred_recovery_tier','stale_revision')
DRAIN=False
sha=lambda raw:hashlib.sha256(raw).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,raw):
    path=Path(path);missing=[];ancestor=path.parent
    while not ancestor.exists():missing.append(ancestor);ancestor=ancestor.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True);fd=os.open(str(directory.parent),os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(fd)
        finally:os.close(fd)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.initial.tmp')
    try:
        with tmp.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        tmp.replace(path)
        directory=os.open(str(path.parent),os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if tmp.exists():tmp.unlink()


def raw_json(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()


def exists(db,table):return db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone() is not None


def birth(pid):
    try:raw=Path('/proc/'+str(pid)+'/stat').read_text();return int(raw[raw.rindex(')')+2:].split()[19])
    except (OSError,ValueError,IndexError):return None


def implementation():
    scripts=Path(__file__).resolve().parent
    paths=[scripts/name for name in ['initial_conversion_supervisor_v1b.py','initial_conversion_supervisor_v1.py','bounded_sqlite_transaction_v1.py','initial_conversion_case_v1b.py','initial_conversion_case_v1.py','initial_conversion_process_v1.py','durable_sqlite.py','sandbox_runner.py','pdf_to_native.py','svg_convert_v2.py','tikz_connectivity.py','native_worker.py','svg_batch.py']]
    paths += [R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',W/'scripts/svg_dom_pdf.js',W/'rendering_fonts/remote_render.py',W/'runtime/tectonic/tectonic',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
    pins={str(path.resolve()):sha(path.read_bytes()) for path in paths}
    return 'bounded_offline_initial_tikz_v1b:'+sha(raw_json(pins))[:20],pins


def check_pins(pins):
    for path,digest in pins.items():
        if sha(Path(path).read_bytes())!=digest:raise RuntimeError('Frozen initial implementation changed: '+path)


def init(db,admission_timeout=60):
    if tuple(row[1] for row in db.execute('PRAGMA table_info(jobs)'))!=JOB_COLUMNS:raise RuntimeError('Unknown jobs schema; full-column CAS review required')
    budget=BusyBudget(admission_timeout,5)
    while True:
        try:
            budget.begin(db)
            db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(id TEXT,stage TEXT,source_code_hash TEXT,source_image_hash TEXT,stage_input_hash TEXT,state TEXT,owner_pid INT,owner_start_ticks INT,claim_token TEXT,policy TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,stage,source_code_hash,source_image_hash,stage_input_hash))')
            db.execute('CREATE TABLE IF NOT EXISTS '+RECOVERY+'(id TEXT,stage TEXT,source_code_hash TEXT,source_image_hash TEXT,stage_input_hash TEXT,reason TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,stage,source_code_hash,source_image_hash,stage_input_hash))')
            db.execute('CREATE TABLE IF NOT EXISTS '+RUNS+'(run_id TEXT,stage TEXT,quota INT,claimed INT DEFAULT 0,policy TEXT,publish INT,created_at TEXT,PRIMARY KEY(run_id,stage))')
            budget.commit(db);return budget.diagnostics()
        except BaseException as error:
            if db.in_transaction:db.rollback()
            if not is_busy(error):raise
            budget.retry(error)  # Only idempotent CREATE IF NOT EXISTS is replayed.


def create_run(db,run_id,policy,publish,quotas,admission_timeout=60):
    budget=BusyBudget(admission_timeout,5);expected=sorted((stage,quota,policy,int(publish)) for stage,quota in quotas.items())
    while True:
        try:
            budget.begin(db)
            receipt=sorted(db.execute('SELECT stage,quota,policy,publish FROM '+RUNS+' WHERE run_id=?',(run_id,)).fetchall())
            if receipt:
                if receipt!=expected:raise RuntimeError('Run nonce receipt differs; refusing replay')
                db.rollback();return budget.diagnostics()
            for stage,quota in quotas.items():db.execute('INSERT INTO '+RUNS+' VALUES(?,?,?,0,?,?,?)',(run_id,stage,quota,policy,int(publish),now()))
            budget.commit(db);return budget.diagnostics()
        except BaseException as error:
            if db.in_transaction:db.rollback()
            if not is_busy(error):raise
            # Same UUID/parameters are probed inside the next transaction.
            budget.retry(error)


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


class AdmissionDeferred(TimeoutError):
    def __init__(self,reason,intent_file,diagnostics=None):
        self.reason=reason;self.intent_file=str(intent_file);self.diagnostics=diagnostics or {}
        super().__init__(reason+'; durable intent='+str(intent_file))


def save_intent(kind,payload,intent_dir=None,token=None):
    directory=Path(intent_dir) if intent_dir is not None else R/OWNER/'database_intents_v1b'
    directory.mkdir(parents=True,exist_ok=True);path=directory/(kind+'.'+(token or uuid.uuid4().hex)+'.json')
    atomic(path,raw_json({'version':1,'kind':kind,'at':now(),'model_calls':0,**payload}));return path


def _row_receipt(db,key,token):
    row=db.execute('SELECT state,owner_pid,owner_start_ticks,claim_token,record FROM '+TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',tuple(key)).fetchone()
    return row if row and row[3]==token else None


def claim(db,prior,stage,run_id,policy,pid=None,pid_start=None,owner_context=None,admission_timeout=30,busy_step_seconds=5,intent_dir=None):
    if db.in_transaction:raise RuntimeError('Claim cannot borrow a foreign/open transaction')
    pid=pid or os.getpid();pid_start=birth(pid) if pid_start is None else pid_start
    if pid_start is None:raise RuntimeError('Cannot prove slot process birth identity')
    budget=BusyBudget(admission_timeout,busy_step_seconds);token=uuid.uuid4().hex;current=None;original_context=None
    while True:
        try:
            budget.begin(db)
            try:
                key=admission(db,prior,stage)
                if (not owner_valid(owner_context) or snapshot(db,prior[0])!=prior or not key or not quota_available(db,run_id,stage)):
                    db.rollback();return None
                row=db.execute('SELECT claim_token FROM '+TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone()
                if row:db.rollback();return None
                context=(outcome_snapshot(db,prior[0]),execution_snapshot(db,prior[0]),pointer_snapshot(prior[0]))
                if original_context is not None and context!=original_context:db.rollback();return None
                original_context=context;stamp=now();job=as_job(prior);owned=list(prior);owned[5]=STATES[stage];owned[7]=job['attempts']+1;owned[8]=stamp;owned[12]=pid
                current={'id':job['id'],'key':list(key),'stage':stage,'run_id':run_id,'policy':policy,'pid':pid,'pid_start_ticks':pid_start,'token':token,
                    'prior_snapshot':list(prior),'owned_snapshot':owned,'prior_execution':list(context[1]) if context[1] else None,
                    'main_owner_context':owner_context,'prior_outcome':list(context[0]),'prior_conversion_metadata_sha256':context[2],
                    'claimed_at':stamp,'accepted':False,'model_calls':0,'db_admission':budget.diagnostics()}
                db.execute('INSERT INTO '+TABLE+' VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(*key,'running',pid,pid_start,token,policy,json.dumps(current),stamp))
                db.execute('UPDATE '+RUNS+' SET claimed=claimed+1 WHERE run_id=? AND stage=?',(run_id,stage))
                db.execute('UPDATE jobs SET state=?,attempts=?,updated_at=?,worker_pid=? WHERE id=?',(STATES[stage],owned[7],stamp,pid,job['id']))
                budget.commit(db);current['db_admission']=budget.diagnostics();return current
            except BaseException:
                if db.in_transaction:db.rollback()
                raise
        except (sqlite3.OperationalError,BusyBudgetExceeded) as error:
            busy=isinstance(error,BusyBudgetExceeded) or is_busy(error)
            # A successful COMMIT followed by a BUSY acknowledgement must not
            # consume a second quota or mutate the source revision again.
            if current is not None and not db.in_transaction:
                try:
                    receipt=_row_receipt(db,current['key'],token)
                    if (receipt and receipt[:4]==('running',pid,pid_start,token) and snapshot(db,current['id'])==tuple(current['owned_snapshot'])):
                        saved=json.loads(receipt[4]);saved['db_admission']={**budget.diagnostics(),'committed_claim_receipt_recovered':True};return saved
                except sqlite3.OperationalError as probe_error:
                    if not is_busy(probe_error):busy=False
            if not busy:
                path=save_intent('claim_nonbusy_failure',{'status':'fail_closed_no_retry','prior_snapshot':list(prior),'stage':stage,'run_id':run_id,'policy':policy,'error_type':type(error).__name__,'error':str(error)[:2500],'diagnostics':budget.diagnostics()},intent_dir,token);error.intent_file=str(path);raise
            if isinstance(error,BusyBudgetExceeded):
                path=save_intent('claim_admission_deferred',{'status':'not_claimed','prior_snapshot':list(prior),'stage':stage,'run_id':run_id,'policy':policy,'diagnostics':budget.diagnostics(),'no_claim_committed':True},intent_dir,token)
                raise AdmissionDeferred('claim_database_admission_budget_exhausted',path,budget.diagnostics()) from error
            try:budget.retry(error)
            except BusyBudgetExceeded as exhausted:
                path=save_intent('claim_admission_deferred',{'status':'not_claimed','prior_snapshot':list(prior),'stage':stage,'run_id':run_id,'policy':policy,'diagnostics':budget.diagnostics(),'no_claim_committed':True},intent_dir,token)
                raise AdmissionDeferred('claim_database_admission_budget_exhausted',path,budget.diagnostics()) from exhausted
        except BaseException as error:
            if db.in_transaction:db.rollback()
            path=save_intent('claim_nonbusy_failure',{'status':'fail_closed_no_retry','prior_snapshot':list(prior),'stage':stage,'run_id':run_id,'policy':policy,'error_type':type(error).__name__,'error':str(error)[:2500],'diagnostics':budget.diagnostics()},intent_dir,token);error.intent_file=str(path);raise

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
            with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        descriptor=os.open(str(path.parent),os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    pointer=pointer_path(current['id']);before=pointer.read_bytes() if pointer.exists() else None
    atomic(Path(work)/'publication_intent.json',raw_json({'token':current['token'],'id':current['id'],'source_code_sha256':current['key'][2],'source_image_sha256':current['key'][3],'record':record,'accepted':False}))
    if before is not None:atomic(Path(work)/'prior_conversion_metadata.bin',before)
    replacement=raw_json(record);atomic(pointer,replacement);return pointer,before,replacement


def _finish_receipt(db,current):
    row=_row_receipt(db,current['key'],current['token'])
    if row and row[0] in TERMINAL:
        report=json.loads(row[4]);report['db_commit_receipt_recovered']=True;return report
    return None


def sync_prepared_files(result,work):
    """Persist frozen child outputs before any writer-admission waiting."""
    entries=list(result.get('artifacts',{}).values())+list(result.get('publish_files',{}).values())
    entries += [result[name] for name in ['record_file','partial_artifact_inventory'] if result.get(name)]
    paths={_owned(entry['file'],work) for entry in entries};directories={Path(work).resolve()}
    for path in paths:
        with path.open('rb') as stream:os.fsync(stream.fileno())
        directories.add(path.parent)
    floor=(R/OWNER).resolve()
    for directory in tuple(directories):
        parent=directory
        while parent.is_relative_to(floor):directories.add(parent);parent=parent.parent
    for directory in sorted(directories,key=lambda path:len(path.parts),reverse=True):
        descriptor=os.open(str(directory),os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def _restore_pointer_if_ours(db,current,pointer,before,replacement):
    if (pointer is not None and replacement is not None and snapshot(db,current['id'])==tuple(current['owned_snapshot'])
            and pointer.exists() and pointer.read_bytes()==replacement):
        if before is None:pointer.unlink()
        else:atomic(pointer,before)


def _park_prepared(db,current,result,work,intent,reason,handoff_timeout=30,busy_step_seconds=5):
    """Release only this exact lease to a durable prepared queue, never rerun it."""
    budget=BusyBudget(handoff_timeout,busy_step_seconds);key=tuple(current['key']);owned=tuple(current['owned_snapshot']);expected=('running',current['pid'],current['pid_start_ticks'],current['token']);parked=None
    try:
        budget.begin(db)
        owner=db.execute('SELECT state,owner_pid,owner_start_ticks,claim_token FROM '+TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone()
        if (owner!=expected or snapshot(db,current['id'])!=owned or birth(current['pid'])!=current['pid_start_ticks']
                or outcome_snapshot(db,current['id'])!=tuple(current['prior_outcome'])
                or execution_snapshot(db,current['id'])!=(tuple(current['prior_execution']) if current['prior_execution'] else None)):
            db.rollback();return {'parked':False,'foreign_lease_or_admission_changed':True,'diagnostics':budget.diagnostics()}
        stamp=now();parked=list(owned);parked[5]='initial_conversion_prepared_v1b';parked[8]=stamp;parked[10]='Prepared conversion retained; database/publication recovery required';parked[12]=None
        db.execute('UPDATE jobs SET state=?,worker_pid=NULL,error=?,updated_at=? WHERE id=?',(parked[5],parked[10],stamp,current['id']))
        record={'claim':current,'prepared_result':result,'work':str(Path(work).relative_to(R)),'intent_file':str(intent),'parked_snapshot':parked,'reason':reason,'accepted':False,'model_calls':0}
        db.execute('INSERT OR REPLACE INTO '+RECOVERY+' VALUES(?,?,?,?,?,?,?,?)',(*key,reason,json.dumps(record),stamp))
        db.execute('UPDATE '+TABLE+' SET state=?,record=?,updated_at=? WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',('prepared_waiting_publication',json.dumps(record),stamp,*key))
        budget.commit(db);return {'parked':True,'parked_snapshot':parked,'diagnostics':budget.diagnostics()}
    except BaseException as error:
        if db.in_transaction:db.rollback()
        if parked is not None:
            try:
                row=_row_receipt(db,key,current['token'])
                if row and row[0]=='prepared_waiting_publication' and snapshot(db,current['id'])==tuple(parked):return {'parked':True,'parked_snapshot':parked,'receipt_recovered':True,'diagnostics':budget.diagnostics()}
            except sqlite3.Error:pass
        return {'parked':False,'lease_retained_with_intent':True,'error_type':type(error).__name__,'error':str(error)[:1500],'diagnostics':budget.diagnostics()}


def finish(db,current,result,work,publish=False,artifact_writer=publish_native,deadline=None,admission_timeout=60,busy_step_seconds=5,publication_timeout=30,intent_dir=None,handoff_timeout=30):
    if db.in_transaction:raise RuntimeError('Finish cannot borrow a foreign/open transaction')
    key=tuple(current['key']);prior=tuple(current['prior_snapshot']);owned=tuple(current['owned_snapshot']);budget=BusyBudget(admission_timeout,busy_step_seconds)
    # This durable journal exists before DB waiting and never regenerates the
    # child/result. A terminal SQL nonce receipt is authoritative after crashes.
    payload={'status':'prepared_before_database_admission','claim':current,'prepared_result':result,'work':str(Path(work).relative_to(R)),'publish_requested':bool(publish),'child_generation_replayed':False}
    intent=save_intent('finish_prepared',payload,intent_dir,current['token'])
    if deadline is not None:publication_timeout=max(0.,deadline-time.monotonic())
    try:record=validate_result(current,result,work);sync_prepared_files(result,work)
    except BaseException as error:
        parking=_park_prepared(db,current,result,work,intent,'prepared_validation_failure',handoff_timeout,busy_step_seconds)
        save_intent('finish_prepared',{**payload,'status':'validation_failed_closed','parking':parking,'error_type':type(error).__name__,'error':str(error)[:2500]},intent.parent,current['token']);error.intent_file=str(intent);raise
    while True:
        pointer=None;before=replacement=None;publication_started=None
        try:
            # Read-only receipt lookup is allowed only for this exact nonce.
            receipt=_finish_receipt(db,current)
            if receipt:
                save_intent('finish_prepared',{**payload,'status':'committed_receipt_recovered','report':receipt,'diagnostics':budget.diagnostics()},intent.parent,current['token']);return receipt
            budget.begin(db);publication_started=time.monotonic()
            try:
                owner=db.execute('SELECT state,owner_pid,owner_start_ticks,claim_token FROM '+TABLE+' WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',key).fetchone();expected=('running',current['pid'],current['pid_start_ticks'],current['token'])
                if owner!=expected or snapshot(db,current['id'])!=owned or birth(current['pid'])!=current['pid_start_ticks']:
                    report={**result,'state':'stale_revision','published':False,'accepted':False,'model_calls':0}
                elif (not owner_valid(current.get('main_owner_context')) or outcome_snapshot(db,current['id'])!=tuple(current['prior_outcome'])
                      or execution_snapshot(db,current['id'])!=(tuple(current['prior_execution']) if current['prior_execution'] else None)
                      or model_busy(db,current['id']) or current['stage']=='native' and pointer_snapshot(current['id'])!=current.get('prior_conversion_metadata_sha256')):
                    _restore(db,prior);report={**result,'state':'stale_revision','published':False,'accepted':False,'reason':'Source/outcome/execution/model/owner admission changed'}
                elif not result.get('ok'):
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
                    pointer=pointer_path(current['id']);before=pointer.read_bytes() if pointer.exists() else None;replacement=raw_json(record);artifact_writer(current,result,record,work)
                    db.execute('UPDATE jobs SET state=?,output_record=?,worker_pid=NULL,error=?,updated_at=? WHERE id=?',('needs_quality_repair' if result['requires_quality_repair'] else 'rendered',json.dumps(record,ensure_ascii=False),'Pending full native/source quality validation',now(),current['id']))
                    report={**result,'state':'published_pending_quality','published':True,'accepted':False,'model_calls':0}
                if time.monotonic()-publication_started>publication_timeout:raise TimeoutError('Bounded active publication execution exceeded; prepared result retained')
                if owner==expected:db.execute('UPDATE '+TABLE+' SET state=?,record=?,updated_at=? WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',(report['state'],json.dumps(report,ensure_ascii=False),now(),*key))
                budget.commit(db)
            except BaseException:
                if db.in_transaction:db.rollback()
                raise
            report['db_admission']=budget.diagnostics();report['prepared_intent_file']=str(intent)
            save_intent('finish_prepared',{**payload,'status':'committed','report':report,'diagnostics':budget.diagnostics()},intent.parent,current['token'])
            try:atomic(Path(work)/'supervisor_result.json',raw_json(report))
            except OSError:pass
            return report
        except BaseException as error:
            if db.in_transaction:db.rollback()
            try:receipt=_finish_receipt(db,current)
            except sqlite3.Error:receipt=None
            if receipt:
                receipt['db_admission']={**budget.diagnostics(),'committed_finish_receipt_recovered':True}
                save_intent('finish_prepared',{**payload,'status':'committed_receipt_recovered','report':receipt,'error_type':type(error).__name__,'diagnostics':budget.diagnostics()},intent.parent,current['token'])
                if not isinstance(error,(sqlite3.OperationalError,BusyBudgetExceeded)) or isinstance(error,sqlite3.OperationalError) and not is_busy(error):
                    error.committed_receipt=receipt;error.intent_file=str(intent);raise
                return receipt
            _restore_pointer_if_ours(db,current,pointer,before,replacement)
            busy=isinstance(error,BusyBudgetExceeded) or is_busy(error)
            if busy and not isinstance(error,BusyBudgetExceeded):
                try:budget.retry(error);continue
                except BusyBudgetExceeded as exhausted:error=exhausted
            parking=_park_prepared(db,current,result,work,intent,'prepared_database_admission_timeout' if busy else 'prepared_publication_failed_closed',handoff_timeout,busy_step_seconds)
            status='prepared_unowned_recovery' if parking.get('parked') else 'foreign_lease_preserved' if parking.get('foreign_lease_or_admission_changed') else 'lease_retained_with_durable_intent'
            save_intent('finish_prepared',{**payload,'status':status,'parking':parking,'error_type':type(error).__name__,'error':str(error)[:2500],'diagnostics':budget.diagnostics()},intent.parent,current['token'])
            if busy:raise AdmissionDeferred('finish_database_admission_budget_exhausted',intent,budget.diagnostics()) from error
            error.intent_file=str(intent);raise


def resume_prepared_intent(db,intent_file,owner_context=None,pid=None,pid_start=None,admission_timeout=60,publication_timeout=30):
    """Explicit recovery of this producer's parked lease; never legacy or foreign."""
    path=_owned(intent_file);journal=json.loads(path.read_text());current=journal['claim'];result=journal['prepared_result'];work=_owned(journal['work']);key=tuple(current['key'])
    if not current['policy'].startswith('bounded_offline_initial_tikz_v1b:') or current['owned_snapshot'][5]!=STATES[current['stage']]:raise ValueError('Recovery cannot consume another producer/version lease')
    if (work/'request.json').exists():check_pins(json.loads((work/'request.json').read_text())['pins'])
    record=validate_result(current,result,work);receipt=_finish_receipt(db,current)
    if receipt:return receipt
    parking=journal.get('parking') or {};parked=parking.get('parked_snapshot');expected_snapshot=tuple(parked) if parked else tuple(current['owned_snapshot'])
    old_actor=birth(current['pid'])
    if not parked and old_actor==current['pid_start_ticks']:raise RuntimeError('Prepared owner is still alive; recovery will not steal it')
    pid=pid or os.getpid();pid_start=birth(pid) if pid_start is None else pid_start
    if pid_start is None or not owner_valid(owner_context):raise RuntimeError('New recovery owner identity invalid')
    budget=BusyBudget(admission_timeout,5);budget.begin(db)
    try:
        row=_row_receipt(db,key,current['token']);wanted_state='prepared_waiting_publication' if parked else 'running'
        if (not row or row[0]!=wanted_state or snapshot(db,current['id'])!=expected_snapshot
                or outcome_snapshot(db,current['id'])!=tuple(current['prior_outcome'])
                or execution_snapshot(db,current['id'])!=(tuple(current['prior_execution']) if current['prior_execution'] else None) or model_busy(db,current['id'])):
            db.rollback();raise RuntimeError('Prepared full source/revision/lease CAS changed; nothing recovered')
        stamp=now();owned=list(expected_snapshot);owned[5]=STATES[current['stage']];owned[8]=stamp;owned[12]=pid
        transferred={**current,'pid':pid,'pid_start_ticks':pid_start,'owned_snapshot':owned,'main_owner_context':owner_context,'recovered_from_intent':str(path),'old_owner':{'pid':current['pid'],'start_ticks':current['pid_start_ticks']}}
        db.execute('UPDATE jobs SET state=?,worker_pid=?,updated_at=? WHERE id=?',(owned[5],pid,stamp,current['id']))
        db.execute('UPDATE '+TABLE+' SET state=?,owner_pid=?,owner_start_ticks=?,record=?,updated_at=? WHERE id=? AND stage=? AND source_code_hash=? AND source_image_hash=? AND stage_input_hash=?',('running',pid,pid_start,json.dumps(transferred),stamp,*key));budget.commit(db)
    except BaseException:
        if db.in_transaction:db.rollback()
        raise
    # Existing immutable candidate and nonce are reused. No quota, attempts,
    # child generation, source code or PNG transformation is repeated.
    return finish(db,transferred,result,work,journal['publish_requested'],admission_timeout=admission_timeout,publication_timeout=publication_timeout,intent_dir=path.parent)

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
    process=run([sys.executable,str(Path(__file__).with_name('initial_conversion_case_v1b.py')),str(work/'request.json')],work,max(.001,deadline-time.monotonic()) if deadline is not None else timeout,env)
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


def read_candidate(db,run_id,stage,ids=(),admission_timeout=30):
    budget=BusyBudget(admission_timeout,5)
    while True:
        try:return select_candidate(db,run_id,stage,ids)
        except sqlite3.OperationalError as error:
            if not is_busy(error):raise
            budget.retry(error)


def write_event(metadata,event):
    fd=os.open(metadata['events_file'],os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
    try:os.write(fd,(json.dumps({'at':now(),'model_calls':0,'accepted':False,**event})+'\n').encode());os.fsync(fd)
    finally:os.close(fd)


def slot_failure(args,metadata,error,current=None,work=None):
    diagnostic={'status':'slot_failed_closed','pid':os.getpid(),'pid_start_ticks':birth(os.getpid()),'stage':args.stage,'run_id':args.run_id,
        'error_type':type(error).__name__,'error':str(error)[:2500],'intent_file':getattr(error,'intent_file',None),'claim':current,'no_automatic_restart':True,'model_calls':0,'accepted':False}
    path=Path(metadata['events_file']).parent/(args.stage+'.'+str(os.getpid())+'.failure.json');atomic(path,raw_json(diagnostic))
    if work is not None:atomic(Path(work)/'slot_recovery_required.json',raw_json(diagnostic))
    atomic(args.control,raw_json({'drain':True,'requested_at':now(),'reason':'slot_failure','failed_pid':os.getpid(),'diagnostic_file':str(path),'scope':'Finish bounded current case; no new claims'}))
    write_event(metadata,{'state':'slot_failed_closed','stage':args.stage,'id':current['id'] if current else None,'error_type':type(error).__name__,'intent_file':getattr(error,'intent_file',None),'diagnostic_file':str(path)})
    return diagnostic


def slot(args):
    signal.signal(signal.SIGUSR1,request_drain);db=sqlite3.connect(args.db,timeout=0);metadata=json.loads(Path(args.run_metadata).read_text());pins=metadata['pins'];counts={};processed=0;current=None;work=None
    owner_file=Path(metadata['owner_file']);context={'file':str(owner_file),'sha256':sha(owner_file.read_bytes()),**{key:metadata[key] for key in ['run_id','policy','pid','pid_start_ticks']}}
    try:
        while not draining(args.control):
            current=None;work=None;check_pins(pins)
            if not owner_valid(context) or os.getppid()!=metadata['pid']:raise RuntimeError('Launcher owner/birth changed; slot stops before new claim')
            prior=read_candidate(db,args.run_id,args.stage,metadata.get('authorized_sample_ids',()),args.claim_admission_timeout)
            if prior is None:
                if not args.watch or not quota_available(db,args.run_id,args.stage):break
                time.sleep(5);continue
            current=claim(db,prior,args.stage,args.run_id,metadata['policy'],owner_context=context,admission_timeout=args.claim_admission_timeout)
            if current is None:continue
            deadline=time.monotonic()+args.timeout
            work,result,isolation=run_case(current,pins,args.timeout,args.max_side,deadline=deadline)
            if not isolation.get('cleanup_complete'):raise RuntimeError('New owned process subtree not fully reaped; halt slot for recovery')
            # The generated proposal is finished once. DB admission and active
            # publication each have independent budgets after the child exits.
            report=finish(db,current,result,work,args.publish,admission_timeout=args.finish_admission_timeout,publication_timeout=args.publication_timeout,handoff_timeout=args.handoff_timeout)
            owned=db.execute('SELECT id FROM jobs WHERE worker_pid=? AND state IN (?,?)',(os.getpid(),*STATES.values())).fetchall()
            if owned:raise RuntimeError('Slot retains owned lease after finish; durable diagnosis required')
            processed+=1;counts[report['state']]=counts.get(report['state'],0)+1
            write_event(metadata,{'id':current['id'],'stage':args.stage,'state':report['state'],'reason':report.get('reason'),'seconds':report.get('seconds'),'code_sha256':report.get('record',{}).get('code_sha256'),'pdf_sha256':report.get('record',{}).get('pdf_sha256'),'published':report['published']})
    except BaseException as error:
        if db.in_transaction:db.rollback()
        # Never replay/reclassify finish on AdmissionDeferred or a failed
        # publication. Its prepared result and nonce remain authoritative.
        slot_failure(args,metadata,error,current,work);raise
    finally:db.close()
    return {'pid':os.getpid(),'stage':args.stage,'processed':processed,'counts':counts}


def monitor_slots(children,control,work,poll_seconds=.5,watch=False):
    failures={};drain_written=False
    while True:
        for child,_ in children:
            code=child.poll()
            unexpected=code is not None and (code!=0 or watch and not draining(control))
            if unexpected and child.pid not in failures:
                failures[child.pid]={'pid':child.pid,'returncode':code,'detected_at':now(),'unexpected_watch_exit':code==0}
        if (failures or DRAIN) and not drain_written:
            diagnostic={'drain':True,'requested_at':now(),'reason':'child_slot_failure' if failures else 'requested_drain','failed_slots':list(failures.values()),'scope':'Finish bounded current case; no new claims; no automatic slot restart'}
            atomic(control,raw_json(diagnostic));atomic(Path(work)/'supervisor_drain.json',raw_json(diagnostic));drain_written=True
        if all(child.poll() is not None for child,_ in children):break
        time.sleep(poll_seconds)
    return {'failed':bool(failures),'drain_requested':drain_written,'failures':list(failures.values())}


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
    lock=(W/'initial_conversion_supervisor_v1b.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.publish:database=W/'jobs.sqlite';bootstrap=None
    else:database=work/'private_jobs.sqlite';bootstrap=bootstrap_private(W/'jobs.sqlite',database,{'compile':args.compile_limit,'native':args.native_limit},args.ids)
    db=sqlite3.connect(database,timeout=0)
    try:
        init(db,args.startup_admission_timeout);quotas={'compile':0 if args.watch else args.compile_limit,'native':0 if args.watch else args.native_limit};create_run(db,run_id,policy,args.publish,quotas,args.startup_admission_timeout)
    except BaseException as error:
        if db.in_transaction:db.rollback()
        save_intent('startup_admission_failure',{'status':'startup_failed_no_slots','run_id':run_id,'policy':policy,'database':str(database),'error_type':type(error).__name__,'error':str(error)[:2500],'model_calls':0},work/'database_intents')
        raise
    finally:db.close()
    control=(W/'initial_conversion_supervisor_v1b_control.json') if args.publish else (work/'control.json');events=work/'events.jsonl';metadata={'pid':os.getpid(),'pid_start_ticks':birth(os.getpid()),'at':now(),'run_id':run_id,'policy':policy,'pins':pins,'publish':args.publish,'private_smoke':not args.publish,'database':str(database),'owner_file':str(W/'initial_conversion_supervisor_v1b_owner.json'),'control':str(control),'events_file':str(events),'bootstrap':bootstrap,'authorized_sample_ids':args.ids,'model_calls':0,'accepted':0}
    meta=work/'run.json';atomic(meta,raw_json(metadata));atomic(W/'initial_conversion_supervisor_v1b_owner.json',raw_json(metadata));children=[]
    launch_error=None
    try:
        for stage,workers,deadline in [('compile',args.compile_workers,args.compile_timeout),('native',args.native_workers,args.native_timeout)]:
            for index in range(workers):
                output=(work/(stage+'.'+str(index)+'.log')).open('wb');cmd=[sys.executable,str(Path(__file__).resolve()),'--slot','--db',str(database),'--run-id',run_id,'--run-metadata',str(meta),'--control',str(control),'--stage',stage,'--timeout',str(deadline),'--max-side',str(args.max_side)]
                for name in ['claim_admission_timeout','finish_admission_timeout','publication_timeout','handoff_timeout']:cmd+=['--'+name.replace('_','-'),str(getattr(args,name))]
                if args.publish:cmd+=['--publish']
                if args.watch:cmd+=['--watch']
                try:child=subprocess.Popen(cmd,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
                except BaseException:output.close();raise
                children.append((child,output))
    except BaseException as error:
        launch_error={'error_type':type(error).__name__,'error':str(error)[:2500]};atomic(control,raw_json({'drain':True,'reason':'slot_launch_failure','error':launch_error,'scope':'Finish current bounded case; no new claims'}));atomic(work/'launch_failure.json',raw_json(launch_error))
    monitored=monitor_slots(children,control,work,watch=args.watch)
    outcomes=[]
    for child,output in children:output.close();outcomes.append({'pid':child.pid,'returncode':child.returncode})
    db=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=2);states=[dict(zip(['stage','state','count'],row)) for row in db.execute('SELECT stage,state,count(*) FROM '+TABLE+' GROUP BY stage,state')];db.close()
    summary={**{key:metadata[key] for key in ['run_id','policy','publish','private_smoke','database','bootstrap']},'at':now(),'slot_processes':outcomes,'stage_states':states,'events_file':str(events),'model_calls':0,'accepted':0,'production_canonical_claimed':args.publish,'monitor':monitored,'launch_error':launch_error,'failed':bool(monitored['failed'] or launch_error)}
    atomic(work/'summary.json',raw_json(summary));atomic(W/'initial_conversion_supervisor_v1b_summary.json',raw_json(summary));print(json.dumps(summary))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--publish',action='store_true');parser.add_argument('--id',dest='ids',action='append',default=[]);parser.add_argument('--watch',action='store_true');parser.add_argument('--compile-limit',type=int,default=2);parser.add_argument('--native-limit',type=int,default=2);parser.add_argument('--compile-workers',type=int,default=1);parser.add_argument('--native-workers',type=int,default=1);parser.add_argument('--compile-timeout',type=float,default=240);parser.add_argument('--native-timeout',type=float,default=180);parser.add_argument('--max-side',type=int,default=8192)
    parser.add_argument('--startup-admission-timeout',type=float,default=60);parser.add_argument('--claim-admission-timeout',type=float,default=30);parser.add_argument('--finish-admission-timeout',type=float,default=60);parser.add_argument('--publication-timeout',type=float,default=30);parser.add_argument('--handoff-timeout',type=float,default=60)
    parser.add_argument('--slot',action='store_true');parser.add_argument('--db');parser.add_argument('--run-id');parser.add_argument('--run-metadata');parser.add_argument('--control');parser.add_argument('--stage',choices=['compile','native']);parser.add_argument('--timeout',type=float)
    args=parser.parse_args()
    if any(not math.isfinite(v) or v<.1 or v>300 for v in [args.startup_admission_timeout,args.claim_admission_timeout,args.finish_admission_timeout,args.publication_timeout,args.handoff_timeout]):parser.error('Admission/publication/handoff budgets must be 0.1..300 seconds')
    if args.slot:print(json.dumps(slot(args)))
    else:
        if not 1<=args.max_side<=16384:parser.error('max-side must be 1..16384; oversized pages are deferred, never scaled')
        if args.watch and not args.publish:parser.error('Watch requires explicit production --publish; smoke is always finite')
        if any(v<1 or v>64 for v in [args.compile_limit,args.native_limit]) or any(v<1 or v>16 for v in [args.compile_workers,args.native_workers]) or any(not math.isfinite(v) or v<1 or v>3600 for v in [args.compile_timeout,args.native_timeout]):parser.error('Finite limits 1..64, workers 1..16, deadline 1..3600 required')
        summary=main(args)
        if summary['failed']:sys.exit(1)
