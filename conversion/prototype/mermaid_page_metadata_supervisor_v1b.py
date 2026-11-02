"""Short atomic Mermaid page publication over the frozen v1 algorithm.

All selection, rendering, hashes, archives and immutable clean-file preparation
occur before the writer transaction. Claim and finish share one transaction:
an owned job is never committed separately. SQLite exhaustion leaves a durable
prepared-unowned intent, not a suspended job or a changed validation rule.
"""
import argparse,concurrent.futures,copy,fcntl,hashlib,importlib.util,json,os,signal,sqlite3,threading,time,uuid
from pathlib import Path
import mermaid_page_metadata_batch_v1 as base
import mermaid_page_metadata_candidate_v1 as generator
from bounded_sqlite_transaction_v1 import BusyBudget,BusyBudgetExceeded,is_busy

VERSION='mermaid_page_metadata_short_atomic_supervisor_v1b';DIRECTORY='conversion/mermaid_page_metadata_v1b';OWNER='mermaid_page_metadata_v1b_owner.json';CONTROL='mermaid_page_metadata_v1b_control.json';PREFLIGHT='mermaid_page_metadata_v1b_reviewed_preflight.json';sha=lambda b:hashlib.sha256(b).hexdigest();canonical=generator.canonical
FROZEN_CORE_SHA='06ab98abeb228f9d1f87562fe9bee95e128e4fc9861be133ccc5f550b9440f82';FROZEN_BATCH_SHA='6669f87a23062c3bf997ecc7b5eec021c1a8a8fc8551c3b262410f6b5dfad7e3';FROZEN_AUDIT_SHA='7aca68a338e1daaeb9d4c6ad4dd9c5c9a7eb6d617d64f17b4b689f232433444f'
FROZEN_BUSY_SHA='09cec83436cc87b244416375d1571254d81982c133ab28894693dd8b39e92740'
RESUMABLE={'deferred_model_running','validated_dry_run'}
DRAIN=threading.Event()
class Stale(ValueError):pass
class PendingIntent(RuntimeError):
    def __init__(self,state,path,error,diagnostics):self.state=state;self.path=str(path);self.diagnostics=diagnostics;super().__init__(state+': '+repr(error))
class CommittedThenFailed(PendingIntent):
    def __init__(self,path,error,diagnostics,receipt):self.receipt=receipt;super().__init__('confirmed_commit_nonbusy_failure_draining',path,error,diagnostics)
def require(ok,reason):
    if not ok:raise Stale(reason)
def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex);fd=None
    try:
        with temporary.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        temporary.replace(path);fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd)
    finally:
        if fd is not None:os.close(fd)
        try:temporary.unlink()
        except FileNotFoundError:pass
