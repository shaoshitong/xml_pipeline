"""Finite manifest-order initial screening. No watch, repair loop or model client.

The input jobs database is read-only. This run's durable ledger and final two
manifests are its outcome authority; historical job/claim/budget rows are kept.
"""
import argparse, concurrent.futures, datetime, fcntl, hashlib, json, multiprocessing, os, sqlite3, sys, time, uuid
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
EXPECTED=131904
INPUT_SHA='361bce924762d14481da9b541cfbcf0f6879f97618fbc750922ac1c918a70a85'
TERMINAL=('qualified','abandoned')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def raw(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
def sha(blob):return hashlib.sha256(blob).hexdigest()
def atomic(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
    temp.replace(path)
def create_schema(d):
    d.execute('''create table if not exists samples(seq integer primary key,id text unique not null,source text not null,
      status text not null default 'queued',attempts integer not null default 0 check(attempts between 0 and 1),
      started_at text,finished_at text,result text,
      check(status in ('queued','running','qualified','abandoned')))''')
    d.execute('create table if not exists metadata(key text primary key,value text not null)');d.commit()
def metadata(d):return {k:json.loads(v) for k,v in d.execute('select key,value from metadata')}
def meta(d,key,value):d.execute('insert or replace into metadata values(?,?)',(key,json.dumps(value)))
def create_run(run,ids=()):
    run=Path(run);run.mkdir(parents=True,exist_ok=True);path=run/'status.sqlite'
    if path.exists():raise ValueError('run_already_exists_use_run_or_status')
    d=sqlite3.connect(path);create_schema(d);wanted=set(ids);digest=hashlib.sha256();count=0;categories={};formats={};seen=set()
    order=run/'input_order.jsonl'
    try:
        with (R/'release/manifest.jsonl').open('rb') as stream,order.open('xb') as out:
            for line in stream:
                digest.update(line);s=json.loads(line)
                if s.get('category') not in ('scientific_diagram','poster'):continue
                identifier=s['pair_sha256']
                if wanted and identifier not in wanted:continue
                if identifier in seen:raise ValueError('duplicate_original_id')
                seen.add(identifier);count+=1;categories[s['category']]=categories.get(s['category'],0)+1;formats[s['format']]=formats.get(s['format'],0)+1
                d.execute('insert into samples(seq,id,source) values(?,?,?)',(count,identifier,json.dumps(s,ensure_ascii=False)))
                out.write(raw({'seq':count,'id':identifier,'source_code_sha256':s['code_sha256'],'source_image_sha256':s['image_sha256'],'format':s['format'],'category':s['category']}))
                if count%1000==0:d.commit()
            out.flush();os.fsync(out.fileno())
        if digest.hexdigest()!=INPUT_SHA:raise ValueError('authoritative_input_manifest_sha_changed')
        if wanted and seen!=wanted:raise ValueError('requested_smoke_ids_not_in_scope')
        if not wanted and (count!=EXPECTED or categories!={'poster':24743,'scientific_diagram':107161}):raise ValueError('full_input_scope_mismatch')
        for k,v in {'created_at':now(),'total':count,'input_manifest_sha256':digest.hexdigest(),'categories':categories,'formats':formats,
                    'full_scope':not bool(wanted),'policy':'fixed_program_single_initial_screen_v1','model_calls':0,'finished':False}.items():meta(d,k,v)
        d.commit()
        return metadata(d)
    except BaseException:
        d.close();atomic(run/'initialization_failed.json',raw({'at':now(),'count':count,'reason':'input_scope_initialization_failed'}));raise
    finally:d.close()
def claim(d,seq):
    d.execute('begin immediate')
    row=d.execute('select id,source,status,attempts from samples where seq=?',(seq,)).fetchone()
    if not row or row[2:]!=('queued',0):d.rollback();raise RuntimeError('sample_not_eligible_for_exactly_once_dispatch')
    d.execute('update samples set status="running",attempts=1,started_at=? where seq=?',(now(),seq));d.commit()
    return {'seq':seq,'id':row[0],'source':json.loads(row[1])}
def finish(d,seq,result):
    d.execute('begin immediate');row=d.execute('select id,status,attempts from samples where seq=?',(seq,)).fetchone()
    if not row or row!=(result['id'],'running',1) or result['status'] not in TERMINAL:d.rollback();raise RuntimeError('result_identity_or_dispatch_changed')
    d.execute('update samples set status=?,finished_at=?,result=? where seq=?',(result['status'],now(),json.dumps(result,ensure_ascii=False),seq));d.commit()
def pins():
    import auto_quality_batch_v4b as qa
    qa.ensure_pinned();p={str(Path(__file__).parent/n):sha((Path(__file__).parent/n).read_bytes()) for n in ['fixed_batch_pipeline_v1.py','fixed_batch_case_v1.py','fixed_batch_conversion_adapters_v1.py','initial_conversion_case_v1.py','initial_conversion_case_v1b.py','initial_conversion_process_v1.py']}
    for n,h in qa.IMPLEMENTATION.items():p[str(Path(n) if Path(n).is_absolute() else Path(__file__).parent/n)]=h
    import fixed_batch_conversion_adapters_v1 as adapter
    # Include converter runtime modules, not just the coordinator. No mutable
    # global cache inventory participates in per-source implementation identity.
    for n in ['native_worker.py','svg_convert_v2.py','html_batch_v3.py','mermaid_geometry_batch.py','python_capture.py','python_source_context.py','plantuml_runtime.py','plantuml_native.py','plantuml_native_v4.py','sandbox_runner.py','pdf_to_native.py','tikz_connectivity.py']:
        path=Path(__file__).parent/n
        if path.exists():p[str(path)]=sha(path.read_bytes())
    policy=W/'model_usage_policy_v2.json'
    if policy.exists():
        x=json.loads(policy.read_bytes())
        # The pre-existing gateway must remain disabled. Its exact schema is
        # additionally hash-bound, and none of these modules imports a client.
        if not (x.get('legacy_sdk_disabled') is True and x.get('legacy_batch_generation_disabled') is True and x.get('automatic_model_critics_disabled') is True and x.get('new_gateway_enabled') is False and x.get('authorized_model_sample_ids')==[]):raise RuntimeError('new_model_dispatch_must_remain_disabled')
        p[str(policy)]=sha(policy.read_bytes())
    else:raise RuntimeError('missing_disabled_model_policy')
    return p
def ensure_pins(p):
    for path,h in p.items():
        if sha(Path(path).read_bytes())!=h:raise RuntimeError('implementation_changed:'+path)
def execute_case(task):
    # A pool slot has one child tree at a time, as required by the owned Linux
    # subreaper/pidfd process wrapper. Pool workers never write the outcome DB.
    from initial_conversion_process_v1 import run
    seq=task['seq'];identifier=task['id'];work=Path(task['work']);work.mkdir(parents=True,exist_ok=False)
    atomic(work/'request.json',raw(task));env={k:os.environ[k] for k in ['PATH','HOME','LANG','LC_ALL','TMPDIR','XDG_CACHE_HOME'] if k in os.environ}
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=str(R/'env')+':'+str(W/'scripts'),PYTHONDONTWRITEBYTECODE='1')
    isolation=run([sys.executable,'-B',str(W/'scripts/fixed_batch_case_v1.py'),str(work/'request.json')],work,task['case_timeout_seconds'],env)
    atomic(work/'isolation.json',raw(isolation))
    base={'seq':seq,'id':identifier,'source_code_sha256':task['source']['code_sha256'],'source_image_sha256':task['source']['image_sha256'],
          'model_calls':0,'evidence_directory':str(work.relative_to(R)),'case_cleanup_complete':isolation.get('cleanup_complete') is True}
    result_path=work/'result.json'
    if not isolation.get('cleanup_complete'):
        return {**base,'status':'abandoned','reason':'initial_screen_cleanup_failed','infrastructure_failure':True}
    if isolation.get('deadline_exceeded'):
        return {**base,'status':'abandoned','reason':'initial_screen_whole_case_timeout','phase':'timeout','timeout_seconds':task['case_timeout_seconds']}
    if not isolation.get('ok') or not result_path.exists():
        return {**base,'status':'abandoned','reason':'initial_screen_case_process_failed','phase':'runtime','isolation':{k:v for k,v in isolation.items() if k not in ['processes']}}
    r=json.loads(result_path.read_bytes())
    if any(r.get(k)!=base[k] for k in ['id','seq','source_code_sha256','source_image_sha256']):raise RuntimeError('case_result_source_identity_mismatch')
    return {**r,**base}
def status(run):
    run=Path(run);d=sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True);m=metadata(d)
    counts=dict(d.execute('select status,count(*) from samples group by status'));attempts=dict(d.execute('select attempts,count(*) from samples group by attempts'))
    last=d.execute('select seq,id,status,finished_at from samples where status in ("qualified","abandoned") order by finished_at desc limit 1').fetchone();d.close()
    live=False;owner={}
    try:
        owner=json.loads((run/'owner.json').read_bytes());proc=Path('/proc',str(owner['pid']));f=(proc/'stat').read_text().rsplit(') ',1)[1].split()
        live=f[0]!='Z' and int(f[19])==int(owner['start_ticks']) and str(W/'scripts/fixed_batch_pipeline_v1.py').encode() in (proc/'cmdline').read_bytes().split(b'\0')
    except (OSError,ValueError,KeyError):pass
    return {'at':now(),'run':str(run),'total':m['total'],'full_scope':m['full_scope'],'counts':counts,'dispatch_attempt_counts':attempts,
            'finished':m.get('finished',False),'last_completed':last,'model_calls':0,'policy':m['policy'],
            'supervisor_live':live,'supervisor_pid':owner.get('pid'),'workers':owner.get('workers'),'infrastructure_stop_recorded':(run/'infrastructure_stop.json').exists()}
