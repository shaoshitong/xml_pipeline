"""Terminal outcome publication with crypto and durable decisions outside SQL.

The frozen planner determines support semantics. The writer transaction only
compares complete row sets, owner guards and stable filesystem identities, then
updates one outcome row. Source, jobs, queues and histories are never changed.
"""
import argparse,copy,hashlib,json,os,re,secrets,sqlite3,stat,sys,time
from pathlib import Path
import bounded_program_terminal_planner_v1 as planner
import program_terminal_outcomes_v1 as frozen
from bounded_sqlite_transaction_v1 import BusyBudget,is_busy

POLICY='bounded_program_terminal_outcome_registry_only_v2'
DIRECTORY='conversion/program_terminal_outcomes_v2'
TABLE='processing_outcomes_v2'
MARKER='program_terminal_outcome_v2'
REGISTRY_COLUMNS=frozen.REGISTRY_COLUMNS
Refused=frozen.Refused
require=frozen.require
canonical=frozen.canonical
sha=frozen.sha
_SEAL=object()


def begin(db,seconds=30):
    budget=BusyBudget(seconds,5);budget.begin(db);return budget.diagnostics()


def commit(db,seconds=30):
    budget=BusyBudget(seconds,5);budget.commit(db);return budget.diagnostics()


def _registry(db,identifier):return frozen._registry(db,identifier)


def _names(db,table):
    require(re.fullmatch('[A-Za-z0-9_]+',table) is not None,'unknown_table_identifier')
    return db.execute('PRAGMA main.table_info('+table+')').fetchall()


