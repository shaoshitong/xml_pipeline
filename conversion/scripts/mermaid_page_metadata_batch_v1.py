"""Owned missing-page metadata candidates; explicit publish, never acceptance/API."""
import argparse,concurrent.futures,copy,hashlib,importlib.util,json,os,signal,sqlite3,time,uuid
from pathlib import Path
from durable_sqlite import begin,commit
from mermaid_page_metadata_candidate_v1 import canonical,checked,verify_metadata,generate

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';TABLE='mermaid_page_metadata_candidates_v1';HISTORY='mermaid_page_metadata_history_v1';STATE='mermaid_page_metadata_v1_repairing';IDLE=('rendered','needs_quality_repair','harness_review_pending');CONTROL='mermaid_page_metadata_v1_control.json';OWNER='mermaid_page_metadata_v1_owner.json';DRAIN=False;sha=lambda b:hashlib.sha256(b).hexdigest();now=lambda:time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def require(condition,reason):
    if not condition:raise ValueError(reason)
def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(data);tmp.replace(path)
def exists(db,table):return db.execute('select 1 from sqlite_master where type="table" and name=?',(table,)).fetchone() is not None
def snapshot(db,table,id):
    columns=[r[1] for r in db.execute('pragma table_info('+table+')')];rows=db.execute('select * from '+table+' where id=?',(id,)).fetchall();return {'columns':columns,'rows':[list(r) for r in rows]}
def queues(db,id):return {t:snapshot(db,t,id) for t in ('harness_queue','harness_queue_v2','harness_queue_v3') if exists(db,t)}
def model_owned(db,id):
    for table,rows in queues(db,id).items():
        for values in rows['rows']:
            row=dict(zip(rows['columns'],values))
            if row.get('state')=='running' or row.get('worker_pid') is not None:return True
    return False
def context(db,id):
    job=snapshot(db,'jobs',id);require(len(job['rows'])==1,'missing_job');row=dict(zip(job['columns'],job['rows'][0]));require(row['state'] in IDLE and row.get('worker_pid') is None and row.get('format')=='mermaid' and row.get('output_record'),'not_idle_mermaid_candidate');old=json.loads(row['output_record']);source=json.loads(row['input_record']);require(old.get('id')==old.get('source_pair_sha256')==source.get('pair_sha256')==id,'original_pair_identity_mismatch');require((row.get('format'),row.get('source'),row.get('category'))==(source.get('format'),source.get('source'),source.get('category'))==(old.get('source_format'),old.get('source'),old.get('category')),'authoritative_source_scope_changed');require((old['source_code_sha256'],old['source_image_sha256'])==(source['code_sha256'],source['image_sha256']),'authoritative_source_hash_changed');outcome=snapshot(db,'processing_outcomes_v2',id);require(len(outcome['rows'])==1,'missing_outcome');registry=dict(zip(outcome['columns'],outcome['rows'][0]));require(registry['status']=='pending' and (registry['category'],registry['format'],registry['source_code_hash'],registry['source_image_hash'])==(old['category'],old['source_format'],old['source_code_sha256'],old['source_image_sha256']),'outcome_not_pending_current_source');require(not model_owned(db,id),'model_queue_owned');return job,outcome,queues(db,id),old,source
def initialize(db):
    begin(db)
    try:
        db.execute('create table if not exists '+TABLE+'(id,code_hash,image_hash,source_code_hash,source_image_hash,policy,state,owner_pid,claim_token,record,updated_at,primary key(id,code_hash,image_hash,source_code_hash,source_image_hash,policy))');db.execute('create table if not exists '+HISTORY+'(id,claim_token primary key,record,updated_at)');commit(db)
    except BaseException:db.rollback();raise
def implementation(root=R):
    root=Path(root);from mermaid_page_metadata_candidate_v1 import _dependencies
    files=_dependencies(root);files[str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes());durable=Path(importlib.util.find_spec('durable_sqlite').origin);files[str(durable)]=sha(durable.read_bytes());files[str(root/'conversion/auto_quality_owner.json')]=sha((root/'conversion/auto_quality_owner.json').read_bytes());files[str(root/'conversion/mermaid_canvas_metadata_audit_v1.json')]=sha((root/'conversion/mermaid_canvas_metadata_audit_v1.json').read_bytes());return 'mermaid_missing_page_metadata_candidate_v1:'+sha(canonical(files))[:20],files
