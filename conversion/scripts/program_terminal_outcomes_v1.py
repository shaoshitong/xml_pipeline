"""CAS-guarded explicit outcomes for the frozen bounded program, never success.

Default dry run. Only processing_outcomes_v2 may change; source/candidate jobs,
queues, attempts and histories remain intact. Complete plans live in immutable,
hash-named receipts. Unsupported describes this program's current verified rules,
not an intrinsic inability to express the source in drawio.
"""
import argparse,copy,hashlib,json,os,re,secrets,sqlite3,stat,sys
from pathlib import Path
import bounded_program_terminal_planner_v1 as planner
from durable_sqlite import begin,commit

POLICY='bounded_program_terminal_outcome_registry_only_v1'
TABLE='processing_outcomes_v2'
DIRECTORY='conversion/program_terminal_outcomes_v1'
REGISTRY_COLUMNS=('category','format','source_code_hash','source_image_hash','status','reason','record','updated_at')
sha=lambda b:hashlib.sha256(b).hexdigest()

class Refused(ValueError):pass

def require(condition,reason):
    if not condition:raise Refused(reason)

def canonical(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()

def _registry(db,identifier):
    return db.execute('select '+','.join(REGISTRY_COLUMNS)+' from '+TABLE+' where id=?',(identifier,)).fetchone()

def _semantics(plan):
    value=copy.deepcopy(plan);value.pop('prepared_at',None);return value

def _fresh(db,plan,config):
    fresh=planner.prepare(db,plan['id'],config)
    require(canonical(_semantics(fresh))==canonical(_semantics(plan)),'supplied_plan_differs_from_fresh_frozen_preparation')
    return fresh

def _owner_guard(db,plan):
    """Reject unknown owner leases, retaining one CAS-bound historical receipt.

    The frozen PGF worker keeps owner_pid after terminal completion. Its exact
    unsupported_source receipt is already reconstructed and CAS-bound by the
    planner, so this one PID is provenance, not a live lease. Every other
    non-NULL owner/worker in a stage remains a refusal.
    """
    evidence=plan['evidence'];cas=plan['cas'];identifier=plan['id'];historical=[]
    for (table,) in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'").fetchall():
        if not re.fullmatch(r'[A-Za-z0-9_]+',table) or table=='jobs':continue
        columns={row[1] for row in db.execute('pragma table_info('+table+')')}
        owners=[name for name in ('worker_pid','owner_pid') if name in columns]
        if not {'id','state'}<=columns or not owners:continue
        rows=db.execute('select * from '+table+' where id=? and ('+' or '.join(name+' is not NULL' for name in owners)+')',(identifier,)).fetchall()
        names=[row[1] for row in db.execute('pragma table_info('+table+')')]
        for row in rows:
            record=dict(zip(names,row));allowed=False
            if table==planner.STAGE and record.get('state')=='unsupported_source' and record.get('worker_pid') is None and isinstance(record.get('owner_pid'),int) and record['owner_pid']>0 and cas.get('terminal_snapshot_sha256'):
                snapshot=tuple(record[name] for name in planner.STAGE_COLUMNS.split(','))
                allowed=planner.json_sha(snapshot)==cas['terminal_snapshot_sha256'] and evidence.get('stage_table')==table
            require(allowed,'nonterminal_or_unverified_stage_owner:'+table)
            historical.append({'table':table,'state':'unsupported_source','owner_pid':record.get('owner_pid'),'terminal_snapshot_sha256':cas['terminal_snapshot_sha256'],'historical_receipt_not_live_lease':True})
    return historical

def _receipt(plan,registry,config,historical):
    document={'version':1,'created_at':planner.now(),'writer_policy':POLICY,'writer_sha256':sha(Path(__file__).read_bytes()),'planner_sha256':sha(Path(planner.__file__).read_bytes()),'plan':copy.deepcopy(plan),'plan_sha256':sha(canonical(plan)),'prior_outcome':dict(zip(REGISTRY_COLUMNS,registry)),'historical_terminal_receipt_owners':historical,'scope':'Current frozen verified program support only; not intrinsic drawio inexpressibility.','deterministic_recovery_permitted':True,'abandonment_is_not_conversion_success':True,'new_model_calls':0}
    payload=canonical(document);digest=sha(payload);relative=str(Path(DIRECTORY)/plan['id']/('decision.'+digest+'.json'))
    return {'file':relative,'sha256':digest,'plan_sha256':document['plan_sha256'],'created_at':document['created_at']},payload

def _outcome_record(plan,receipt):
    evidence=copy.deepcopy(plan['evidence']);require(evidence.get('deterministic_recovery_permitted') is True and evidence.get('abandonment_is_not_conversion_success') is True,'missing_recovery_or_nonsuccess_contract');evidence['program_terminal_outcome_v1']={'policy':POLICY,'decision':receipt,'prior_registry_snapshot_sha256':plan['cas']['registry_snapshot_sha256'],'active_quality_policy':plan['cas']['active_policy'],'scope':'Unsupported by the current frozen bounded verified program; not intrinsic drawio inexpressibility.'};reason='current_frozen_program:'+evidence['reason_code']+'; '+evidence['reason_detail'];return reason,canonical(evidence).decode()

def _read_receipt(root,receipt):
    require(re.fullmatch(r'[0-9a-f]{64}',receipt.get('sha256','')) is not None,'invalid_decision_digest')
    relative=Path(receipt['file']);expected=Path(DIRECTORY)
    require(not relative.is_absolute() and '..' not in relative.parts and len(relative.parts)==len(expected.parts)+2 and relative.parts[:len(expected.parts)]==expected.parts and re.fullmatch('[0-9a-f]{64}',relative.parent.name) is not None and relative.name=='decision.'+receipt['sha256']+'.json','invalid_decision_locator')
    root=Path(root).resolve();path=root/relative;require(path.resolve(strict=True).is_relative_to(root/expected),'decision_outside_owned_directory')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        before=os.fstat(fd);require(stat.S_ISREG(before.st_mode),'decision_not_regular_file');parts=[]
        while True:
            data=os.read(fd,1024*1024)
            if not data:break
            parts.append(data)
        after=os.fstat(fd)
    finally:os.close(fd)
    require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'decision_changed_while_reading')
    payload=b''.join(parts);require(sha(payload)==receipt['sha256'],'decision_hash_mismatch');document=json.loads(payload);require(canonical(document)==payload,'decision_not_canonical_json');require(document.get('plan',{}).get('id')==relative.parent.name,'decision_sample_directory_identity_mismatch');return document,payload