def _db_snapshot(db,identifier):
    """All columns and relevant complete row sets; no file or content reads."""
    schema=db.execute("SELECT type,name,tbl_name,rootpage,sql FROM main.sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    tables={};registry=None;job=None
    for kind,table,_,_,_ in schema:
        if kind!='table':continue
        info=_names(db,table);columns=[row[1] for row in info]
        if 'id' not in columns:continue
        if table not in ['jobs',TABLE,'auto_quality_audits_v1','auto_quality_exceptions_v1'] and 'state' not in columns and not any(name in columns for name in ['worker_pid','owner_pid']):continue
        primary=[row[1] for row in sorted(info,key=lambda row:row[5]) if row[5]];order=primary or columns
        require(all(re.fullmatch('[A-Za-z0-9_]+',name) for name in columns),'unknown_column_identifier')
        rows=db.execute('SELECT * FROM main.'+table+' WHERE id=? ORDER BY '+','.join(order),(identifier,)).fetchall()
        value={'columns':columns,'rows':[list(row) for row in rows]};tables[table]=value
        if table=='jobs':job=value
        if table==TABLE:registry=value
    require(job and len(job['rows'])==1 and registry and len(registry['rows'])==1,'missing_full_job_or_registry_snapshot')
    return {'schema_version':db.execute('PRAGMA main.schema_version').fetchone()[0],'schema':[list(row) for row in schema],'tables':tables}


def _owners(snapshot,plan):
    historical=[]
    for table,value in snapshot['tables'].items():
        columns=value['columns'];owners=[name for name in ['worker_pid','owner_pid'] if name in columns]
        for row in value['rows']:
            item=dict(zip(columns,row));state=item.get('state')
            if table in ['harness_queue','harness_queue_v2','harness_queue_v3']:require(state!='running' and item.get('worker_pid') is None,'model_owned_or_running')
            if table not in ['jobs','auto_quality_audits_v1','auto_quality_exceptions_v1']:require(state not in ['running','producing'],'deterministic_stage_running:'+table)
            if table=='jobs' or not any(item.get(name) is not None for name in owners):continue
            allowed=False
            if table==planner.STAGE and state=='unsupported_source' and item.get('worker_pid') is None and type(item.get('owner_pid')) is int and item['owner_pid']>0 and plan['cas'].get('terminal_snapshot_sha256'):
                relevant=tuple(item[name] for name in planner.STAGE_COLUMNS.split(','));allowed=(planner.json_sha(relevant)==plan['cas']['terminal_snapshot_sha256'] and plan['evidence'].get('stage_table')==table)
            require(allowed,'nonterminal_or_unverified_stage_owner:'+table)
            historical.append({'table':table,'state':'unsupported_source','owner_pid':item['owner_pid'],'terminal_snapshot_sha256':plan['cas']['terminal_snapshot_sha256'],'historical_receipt_not_live_lease':True})
    return historical


def _capture(db,plan,config):
    require(not db.in_transaction,'preparation_requires_no_existing_transaction');db.execute('BEGIN')
    try:
        require(planner.revalidate(db,plan,config,check_files=False)=='current','stale_or_ineligible')
        snapshot=_db_snapshot(db,plan['id']);historical=_owners(snapshot,plan);db.rollback();return snapshot,historical
    except BaseException:
        if db.in_transaction:db.rollback()
        raise


def _stat_tuple(info):
    return {'dev':info.st_dev,'inode':info.st_ino,'size':info.st_size,'mtime_ns':info.st_mtime_ns,'ctime_ns':info.st_ctime_ns,'mode':info.st_mode}


def file_identity(root,logical):
    root=Path(root).resolve();path=Path(logical);path=path if path.is_absolute() else root/path;resolved=path.resolve(strict=True);target=resolved.stat();require(stat.S_ISREG(target.st_mode),'witness_not_regular_file');nodes={}
    for route in [path,resolved]:
        parts=route.parts;prefix=Path(parts[0])
        for part in parts[1:]:
            prefix=prefix/part;info=prefix.lstat()
            if prefix==resolved and not stat.S_ISLNK(info.st_mode):continue
            if stat.S_ISLNK(info.st_mode):nodes[str(prefix)]={**_stat_tuple(info),'link':os.readlink(prefix)}
            elif stat.S_ISDIR(info.st_mode):nodes[str(prefix)]={'dev':info.st_dev,'inode':info.st_ino,'mode':info.st_mode}
            else:nodes[str(prefix)]=_stat_tuple(info)
    return {'logical':str(path),'resolve':str(resolved),'target':_stat_tuple(target),'resolution_nodes':nodes}


def file_witness(root,path,digest=None):
    before=file_identity(root,path);fd=os.open(before['logical'],os.O_RDONLY);hasher=hashlib.sha256();count=0
    try:
        opened=_stat_tuple(os.fstat(fd));require(opened==before['target'],'file_changed_before_hash_read')
        while True:
            block=os.read(fd,1024*1024)
            if not block:break
            count+=len(block);hasher.update(block)
        after_open=_stat_tuple(os.fstat(fd))
    finally:os.close(fd)
    after=file_identity(root,path);actual=hasher.hexdigest();require(before==after and opened==after_open and count==opened['size'],'file_changed_during_crypto_preparation');require(digest is None or actual==digest,'payload_or_proof_hash_mismatch:'+str(path));return {'identity':before,'sha256':actual}


def _check_identities(root,witnesses):
    for witness in witnesses.values():require(file_identity(root,witness['identity']['logical'])==witness['identity'],'file_identity_changed_after_crypto_preparation:'+witness['identity']['logical'])


def _logical_aliases(record,root,resolved):
    result={}
    def visit(value):
        if isinstance(value,dict):
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,str) and 0<len(value)<4096 and '\0' not in value:
            try:
                path=Path(root)/value;target=path.resolve(strict=True)
                if str(target) in resolved and target.is_file():result[str(path)]=resolved[str(target)]
            except (OSError,ValueError):pass
    visit(record);return result


