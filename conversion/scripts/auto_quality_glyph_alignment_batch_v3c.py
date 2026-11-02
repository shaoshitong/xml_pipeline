"""Revision-owned actual-Range glyph repair candidates, never automatic acceptance.

Default: two workers, finite two cases per worker. --watch explicitly watches.
Only current pending HTML poster local_text failures without a prior glyph or
layout-v5 revision are eligible. --limit bounds EACH worker. --publish
is required to publish versioned clean payloads; otherwise only audited proposals
are written and the exact prior job state is restored. Runtime deployment is
separate from importing this module or running its isolated state tests.
"""
import argparse
import collections
import concurrent.futures
import datetime
import fcntl
import hashlib
import io
import json
import os
import signal
from pathlib import Path
import sqlite3
import time
import traceback
import uuid
import xml.etree.ElementTree as E
from durable_sqlite import begin, commit

R=Path('/backup/shaoshitong/img2code_20261029')
W=R/'conversion'
STATE='auto_quality_html_glyph_v3c_repairing'
TABLE='auto_quality_html_glyph_candidates_v3c'
HISTORY='auto_quality_html_glyph_history_v3c'
IDLE=('rendered','needs_quality_repair','harness_review_pending')
SNAPSHOT_COLUMNS='state,output_record,worker_pid,error,updated_at,input_record,input_manifest'
DEPENDENCIES=('auto_quality_glyph_alignment_batch_v3c.py','auto_quality_glyph_candidate_generate_v3b.py','html_actual_text_registration.py','auto_quality_html_glyph_profile_v3.py','html_actual_text_alignment.py','auto_quality_source_vector_v2.py','html_range_extractor_v2.py','html_dom_clip.js','auto_quality_common_v2.py','auto_quality_common.py','auto_quality_canvas_repair.py','harness_canvas_contract.py','native_font_embedding_batch.py','native_text_clip.py','native_clip_reference_box.py','native_worker.py','durable_sqlite.py','svg_batch.py','svg_convert_v2.py','harness_context.py','harness_source_provenance.py')
PRIOR_TABLE='auto_quality_html_glyph_candidates_v3b'
FROZEN_GENERATOR_SHA256='fc9bb37996b4d8bb658ba92b8334205bdb2456fa4d752ca52d48a3cdbae95e79'
DRAIN=False
sha=lambda blob:hashlib.sha256(blob).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+str(os.getpid())+'.glyphqa.tmp')
    tmp.write_bytes(blob);tmp.replace(path)


def implementation():
    directory=Path(__file__).resolve().parent
    paths=[directory/name for name in DEPENDENCIES]
    paths += [R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',W/'rendering_paintbounds_strict/remote_render.py',W/'rendering_clipbox_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
    missing=[str(path) for path in paths if not path.is_file()]
    if missing:raise RuntimeError('Missing pinned repair implementation files: '+repr(missing))
    files={str(path):sha(path.read_bytes()) for path in paths}
    assert files[str(directory/'auto_quality_glyph_candidate_generate_v3b.py')]==FROZEN_GENERATOR_SHA256,'Frozen glyph-v3b generator changed'
    return 'html_actual_range_glyph_candidate_v3c:'+sha(json.dumps(files,sort_keys=True).encode())[:20],files


def ensure_implementation(policy,files):
    current,current_files=implementation()
    if (current,current_files)!=(policy,files):raise RuntimeError('Pinned HTML repair implementation changed; deploy a versioned worker')


def exists(db,table):
    return db.execute('select 1 from sqlite_master where type="table" and name=?',(table,)).fetchone() is not None


def draining():
    if DRAIN:return True
    control=W/'auto_quality_glyph_alignment_v3c_control.json'
    if not control.exists():return False
    try:return json.loads(control.read_text()).get('drain') is True
    except (OSError,ValueError):return True


def request_drain(*_):
    global DRAIN
    DRAIN=True
    control=W/'auto_quality_glyph_alignment_v3c_control.json'
    try:settings=json.loads(control.read_text()) if control.exists() else {}
    except (OSError,ValueError):settings={}
    settings.update(drain=True,requested_at=now(),requested_by_pid=os.getpid())
    atomic(control,(json.dumps(settings,indent=2)+'\n').encode())


def outcome_pending(db,id,old=None):
    if not exists(db,'processing_outcomes_v2'):return False
    row=db.execute('select status,category,format,source_code_hash,source_image_hash from processing_outcomes_v2 where id=?',(id,)).fetchone()
    if not row or row[0]!='pending':return False
    return old is None or row[1:]==(old.get('category'),old.get('source_format'),old.get('source_code_sha256'),old.get('source_image_sha256'))


def prior_attempted(db,id,code,image):
    if not exists(db,PRIOR_TABLE):return False
    # A running abandoned old ledger also requires explicit root recovery;
    # never steal it solely because a new coordinator has a different hash.
    return db.execute('select 1 from '+PRIOR_TABLE+" where id=? and code_hash=? and image_hash=? and state!='deferred_model_running' limit 1",(id,code,image)).fetchone() is not None


def init(db):
    begin(db)
    db.execute('create table if not exists '+TABLE+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT,owner_pid INTEGER,claim_token TEXT,record TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy))')
    db.execute('create table if not exists '+HISTORY+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,attempt_token TEXT,record TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy,attempt_token))')
    commit(db)