def _owned_directory(root,identifier):
    """Open/create each owned directory without following intermediate symlinks."""
    descriptor=os.open(Path(root).resolve(),os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
    try:
        for name in (*Path(DIRECTORY).parts,identifier):
            try:os.mkdir(name,0o755,dir_fd=descriptor)
            except FileExistsError:pass
            child=os.open(name,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0),dir_fd=descriptor)
            # Persist newly created ancestry before an outcome can reference it.
            try:os.fsync(descriptor);os.fsync(child)
            except BaseException:os.close(child);raise
            os.close(descriptor);descriptor=child
        result=descriptor;descriptor=None;return result
    finally:
        if descriptor is not None:os.close(descriptor)

def _write_receipt(root,receipt,payload):
    """Link a fully fsynced temporary inode once; never overwrite a decision."""
    root=Path(root).resolve();path=root/receipt['file'];require(sha(payload)==receipt['sha256'],'decision_payload_digest_mismatch');relative=Path(receipt['file']);require(relative.parent.parent==Path(DIRECTORY) and re.fullmatch('[0-9a-f]{64}',relative.parent.name) is not None and relative.name=='decision.'+receipt['sha256']+'.json','invalid_decision_locator');directory_fd=_owned_directory(root,relative.parent.name);temporary='.'+path.name+'.'+secrets.token_hex(16)+'.tmp';fd=None
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600,dir_fd=directory_fd)
        remaining=memoryview(payload)
        while remaining:
            count=os.write(fd,remaining);require(count>0,'short_decision_write');remaining=remaining[count:]
        os.fsync(fd);os.fchmod(fd,0o444);os.fsync(fd);os.close(fd);fd=None
        try:os.link(temporary,path.name,src_dir_fd=directory_fd,dst_dir_fd=directory_fd,follow_symlinks=False)
        except FileExistsError:
            _,existing=_read_receipt(root,receipt);require(existing==payload,'existing_decision_content_conflict')
        os.fsync(directory_fd)
        _,stored=_read_receipt(root,receipt);require(stored==payload,'decision_durable_verification_failed')
    finally:
        if fd is not None:os.close(fd)
        try:os.unlink(temporary,dir_fd=directory_fd);os.fsync(directory_fd)
        except FileNotFoundError:pass
        finally:os.close(directory_fd)