def _read_receipt(root,receipt):
    require(re.fullmatch('[0-9a-f]{64}',receipt.get('sha256','')) is not None,'invalid_decision_digest');relative=Path(receipt['file']);expected=Path(DIRECTORY)
    require(not relative.is_absolute() and '..' not in relative.parts and relative.parent.parent==expected and re.fullmatch('[0-9a-f]{64}',relative.parent.name) and relative.name=='decision.'+receipt['sha256']+'.json','invalid_decision_locator');path=Path(root).resolve()/relative;info=path.lstat();require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o444,'decision_must_be_immutable_regular_file');require(path.resolve(strict=True).is_relative_to(Path(root).resolve()/expected),'decision_outside_owned_directory');witness=file_witness(root,relative,receipt['sha256']);payload=path.read_bytes();require(sha(payload)==receipt['sha256'],'decision_read_hash_mismatch');document=json.loads(payload);require(canonical(document)==payload and document.get('plan',{}).get('id')==relative.parent.name,'noncanonical_or_misidentified_decision');return document,payload,witness


def _owned_directory(root,identifier):
    descriptor=os.open(Path(root).resolve(),os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
    try:
        for name in (*Path(DIRECTORY).parts,identifier):
            try:os.mkdir(name,0o755,dir_fd=descriptor)
            except FileExistsError:pass
            child=os.open(name,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0),dir_fd=descriptor)
            try:os.fsync(descriptor);os.fsync(child)
            except BaseException:os.close(child);raise
            os.close(descriptor);descriptor=child
        result=descriptor;descriptor=None;return result
    finally:
        if descriptor is not None:os.close(descriptor)