def model_running(db,id):
    for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
        if not exists(db,table):continue
        columns={row[1] for row in db.execute('pragma table_info('+table+')')}
        condition="state='running'"+(' or worker_pid is not NULL' if 'worker_pid' in columns else '')
        if db.execute('select 1 from '+table+' where id=? and ('+condition+')',(id,)).fetchone():return True
    return False


def snapshot(db,id):
    return db.execute('select '+SNAPSHOT_COLUMNS+' from jobs where id=?',(id,)).fetchone()


def matches_exception(db,id,code_hash,image_hash):
    if not exists(db,'auto_quality_exceptions_v1'):return False
    return db.execute('''select 1 from auto_quality_exceptions_v1 e where e.id=? and e.code_hash=? and e.image_hash=? and e.state='pending' and e.reason like '%local_text_line_ssim%' limit 1''',(id,code_hash,image_hash)).fetchone() is not None


def stage_eligible(db,id,code_hash,image_hash,policy,publish):
    row=db.execute('select state from '+TABLE+' where id=? and code_hash=? and image_hash=? and policy=?',(id,code_hash,image_hash,policy)).fetchone()
    return row is None or row[0]=='deferred_model_running' or publish and row[0]=='validated_dry_run'


def select_candidate(db,policy,publish=False,ids=()):
    if draining() or not exists(db,'auto_quality_exceptions_v1') or not exists(db,'processing_outcomes_v2'):return None
    restriction=' and e.id in ('+','.join('?' for _ in ids)+')' if ids else ''
    rows=db.execute('''select distinct e.id,e.code_hash,e.image_hash from auto_quality_exceptions_v1 e
      join jobs j on j.id=e.id join processing_outcomes_v2 o on o.id=j.id
      where j.format='html' and j.state in ('rendered','needs_quality_repair','harness_review_pending')
      and j.worker_pid is NULL and o.status='pending' and o.category='poster' and o.format='html'
      and e.state='pending' and e.reason like '%local_text_line_ssim%' '''+restriction+' order by e.id',list(ids)).fetchall()
    cached={}
    for id,code,image in rows:
        if prior_attempted(db,id,code,image) or model_running(db,id) or not stage_eligible(db,id,code,image,policy,publish):continue
        if id not in cached:cached[id]=snapshot(db,id)
        prior=cached[id]
        if not prior or prior[2] is not None or prior[0] not in IDLE:continue
        old=json.loads(prior[1])
        if ('html_text_layout_v5' in old or 'html_actual_text_alignment' in old or old.get('source_format')!='html'
            or old.get('category')!='poster' or (old.get('code_sha256'),old.get('image_sha256'))!=(code,image) or not outcome_pending(db,id,old)):continue
        return id,tuple(prior)
    return None


def claim(db,selection,policy,publish=False,pid=None):
    id,prior=selection;pid=pid or os.getpid();old=json.loads(prior[1]);key=(id,old['code_sha256'],old['image_sha256'],policy)
    begin(db)
    try:
        if draining() or snapshot(db,id)!=prior or prior[0] not in IDLE or prior[2] is not None or model_running(db,id) or not matches_exception(db,id,*key[1:3]) or not stage_eligible(db,*key,publish) or not outcome_pending(db,id,old) or prior_attempted(db,id,*key[1:3]):
            db.rollback();return None
        if old.get('source_format')!='html' or old.get('category')!='poster' or 'html_actual_text_alignment' in old or 'html_text_layout_v5' in old:db.rollback();return None
        previous=db.execute('select record,claim_token from '+TABLE+' where id=? and code_hash=? and image_hash=? and policy=?',key).fetchone()
        if previous:
            db.execute('insert or replace into '+HISTORY+' values(?,?,?,?,?,?,?)',(*key,previous[1] or uuid.uuid4().hex,previous[0],now()))
        token=uuid.uuid4().hex;claimed_at=now();claim_record={'id':id,'key':list(key),'pid':pid,'token':token,'prior_snapshot':list(prior),'claimed_at':claimed_at,'accepted':False}
        db.execute('insert or replace into '+TABLE+' values(?,?,?,?,?,?,?,?,?)',(*key,'running',pid,token,json.dumps(claim_record),claimed_at))
        db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,pid,claimed_at,id));commit(db)
        claim_record['owned_snapshot']=[STATE,prior[1],pid,prior[3],claimed_at,prior[5],prior[6]]
        return claim_record
    except Exception:
        db.rollback();raise


