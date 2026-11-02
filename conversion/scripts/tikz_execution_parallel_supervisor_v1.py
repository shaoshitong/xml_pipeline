"""Two additional dispatch workers for the unchanged PGF candidate algorithm.

Default --smoke copies two eligible jobs to a private remote SQLite database and
never claims/publishes canonical jobs. Production --publish --watch is gated by
an exact dispatcher/generator preflight. No original supervisor owner/control or
frozen helper is edited. Every candidate is still pending, never accepted here.
"""
import argparse,collections,fcntl,hashlib,json,multiprocessing,os,queue,re,signal,sqlite3,sys,time,traceback,uuid
from pathlib import Path
import tikz_execution_candidate_batch_v1 as base

VERSION='two_extra_PGF_dispatch_workers_v1'
MAX_EXTRA_WORKERS=2
sha=lambda b:hashlib.sha256(b).hexdigest()
now=base.now


def exists(db,name):return base.exists(db,name)

def model_owned(db,identifier):
    for table in base.MODEL_TABLES:
        if not exists(db,table):continue
        columns={r[1] for r in db.execute('pragma table_info('+table+')')}
        condition="state='running'"+(' or worker_pid is not NULL' if 'worker_pid' in columns else '')
        if db.execute('select 1 from '+table+' where id=? and ('+condition+')',(identifier,)).fetchone():return True
    return False


def pending(db,identifier):
    if not exists(db,'processing_outcomes_v2'):raise RuntimeError('Original outcome registry is required')
    row=db.execute('select status from processing_outcomes_v2 where id=?',(identifier,)).fetchone()
    return row==('pending',)


def shortlist(db,policy,run_id,publish,limit=128,descending=False):
    """Bounded ID page; frozen selector still owns exact algorithm admission."""
    guards=[]
    for table in base.MODEL_TABLES:
        if not exists(db,table):continue
        columns={r[1] for r in db.execute('pragma table_info('+table+')')}
        condition="h.state='running'"+(' or h.worker_pid is not NULL' if 'worker_pid' in columns else '')
        guards.append(' and not exists(select 1 from '+table+' h where h.id=j.id and ('+condition+'))')
    sql='''select j.id from jobs j join processing_outcomes_v2 o on o.id=j.id
      where o.status='pending' and j.format='tikz' and j.state in ('rendered','needs_quality_repair','harness_review_pending')
      and j.worker_pid is NULL and j.output_record is not NULL and json_extract(j.output_record,'$.source_format')='tikz'
      and coalesce(json_extract(j.output_record,'$.edges'),0)=0
      and json_extract(j.output_record,'$.source_render_pdf') is not NULL and json_extract(j.output_record,'$.source_render_svg') is not NULL
      and json_extract(j.output_record,'$.native_page_padding') is NULL and json_extract(j.output_record,'$.native_canvas_contract') is NULL
      and not exists(select 1 from tikz_execution_candidates_v1 t where t.id=j.id
        and t.code_hash=json_extract(j.output_record,'$.code_sha256') and t.image_hash=json_extract(j.output_record,'$.image_sha256')
        and t.source_code_hash=json_extract(j.output_record,'$.source_code_sha256') and t.source_image_hash=json_extract(j.output_record,'$.source_image_sha256')
        and t.policy=? and (t.run_id=? or not(t.state='deferred_model_running' or (? and t.state='validated_dry_run'))))'''+''.join(guards)+' order by j.id '+('desc' if descending else 'asc')+' limit ?'
    return [r[0] for r in db.execute(sql,(policy,run_id,int(publish),limit))]


def selection(db,policy,run_id,publish=False):
    ids=shortlist(db,policy,run_id,publish)
    return base.select_candidate(db,policy,run_id,publish,False,ids) if ids else None