def export(run,final=False):
    run=Path(run);d=sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True);d.execute('begin');m=metadata(d);counts=dict(d.execute('select status,count(*) from samples group by status'))
    if final and (sum(counts.get(s,0) for s in TERMINAL)!=m['total'] or any(s not in TERMINAL for s in counts)):raise RuntimeError('cannot_export_incomplete_run_as_final')
    hashes={};prefix='' if final else 'inprogress.'
    for kind in ['qualified','failed','processed']:
        target=run/(prefix+kind+'.jsonl');tmp=target.with_suffix('.tmp');h=hashlib.sha256();n=0
        with tmp.open('wb') as out:
            for state,body in d.execute('select status,result from samples where status in ("qualified","abandoned") order by seq'):
                if kind=='qualified' and state!='qualified' or kind=='failed' and state!='abandoned':continue
                r=json.loads(body);value=r['manifest'] if kind=='qualified' else r
                line=raw(value);out.write(line);h.update(line);n+=1
            out.flush();os.fsync(out.fileno())
        tmp.replace(target);hashes[kind]={'records':n,'sha256':h.hexdigest(),'file':str(target.relative_to(R))}
    d.rollback();d.close();summary={'at':now(),'total':m['total'],'full_scope':m['full_scope'],'finished':final,'counts':counts,'files':hashes,'model_calls':0,
      'interpretation':'One fixed-program initial screen per input. Abandoned means failed/skipped under this bounded run, not intrinsic source impossibility. Historical DB records are preserved; this run ledger is authoritative for this run.'}
    atomic(run/('summary.json' if final else 'progress.json'),raw(summary));return summary