def _duplicate(db,plan,registry,config):
    try:
        current=json.loads(registry[6]);receipt=current['program_terminal_outcome_v1']['decision'];document,_=_read_receipt(config['root'],receipt)
        require(document['writer_policy']==POLICY and document['plan_sha256']==sha(canonical(plan))==receipt['plan_sha256'],'different_terminal_decision')
        require(canonical(document['plan'])==canonical(plan),'different_terminal_plan')
        require(document['created_at']==receipt.get('created_at'),'decision_creation_timestamp_changed')
        reason,record=_outcome_record(plan,receipt);prior=tuple(document['prior_outcome'][key] for key in REGISTRY_COLUMNS)
        require(planner.json_sha(prior)==plan['cas']['registry_snapshot_sha256'],'decision_prior_registry_changed')
        require(registry==tuple(list(prior[:4])+['abandoned',reason,record,receipt['created_at']]),'abandoned_registry_row_changed_since_decision')
        row=db.execute('select '+planner.JOB_COLUMNS+' from jobs where id=?',(plan['id'],)).fetchone()
        require(row is not None and planner.json_sha(row)==plan['cas']['job_snapshot_sha256'],'current_job_changed_since_abandonment')
        require(all(current.get(key)==plan['evidence'].get(key) for key in ('id','code_sha256','image_sha256','source_code_sha256','source_image_sha256')),'current_outcome_identity_differs_from_decision')
        return {'state':'already_applied','id':plan['id'],'applied':False,'idempotent':True,'decision':receipt,'accepted':False}
    except (ValueError,KeyError,TypeError,OSError):return {'state':'preserved_abandoned','id':plan['id'],'applied':False,'idempotent':False,'accepted':False}