def immutable(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    except FileExistsError:require(path.read_bytes()==data,'immutable_intent_conflict')
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def implementation(root=base.R):
    require(sha(Path(base.__file__).read_bytes())==FROZEN_BATCH_SHA and sha(Path(generator.__file__).read_bytes())==FROZEN_CORE_SHA,'frozen_metadata_algorithm_changed');validation_policy,validation_files=base.implementation(root);require(validation_files[str(Path(root)/'conversion/mermaid_canvas_metadata_audit_v1.json')]==FROZEN_AUDIT_SHA,'original_953_audit_changed');files=dict(validation_files);files[str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes());helper=Path(importlib.util.find_spec('bounded_sqlite_transaction_v1').origin);files[str(helper)]=sha(helper.read_bytes());require(files[str(helper)]==FROZEN_BUSY_SHA,'shared_busy_helper_changed');return validation_policy,VERSION+':'+sha(canonical(files))[:20],files
def logical_rows(db,key):
    if not base.exists(db,base.TABLE):return []
    return [list(row) for row in db.execute('select * from '+base.TABLE+' where id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? order by policy',tuple(key[:5])).fetchall()]
def terminal(rows,publish):
    for row in rows:
        state=row[6]
        if state=='running':return True
        if state not in RESUMABLE or state=='validated_dry_run' and not publish:return True
    return False
def next_selection(db,audit,validation_policy,publish=False,ids=None):
    """Read-only full preselection. Never invoke from an open transaction."""
    require(not db.in_transaction,'preselection_must_be_outside_transaction')
    for item in audit['records']:
        if ids is not None and item['id'] not in ids:continue
        try:job,outcome,queues,old,source=base.context(db,item['id'])
        except (ValueError,KeyError,TypeError):continue
        if (old['code_sha256'],old['image_sha256'],old['source_image_sha256'])!=(item['code_sha256'],item['image_sha256'],item['source_image_sha256']):continue
        key=[old['id'],old['code_sha256'],old['image_sha256'],old['source_code_sha256'],old['source_image_sha256'],validation_policy];rows=logical_rows(db,key)
        if terminal(rows,publish):continue
        return {'id':old['id'],'key':key,'prior_job':job,'prior_outcome':outcome,'prior_queues':queues,'expected_logical_rows':rows,'record':old,'source_record':source,'audit_record':item}
    return None
def _stat(path):
    s=Path(path).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def _file_inventory(paths):return {str(Path(path)): {'sha256':sha(Path(path).read_bytes()),'stat':_stat(path)} for path in paths}
def _status(path,state,**extra):
    try:atomic(Path(path).parent/'recovery_status.json',canonical({'state':state,'intent_file':str(path),'at':base.now(),'owned_job_committed':False,**extra}));return None
    except OSError as error:return repr(error) # Immutable intent and SQL nonce remain authoritative.
def prepare(db,selection,work,validation_policy,supervisor_policy,files,publish=False,root=base.R,case_generator=generator.generate,artifact_writer=base.publish_artifacts):
    """No canonical DB mutation; production files, if requested, are unreferenced."""
    require(not db.in_transaction,'prepare_must_be_outside_transaction');base.ensure(files);require(selection['key'][5]==validation_policy,'validation_policy_mismatch');require(not terminal(logical_rows(db,selection['key']),publish),'same_source_hash_already_terminal');work=Path(work);token=uuid.uuid4().hex;pid=os.getpid();stamp=base.now();owned=copy.deepcopy(selection['prior_job']);indexes={name:i for i,name in enumerate(owned['columns'])}
    for name,value in [('state',base.STATE),('worker_pid',pid),('updated_at',stamp)]:owned['rows'][0][indexes[name]]=value
    current={'id':selection['id'],'key':selection['key'],'pid':pid,'token':token,'prior_job':selection['prior_job'],'owned_job':owned,'prior_outcome':selection['prior_outcome'],'prior_queues':selection['prior_queues'],'policy':validation_policy,'claimed_at':stamp,'implementation':files,'accepted':False,'supervisor_policy':supervisor_policy,'no_owned_job_separately_committed':True}
    out,proof=case_generator(selection['record'],selection['source_record'],work,root);base.ensure(files)
    if out is not None and publish:finalized=artifact_writer(current,out,proof,work,root)
    else:finalized=None
    report={'id':selection['id'],'policy':validation_policy,'supervisor_policy':supervisor_policy,'claim':current,'work':str(work),'accepted':False,'published':bool(finalized),'state':'published_pending_candidate' if finalized else 'validated_dry_run' if out is not None else 'deferred_retained_prior','proof':proof,'submission_nonce':token,'no_owned_job_separately_committed':True}
    if finalized is not None:
        require(finalized.get('quality_state','').startswith('pending_'),'candidate_cannot_be_accepted');require((finalized['code_sha256'],finalized['image_sha256'])==(proof['output_code_sha256'],proof['output_image_sha256']),'candidate_pair_hash_mismatch');require(all(finalized.get(k)==selection['record'].get(k) for k in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256','original_source_code','original_reference','previous_candidate_archive')),'candidate_source_identity_changed');report['out']=finalized
    paths=set(files)
    for name,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:generator.checked(root,selection['record'][name],selection['record'][digest]);paths.add(str(Path(root)/selection['record'][name]))
    for path in work.rglob('*'):
        if path.is_file():paths.add(str(path))
    for relative in proof.get('source_resources',{}).get('verified_files',[]):paths.add(str(Path(root)/relative))
    if finalized:
        for name in ('code_file','image_file'):paths.add(str(Path(root)/finalized[name]))
        paths.add(str((Path(root)/finalized['code_file']).parent/'conversion.json'))
    inventory=_file_inventory(paths);base.ensure(files);intent={'version':1,'phase':'prepared_unowned','selection':selection,'current':current,'publish':publish,'out':finalized,'out_raw':canonical(finalized).decode() if finalized else None,'report':report,'report_raw':canonical(report).decode(),'files':inventory,'root':str(Path(root).resolve()),'supervisor_policy':supervisor_policy,'validation_policy':validation_policy,'source_validation_algorithm_unchanged':True,'accepted':False,'model_calls':0};payload=canonical(intent);path=work/'intents'/('prepared.'+sha(payload)+'.json');immutable(path,payload);_status(path,'prepared_unowned');return path,intent
def verify_intent(path,intent=None):
    raw=Path(path).read_bytes();require(Path(path).name=='prepared.'+sha(raw)+'.json','prepared_intent_digest_mismatch');decoded=json.loads(raw);require(raw==canonical(decoded),'prepared_intent_not_canonical');require(intent is None or decoded==intent,'prepared_intent_memory_mismatch');require(decoded.get('phase')=='prepared_unowned' and decoded.get('accepted') is False,'unknown_prepared_intent_contract')
    for locator,entry in decoded['files'].items():require(sha(Path(locator).read_bytes())==entry['sha256'] and _stat(locator)==entry['stat'],'prepared_proof_or_source_file_changed:'+locator)
    c=decoded['current'];selection=decoded['selection'];report=decoded['report'];prior=dict(zip(selection['prior_job']['columns'],selection['prior_job']['rows'][0]));record=json.loads(prior['output_record']);source=json.loads(prior['input_record']);require(record==selection['record'] and source==selection['source_record'],'intent_source_or_job_record_mismatch');require(c['key']==selection['key'] and c['key'][5]==c['policy']==decoded['validation_policy'] and c['prior_job']==selection['prior_job'] and c['prior_outcome']==selection['prior_outcome'] and c['prior_queues']==selection['prior_queues'],'intent_claim_contract_mismatch');require(report['claim']==c and report['submission_nonce']==c['token'] and canonical(report).decode()==decoded['report_raw'],'intent_terminal_receipt_not_bound_to_claim');require(decoded['out_raw']==(canonical(decoded['out']).decode() if decoded['out'] else None),'intent_output_record_encoding_changed');require(report.get('accepted') is False and report.get('published')==bool(decoded['out']),'intent_cannot_accept_or_change_publication_scope')
    proof=report['proof'];work=Path(report['work']);require((work/'proof.json').read_bytes()==canonical(proof),'intent_frozen_proof_changed')
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:generator.checked(decoded['root'],record[key],record[digest])
    if proof.get('candidate_checks_passed'):
        before=generator.checked(decoded['root'],record['code_file'],record['code_sha256']).decode();after=(work/'candidate.drawio').read_bytes().decode();generator.verify_metadata(before,after,proof['metadata_delta']);require(sha(after.encode())==proof['output_code_sha256'] and sha((work/'candidate.png').read_bytes())==proof['output_image_sha256']==proof['fresh_before_png_sha256']==proof['fresh_after_png_sha256'],'intent_metadata_or_fresh_pixels_not_bound')
    if decoded['out']:
        out=decoded['out'];require(out==report.get('out') and out.get('quality_state','').startswith('pending_'),'intent_output_cannot_be_accepted');require(all(out.get(k)==record.get(k) for k in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256','original_source_code','original_reference','previous_candidate_archive')),'intent_output_source_lineage_changed');require((out['code_sha256'],out['image_sha256'])==(proof['output_code_sha256'],proof['output_image_sha256']),'intent_output_pair_hash_mismatch');generator.checked(decoded['root'],out['code_file'],out['code_sha256']);generator.checked(decoded['root'],out['image_file'],out['image_sha256'])
    return decoded
def _match_sql(db,intent):
    selected=intent['selection'];id=selected['id'];require(base.snapshot(db,'jobs',id)==selected['prior_job'],'job_full_snapshot_changed');require(base.snapshot(db,'processing_outcomes_v2',id)==selected['prior_outcome'],'outcome_full_snapshot_changed');require(base.queues(db,id)==selected['prior_queues'],'model_queue_full_snapshot_changed');require(logical_rows(db,selected['key'])==selected['expected_logical_rows'],'logical_stage_snapshot_changed');require(not terminal(selected['expected_logical_rows'],intent['publish']),'same_source_hash_already_terminal')
    # Metadata-only stat CAS closes the lock-wait window; no file bytes are read.
    for path,entry in intent['files'].items():require(_stat(path)==entry['stat'],'prepared_file_metadata_changed_while_waiting:'+path)
def _receipt(db,intent):
    c=intent['current'];row=db.execute('select state,owner_pid,claim_token,record from '+base.TABLE+' where id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?',tuple(c['key'])).fetchone()
    if row is None or row[2]!=c['token'] or row[3]!=intent['report_raw'] or row[0]!=intent['report']['state']:return None
    job=base.snapshot(db,'jobs',c['id']);actual=dict(zip(job['columns'],job['rows'][0]))
    if intent['out']:
        record=json.loads(actual['output_record'])
        if (record.get('code_sha256'),record.get('image_sha256'))!=(intent['out']['code_sha256'],intent['out']['image_sha256']):return None
    elif job!=intent['selection']['prior_job']:return None
    return {'state':row[0],'id':c['id'],'published':intent['report']['published'],'accepted':False,'submission_nonce':c['token'],'confirmed_committed_receipt':True,'owned_job_committed':False}
def _sql_once(db,intent):
    """Only single-ID SQL/CAS and pre-encoded JSON. No hash/read/fsync/render."""
    _match_sql(db,intent);c=intent['current'];key=tuple(c['key']);stamp=c['claimed_at'];where='id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?';prior=[r for r in intent['selection']['expected_logical_rows'] if r[5]==c['policy']]
    if prior:db.execute('insert into '+base.HISTORY+' values(?,?,?,?)',(c['id'],c['token'],prior[0][9],stamp))
    db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(base.STATE,c['pid'],stamp,c['id']));require(base.snapshot(db,'jobs',c['id'])==c['owned_job'],'actual_claim_differs_from_predicted_full_snapshot');db.execute('insert or replace into '+base.TABLE+' values(?,?,?,?,?,?,?,?,?,?,?)',(*key,'running',c['pid'],c['token'],intent['report_raw'],stamp));require(db.execute('select state,owner_pid,claim_token from '+base.TABLE+' where '+where,key).fetchone()==('running',c['pid'],c['token']),'atomic_claim_ownership_lost')
    if intent['out']:
        db.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=NULL,error=?,updated_at=? where id=?',(intent['out_raw'],'Missing page metadata repaired; complete QA4b required',stamp,c['id']))
        for table,snap in c['prior_queues'].items():db.execute('update '+table+' set state="held_for_quality_v2" where id=? and state!="running"'+(' and worker_pid is NULL' if 'worker_pid' in snap['columns'] else ''),(c['id'],))
    else:
        prior=dict(zip(c['prior_job']['columns'],c['prior_job']['rows'][0]));db.execute('update jobs set state=?,worker_pid=?,error=?,updated_at=? where id=?',(prior['state'],prior.get('worker_pid'),prior.get('error'),prior['updated_at'],c['id']));require(base.snapshot(db,'jobs',c['id'])==c['prior_job'],'atomic_dryrun_restore_changed_job')
    db.execute('update '+base.TABLE+' set state=?,record=?,updated_at=? where '+where,(intent['report']['state'],intent['report_raw'],stamp,*key))
def _probe(db,intent,budget,path):
    """Never replay a transaction while a previous nonce result is unknown."""
    while True:
        try:return _receipt(db,intent)
        except sqlite3.OperationalError as error:
            try:budget.retry(error)
            except BaseException as terminal_error:
                state='receipt_probe_busy_prepared_unowned' if isinstance(terminal_error,BusyBudgetExceeded) else 'receipt_probe_nonbusy_failed_closed_unowned';_status(path,state,error=repr(terminal_error),commit_status_unknown=True,db_budget=budget.diagnostics());raise PendingIntent(state,path,terminal_error,budget.diagnostics()) from terminal_error
def commit_prepared(db,path,intent=None,seconds=15,step_seconds=.25,budget_factory=BusyBudget,cancel_check=None):
    require(not db.in_transaction,'cannot_borrow_external_transaction');intent=verify_intent(path,intent);old_timeout=db.execute('pragma busy_timeout').fetchone()[0];db.execute('pragma busy_timeout=0');budget=budget_factory(seconds=seconds,step_seconds=step_seconds);hold=[]
    try:
        already=_probe(db,intent,budget,path)
        if already:_status(path,'confirmed_committed',receipt=already);return already
        while True:
            began=None
            try:
                # Expensive checks are repeated before waiting, never under the lock.
                verify_intent(path,intent)
                if cancel_check and cancel_check():_status(path,'drained_prepared_unowned');return {'state':'drained_prepared_unowned','published':False,'accepted':False,'owned_job_committed':False}
                budget.begin(db);began=time.monotonic()
                if cancel_check and cancel_check():db.rollback();_status(path,'drained_prepared_unowned');return {'state':'drained_prepared_unowned','published':False,'accepted':False,'owned_job_committed':False}
                _sql_once(db,intent);budget.commit(db);hold.append(time.monotonic()-began);receipt=_probe(db,intent,budget,path);require(receipt is not None,'committed_nonce_receipt_missing');_status(path,'committed',receipt=receipt,db_budget=budget.diagnostics(),transaction_seconds=hold);return {**receipt,'db_budget':budget.diagnostics(),'transaction_seconds':hold}
            except BaseException as error:
                if db.in_transaction:db.rollback()
                if began is not None:hold.append(time.monotonic()-began)
                if isinstance(error,PendingIntent):raise
                receipt=_probe(db,intent,budget,path)
                if receipt:
                    _status(path,'confirmed_commit_after_ack_error',receipt=receipt,error=repr(error),db_budget=budget.diagnostics())
                    if not is_busy(error) and not isinstance(error,BusyBudgetExceeded):raise CommittedThenFailed(path,error,budget.diagnostics(),receipt) from error
                    return {**receipt,'commit_ack_error':repr(error),'db_budget':budget.diagnostics(),'transaction_seconds':hold}
                if isinstance(error,(KeyboardInterrupt,SystemExit)):_status(path,'interrupted_prepared_unowned',error=repr(error));raise
                if isinstance(error,Stale):_status(path,'stale_prepared_unowned',error=str(error));return {'state':'stale_prepared_unowned','published':False,'accepted':False,'owned_job_committed':False,'reason':str(error)}
                try:
                    if isinstance(error,BusyBudgetExceeded):raise error
                    budget.retry(error)
                except BaseException as terminal_error:
                    state='busy_prepared_unowned' if isinstance(terminal_error,BusyBudgetExceeded) else 'nonbusy_failed_closed_unowned';_status(path,state,error=repr(terminal_error),db_budget=budget.diagnostics(),transaction_seconds=hold);raise PendingIntent(state,path,terminal_error,budget.diagnostics()) from terminal_error
    finally:
        if db.in_transaction:db.rollback()
        db.execute('pragma busy_timeout='+str(old_timeout))
def initialize(db,seconds=15):
    require(not db.in_transaction,'initialize_cannot_borrow_transaction');db.execute('pragma busy_timeout=0');budget=BusyBudget(seconds=seconds,step_seconds=.25)
    try:
        budget.begin(db);db.execute('create table if not exists '+base.TABLE+'(id,code_hash,image_hash,source_code_hash,source_image_hash,policy,state,owner_pid,claim_token,record,updated_at,primary key(id,code_hash,image_hash,source_code_hash,source_image_hash,policy))');db.execute('create table if not exists '+base.HISTORY+'(id,claim_token primary key,record,updated_at)');budget.commit(db)
    except BaseException:db.rollback();raise
def revision_lock(root,key):
    path=Path(root)/DIRECTORY/'revision_locks'/(sha(canonical(key[:5]))+'.lock');path.parent.mkdir(parents=True,exist_ok=True);stream=path.open('a+')
    try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);return stream
    except BaseException:stream.close();raise
def draining(root):
    path=Path(root)/'conversion'/CONTROL
    if DRAIN.is_set():return True
    if not path.exists():return False
    try:return json.loads(path.read_text()).get('drain') is True
    except (OSError,ValueError):return True
def scope_audit(root=base.R):
    root=Path(root);scope_path=root/'conversion/mermaid_canvas_metadata_audit_v1.json';raw=scope_path.read_bytes();require(sha(raw)==FROZEN_AUDIT_SHA,'original_953_audit_changed');audit=json.loads(raw);require(len(audit['records'])==953,'audit_full_scope_changed');ids={r['id'] for r in audit['records']};require(len(ids)==953,'audit_ids_not_unique');return audit,ids,scope_path
def _open(database):return sqlite3.connect(str(database),timeout=0,isolation_level=None)
def run(database,audit,ids,root=base.R,workers=2,limit=2,publish=False,seconds=15,step_seconds=.25,validation=None,case_generator=generator.generate,artifact_writer=base.publish_artifacts):
    """Finite TOTAL limit; selection/render/immutable work is outside SQLite Tx."""
    require(1<=workers<=8 and limit>0,'finite_positive_total_limit_and_1_to_8_workers_required');root=Path(root);validation=validation or implementation(root);validation_policy,supervisor_policy,files=validation;stop=threading.Event();count=0;mutex=threading.Lock();results=[];attempted=set();run_id=uuid.uuid4().hex;scope=root/DIRECTORY/'runs'/run_id;scope.mkdir(parents=True,exist_ok=False)
    def slot(_):
        nonlocal count
        db=_open(database)
        try:
            while not stop.is_set():
                if draining(root):stop.set();break
                base.ensure(files)
                with mutex:
                    if count>=limit:break
                    selection=next_selection(db,audit,validation_policy,publish,ids-set(attempted))
                    if selection is None:break
                    attempted.add(selection['id']);count+=1
                try:lock=revision_lock(root,selection['key'])
                except BlockingIOError:continue
                try:
                    # Re-read the exact one ID after obtaining the process-death-safe lock.
                    selected=next_selection(db,{'records':[selection['audit_record']]},validation_policy,publish,{selection['id']})
                    if selected is None:continue
                    work=scope/selected['id']/uuid.uuid4().hex;work.parent.mkdir(parents=True,exist_ok=True);path,intent=prepare(db,selected,work,validation_policy,supervisor_policy,files,publish,root,case_generator,artifact_writer)
                    if stop.is_set() or draining(root):_status(path,'drained_prepared_unowned');stop.set();break
                    result=commit_prepared(db,path,intent,seconds,step_seconds,cancel_check=lambda:stop.is_set() or DRAIN.is_set());result.update(intent_file=str(path),work=str(work));
                    with mutex:results.append(result)
                    print(json.dumps(result),flush=True)
                except PendingIntent as error:
                    stop.set();atomic(root/'conversion'/CONTROL,canonical({'drain':True,'reason':str(error),'prepared_intent':error.path,'at':base.now()}));
                    with mutex:results.append({'state':error.state,'prepared_intent':error.path,'error':str(error),'owned_job_committed':False,'accepted':False,'confirmed_commit_receipt':getattr(error,'receipt',None)})
                    raise
                finally:lock.close()
        except BaseException as error:
            stop.set();atomic(root/'conversion'/CONTROL,canonical({'drain':True,'reason':repr(error),'at':base.now(),'owned_job_committed':False}));raise
        finally:db.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(slot,i) for i in range(workers)]
        while not all(future.done() for future in futures):
            if draining(root):stop.set()
            concurrent.futures.wait(futures,timeout=.2)
        errors=[]
        for future in futures:
            try:future.result()
            except BaseException as error:stop.set();errors.append(repr(error))
    summary={'version':VERSION,'validation_policy':validation_policy,'supervisor_policy':supervisor_policy,'total_attempts':count,'total_limit':limit,'workers':workers,'publish':publish,'watch':False,'results':results,'errors':errors,'drained':stop.is_set(),'scope':str(scope),'accepted':0,'model_calls':0};atomic(scope/'summary.json',canonical(summary));require(not errors,'supervisor_drained_after_typed_failure:'+str(errors));return summary
def private_smoke(root=base.R,limit=2):
    """Copy metadata rows only, render real remote clean sources, no canonical writes."""
    root=Path(root);validation=implementation(root);audit,ids,_=scope_audit(root);source=sqlite3.connect('file:'+str(root/'conversion/jobs.sqlite')+'?mode=ro',uri=True);selected=[]
    for _ in range(limit):
        item=next_selection(source,audit,validation[0],False,ids-{x['id'] for x in selected})
        require(item is not None,'not_enough_current_unattempted_page_metadata_cases');selected.append(item)
    directory=root/DIRECTORY/'private_smoke'/uuid.uuid4().hex;directory.mkdir(parents=True);database=directory/'jobs.sqlite';private=_open(database);tables=('jobs','processing_outcomes_v2','harness_queue','harness_queue_v2','harness_queue_v3',base.TABLE,base.HISTORY,'auto_quality_dirty_v2')
    for table in tables:
        schema=source.execute("select sql from sqlite_master where type='table' and name=?",(table,)).fetchone()
        if not schema:continue
        private.execute(schema[0])
        for item in selected:
            for row in source.execute('select * from '+table+' where id=?',(item['id'],)).fetchall():private.execute('insert into '+table+' values('+','.join('?' for _ in row)+')',row)
    triggers=source.execute("select sql from sqlite_master where type='trigger' and tbl_name='jobs'").fetchall()
    for (sql,) in triggers:private.execute(sql)
    private.execute('pragma journal_mode=WAL');initialize(private);private.close();before={x['id']:base.context(source,x['id'])[:3] for x in selected};summary=run(database,audit,{x['id'] for x in selected},root,workers=min(2,limit),limit=limit,publish=False,validation=validation);after={x['id']:base.context(source,x['id'])[:3] for x in selected};source.close();private=_open(database);restored={x['id']:base.context(private,x['id'])[:3] for x in selected};rows=private.execute('select id,state,claim_token from '+base.TABLE).fetchall();private.close();require(before==after==restored,'private_smoke_changed_canonical_or_private_job_queue_outcome');receipt={'at':base.now(),'ok':True,'canonical_job_outcome_queues_unchanged':True,'private_jobs_outcomes_queues_restored':True,'actual_job_triggers_copied':len(triggers),'scope':str(directory),'private_database':str(database),'selected_ids':[x['id'] for x in selected],'stage_rows':rows,'summary':summary,'published':0,'accepted':0,'model_calls':0,'owned_job_committed':False};atomic(directory/'receipt.json',canonical(receipt));return receipt
def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--private-smoke',action='store_true');parser.add_argument('--publish',action='store_true');parser.add_argument('--resume',type=Path);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--limit',type=int,default=2);parser.add_argument('--db-wait-seconds',type=float,default=15);parser.add_argument('--db-step-seconds',type=float,default=.25);args=parser.parse_args(argv)
    if args.private_smoke or not args.publish:
        require(not args.resume,'resume_requires_explicit_publish_and_reviewed_preflight');receipt=private_smoke(limit=args.limit);print(json.dumps({'private_smoke_receipt':receipt['scope']+'/receipt.json','ok':receipt['ok'],'published':0}),flush=True);return
    validation=implementation();preflight_path=base.W/PREFLIGHT;preflight=json.loads(preflight_path.read_text());require(preflight.get('root_reviewed_for_publish') is True and preflight.get('supervisor_policy')==validation[1] and preflight.get('validation_policy')==validation[0] and preflight.get('private_smoke_passed') is True,'exact_supervisor_requires_root_reviewed_preflight');coordinator=(base.W/'mermaid_page_metadata_v1b.lock').open('a+');fcntl.flock(coordinator,fcntl.LOCK_EX|fcntl.LOCK_NB);db=_open(base.W/'jobs.sqlite');initialize(db,args.db_wait_seconds);atomic(base.W/OWNER,canonical({'pid':os.getpid(),'policy':validation[1],'validation_policy':validation[0],'implementation':validation[2],'watch':False,'workers':args.workers,'total_limit':args.limit,'started_at':base.now(),'accepted':False,'model_calls':0}));
    for signum in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):signal.signal(signum,lambda *_:DRAIN.set())
    try:
        if args.resume:
            intent=verify_intent(args.resume);require(intent['publish'] is True and intent['root']==str(base.R.resolve()) and intent['validation_policy']==validation[0] and intent['supervisor_policy']==validation[1],'resume_requires_same_reviewed_production_intent');result=commit_prepared(db,args.resume,intent,seconds=args.db_wait_seconds,step_seconds=args.db_step_seconds)
        else:
            audit,ids,_=scope_audit();result=run(base.W/'jobs.sqlite',audit,ids,workers=args.workers,limit=args.limit,publish=True,seconds=args.db_wait_seconds,step_seconds=args.db_step_seconds,validation=validation)
        print(json.dumps(result),flush=True)
    finally:db.close();coordinator.close()
if __name__=='__main__':main()