def final_asset_audit(d):
    """No rerender/retry: a damaged final payload is recorded failed, not shipped."""
    audited=0;failed=0
    for seq,source_json,result_json in d.execute('select seq,source,result from samples where status="qualified" order by seq').fetchall():
        s=json.loads(source_json);r=json.loads(result_json);m=r['manifest']
        try:
            if (m['id'],m['source_code_sha256'],m['source_image_sha256'])!=(r['id'],s['code_sha256'],s['image_sha256']):raise ValueError('qualified_source_identity_mismatch')
            for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('metadata_file','metadata_sha256')]:
                path=(R/m[field]).resolve(strict=True)
                if not path.is_relative_to((R/'clean').resolve()):raise ValueError('qualified_payload_outside_clean:'+field)
                if sha(path.read_bytes())!=m[digest]:raise ValueError('qualified_payload_hash_changed:'+field)
            audited+=1
        except Exception as e:
            failed+=1;r.update(status='abandoned',reason='initial_screen_final_asset_audit_failed',detail=repr(e),prior_qualified_manifest=r.pop('manifest'))
            d.execute('update samples set status="abandoned",result=?,finished_at=? where seq=?',(json.dumps(r,ensure_ascii=False),now(),seq))
    d.commit();return {'qualified_payloads_verified':audited,'late_asset_failures':failed,'at':now()}