def ensure(files):require(all(sha(Path(p).read_bytes())==digest for p,digest in files.items()),'pinned_page_metadata_policy_changed')
def draining(root=R):
    path=Path(root)/'conversion'/CONTROL
    if DRAIN:return True
    if not path.exists():return False
    try:return json.loads(path.read_text()).get('drain') is True
    except (ValueError,OSError):return True
def request_drain(*_):
    global DRAIN
    DRAIN=True;atomic(W/CONTROL,canonical({'drain':True,'requested_at':now(),'requested_by_pid':os.getpid()}))
def select_candidate(db,audit,policy,publish=False):
    for item in audit['records']:
        id=item['id']
        try:job,outcome,q,old,source=context(db,id)
        except (ValueError,KeyError,TypeError):continue
        if (old['code_sha256'],old['image_sha256'],old['source_image_sha256'])!=(item['code_sha256'],item['image_sha256'],item['source_image_sha256']):continue
        key=(id,old['code_sha256'],old['image_sha256'],old['source_code_sha256'],old['source_image_sha256'],policy);previous=db.execute('select state from '+TABLE+' where id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?',key).fetchone()
        if previous is not None and previous[0] not in (('deferred_model_running','validated_dry_run') if publish else ('deferred_model_running',)):continue
        return id,key,job,outcome,q
    return None
def claim(db,audit,policy,files,pid=None,root=R,publish=False):
    if draining(root):return None
    pid=pid or os.getpid();ensure(files);begin(db)
    try:
        chosen=select_candidate(db,audit,policy,publish)
        if chosen is None:db.rollback();return None
        id,key,prior,outcome,q=chosen;current=context(db,id);require(current[0]==prior and current[1]==outcome and current[2]==q,'claim_full_snapshot_stolen');token=uuid.uuid4().hex;stamp=now();before=db.execute('select record from '+TABLE+' where id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?',key).fetchone()
        if before:db.execute('insert into '+HISTORY+' values(?,?,?,?)',(id,uuid.uuid4().hex,before[0],stamp))
        db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,pid,stamp,id));owned=snapshot(db,'jobs',id);record={'id':id,'key':list(key),'pid':pid,'token':token,'prior_job':prior,'owned_job':owned,'prior_outcome':outcome,'prior_queues':q,'policy':policy,'claimed_at':stamp,'implementation':files,'accepted':False};db.execute('insert or replace into '+TABLE+' values(?,?,?,?,?,?,?,?,?,?,?)',(*key,'running',pid,token,canonical(record).decode(),stamp));commit(db);return record
    except BaseException:db.rollback();raise
def _restore(db,current):
    prior=dict(zip(current['prior_job']['columns'],current['prior_job']['rows'][0]));db.execute('update jobs set state=?,worker_pid=?,error=?,updated_at=? where id=?',(prior['state'],prior.get('worker_pid'),prior.get('error'),prior['updated_at'],current['id']));require(snapshot(db,'jobs',current['id'])==current['prior_job'],'restore_changed_other_job_fields')