def generate_one(db,current,policy,files,publish,generator=base.generate):
    """Only reuse frozen generation/publication and exact owned restore."""
    started=time.monotonic();out=None;work=None
    if not pending(db,current['id']):
        report={'id':current['id'],'state':'cancelled_registered_outcome','accepted':False,'previous_candidate_retained':True,'reason':'Outcome ceased to be pending after claim'}
        return base.finish(db,current,report,None,None,False),report,work
    if model_owned(db,current['id']):
        report={'id':current['id'],'state':'deferred_model_running','accepted':False,'previous_candidate_retained':True,'reason':'A model queue is owned; never interrupt its call'}
        return base.finish(db,current,report,None,None,False),report,work
    try:work,out,report=generator(current,policy,files,publish)
    except Exception as error:
        report={'id':current['id'],'at':now(),'policy':policy,'state':'unsupported_source' if isinstance(error,ValueError) and ('Unsupported' in str(error) or 'unsupported' in str(error)) else 'failed_retained_prior','error':repr(error)[:4000],'accepted':False,'previous_candidate_retained':True}
        work=base.W/'tikz_execution_candidates_v1'/current['id']/(current['key'][1]+'_'+current['key'][2][:16])/policy.rsplit(':',1)[-1]/current['token'];work.mkdir(parents=True,exist_ok=True);base.atomic(work/'parallel_traceback.txt',traceback.format_exc().encode())
    report['seconds']=round(time.monotonic()-started,3)
    # A root outcome decision or model owner appearing in flight cancels only
    # this deterministic publication. No model job/history is modified.
    if not pending(db,current['id']):out=None;report.update(state='cancelled_registered_outcome',reason='Outcome changed while generating; preserve prior candidate')
    elif model_owned(db,current['id']):out=None;report.update(state='deferred_model_running',reason='Model ownership appeared while generating')
    try:
        base.ensure_implementation(policy,files)
        stage=base.finish(db,current,report,out,work,publish)
    except Exception as error:
        if db.in_transaction:db.rollback()
        stage=base.finish(db,current,{**report,'state':'publication_failed','error':repr(error),'accepted':False},None,work,False)
    return stage,report,work


def worker(database,index,run_id,policy,files,publish,watch,idle_seconds,stop,claims,limit,messages,generator=base.generate):
    for signum in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):signal.signal(signum,lambda *_:stop.set())
    db=sqlite3.connect(database,timeout=2);done=0;counts=collections.Counter();serial=0
    try:
        while not stop.is_set():
            base.ensure_implementation(policy,files);serial+=1;attempt=run_id+'_'+str(index)+'_'+str(serial)
            candidate=selection(db,policy,attempt,publish)
            if candidate is None:
                if not watch:break
                stop.wait(idle_seconds);continue
            with claims.get_lock():
                if stop.is_set() or limit and claims.value>=limit:break
                claims.value+=1
            if stop.is_set():
                with claims.get_lock():claims.value-=1
                break
            current=base.claim(db,candidate,policy,attempt,publish,False,pid=os.getpid())
            if current is None:
                with claims.get_lock():claims.value-=1
                continue
            messages.put({'stage':'claimed','worker':index,'pid':os.getpid(),'id':current['id'],'token':current['token'],'at':now()})
            stage,report,work=generate_one(db,current,policy,files,publish,generator)
            done+=1;counts[stage]+=1
            messages.put({'stage':'finished','worker':index,'pid':os.getpid(),'id':current['id'],'result':stage,'seconds':report.get('seconds'),'work':str(work) if work else None,'error':report.get('error'),'at':now(),'accepted':False})
            if limit and claims.value>=limit:break
    except BaseException as error:
        if db.in_transaction:db.rollback()
        stop.set();messages.put({'stage':'worker_error','worker':index,'pid':os.getpid(),'error':repr(error),'traceback':traceback.format_exc()[-5000:],'at':now()})
        raise
    finally:
        db.close();messages.put({'stage':'worker_terminal','worker':index,'pid':os.getpid(),'processed':done,'counts':dict(counts),'at':now()})