def main_run(run,workers=16,timeout=600,selected_ids=()):
    run=Path(run).resolve()
    if not run.is_relative_to((R/'release/fixed_batch_v1').resolve()):raise ValueError('run_outside_fixed_release_root')
    lock=(run/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    global_lock=(W/'fixed_batch_v1.lock').open('a+');fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    d=sqlite3.connect(run/'status.sqlite');m=metadata(d)
    if m.get('finished'):return export(run,True)
    # A manual restart never silently repeats an interrupted original. Its
    # already-dispatched attempt is recorded failed before moving onward.
    for seq,identifier,source in d.execute('select seq,id,source from samples where status="running"').fetchall():
        s=json.loads(source);work=W/'fixed_batch_v1'/run.name/(str(seq).zfill(6)+'_'+identifier)
        evidence=work/'isolation.json'
        if not evidence.exists() or json.loads(evidence.read_bytes()).get('cleanup_complete') is not True:
            raise RuntimeError('manual_resume_requires_proof_previous_case_tree_is_gone:'+identifier)
        recovered=json.loads((work/'result.json').read_bytes()) if (work/'result.json').exists() else None
        if recovered and (recovered.get('id'),recovered.get('seq'),recovered.get('source_code_sha256'),recovered.get('source_image_sha256'))==(identifier,seq,s['code_sha256'],s['image_sha256']):
            finish(d,seq,{**recovered,'case_cleanup_complete':True,'recovered_finished_attempt_without_reexecution':True})
        else:finish(d,seq,{'id':identifier,'seq':seq,'status':'abandoned','reason':'initial_screen_interrupted_prior_dispatch','model_calls':0,'source_code_sha256':s['code_sha256'],'source_image_sha256':s['image_sha256']})
    p=pins();owner={'pid':os.getpid(),'start_ticks':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
          'at':now(),'workers':workers,'case_timeout_seconds':timeout,'run':str(run),'pins':p,'model_calls':0,'watch':False}
    atomic(run/'owner.json',raw(owner));atomic(run/'control.json',raw({'stop_dispatch':False}));meta(d,'last_started_at',now());d.commit()
    restriction=' and id in ('+','.join('?' for _ in selected_ids)+')' if selected_ids else ''
    todo=iter([x[0] for x in d.execute('select seq from samples where status="queued"'+restriction+' order by seq',list(selected_ids))]);active={};exhausted=False;fatal=None;done=0;last_export=time.monotonic()
    context=multiprocessing.get_context('spawn')
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=context) as pool:
            while active or not exhausted:
                ensure_pins(p)
                stopped=json.loads((run/'control.json').read_bytes()).get('stop_dispatch') is True
                while not exhausted and not fatal and not stopped and len(active)<workers:
                    seq=next(todo,None)
                    if seq is None:exhausted=True;break
                    task=claim(d,seq);task.update(work=str(W/'fixed_batch_v1'/run.name/(str(seq).zfill(6)+'_'+task['id'])),pins=p,case_timeout_seconds=timeout)
                    active[pool.submit(execute_case,task)]=task
                if not active:break
                completed,_=concurrent.futures.wait(active,timeout=5,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in completed:
                    task=active.pop(future)
                    try:r=future.result()
                    except Exception as e:r={'id':task['id'],'seq':task['seq'],'status':'abandoned','reason':'initial_screen_supervisor_error','detail':repr(e),'model_calls':0,'infrastructure_failure':True,'source_code_sha256':task['source']['code_sha256'],'source_image_sha256':task['source']['image_sha256']}
                    finish(d,task['seq'],r);done+=1
                    if r.get('infrastructure_failure'):fatal=r
                    if done%100==0:print(json.dumps({'at':now(),'completed_this_start':done,'latest_seq':task['seq'],'latest_status':r['status']},ensure_ascii=False),flush=True)
                if time.monotonic()-last_export>60:
                    export(run);last_export=time.monotonic()
            if fatal:atomic(run/'infrastructure_stop.json',raw(fatal))
        remaining=d.execute('select count(*) from samples where status not in ("qualified","abandoned")').fetchone()[0]
        if remaining==0:
            audit=final_asset_audit(d);atomic(run/'final_asset_audit.json',raw(audit));result=export(run,True)
            meta(d,'finished',True);meta(d,'finished_at',now());d.commit();return result
        return export(run,False)
    finally:d.close()
def cli():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['create','run','status','export']);p.add_argument('--run-id',required=True);p.add_argument('--id',dest='ids',action='append',default=[]);p.add_argument('--workers',type=int,default=16);p.add_argument('--case-timeout',type=float,default=600)
    a=p.parse_args()
    if not all(c.isalnum() or c in '-_' for c in a.run_id):p.error('Invalid run ID')
    if not 1<=a.workers<=24 or not 30<=a.case_timeout<=1800:p.error('workers1..24, case timeout30..1800')
    run=R/'release/fixed_batch_v1'/a.run_id
    if a.action=='create':r=create_run(run,a.ids)
    elif a.action=='run':r=main_run(run,a.workers,a.case_timeout,a.ids)
    elif a.action=='status':r=status(run)
    else:r=export(run,False)
    print(json.dumps(r,ensure_ascii=False),flush=True)
if __name__=='__main__':cli()