def _write_receipt(root,receipt,payload):
    require(sha(payload)==receipt['sha256'],'decision_payload_digest_mismatch');relative=Path(receipt['file']);require(relative.parent.parent==Path(DIRECTORY) and re.fullmatch('[0-9a-f]{64}',relative.parent.name) and relative.name=='decision.'+receipt['sha256']+'.json','invalid_decision_locator');directory=_owned_directory(root,relative.parent.name);temporary='.'+relative.name+'.'+secrets.token_hex(16)+'.tmp';fd=None
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600,dir_fd=directory);remaining=memoryview(payload)
        while remaining:
            count=os.write(fd,remaining);require(count>0,'short_decision_write');remaining=remaining[count:]
        os.fsync(fd);os.fchmod(fd,0o444);os.fsync(fd);os.close(fd);fd=None
        try:os.link(temporary,relative.name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
        except FileExistsError:
            _,stored,_=_read_receipt(root,receipt);require(stored==payload,'immutable_decision_content_conflict')
        os.fsync(directory)
    finally:
        if fd is not None:os.close(fd)
        try:os.unlink(temporary,dir_fd=directory);os.fsync(directory)
        except FileNotFoundError:pass
        finally:os.close(directory)


def _outcome_record(plan,receipt):
    evidence=copy.deepcopy(plan['evidence']);require(evidence.get('deterministic_recovery_permitted') is True and evidence.get('abandonment_is_not_conversion_success') is True,'missing_recovery_or_nonsuccess_contract');evidence[MARKER]={'policy':POLICY,'decision':receipt,'commit_nonce':receipt['commit_nonce'],'prior_registry_snapshot_sha256':plan['cas']['registry_snapshot_sha256'],'active_quality_policy':plan['cas']['active_policy'],'scope':'Unsupported by the current frozen bounded verified program; not intrinsic drawio inexpressibility.'};return 'current_frozen_program:'+evidence['reason_code']+'; '+evidence['reason_detail'],canonical(evidence).decode()


def _configuration_signature(config):
    return canonical({name:config.get(name) for name in ['root','policy','owner_sha256','execution_policy','execution_owner_sha256','model_allowlist','pinned_files','equivalences','model_policy_sha256']})


def prepare_decision(db,plan,config,publish=False):
    require(not db.in_transaction and db.row_factory is None,'preparation_requires_fresh_default_connection');require(type(publish) is bool,'publish_must_be_explicit_boolean');require(isinstance(plan,dict) and re.fullmatch('[0-9a-f]{64}',plan.get('id','')),'invalid_original_identifier');require(not db.execute('SELECT 1 FROM sqlite_temp_master LIMIT 1').fetchone(),'temporary_schema_not_allowed');require(all(row[1] in ['main','temp'] for row in db.execute('PRAGMA database_list')),'attached_database_not_allowed');started=time.monotonic();plan=copy.deepcopy(plan);fresh=frozen._fresh(db,plan,config);snapshot,historical=_capture(db,plan,config);registry=_registry(db,plan['id']);require(registry is not None and registry[4]=='pending','not_pending_registry');require(planner.json_sha(registry)==plan['cas']['registry_snapshot_sha256'],'registry_changed_during_preparation');files=dict(plan['cas']['proof_files']);files['conversion/auto_quality_owner.json']=plan['cas']['active_owner_sha256']
    if plan['cas'].get('execution_owner_sha256'):files['conversion/tikz_execution_candidate_watch_v1_owner.json']=plan['cas']['execution_owner_sha256']
    for module in [sys.modules[__name__],planner,frozen,sys.modules[BusyBudget.__module__]]:files[str(Path(module.__file__).resolve())]=sha(Path(module.__file__).read_bytes())
    witnesses={str(path):file_witness(config['root'],path,digest) for path,digest in sorted(files.items())};resolved={witness['identity']['resolve']:witness['sha256'] for witness in witnesses.values()};job=snapshot['tables']['jobs'];record=json.loads(job['rows'][0][job['columns'].index('output_record')])
    for path,digest in _logical_aliases(record,config['root'],resolved).items():
        if path not in witnesses:witnesses[path]=file_witness(config['root'],path,digest)
    current,current_historical=_capture(db,plan,config);require(current==snapshot and historical==current_historical,'database_changed_during_crypto_preparation');_check_identities(config['root'],witnesses);nonce=secrets.token_hex(16);created=planner.now();document={'version':2,'created_at':created,'writer_policy':POLICY,'writer_sha256':sha(Path(__file__).read_bytes()),'planner_sha256':sha(Path(planner.__file__).read_bytes()),'legacy_helper_sha256':sha(Path(frozen.__file__).read_bytes()),'plan':copy.deepcopy(plan),'plan_sha256':sha(canonical(plan)),'prior_outcome':dict(zip(REGISTRY_COLUMNS,registry)),'historical_terminal_receipt_owners':historical,'commit_nonce':nonce,'preparation':{'db_cas_snapshots':snapshot,'file_witnesses':witnesses},'scope':'Current frozen verified program support only; not intrinsic drawio inexpressibility.','deterministic_recovery_permitted':True,'abandonment_is_not_conversion_success':True,'new_model_calls':0};payload=canonical(document);digest=sha(payload);receipt={'file':str(Path(DIRECTORY)/plan['id']/('decision.'+digest+'.json')),'sha256':digest,'plan_sha256':document['plan_sha256'],'created_at':created,'commit_nonce':nonce};reason,raw=_outcome_record(fresh,receipt);expected=tuple(list(registry[:4])+['abandoned',reason,raw,created])
    if publish:
        _write_receipt(config['root'],receipt,payload);stored,stored_payload,witness=_read_receipt(config['root'],receipt);require(stored_payload==payload,'durable_decision_verification_failed');witnesses={**witnesses,'decision:'+receipt['sha256']:witness}
    return {'_seal':_SEAL,'plan':plan,'snapshot':snapshot,'historical':historical,'witnesses':witnesses,'registry':registry,'expected':expected,'receipt':receipt,'document':document,'publish':publish,'config_signature':_configuration_signature(config),'preparation_seconds':time.monotonic()-started}


def _probe_commit(db,prepared):
    return _registry(db,prepared['plan']['id'])==prepared['expected']


def _already_applied(db,plan,config):
    registry=_registry(db,plan['id'])
    if registry is None:return {'state':'preserved_missing_registry','id':plan['id'],'applied':False,'accepted':False}
    if registry[4]=='pending':return None
    if registry[4]!='abandoned':return {'state':'preserved_'+str(registry[4]),'id':plan['id'],'applied':False,'accepted':False}
    try:
        evidence=json.loads(registry[6]);receipt=evidence[MARKER]['decision'];document,payload,_=_read_receipt(config['root'],receipt);require(document['version']==2 and document['writer_policy']==POLICY and document['writer_sha256']==sha(Path(__file__).read_bytes()) and document['planner_sha256']==sha(Path(planner.__file__).read_bytes()),'different_writer_or_planner');require(document['plan_sha256']==receipt['plan_sha256']==sha(canonical(plan)) and canonical(document['plan'])==canonical(plan),'different_terminal_plan');require(document['commit_nonce']==receipt['commit_nonce']==evidence[MARKER]['commit_nonce'],'different_commit_nonce');prior=tuple(document['prior_outcome'][key] for key in REGISTRY_COLUMNS);require(planner.json_sha(prior)==plan['cas']['registry_snapshot_sha256'],'prior_registry_snapshot_changed');reason,raw=_outcome_record(plan,receipt);require(registry==tuple(list(prior[:4])+['abandoned',reason,raw,receipt['created_at']]),'changed_abandoned_registry');stored=document['preparation']['db_cas_snapshots']['tables']['jobs'];names=stored['columns'];require([list(row) for row in db.execute('SELECT '+','.join(names)+' FROM jobs WHERE id=?',(plan['id'],))]==stored['rows'],'changed_job_after_decision');return {'state':'already_applied','id':plan['id'],'applied':False,'accepted':False,'idempotent':True,'decision':receipt,'policy':POLICY}
    except (ValueError,KeyError,TypeError,OSError):return {'state':'preserved_abandoned','id':plan['id'],'applied':False,'accepted':False,'idempotent':False}


def _apply_prepared(db,prepared,config):
    require(prepared.get('_seal') is _SEAL,'unverified_preparation_bundle');base={'id':prepared['plan']['id'],'policy':POLICY,'applied':False,'accepted':False,'decision':prepared['receipt'],'preparation_seconds':prepared['preparation_seconds']};acquired=None;committing=False;updated=False;begin_diagnostics=None
    try:
        # This historical PGF guard hashes its recorded row. Do it before the
        # writer lock; exact equality of every current row/schema below proves
        # the verified ownership semantics remained unchanged.
        require(_owners(prepared['snapshot'],prepared['plan'])==prepared['historical'],'unknown_owner_changed')
        if prepared['publish']:begin_diagnostics=begin(db,seconds=config.get('writer_begin_seconds',30))
        else:db.execute('BEGIN')
        acquired=time.monotonic();require(_configuration_signature(config)==prepared['config_signature'],'configuration_changed');require(_db_snapshot(db,base['id'])==prepared['snapshot'],'full_database_compare_and_swap_changed');_check_identities(config['root'],prepared['witnesses'])
        if not prepared['publish']:
            seconds=time.monotonic()-acquired;db.rollback();return {**base,'state':'dry_run_current','would_apply':True,'decision_file_written':False,'transaction_kind':'readonly_deferred','transaction_seconds':seconds,'writer_lock_held_seconds':0.0}
        reason,raw=prepared['expected'][5:7];stamp=prepared['expected'][7];before_changes=db.total_changes;where=' AND '.join(name+' IS ?' for name in REGISTRY_COLUMNS);cursor=db.execute('UPDATE '+TABLE+' SET status="abandoned",reason=?,record=?,updated_at=? WHERE id=? AND '+where,(reason,raw,stamp,base['id'],*prepared['registry']));cursor.fetchall();require(cursor.rowcount==1,'registry_complete_compare_and_swap_lost');updated=True;require(db.total_changes-before_changes==1,'trigger_or_other_table_side_effect_refused');require(_registry(db,base['id'])==prepared['expected'],'registry_after_update_differs_from_exact_decision');_check_identities(config['root'],prepared['witnesses']);before_commit=time.monotonic();committing=True;commit_diagnostics=commit(db,seconds=config.get('writer_commit_seconds',30));finished=time.monotonic();return {**base,'state':'abandoned','applied':True,'decision_file_written':True,'commit_nonce':prepared['receipt']['commit_nonce'],'deterministic_recovery_permitted':True,'jobs_queues_source_and_histories_unchanged':True,'transaction_kind':'writer_immediate','lock_body_seconds':before_commit-acquired,'commit_seconds':finished-before_commit,'writer_lock_held_seconds':finished-acquired,'begin_diagnostics':begin_diagnostics,'commit_diagnostics':commit_diagnostics}
    except BaseException as error:
        was_active=db.in_transaction
        if was_active:db.rollback()
        if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
        recovered=False
        if committing and updated and not was_active:
            try:recovered=_probe_commit(db,prepared)
            except sqlite3.Error:pass
        if recovered:return {**base,'state':'abandoned','applied':True,'decision_file_written':True,'commit_nonce':prepared['receipt']['commit_nonce'],'commit_receipt_recovered':True,'error_after_commit':repr(error),'writer_lock_held_seconds':time.monotonic()-acquired,'jobs_queues_source_and_histories_unchanged':True}
        unknown=bool(committing and updated and not was_active)
        return {**base,'state':'commit_outcome_unknown' if unknown else 'failed_rolled_back','error':repr(error),'decision_may_be_unreferenced':prepared['publish'],'may_have_committed':unknown,'transaction_rolled_back':was_active,'writer_lock_held_seconds':time.monotonic()-acquired if acquired is not None else 0.0}


def apply(db,plan,config,publish=False):
    require(type(publish) is bool,'publish_must_be_explicit_boolean');require(not db.in_transaction,'writer_requires_no_existing_transaction');require(db.row_factory is None,'writer_requires_default_tuple_row_factory');plan=copy.deepcopy(plan);require(isinstance(plan,dict) and re.fullmatch('[0-9a-f]{64}',plan.get('id','')),'invalid_original_identifier');canonical(plan)
    existing=_already_applied(db,plan,config)
    if existing is not None:return existing
    try:prepared=prepare_decision(db,plan,config,publish)
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as error:return {'id':plan['id'],'state':'preparation_refused','policy':POLICY,'applied':False,'accepted':False,'error':repr(error),'no_writer_transaction_opened':True}
    return _apply_prepared(db,prepared,config)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=planner.ROOT);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--limit',type=int,default=16);parser.add_argument('--publish',action='store_true');args=parser.parse_args(argv);require(1<=args.limit<=64,'finite_limit_must_be_1_to_64');report=json.loads(args.report.read_text());ids=[plan['id'] for plan in report.get('plans',[])];require(len(ids)==len(set(ids)),'duplicate_report_identifiers');config=planner.configuration(args.root);database=args.root/'conversion/jobs.sqlite';db=sqlite3.connect(str(database) if args.publish else 'file:'+str(database)+'?mode=ro',uri=not args.publish,timeout=0);results=[]
    try:
        for identifier in ids[:args.limit]:
            try:plan=planner.prepare(db,identifier,config);result=apply(db,plan,config,publish=args.publish)
            except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as error:result={'id':identifier,'state':'fresh_prepare_refused','applied':False,'accepted':False,'error':repr(error)}
            results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:db.close()
    return 2 if any(result['state'] in ['failed_rolled_back','commit_outcome_unknown'] for result in results) else 0


if __name__=='__main__':sys.exit(main())