def apply(db,plan,config,publish=False):
    """Fresh-prepare then full CAS under one immediate transaction per plan.

    Failed transactions may leave an immutable *unreferenced* receipt. It is not
    an applied decision, and is never deleted here because another successful
    retry may have reused it. Dry runs create no files and update no rows.
    """
    require(type(publish) is bool,'publish_must_be_explicit_boolean');require(not db.in_transaction,'writer_requires_no_existing_transaction');require(db.row_factory is None,'writer_requires_default_tuple_row_factory');plan=copy.deepcopy(plan);require(isinstance(plan,dict) and re.fullmatch(r'[0-9a-f]{64}',plan.get('id','')) is not None,'invalid_original_identifier');canonical(plan)
    identifier=plan['id'];base={'id':identifier,'applied':False,'accepted':False,'policy':POLICY};fresh=None;preparation_error=None
    registry=_registry(db,identifier)
    if registry is not None and registry[4]=='pending':
        try:fresh=_fresh(db,plan,config)
        except (ValueError,OSError,KeyError,TypeError) as error:preparation_error=str(error)
    receipt=None;updated=False;committing=False
    try:
        begin(db,seconds=config.get('writer_begin_seconds',30));registry=_registry(db,identifier)
        if registry is None:db.rollback();return {**base,'state':'preserved_missing_registry'}
        if registry[4]=='abandoned':result=_duplicate(db,plan,registry,config);db.rollback();return result
        if registry[4]!='pending':db.rollback();return {**base,'state':'preserved_'+str(registry[4])}
        require(fresh is not None,'fresh_prepare_refused:'+str(preparation_error));require(planner.revalidate(db,plan,config,check_files=True)=='current','stale_or_ineligible');require(identifier not in config.get('model_allowlist',[]),'authorized_localized_model_case_reserved');historical=_owner_guard(db,plan)
        receipt,payload=_receipt(plan,registry,config,historical)
        if not publish:db.rollback();return {**base,'state':'dry_run_current','would_apply':True,'decision':receipt,'decision_file_written':False,'deterministic_recovery_permitted':True}
        _write_receipt(config['root'],receipt,payload)
        require(planner.revalidate(db,plan,config,check_files=True)=='current','changed_during_decision_publication');_owner_guard(db,plan)
        reason,raw=_outcome_record(fresh,receipt);stamp=receipt['created_at'];before_changes=db.total_changes
        where=' and '.join(column+' is ?' for column in REGISTRY_COLUMNS)
        cursor=db.execute('update '+TABLE+' set status="abandoned",reason=?,record=?,updated_at=? where id=? and '+where,(reason,raw,stamp,identifier,*registry));cursor.fetchall();require(cursor.rowcount==1,'registry_complete_compare_and_swap_lost');updated=True
        require(db.total_changes-before_changes==1,'trigger_or_other_table_side_effect_refused')
        expected=tuple(list(registry[:4])+['abandoned',reason,raw,stamp]);require(_registry(db,identifier)==expected,'registry_after_update_differs_from_exact_decision')
        # Source, policy and proof files must still match immediately before commit.
        proofs={}
        for path,digest in plan['cas']['proof_files'].items():planner.read_file(config['root'],path,proofs,digest)
        planner.read_file(config['root'],'conversion/auto_quality_owner.json',proofs,plan['cas']['active_owner_sha256'])
        if plan['cas'].get('execution_owner_sha256'):planner.read_file(config['root'],'conversion/tikz_execution_candidate_watch_v1_owner.json',proofs,plan['cas']['execution_owner_sha256'])
        _,stored=_read_receipt(config['root'],receipt);require(stored==payload,'decision_changed_before_commit');committing=True;commit(db,seconds=config.get('writer_commit_seconds',30))
        return {**base,'state':'abandoned','applied':True,'decision':receipt,'decision_file_written':True,'deterministic_recovery_permitted':True,'jobs_queues_source_and_histories_unchanged':True}
    except BaseException as error:
        was_active=db.in_transaction
        if was_active:db.rollback()
        if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
        unknown=bool(committing and updated and not was_active)
        return {**base,'state':'commit_outcome_unknown' if unknown else 'failed_rolled_back','error':repr(error),'decision':receipt,'decision_may_be_unreferenced':receipt is not None,'may_have_committed':unknown,'transaction_rolled_back':was_active}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=planner.ROOT);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--limit',type=int,default=16);parser.add_argument('--publish',action='store_true');args=parser.parse_args(argv);require(1<=args.limit<=64,'finite_limit_must_be_1_to_64');report=json.loads(args.report.read_text());identifiers=[plan['id'] for plan in report.get('plans',[])];require(len(set(identifiers))==len(identifiers),'duplicate_report_identifiers');config=planner.configuration(args.root);db=sqlite3.connect(str(args.root/'conversion/jobs.sqlite'),timeout=30,isolation_level=None);results=[]
    try:
        for identifier in identifiers[:args.limit]:
            try:plan=planner.prepare(db,identifier,config);result=apply(db,plan,config,publish=args.publish)
            except (ValueError,OSError,KeyError,TypeError) as error:result={'id':identifier,'state':'fresh_prepare_refused','applied':False,'error':repr(error),'accepted':False}
            results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:db.close()
    return 2 if any(r['state'] in ('failed_rolled_back','commit_outcome_unknown') for r in results) else 0

if __name__=='__main__':sys.exit(main())
