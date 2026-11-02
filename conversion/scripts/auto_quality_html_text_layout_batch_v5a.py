"""Finite candidate-only HTML layout producer. Default: dry run, total limit 2.

No acceptance, model API, model queue release or watcher. Only current idle
pending outcomes with an exact active-QA local-text failure may be claimed.
Each input revision/rule builds once; an explicit later publication reuses its
frozen validated dry-run candidate instead of running the builder again.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import traceback
import uuid

from durable_sqlite import begin,commit

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
OWNER='conversion/auto_quality_html_text_layout_v5'
STATE='auto_quality_html_layout_v5a_repairing'
TABLE='auto_quality_html_text_layout_candidates_v5a'
HISTORY='auto_quality_html_text_layout_history_v5a'
IDLE=('rendered','needs_quality_repair','harness_review_pending')
EQUIVALENT_QA4='bounded_deterministic_font_text_layout_and_native_quality_v4:d2f5d9ada102865c'
FROZEN_QA3_TRIGGER='source_execution_glyph_lineage_native_render_and_local_fidelity_v3:210bf4dbced804c5'
SNAPSHOT_COLUMNS='state,output_record,worker_pid,error,updated_at,input_record,input_manifest'
FROZEN={'html_text_layout_registration_v5.py':'e7f21cb65871853bfecb96d210668aaa7d8f17bb8646fe67bae8dd5ad1a0e551',
 'auto_quality_html_text_layout_profile_v5.py':'3885454323eda9ed8b75499e3725f78287f9df23431b449059db7a3cb909e9a4',
 'html_text_layout_candidate_v5.py':'8618fea49c80acc8dc7bb9c87f0e3627266b642f9e6fee9991c778c991e6988c',
 'html_text_whitespace_advance_v5.py':'8a0331c11c863d51231102adc876695a7c8dfedea63e169c52131e5c04b8c523',
 'html_actual_text_clip_alignment_v4.py':'f7d9b0a063b7cc5a0bc60ce79235af6f91afa3cb98182d691628857f9dfb4fda'}
DEPENDENCIES=tuple(FROZEN)+('auto_quality_html_text_layout_batch_v5a.py','html_text_layout_candidate_batch_v5a.py',
 'html_actual_text_registration.py','auto_quality_html_glyph_profile_v3.py','html_actual_text_alignment.py',
 'auto_quality_source_vector_v2.py','html_range_extractor_v2.py','html_dom_clip.js','auto_quality_common_v2.py',
 'auto_quality_common.py','auto_quality_canvas_repair.py','harness_canvas_contract.py','native_font_embedding_batch.py',
 'native_worker.py','svg_convert_v2.py','harness_context.py','harness_source_provenance.py','durable_sqlite.py')
sha=lambda blob:hashlib.sha256(blob).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+str(os.getpid())+'.layout-v5a.tmp');tmp.write_bytes(data);tmp.replace(path)


def implementation():
    directory=Path(__file__).resolve().parent
    paths=[directory/name for name in DEPENDENCIES]+[R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',
       W/'rendering_clipbox_strict/remote_render.py',W/'rendering_paintbounds_strict/remote_render.py',
       R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
    files={str(path):sha(path.read_bytes()) for path in paths}
    for name,digest in FROZEN.items():
        if files[str(directory/name)]!=digest:raise RuntimeError('Frozen layout API changed: '+name)
    return 'html_text_layout_candidate_batch_v5a:'+sha(json.dumps(files,sort_keys=True).encode())[:20],files


def ensure_implementation(policy,files):
    if implementation()!=(policy,files):raise RuntimeError('Pinned layout producer changed; use a new rule version')


def exists(db,table):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())


def init(db):
    begin(db)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT,owner_pid INT,claim_token TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,code_hash,image_hash,policy))')
        db.execute('CREATE TABLE IF NOT EXISTS '+HISTORY+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,attempt_token TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,code_hash,image_hash,policy,attempt_token))')
        commit(db)
    except BaseException:db.rollback();raise


def active_qa_policy():
    value=json.loads((W/'auto_quality_owner.json').read_text()).get('policy')
    if not isinstance(value,str) or not value:raise ValueError('Unknown current automatic QA policy')
    return value


def model_running(db,identifier):
    for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
        if not exists(db,table):continue
        columns={row[1] for row in db.execute('PRAGMA table_info('+table+')')}
        condition="state='running'"+(' OR worker_pid IS NOT NULL' if 'worker_pid' in columns else '')
        if db.execute('SELECT 1 FROM '+table+' WHERE id=? AND ('+condition+')',(identifier,)).fetchone():return True
    return False


def snapshot(db,identifier):
    return db.execute('SELECT '+SNAPSHOT_COLUMNS+' FROM jobs WHERE id=?',(identifier,)).fetchone()


def snapshot_hash(value):
    return sha(json.dumps(list(value),ensure_ascii=False,separators=(',',':')).encode())


def smoke_cache(key,prior):
    """Adopt a prior RO smoke only with this exact complete original snapshot."""
    path=W/'auto_quality_html_text_layout_v5a_smoke.json'
    if not path.is_file():return None
    report=json.loads(path.read_text())
    if report.get('policy')!=key[3] or not report.get('smoke'):return None
    for row in report.get('results',[]):
        if (row.get('id'),row.get('input_code_sha256'),row.get('input_image_sha256'))==tuple(key[:3]):
            if row.get('same_job_snapshot') is True and row.get('prior_snapshot_sha256')==snapshot_hash(prior):return row.get('cache')
    return None


def outcome_snapshot(db,identifier):
    if not exists(db,'processing_outcomes_v2'):return None
    return db.execute('SELECT id,category,format,source_code_hash,source_image_hash,status,reason,record,updated_at FROM processing_outcomes_v2 WHERE id=?',(identifier,)).fetchone()


def source_pending(db,identifier,prior):
    outcome=outcome_snapshot(db,identifier)
    if not outcome or outcome[5]!='pending':return False
    try:
        old=json.loads(prior[1]);original=json.loads(prior[5])
        job_kind=db.execute('SELECT category,format FROM jobs WHERE id=?',(identifier,)).fetchone()
        return (job_kind==('poster','html') and old['id']==old['source_pair_sha256']==identifier and old['source_format']=='html' and old['category']=='poster'
          and outcome[1:3]==('poster','html') and outcome[3:5]==(old['source_code_sha256'],old['source_image_sha256'])
          and original['code_sha256']==old['source_code_sha256'] and original['image_sha256']==old['source_image_sha256'])
    except (ValueError,KeyError,TypeError):return False


def trigger_policies(owner_policy,record=None):
    # Explicit family equivalence for repair triggering ONLY. New layout5
    # revisions require the current QA4 policy and its complete final gates.
    legacy=(owner_policy==EQUIVALENT_QA4 and (record is None or
        record.get('source_format')=='html' and record.get('category')=='poster' and 'html_text_layout_v5' not in record))
    return (owner_policy,FROZEN_QA3_TRIGGER) if legacy else (owner_policy,)


def matches_exception(db,identifier,code_hash,image_hash,qa_policy,record=None,failure_policy=None):
    failure_policy=failure_policy or qa_policy
    if failure_policy not in trigger_policies(qa_policy,record):return False
    return exists(db,'auto_quality_exceptions_v1') and db.execute('''SELECT 1 FROM auto_quality_exceptions_v1
       WHERE id=? AND code_hash=? AND image_hash=? AND policy=? AND state='pending'
       AND route='source_geometry_or_harness' AND reason LIKE '%local_text_line_ssim%' LIMIT 1''',
       (identifier,code_hash,image_hash,failure_policy)).fetchone() is not None


def stage_eligible(db,identifier,code,image,policy,publish):
    if not exists(db,TABLE):return True
    row=db.execute('SELECT state FROM '+TABLE+' WHERE id=? AND code_hash=? AND image_hash=? AND policy=?',(identifier,code,image,policy)).fetchone()
    return row is None or publish and row[0]=='validated_dry_run'


def select_candidate(db,policy,publish=False,ids=(),excluded=(),qa_policy=None):
    qa_policy=qa_policy or active_qa_policy()
    if not exists(db,'auto_quality_exceptions_v1') or not exists(db,'processing_outcomes_v2'):return None
    restriction=' AND e.id IN ('+','.join('?' for _ in ids)+')' if ids else ''
    triggers=trigger_policies(qa_policy);placeholders=','.join('?' for _ in triggers)
    rows=db.execute('''SELECT DISTINCT e.id,e.code_hash,e.image_hash,e.policy FROM auto_quality_exceptions_v1 e
       JOIN jobs j ON j.id=e.id JOIN processing_outcomes_v2 o ON o.id=j.id
       WHERE j.format='html' AND j.state IN ('rendered','needs_quality_repair','harness_review_pending')
       AND j.worker_pid IS NULL AND o.status='pending' AND o.category='poster' AND o.format='html'
       AND e.policy IN ('''+placeholders+''') AND e.state='pending' AND e.route='source_geometry_or_harness'
       AND e.reason LIKE '%local_text_line_ssim%' '''+restriction+' ORDER BY e.id,CASE WHEN e.policy=? THEN 0 ELSE 1 END',[*triggers,*ids,qa_policy]).fetchall()
    # Thin exception scan only; large output JSON is read once per relevant ID.
    snapshots={}
    for identifier,code,image,failure_policy in rows:
        if identifier in excluded or not stage_eligible(db,identifier,code,image,policy,publish) or model_running(db,identifier):continue
        if identifier not in snapshots:snapshots[identifier]=snapshot(db,identifier)
        prior=snapshots[identifier]
        if not prior or prior[0] not in IDLE or prior[2] is not None or not source_pending(db,identifier,prior):continue
        old=json.loads(prior[1])
        if failure_policy not in trigger_policies(qa_policy,old):continue
        if (old.get('code_sha256'),old.get('image_sha256'))==(code,image):return identifier,tuple(prior),qa_policy,failure_policy
    return None


def claim(db,selection,policy,publish=False,pid=None):
    identifier,prior,qa_policy=selection[:3];failure_policy=selection[3] if len(selection)>3 else qa_policy
    pid=pid or os.getpid();old=json.loads(prior[1]);key=(identifier,old['code_sha256'],old['image_sha256'],policy)
    begin(db)
    try:
        if (snapshot(db,identifier)!=prior or prior[0] not in IDLE or prior[2] is not None
              or not source_pending(db,identifier,prior) or model_running(db,identifier)
              or not matches_exception(db,identifier,*key[1:3],qa_policy,old,failure_policy) or not stage_eligible(db,*key,publish)):
            db.rollback();return None
        previous=db.execute('SELECT state,record,claim_token FROM '+TABLE+' WHERE id=? AND code_hash=? AND image_hash=? AND policy=?',key).fetchone()
        cached=smoke_cache(key,prior)
        if previous:
            prior_report=json.loads(previous[1]);cached=prior_report.get('cache')
            if previous[0]!='validated_dry_run' or not cached or prior_report.get('prior_snapshot_sha256')!=snapshot_hash(prior):db.rollback();return None
            db.execute('INSERT OR REPLACE INTO '+HISTORY+' VALUES(?,?,?,?,?,?,?)',(*key,previous[2] or uuid.uuid4().hex,previous[1],now()))
        token=uuid.uuid4().hex;stamp=now()
        record={'id':identifier,'key':list(key),'pid':pid,'token':token,'qa_policy':qa_policy,'qa_failure_policy':failure_policy,
                'trigger_equivalence_used':failure_policy!=qa_policy,
                'prior_snapshot':list(prior),'prior_outcome':list(outcome_snapshot(db,identifier)),
                'claimed_at':stamp,'accepted':False,'cached_candidate':cached}
        db.execute('INSERT OR REPLACE INTO '+TABLE+' VALUES(?,?,?,?,?,?,?,?,?)',(*key,'running',pid,token,json.dumps(record),stamp))
        db.execute('UPDATE jobs SET state=?,worker_pid=?,updated_at=? WHERE id=?',(STATE,pid,stamp,identifier));commit(db)
        record['owned_snapshot']=[STATE,prior[1],pid,prior[3],stamp,prior[5],prior[6]]
        return record
    except BaseException:db.rollback();raise


def _checked(path,digest):
    raw=Path(path).read_bytes()
    if sha(raw)!=digest:raise ValueError('Layout publication payload hash changed: '+str(path))
    return raw


def _owned(path):
    target=(R/path).resolve()
    if not target.is_relative_to((R/OWNER).resolve()):raise ValueError('Layout evidence outside owned workspace')
    return target


def _cached(claim_record):
    cache=claim_record['cached_candidate'];work=_owned(cache['work'])
    out=json.loads(_checked(work/'candidate_record.json',cache['candidate_record_sha256']))
    proof=json.loads(_checked(work/'evidence.json',cache['proof_sha256']))
    assert proof['policy']==claim_record['key'][3] and proof['input_code_sha256']==claim_record['key'][1] and proof['input_image_sha256']==claim_record['key'][2]
    _checked(work/'candidate.drawio',out['code_sha256']);_checked(work/'candidate.png',out['image_sha256'])
    return work,out,proof


def _summary(claim_record,work,out,proof,cached=False):
    report={'id':claim_record['id'],'at':now(),'policy':claim_record['key'][3],'qa_policy':claim_record['qa_policy'],
            'qa_failure_policy':claim_record.get('qa_failure_policy',claim_record['qa_policy']),
            'trigger_equivalence_used':claim_record.get('trigger_equivalence_used',False),
            'trigger_scope':'Repair trigger only; never acceptance. New layout5 revisions require complete current QA4 gates.',
            'input_code_sha256':claim_record['key'][1],'input_image_sha256':claim_record['key'][2],
            'prior_snapshot_sha256':snapshot_hash(claim_record['prior_snapshot']),
            'accepted':False,'published':False,'builder_reused_from_validated_cache':cached,
            'builder_state':proof.get('state'),'changed_cells':proof.get('changed_cells',[]),
            'unsupported_clip_objects':proof.get('unsupported_clip_objects',[]),'exact_object_rollbacks':proof.get('exact_object_rollbacks',proof.get('rollbacks',[])),
            'previous_candidate_retained':out is None}
    if out:
        report['cache']={'work':str(Path(work).relative_to(R)),
           'candidate_record_sha256':sha((Path(work)/'candidate_record.json').read_bytes()),
           'proof_sha256':sha((Path(work)/'evidence.json').read_bytes())}
        report.update(output_code_sha256=out['code_sha256'],output_image_sha256=out['image_sha256'])
    return report


def generate(claim_record,policy,files):
    ensure_implementation(policy,files)
    if claim_record.get('cached_candidate'):work,out,proof=_cached(claim_record);cached=True
    else:
        from html_text_layout_candidate_batch_v5a import build
        old=json.loads(claim_record['prior_snapshot'][1])
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
        work=R/OWNER/old['id']/(old['code_sha256']+'_'+old['image_sha256'][:16])/policy.rsplit(':',1)[-1]/stamp
        try:work,out,proof=build(old,policy,files,work=work);cached=False
        except Exception as exc:
            work.mkdir(parents=True,exist_ok=True)
            report={'id':claim_record['id'],'policy':policy,'qa_policy':claim_record['qa_policy'],
                    'state':'retained_prior_candidate','error':repr(exc)[:3000],'accepted':False,
                    'published':False,'previous_candidate_retained':True,'failed_workspace':str(work.relative_to(R))}
            atomic(work/'producer_error.json',(json.dumps({**report,'traceback':traceback.format_exc()},ensure_ascii=False,indent=2)+'\n').encode())
            ensure_implementation(policy,files)
            return work,None,report
    ensure_implementation(policy,files)
    return work,out,_summary(claim_record,work,out,proof,cached)


def recheck_resources(record):
    pairs=[]
    for field,digest in [('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_png','source_render_png_sha256'),('original_source_data','source_data_sha256')]:
        if record.get(field):pairs.append((record[field],record[digest]))
    for asset in record.get('original_vector_assets') or []:pairs.append((asset['file'],asset['sha256']))
    for asset in record.get('source_assets') or []:
        for field,digest in [('source','source_sha256'),('file','embedded_sha256'),('original_file','original_sha256')]:
            if asset.get(field) and asset.get(digest) and asset[field]!='embedded_original_html_asset':pairs.append((asset[field],asset[digest]))
    for font in (record.get('native_embedded_fonts') or [])+(record.get('fonts') or []):
        if font.get('file'):pairs.append((font['file'],font['sha256']))
        if font.get('original_file') and font.get('original_sha256'):pairs.append((font['original_file'],font['original_sha256']))
    for locator,digest in pairs:
        target=(R/locator).resolve();assert target.is_relative_to((R/'clean').resolve());_checked(target,digest)
    return len(pairs)


def publish_artifacts(claim_record,out,report,work):
    old=json.loads(claim_record['prior_snapshot'][1]);work=_owned(report['cache']['work'])
    assert work==Path(work).resolve()
    assert json.loads(_checked(work/'candidate_record.json',report['cache']['candidate_record_sha256']))==out
    proof=json.loads(_checked(work/'evidence.json',report['cache']['proof_sha256']))
    assert proof.get('candidate_checks_passed') is True and proof.get('accepted') is False and proof.get('published') is False
    assert proof['policy']==claim_record['key'][3] and (proof['input_code_sha256'],proof['input_image_sha256'])==tuple(claim_record['key'][1:3])
    assert (proof['output_code_sha256'],proof['output_image_sha256'])==(out['code_sha256'],out['image_sha256'])
    for key in ('id','source_pair_sha256','source_code_sha256','source_image_sha256','previous_candidate_archive','source_font_recovery_archive','html_actual_text_alignment'):
        assert out.get(key)==old.get(key),'Layout changed original/source/Harness lineage: '+key
    assert out['quality_state'].startswith('pending_') and not out.get('automatic_quality_policy')
    for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        target=(R/old[field]).resolve();assert target.is_relative_to((R/'clean').resolve());_checked(target,old[digest])
    recheck_resources(out)
    xml=_checked(work/'candidate.drawio',out['code_sha256']);png=_checked(work/'candidate.png',out['image_sha256'])
    from html_text_layout_registration_v5 import registration_record
    registration_record(out,_checked(R/old['original_reference'],old['source_image_sha256']),xml.decode())
    archive=_owned(out['html_text_layout_prior_pair_archive']);assert archive==work/'baseline_archive';archive.mkdir(exist_ok=True)
    for name,data in [('conversion.json',claim_record['prior_snapshot'][1].encode()),('diagram.drawio',_checked(R/old['code_file'],old['code_sha256'])),('image.png',_checked(R/old['image_file'],old['image_sha256']))]:
        path=archive/name
        if path.exists():assert path.read_bytes()==data,'Immutable layout baseline archive changed'
        else:atomic(path,data)
    for key,blob in [('code_file',xml),('image_file',png)]:
        target=(R/out[key]).resolve();assert target.parent==(R/old[key]).resolve().parent and target.is_relative_to((R/'clean').resolve()) and out[key]!=old[key]
        if target.exists():assert target.read_bytes()==blob,'Immutable versioned layout target differs'
        else:atomic(target,blob)
    from harness_source_provenance import resolve,validate_source_record,validate_frozen
    if out.get('source_provenance'):validate_frozen(out['source_provenance'])
    resolved,_,_=resolve(out);validate_source_record(resolved)
    atomic(work/'publish_intent.json',(json.dumps({'id':claim_record['id'],'token':claim_record['token'],'policy':proof['policy'],'out':out,'accepted':False},ensure_ascii=False,indent=2)+'\n').encode())
    atomic((R/old['code_file']).parent/'conversion.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())


def hold_idle_model(db,identifier):
    if not exists(db,'harness_queue_v3'):return None
    assert not model_running(db,identifier),'A paid running/owned queue must never be changed'
    db.execute("INSERT OR IGNORE INTO harness_queue_v3(id,state,attempts,priority) VALUES(?,'held_for_quality_v2',0,1000)",(identifier,))
    db.execute("UPDATE harness_queue_v3 SET state='held_for_quality_v2',heartbeat=? WHERE id=? AND state!='running' AND worker_pid IS NULL",(now(),identifier))
    row=db.execute('SELECT state,worker_pid FROM harness_queue_v3 WHERE id=?',(identifier,)).fetchone()
    assert row and row[0]!='running' and row[0]!='held_for_source_v5' and row[1] is None
    return row[0] # A user-policy trigger may impose a stronger policy hold.


def _restore(db,identifier,prior):
    db.execute('UPDATE jobs SET state=?,output_record=?,worker_pid=?,error=?,updated_at=?,input_record=?,input_manifest=? WHERE id=?',(*prior,identifier))


def finish(db,claim_record,report,out=None,work=None,publish=False,artifact_writer=publish_artifacts,qa_policy=None):
    identifier=claim_record['id'];key=tuple(claim_record['key']);prior=tuple(claim_record['prior_snapshot']);owned=tuple(claim_record['owned_snapshot'])
    pointer=(R/json.loads(prior[1])['code_file']).parent/'conversion.json';before_pointer=None;replacement=None;published=False
    begin(db)
    try:
        owner=db.execute('SELECT state,owner_pid,claim_token FROM '+TABLE+' WHERE id=? AND code_hash=? AND image_hash=? AND policy=?',key).fetchone()
        if owner!=('running',claim_record['pid'],claim_record['token']) or snapshot(db,identifier)!=owned:
            report.update(state='stale_revision_or_ownership',accepted=False)
        elif (outcome_snapshot(db,identifier)!=tuple(claim_record['prior_outcome']) or not source_pending(db,identifier,owned)
              or (qa_policy or active_qa_policy())!=claim_record['qa_policy']
              or not matches_exception(db,identifier,*key[1:3],claim_record['qa_policy'],json.loads(prior[1]),claim_record.get('qa_failure_policy'))):
            # A pending unchanged source may keep its single built cache until
            # the new QA policy independently reports a current local failure.
            cached=out is not None and report.get('cache') and source_pending(db,identifier,owned)
            _restore(db,identifier,prior);report.update(state='validated_dry_run' if cached else 'retained_prior_candidate',reason='Current outcome/QA/source admission changed; nothing published',accepted=False)
        elif model_running(db,identifier):
            _restore(db,identifier,prior);report.update(state='validated_dry_run' if out is not None else 'retained_prior_candidate',reason='Paid model became owned/running; no queue or publication write',accepted=False)
        elif out is not None and publish:
            before_pointer=pointer.read_bytes() if pointer.exists() else None
            if before_pointer is not None:assert json.loads(before_pointer)==json.loads(prior[1]),'Canonical metadata is not the owned prior revision'
            replacement=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()
            artifact_writer(claim_record,out,report,work)
            db.execute('UPDATE jobs SET state=?,output_record=?,worker_pid=NULL,error=?,updated_at=? WHERE id=?',
                       ('needs_quality_repair',json.dumps(out,ensure_ascii=False),'Deterministic text-layout pending candidate; full QA4 gates required',now(),identifier))
            report.update(state='published_candidate',held_model_state=hold_idle_model(db,identifier),accepted=False,published=True);published=True
        else:
            _restore(db,identifier,prior)
            report.update(state='validated_dry_run' if out is not None else 'no_change_required' if report.get('builder_state')=='no_nonworsening_layout_changes' else 'retained_prior_candidate',accepted=False,published=False)
        if owner==('running',claim_record['pid'],claim_record['token']):
            db.execute('UPDATE '+TABLE+' SET state=?,record=?,updated_at=? WHERE id=? AND code_hash=? AND image_hash=? AND policy=?',(report['state'],json.dumps(report,ensure_ascii=False),now(),*key))
        commit(db)
    except BaseException:
        db.rollback()
        if replacement is not None and snapshot(db,identifier)==owned and pointer.exists() and pointer.read_bytes()==replacement:
            if before_pointer is None:pointer.unlink()
            else:atomic(pointer,before_pointer)
        raise
    if work is not None:
        try:atomic(Path(work)/'producer_report.json',(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
        except OSError as exc:print(json.dumps({'id':identifier,'stage':'duplicate_audit_receipt_failed','sql_report_preserved':True,'error':str(exc)}),flush=True)
    return report['state']


def main(args):
    policy,files=implementation();qa=active_qa_policy();selected=[];excluded=set()
    if args.smoke:
        db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=2)
    else:
        lock=(W/'auto_quality_html_text_layout_v5a.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=sqlite3.connect(W/'jobs.sqlite',timeout=2);init(db)
        atomic(W/'auto_quality_html_text_layout_v5a_owner.json',(json.dumps({'pid':os.getpid(),'at':now(),'limit':args.limit,'publish':args.publish,'policy':policy,'qa_policy':qa,'accepted':0,'model_calls':0},indent=2)+'\n').encode())
    results=[]
    for _ in range(args.limit):
        selection=select_candidate(db,policy,args.publish,args.ids,excluded)
        if selection is None:break
        excluded.add(selection[0]);started=time.monotonic()
        current=({'id':selection[0],'key':[selection[0],json.loads(selection[1][1])['code_sha256'],json.loads(selection[1][1])['image_sha256'],policy],
                  'prior_snapshot':list(selection[1]),'qa_policy':selection[2],'qa_failure_policy':selection[3],
                  'trigger_equivalence_used':selection[3]!=selection[2],'cached_candidate':None} if args.smoke else claim(db,selection,policy,args.publish))
        if current is None:continue
        work=out=None
        try:
            work,out,report=generate(current,policy,files)
            ensure_implementation(policy,files)
            if args.smoke:
                report.update(state='nonpublishing_smoke_candidate' if out else 'no_change_required',same_job_snapshot=snapshot(db,current['id'])==tuple(current['prior_snapshot']),published=False)
            else:finish(db,current,report,out,work,args.publish)
        except Exception as exc:
            report={'id':current['id'],'policy':policy,'qa_policy':qa,'error':repr(exc)[:3000],'state':'retained_prior_candidate','accepted':False,'published':False,'previous_candidate_retained':True}
            if not args.smoke:
                try:finish(db,current,report,None,work,False)
                except Exception:report['recovery_required']=True;report['recovery_error']=traceback.format_exc()[-2000:]
        report['seconds']=round(time.monotonic()-started,3);results.append(report)
        print(json.dumps({'id':current['id'],'stage':report['state'],'changed_cells':report.get('changed_cells',[]),'unsupported_clip_objects':report.get('unsupported_clip_objects',[]),'error':report.get('error'),'accepted':False}),flush=True)
    db.close();summary={'at':now(),'policy':policy,'qa_policy':qa,'smoke':args.smoke,'publish':args.publish,'limit':args.limit,'processed':len(results),'results':results,'accepted':0,'model_calls':0}
    atomic(W/('auto_quality_html_text_layout_v5a_smoke.json' if args.smoke else 'auto_quality_html_text_layout_v5a_summary.json'),(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--limit',type=int,default=2)
    parser.add_argument('--publish',action='store_true');parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--id',dest='ids',action='append',default=[]);args=parser.parse_args()
    if not 1<=args.limit<=128 or args.smoke and args.publish:parser.error('limit must be 1..128; --smoke cannot publish')
    main(args)