def generate(claim_record,policy,files):
    ensure_implementation(policy,files)
    from auto_quality_glyph_candidate_generate_v3b import generate as candidate_generate
    result=candidate_generate(claim_record,policy,files)
    ensure_implementation(policy,files)
    return result


def _checked(path,digest):
    data=Path(path).read_bytes()
    if sha(data)!=digest:raise ValueError('Publication payload hash mismatch: '+str(path))
    return data


def recheck_resource_files(record):
    """Recheck preserved clean dependencies immediately before pointer publication."""
    expected=[]
    for key,digest in [('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_png','source_render_png_sha256'),('original_source_data','source_data_sha256')]:
        if record.get(key):expected.append((record[key],record[digest]))
    for asset in record.get('original_vector_assets') or []:
        expected.append((asset['file'],asset['sha256']))
    for asset in record.get('source_assets') or []:
        for key,digest in [('source','source_sha256'),('file','embedded_sha256'),('original_file','original_sha256')]:
            if asset.get(key) and asset.get(digest) and asset[key]!='embedded_original_html_asset':expected.append((asset[key],asset[digest]))
    for font in (record.get('native_embedded_fonts') or [])+(record.get('fonts') or []):
        if font.get('file'):expected.append((font['file'],font['sha256']))
        if font.get('original_file') and font.get('original_sha256'):expected.append((font['original_file'],font['original_sha256']))
    for relative,digest in expected:
        path=(R/relative).resolve()
        assert path.is_relative_to((R/'clean').resolve()),'Preserved dependency moved outside clean'
        _checked(path,digest)
    return len(expected)