def run_workers(database,policy,files,workers=2,limit=2,publish=False,watch=False,idle_seconds=5,control=None,runtime=None,generator=base.generate):
    if not 1<=workers<=MAX_EXTRA_WORKERS or limit<0 or not 1<=idle_seconds<=300:raise ValueError('Two extra workers maximum, nonnegative finite/zero watch limit, bounded idle delay')
    if not watch and limit<1:raise ValueError('Finite mode requires a positive TOTAL limit')
    context=multiprocessing.get_context('fork');stop=context.Event();claims=context.Value('i',0);messages=context.Queue();run_id=uuid.uuid4().hex
    for signum in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):signal.signal(signum,lambda *_:stop.set())
    if control and Path(control).exists() and json.loads(Path(control).read_text()).get('drain'):stop.set()
    processes=[context.Process(target=worker,args=(str(database),i,run_id,policy,files,publish,watch,idle_seconds,stop,claims,limit,messages,generator)) for i in range(workers)]
    for process in processes:process.start()
    started=time.monotonic();events=[];active={};max_active=0;last_runtime=0;control_error=None
    while any(process.is_alive() for process in processes):
        if control and Path(control).exists():
            try:
                if json.loads(Path(control).read_text()).get('drain'):stop.set()
            except Exception as error:
                stop.set();control_error=repr(error);control=None;events.append({'stage':'control_error_draining','error':control_error,'at':now()})
        try:
            event=messages.get(timeout=.2);events.append(event)
            if event['stage']=='claimed':active[event['worker']]=event
            elif event['stage'] in ('finished','worker_terminal','worker_error'):active.pop(event['worker'],None)
            max_active=max(max_active,len(active));print(json.dumps(event),flush=True)
        except queue.Empty:pass
        if runtime and time.monotonic()-last_runtime>=1:
            base.atomic(Path(runtime),(json.dumps({'at':now(),'run_id':run_id,'parent_pid':os.getpid(),'workers':[{'pid':p.pid,'live':p.is_alive()} for p in processes],'active':active,'claims':claims.value,'drain_requested':stop.is_set(),'observed_max_active':max_active,'policy':policy,'publish':publish,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n').encode());last_runtime=time.monotonic()
    for process in processes:process.join()
    while True:
        try:events.append(messages.get_nowait())
        except queue.Empty:break
    result={'at':now(),'run_id':run_id,'policy':policy,'workers':workers,'total_claims':claims.value,'limit_is_total':limit,'publish':publish,'watch':watch,'drained':stop.is_set(),'elapsed_seconds':round(time.monotonic()-started,3),'observed_max_active':max_active,'worker_exits':{str(p.pid):p.exitcode for p in processes},'events':events,'accepted':0,'model_calls':0,'control_error':control_error}
    if control_error or any(p.exitcode for p in processes):raise RuntimeError('Parallel worker failed; no automatic restart: '+json.dumps(result))
    return result


def copied_schema(source,target,table):
    sql=source.execute("select sql from sqlite_master where type='table' and name=?",(table,)).fetchone()
    if sql:target.execute(sql[0])


def canonical_snapshot(db,ids):
    result={}
    for identifier in ids:
        result[identifier]={'job':base.snapshot(db,identifier),'model_queues':{table:db.execute('select * from '+table+' where id=?',(identifier,)).fetchall() for table in base.MODEL_TABLES if exists(db,table)}}
    return result


def private_smoke(workers=2,limit=2):
    if workers!=2 or limit!=2:raise ValueError('Initial real smoke is exactly two workers and two total cases')
    policy,files=base.implementation();base.require_bounded_smoke(policy,False,workers,limit)
    source=sqlite3.connect('file:'+str(base.W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=60)
    ids=shortlist(source,policy,'parallel_readonly_smoke',False,limit=limit,descending=True)
    if len(ids)!=limit:raise ValueError('Two currently idle unattempted pending cases required for the bounded smoke')
    before=canonical_snapshot(source,ids);payload_hashes={}
    for identifier in ids:
        record=json.loads(before[identifier]['job'][1]);base.recheck_old(record)
        for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:payload_hashes[record[key]]=record[digest]
    scope=base.W/'prototype/tikz_execution_parallel_supervisor_v1/smoke'/uuid.uuid4().hex;scope.mkdir(parents=True);database=scope/'jobs.sqlite';private=sqlite3.connect(database)
    for table in ('jobs','processing_outcomes_v2',*base.MODEL_TABLES):
        copied_schema(source,private,table)
        if not exists(source,table):continue
        for identifier in ids:
            for row in source.execute('select * from '+table+' where id=?',(identifier,)):
                private.execute('insert into '+table+' values('+','.join('?' for _ in row)+')',row)
    private.commit();base.init(private);private_before=canonical_snapshot(private,ids);private.close()
    result=run_workers(database,policy,files,workers,limit,False,False,runtime=scope/'runtime.json')
    private=sqlite3.connect(database);private_after=canonical_snapshot(private,ids);rows=private.execute('select id,state,claim_token from '+base.TABLE).fetchall();private.close()
    after=canonical_snapshot(source,ids);source.close()
    unchanged=all(base.sha((base.R/path).read_bytes())==digest for path,digest in payload_hashes.items())
    receipt={'at':now(),'ok':before==after and private_before==private_after and unchanged and result['total_claims']==2 and result['observed_max_active']==2 and len(rows)==2 and len({r[2] for r in rows})==2,'dispatcher_version':VERSION,'dispatcher_sha256':sha(Path(__file__).read_bytes()),'generator_policy':policy,'workers':workers,'publish':False,'accepted':0,'model_calls':0,'canonical_jobs_and_model_queues_unchanged':before==after,'private_jobs_and_queue_history_exactly_restored':private_before==private_after,'all_source_and_native_pair_hashes_unchanged':unchanged,'private_stage_rows':[{'id':r[0],'state':r[1],'claim_token':r[2]} for r in rows],'canonical_ids':ids,'private_database':str(database),'scope':str(scope),'summary':result,'production_started':False}
    base.atomic(base.W/'tikz_execution_parallel_supervisor_v1_smoke.json',(json.dumps(receipt,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in receipt.items() if k!='summary'}),flush=True)
    return receipt


def production_preflight(policy,workers):
    if not 1<=workers<=MAX_EXTRA_WORKERS:raise ValueError('At most two additional workers')
    path=base.W/'tikz_execution_parallel_supervisor_v1_preflight.json';receipt=json.loads(path.read_text())
    if not receipt.get('ok') or receipt.get('dispatcher_sha256')!=sha(Path(__file__).read_bytes()) or receipt.get('generator_policy')!=policy or receipt.get('isolated_tests_passed') is not True or receipt.get('real_private_smoke_passed') is not True or receipt.get('canonical_production_unchanged') is not True:raise ValueError('This exact dispatcher requires reviewed isolated tests and two-case private smoke')
    base.require_bounded_smoke(policy,True,workers+1,1)
    # Frozen batch itself supports up to four workers. With its existing single
    # watch plus these two extra actors the intended maximum is three.
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:args=[x.decode() for x in (path/'cmdline').read_bytes().split(b'\0') if x]
        except (OSError,UnicodeDecodeError):continue
        if any(Path(arg).name=='tikz_execution_candidate_batch_v1.py' for arg in args):
            count=int(args[args.index('--workers')+1]) if '--workers' in args else 1
            if count!=1:raise RuntimeError('Another broader frozen batch is already live; coordinate capacity first')


def main(args):
    if args.smoke or not args.publish:
        if args.watch or args.publish:raise ValueError('Smoke is private, finite and nonpublishing')
        return private_smoke(args.workers,args.limit)
    policy,files=base.implementation();production_preflight(policy,args.workers)
    lock=(base.W/'tikz_execution_parallel_supervisor_v1.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=sqlite3.connect(base.W/'jobs.sqlite',timeout=2)
    if dict(db.execute('select category,count(*) from jobs group by category'))!={'scientific_diagram':107161,'poster':24743}:raise RuntimeError('Original full input scope changed')
    base.init(db);db.close()
    owner={'at':now(),'pid':os.getpid(),'workers':args.workers,'generator_policy':policy,'dispatcher_sha256':sha(Path(__file__).read_bytes()),'publish':True,'accepted':0,'model_calls':0}
    base.atomic(base.W/'tikz_execution_parallel_supervisor_v1_owner.json',(json.dumps(owner,indent=2)+'\n').encode())
    result=run_workers(base.W/'jobs.sqlite',policy,files,args.workers,args.limit,True,args.watch,args.idle_seconds,base.W/'tikz_execution_parallel_supervisor_v1_control.json',base.W/'tikz_execution_parallel_supervisor_v1_runtime.json')
    base.atomic(base.W/'tikz_execution_parallel_supervisor_v1_terminal.json',(json.dumps(result,indent=2)+'\n').encode());return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--publish',action='store_true');parser.add_argument('--watch',action='store_true');parser.add_argument('--workers',type=int,default=2);parser.add_argument('--limit',type=int,default=2);parser.add_argument('--idle-seconds',type=int,default=5);main(parser.parse_args())