def _immutable(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    except FileExistsError:require(path.read_bytes()==data,'immutable_candidate_artifact_conflict:'+str(path))
def publish_artifacts(current,out,proof,work,root=R):
    root=Path(root);work=Path(work);prior=dict(zip(current['prior_job']['columns'],current['prior_job']['rows'][0]));old=json.loads(prior['output_record']);require(proof.get('candidate_checks_passed') is True and proof.get('accepted') is False,'unverified_candidate_cannot_publish');before=checked(root,old['code_file'],old['code_sha256']).decode();stored=checked(root,old['image_file'],old['image_sha256']);checked(root,old['original_source_code'],old['source_code_sha256']);checked(root,old['original_reference'],old['source_image_sha256']);after=(work/'candidate.drawio').read_bytes().decode();png=(work/'candidate.png').read_bytes();verify_metadata(before,after,proof['metadata_delta']);require(sha(after.encode())==proof['output_code_sha256'] and sha(png)==proof['output_image_sha256'],'candidate_artifact_hash_changed');require((work/'proof.json').read_bytes()==canonical(proof),'candidate_proof_changed');from auto_quality_common_v4 import resource_checks
    require(json.loads((work/'candidate_record.json').read_text())==out,'candidate_record_changed');require(json.loads((work/'baseline_record.json').read_text())==old and json.loads((work/'source_record.json').read_text())==json.loads(prior['input_record']),'proof_baseline_or_source_snapshot_changed');resource_checks(root,out,after,checked(root,old['original_reference'],old['source_image_sha256']));proof_bytes=canonical(proof);proof_path=work/'proof.json';relative_proof=str(proof_path.relative_to(root));archive=work/'baseline_archive'
    for name,data in [('conversion.json',prior['output_record'].encode()),('input_record.json',prior['input_record'].encode()),('diagram.drawio',before.encode()),('image.png',stored)]:_immutable(archive/name,data)
    target=(root/old['code_file']).parent/'mermaid_page_metadata_v1'/current['policy'].rsplit(':',1)[-1]/current['token'];require(target.resolve().is_relative_to((root/'clean').resolve()),'new_candidate_not_clean');out=copy.deepcopy(out);out.update(code_file=str((target/'diagram.drawio').relative_to(root)),image_file=str((target/'image.png').relative_to(root)),mermaid_page_metadata_prior_pair_archive=str(archive.relative_to(root)));out['mermaid_page_metadata_v1'].update(proof_file=relative_proof,proof_sha256=sha(proof_bytes),prior_record_sha256=sha(prior['output_record'].encode()),policy=current['policy']);out['source_coverage']={'ok':True,'profile':proof['source_after']['profile'],'audit':relative_proof,'audit_sha256':sha(proof_bytes)}
    font=old.get('native_font_validation') or {}
    if font.get('ok') is True and font.get('output_code_sha256')==old['code_sha256'] and proof.get('all_current_fonts_custom') is True:
        out['native_font_validation']={'ok':True,'output_code_sha256':out['code_sha256'],'physical_faces_preserved':True,'native_pixels_unchanged':True,'native_pixel_comparison_scope':'Fresh before/after XML on the same current runtime; stored PNG is separately preserved and may differ.','stored_png_equals_fresh':proof['old_stored_png_equals_fresh'],'audit':relative_proof,'evidence_sha256':sha(proof_bytes),'page_metadata_only_font_equivalence':{'input_code_sha256':old['code_sha256'],'actual_font_signature_sha256':proof['actual_font_signature_sha256'],'actual_text_signature_sha256':proof['actual_text_signature_sha256'],'all_other_xml_bytes_unchanged':True},'prior_validation':font}
    for key in ('id','source_pair_sha256','source_code_sha256','source_image_sha256','original_source_code','original_reference','previous_candidate_archive'):require(out.get(key)==old.get(key),'source_or_harness_archive_lineage_changed:'+key)
    _immutable(target/'diagram.drawio',after.encode());_immutable(target/'image.png',png);_immutable(target/'conversion.json',canonical(out));atomic(work/'publication_intent.json',canonical({'id':current['id'],'token':current['token'],'old_record_sha256':sha(prior['output_record'].encode()),'new_record_sha256':sha(canonical(out)),'out':out,'accepted':False}));
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:checked(root,old[key],old[digest])
    resource_checks(root,out,after,checked(root,old['original_reference'],old['source_image_sha256']));return out
def finish(db,current,out,proof,work,publish=False,root=R,artifact_writer=publish_artifacts):
    try:ensure(current['implementation']);policy_current=True
    except (ValueError,OSError):policy_current=False
    begin(db);where='id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?';key=tuple(current['key']);report={'id':current['id'],'policy':current['policy'],'claim':current,'work':str(work),'accepted':False,'published':False}
    try:
        owned=db.execute('select state,owner_pid,claim_token from '+TABLE+' where '+where,key).fetchone();ours=owned==('running',current['pid'],current['token']);job_same=snapshot(db,'jobs',current['id'])==current['owned_job']
        if not ours or not job_same:report['state']='stale_revision_or_ownership'
        elif not policy_current:_restore(db,current);report['state']='policy_changed_retained_prior'
        elif model_owned(db,current['id']):_restore(db,current);report['state']='deferred_model_running'
        elif snapshot(db,'processing_outcomes_v2',current['id'])!=current['prior_outcome'] or queues(db,current['id'])!=current['prior_queues']:_restore(db,current);report['state']='outcome_or_queue_snapshot_changed'
        elif out is None or not publish:_restore(db,current);report['state']='validated_dry_run' if out is not None else 'deferred_retained_prior';report['proof']=proof
        else:
            finalized=artifact_writer(current,out,proof,work,root);ensure(current['implementation']);require(finalized.get('quality_state','').startswith('pending_'),'candidate_cannot_be_accepted');require(finalized['code_sha256']==proof['output_code_sha256'] and finalized['image_sha256']==proof['output_image_sha256'],'published_pair_hash_mismatch');old=json.loads(dict(zip(current['prior_job']['columns'],current['prior_job']['rows'][0]))['output_record']);require(all(finalized.get(k)==old.get(k) for k in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256','original_source_code','original_reference','previous_candidate_archive')),'published_original_source_lineage_changed');db.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=NULL,error=?,updated_at=? where id=?',(canonical(finalized).decode(),'Missing page attributes repaired by byte-preserving/fresh-native equivalence; complete QA4b required',now(),current['id']))
            for table in current['prior_queues']:
                columns=current['prior_queues'][table]['columns']
                if 'worker_pid' in columns:db.execute('update '+table+' set state="held_for_quality_v2" where id=? and state!="running" and worker_pid is NULL',(current['id'],))
                else:db.execute('update '+table+' set state="held_for_quality_v2" where id=? and state!="running"',(current['id'],))
            report.update(state='published_pending_candidate',published=True,out=finalized)
        if ours:db.execute('update '+TABLE+' set state=?,record=?,updated_at=? where '+where,(report['state'],canonical(report).decode(),now(),*key))
        commit(db);return report
    except BaseException:db.rollback();raise
def worker(args,policy,files,audit):
    db=sqlite3.connect(W/'jobs.sqlite',timeout=30,isolation_level=None);done=0
    try:
        while not draining() and (args.limit==0 or done<args.limit):
            current=claim(db,audit,policy,files,root=R,publish=args.publish)
            if current is None:
                if not args.watch:break
                time.sleep(2);continue
            row=dict(zip(current['prior_job']['columns'],current['prior_job']['rows'][0]));work=W/'mermaid_page_metadata_v1'/current['id']/(current['key'][1]+'_'+current['key'][2][:16])/policy.rsplit(':',1)[-1]/current['token'];work.parent.mkdir(parents=True,exist_ok=True)
            try:out,proof=generate(json.loads(row['output_record']),json.loads(row['input_record']),work,R);ensure(files);result=finish(db,current,out,proof,work,args.publish,R)
            except Exception as error:
                proof={'candidate_checks_passed':False,'error':repr(error),'accepted':False};result=finish(db,current,None,proof,work,False,R)
            print(json.dumps(result,ensure_ascii=False),flush=True);done+=1
    finally:db.close()
    return done
def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=2);parser.add_argument('--limit',type=int,default=2);parser.add_argument('--watch',action='store_true');parser.add_argument('--publish',action='store_true');args=parser.parse_args(argv);require(1<=args.workers<=8 and args.limit>=0 and (args.limit>0 or args.watch),'invalid_worker_or_explicit_watch_limit');policy,files=implementation();audit=json.loads((W/'mermaid_canvas_metadata_audit_v1.json').read_text());db=sqlite3.connect(W/'jobs.sqlite',timeout=30,isolation_level=None);initialize(db);db.close();atomic(W/OWNER,canonical({'pid':os.getpid(),'policy':policy,'implementation':files,'workers':args.workers,'limit_per_worker':args.limit,'watch':args.watch,'publish_candidates':args.publish,'started_at':now(),'accepted':False}));signal.signal(signal.SIGUSR1,request_drain)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:list(pool.map(lambda _:worker(args,policy,files,audit),range(args.workers)))
if __name__=='__main__':main()