def publish_artifacts(claim_record,out,proof,work):
    old=json.loads(claim_record['prior_snapshot'][1])
    assert proof.get('candidate_checks_passed') is True and not proof.get('accepted'),'Only verified non-accepted candidates may publish'
    assert proof['policy']==claim_record['key'][3]
    for key in ('id','source_code_sha256','source_image_sha256','source_pair_sha256'):
        if key in old:assert out.get(key)==old[key],'Original source identity changed'
    assert proof['output_code_sha256']==out['code_sha256'] and proof['output_image_sha256']==out['image_sha256']
    assert out['source_coverage']['ok'] is True and out['native_font_validation']['output_code_sha256']==out['code_sha256']
    assert out['quality_state'].startswith('pending_'),'A repair candidate cannot be accepted'
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        path=(R/old[key]).resolve();assert path.is_relative_to((R/'clean').resolve());_checked(path,old[digest])
    recheck_resource_files(out)
    from html_actual_text_registration import registration_record
    registration_record(out,_checked(R/old['original_reference'],old['source_image_sha256']),_checked(work/'candidate.drawio',out['code_sha256']).decode())
    for proof_key in ('native_font_validation',):
        source_proof=out.get(proof_key,{})
        if source_proof.get('evidence_file'):
            path=(R/source_proof['evidence_file']).resolve();assert path.is_relative_to(W.resolve()),'Repair evidence outside owned conversion workspace';_checked(path,source_proof['evidence_sha256'])
    new_xml=_checked(work/'candidate.drawio',out['code_sha256']);new_png=_checked(work/'candidate.png',out['image_sha256'])
    assert json.loads((work/'candidate_record.json').read_text())==out
    assert out.get('previous_candidate_archive')==old.get('previous_candidate_archive'),'Glyph repair changed Harness source archive lineage'
    archive=(R/out['glyph_alignment_prior_pair_archive']).resolve();assert archive.is_relative_to((R/'conversion/auto_quality_glyph_alignment_v3').resolve()),'Glyph baseline archive outside the owned revision workspace';archive.mkdir(parents=True,exist_ok=True)
    for name,data in [('conversion.json',claim_record['prior_snapshot'][1].encode()),('diagram.drawio',_checked(R/old['code_file'],old['code_sha256'])),('image.png',_checked(R/old['image_file'],old['image_sha256']))]:
        path=archive/name
        if path.exists():assert path.read_bytes()==data,'Immutable prior-pair archive differs'
        else:atomic(path,data)
    for key,data in [('code_file',new_xml),('image_file',new_png)]:
        target=(R/out[key]).resolve();assert target.is_relative_to((R/'clean').resolve()) and out[key]!=old[key],'Repair payload must use a new clean versioned path'
        if target.exists():assert target.read_bytes()==data,'Immutable versioned target has different bytes'
        else:atomic(target,data)
    from harness_source_provenance import resolve as resolve_source_provenance
    resolve_source_provenance(out)
    intent={'id':claim_record['id'],'token':claim_record['token'],'policy':proof['policy'],'old_record_sha256':sha(claim_record['prior_snapshot'][1].encode()),'new_record_sha256':sha(json.dumps(out,ensure_ascii=False).encode()),'out':out,'accepted':False}
    atomic(work/'publish_intent.json',(json.dumps(intent,ensure_ascii=False,indent=2)+'\n').encode())
    atomic((R/old['code_file']).parent/'conversion.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())


def hold_idle_model(db,id):
    if not exists(db,'harness_queue_v3'):return
    assert not model_running(db,id),'Never overwrite a running paid model call'
    db.execute("insert or ignore into harness_queue_v3(id,state,attempts,priority) values(?,'held_for_quality_v2',0,1000)",(id,))
    db.execute("update harness_queue_v3 set state='held_for_quality_v2',worker_pid=NULL,heartbeat=? where id=? and state!='running'",(now(),id))


def finish(db,claim_record,report,out=None,work=None,publish=False,artifact_writer=publish_artifacts):
    id=claim_record['id'];key=tuple(claim_record['key']);prior=tuple(claim_record['prior_snapshot']);owned=tuple(claim_record['owned_snapshot']);published=False
    begin(db)
    try:
        table_owner=db.execute('select state,owner_pid,claim_token from '+TABLE+' where id=? and code_hash=? and image_hash=? and policy=?',key).fetchone()
        if table_owner!=('running',claim_record['pid'],claim_record['token']) or snapshot(db,id)!=owned:
            report.update(state='stale_revision_or_ownership',accepted=False);out=None
        elif not outcome_pending(db,id,json.loads(prior[1])):
            report.update(state='retained_prior_candidate',accepted=False,reason='Outcome became terminal or original identity changed');out=None
            db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(prior[0],prior[3],now(),id))
        elif model_running(db,id):
            report.update(state='deferred_model_running',accepted=False);out=None
            db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(prior[0],prior[3],now(),id))
        elif out is not None and publish:
            artifact_writer(claim_record,out,report,work)
            db.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=NULL,error=?,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),'Deterministic actual-Range glyph repair candidate; full strict QA v3 recheck required'+('; canvas repair required' if report.get('requires_canvas_repair') else ''),now(),id))
            hold_idle_model(db,id);published=True;report.update(state='published_candidate',accepted=False)
        else:
            stage='validated_dry_run' if out is not None else report.get('state','retained_prior_candidate')
            if stage not in ('validated_dry_run','no_change_required'):stage='retained_prior_candidate'
            report.update(state=stage,accepted=False)
            db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(prior[0],prior[3],now(),id))
        # A stolen/replaced audit-table claim belongs to its new owner and must not be changed.
        if table_owner==('running',claim_record['pid'],claim_record['token']):
            db.execute('update '+TABLE+' set state=?,record=?,updated_at=? where id=? and code_hash=? and image_hash=? and policy=?',(report['state'],json.dumps(report,ensure_ascii=False),now(),*key))
        commit(db)
    except Exception:
        db.rollback()
        # An interrupted FS/SQL boundary can leave only the metadata pointer new;
        # restore it only while we still own this exact prior database revision.
        if snapshot(db,id)==owned:
            old=json.loads(prior[1]);pointer=(R/old['code_file']).parent/'conversion.json'
            if out is not None and pointer.exists():
                try:
                    if json.loads(pointer.read_text())==out:atomic(pointer,prior[1].encode())
                except (OSError,ValueError):pass
        raise
    if work is not None:
        try:
            atomic(Path(work)/'report.json',(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
            if published:atomic(Path(work)/'committed.json',(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256'],'accepted':False})+'\n').encode())
        except OSError as error:
            # SQL already contains the complete audit report. Never undo a committed
            # candidate merely because the duplicate filesystem receipt failed.
            print(json.dumps({'at':now(),'id':id,'stage':'audit_receipt_write_failed','committed_state':report['state'],'error':repr(error),'audit_saved_in_table':TABLE}),flush=True)
    return report['state']


def worker(index,limit,publish,ids,policy,files):
    signal.signal(signal.SIGUSR1,request_drain)
    db=sqlite3.connect(W/'jobs.sqlite',timeout=2);processed=0;counts=collections.Counter()
    while not limit or processed<limit:
        if draining():break
        ensure_implementation(policy,files)
        selection=select_candidate(db,policy,publish,ids)
        if selection is None:
            if limit or draining():break
            time.sleep(15);continue
        current=claim(db,selection,policy,publish)
        if current is None:continue
        started=time.monotonic();out=None;work=None
        try:work,out,report=generate(current,policy,files)
        except Exception as error:
            report={'id':current['id'],'at':now(),'policy':policy,'input_code_sha256':current['key'][1],'input_image_sha256':current['key'][2],'state':'retained_prior_candidate','error':repr(error)[:3000],'accepted':False,'previous_candidate_retained':True}
            work=W/'auto_quality_glyph_alignment_v3'/current['id']/(current['key'][1]+'_'+current['key'][2][:16])/policy.rsplit(':',1)[-1];work.mkdir(parents=True,exist_ok=True);atomic(work/'traceback.txt',traceback.format_exc().encode())
        report['seconds']=round(time.monotonic()-started,3)
        try:
            ensure_implementation(policy,files)
            stage=finish(db,current,report,out,work,publish)
        except Exception as error:
            # Keep a fully diagnosed failed revision rather than silently wedging
            # an otherwise-owned job after a reversible publication I/O failure.
            failure={**report,'state':'retained_prior_candidate','error':'Publication failed: '+repr(error),'accepted':False,'previous_candidate_retained':True}
            try:stage=finish(db,current,failure,None,work,False)
            except Exception:
                atomic(work/'owned_job_requires_recovery.json',(json.dumps({'id':current['id'],'pid':os.getpid(),'claim':current,'error':traceback.format_exc(),'accepted':False},indent=2)+'\n').encode());raise
        processed+=1;counts[stage]+=1
        print(json.dumps({'at':now(),'worker':index,'id':current['id'],'stage':stage,'seconds':report['seconds'],'error':report.get('error'),'accepted':False}),flush=True)
    db.close();return {'worker':index,'processed':processed,'counts':dict(counts),'accepted':0}


def main(args):
    signal.signal(signal.SIGUSR1,request_drain)
    from native_worker import R as runtime_root,W as runtime_work
    assert (R,W)==(runtime_root,runtime_work),'Remote runtime root differs'
    lock=(W/'auto_quality_glyph_alignment_v3c.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    policy,files=implementation();db=sqlite3.connect(W/'jobs.sqlite',timeout=2);init(db);db.close()
    owner={'pid':os.getpid(),'workers':args.workers,'limit_per_worker':args.limit,'publish':args.publish,'at':now(),'policy':policy,'implementation':files,'accepted':0,'frozen_generator':'auto_quality_glyph_candidate_generate_v3b.py','frozen_generator_sha256':FROZEN_GENERATOR_SHA256,'drain_control':str((W/'auto_quality_glyph_alignment_v3c_control.json').relative_to(R))}
    atomic(W/'auto_quality_glyph_alignment_v3c_owner.json',(json.dumps(owner,indent=2)+'\n').encode())
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(worker,index,args.limit,args.publish,args.ids,policy,files) for index in range(args.workers)]
        results=[future.result() for future in futures]
    summary={'at':now(),'policy':policy,'workers':results,'accepted':0,'goal_complete':False}
    atomic(W/'auto_quality_glyph_alignment_v3c_summary.json',(json.dumps(summary,indent=2)+'\n').encode());print(json.dumps(summary),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=2);parser.add_argument('--limit',type=int,default=2);parser.add_argument('--watch',action='store_true');parser.add_argument('--publish',action='store_true');parser.add_argument('--id',dest='ids',action='append',default=[]);arguments=parser.parse_args()
    if not 1<=arguments.workers<=16 or arguments.limit<0:parser.error('workers must be 1..16 and limit must be >=0')
    if arguments.watch:arguments.limit=0
    main(arguments)
