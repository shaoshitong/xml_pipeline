"""Frozen unseen16 then fixed parallel3557 plot conversion, isolated once ledger."""
from pathlib import Path
import argparse,collections,concurrent.futures,datetime,hashlib,json,os,shutil,sqlite3,sys,time,traceback
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from matplotlib_plot_inputs_v1 import payload,sha
from sandbox_runner import run,PYTHON
from matplotlib_plot_engine_v1 import convert,CHROME
from matplotlib_plot_quality_v1 import validate
from playwright.sync_api import sync_playwright
from PIL import Image
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
PIN_CACHE={};RUN_BEGIN=time.monotonic();RUN_BASELINE=0
def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def atomic(p,x):
    q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(q,p)
def birth(pid):
    p=Path('/proc',str(pid),'stat')
    if not p.exists():return None
    f=p.read_text().split(') ',1)[1].split();return f[19] if f[0]!='Z' else None
def connect():
    db=sqlite3.connect(D/'once.sqlite',timeout=60);db.execute('pragma journal_mode=WAL');return db
def pins():
    p=json.loads((D/'policy.json').read_text())
    for name,digest in p['files_sha256'].items():
        path=Path(name);st=path.stat();key=(st.st_ino,st.st_size,st.st_mtime_ns)
        if PIN_CACHE.get(name)!=key:
            if sha(path.read_bytes())!=digest:raise ValueError('frozen_program_dependency_changed:'+name)
            PIN_CACHE[name]=key
    return p
def emit(event,**data):
    line=(enc({'at_utc':now(),'event':event,**data})+'\n').encode();fd=os.open(D/'events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
    try:os.write(fd,line)
    finally:os.close(fd)
def profile_record(row,case,result,quality,policy):
    capture=json.loads((case/'execution.json').read_text())['captures'][0];execution_file=case/'execution.json';xml=case/'native_v1/diagram.drawio';png=case/'native_v1/native.png'
    original=quality['profiles']['provider_original_reference_aligned'];profile='provider_original_reference_aligned' if original else 'source_replay_aligned';reference=case/'original_reference.png' if original else case/capture['png'];refsha=sha(reference.read_bytes());code_sha=row['payloads']['code']['expected_sha256'];newid=sha(enc({'profile':profile,'raw_source_pair_id':row['id'],'release_code_sha256':code_sha,'selected_source_reference_PNG_sha256':refsha,'drawio_sha256':sha(xml.read_bytes()),'policy':policy['policy_id']}).encode())
    return {'id':newid,'raw_source_pair_id':row['id'],'source':row['source'],'category':row.get('category','scientific_diagram'),'source_format':'python','format':'drawio','profile':profile,
      'source_code_sha256':code_sha,'source_image_sha256':refsha,'source_image_origin':'immutable_provider_reference' if original else 'fresh_release_exact_code_Agg_PNG_with_recorded_export_and_RNG',
      'original_source_code':str((case/'source.py').relative_to(R)),'original_reference':str(reference.relative_to(R)),'auxiliary_provider_original_reference':str((case/'original_reference.png').relative_to(R)),'auxiliary_provider_original_reference_sha256':row['payloads']['image']['expected_sha256'],
      'source_render_svg':str((case/capture['svg']).relative_to(R)),'source_render_svg_sha256':capture['svg_sha256'],'source_render_png':str((case/capture['png']).relative_to(R)),'source_render_png_sha256':capture['png_sha256'],
      'source_data_scene':str((case/capture['scene']).relative_to(R)),'source_data_scene_sha256':capture['scene_sha256'],'source_execution_contract':str(execution_file.relative_to(R)),'source_execution_contract_sha256':sha(execution_file.read_bytes()),
      'code_file':str(xml.relative_to(R)),'code_sha256':sha(xml.read_bytes()),'image_file':str(png.relative_to(R)),'image_sha256':sha(png.read_bytes()),'quality_report':str((case/'native_v1/quality/report.json').relative_to(R)),
      'quality_state':'qualified_under_declared_profile','policy':policy['policy_id'],'conversion_method':'release_exact_Matplotlib_Artist_SVG_vector_rect_clip_live_text_to_native_drawio_v1','source_payloads':row['payloads'],
      'all_Artist_arrays_preserved':True,'source_data_vertices':result['source_data_vertices'],'source_axes':result['source_axes'],'editable_objects':result['native_cells'],'editable_text_objects':result['editable_text_cells'],
      'provider_original_fidelity_certified':original,'provider_original_gate':quality['provider_original_reference_gate'],'new_model_calls':0,'whole_figure_wrapper':False,'source_label_glyph_path_substitution':False,'historical_qualified_ledger_modified':False,'qualified_at_utc':now()}
def worker(task):
    row,phase=task;policy=pins();db=connect();ident=row['id'];db.execute('begin immediate');old=db.execute('select status,worker_pid,birth,record from cases where id=?',(ident,)).fetchone()
    if old and old[0]!='running':db.commit();db.close();return {'id':ident,'status':'already_terminal'}
    if old and birth(old[1])==old[2]:db.commit();db.close();return {'id':ident,'status':'already_owned_live'}
    db.execute('insert or replace into cases values(?,?,?,?,?,?)',(ident,phase,'running',os.getpid(),birth(os.getpid()),enc({'id':ident,'stage':'claimed'})));db.commit();case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True);record={'id':ident,'source':row['source'],'phase':phase,'model_calls':0,'status':'technical_failure','qualified_pair':None,'policy':policy['policy_id'],'stratum':row.get('stratum'),'source_execution_completed':False,'stage_seconds':{},'started_epoch':time.time()};began=time.monotonic()
    def measured(name,operation):
        start=time.monotonic()
        try:return operation()
        finally:record['stage_seconds'][name]=record['stage_seconds'].get(name,0)+time.monotonic()-start
    try:
        if row.get('development_excluded'):record.update(status='preserved_development_capture_no_reexecution');return record
        if not row['static_audit']['safe_selfcontained_source']:record.update(status='typed_skip_static_source_domain',reasons=row['static_audit']['security_issues']);return record
        code,image=measured('data_loading',lambda:(payload(row['payloads']['code']),payload(row['payloads']['image'])));audit=dict(row['static_audit'],id=ident,source=row['source'],source_image_sha256=row['payloads']['image']['expected_sha256'],payloads=row['payloads'])
        if not (case/'input_audit.json').exists():(case/'input_audit.json').write_text(json.dumps(audit,indent=2)+'\n');(case/'source.py').write_bytes(code);(case/'original_reference.png').write_bytes(image)
        assert sha((case/'source.py').read_bytes())==row['payloads']['code']['expected_sha256'];assert sha((case/'original_reference.png').read_bytes())==row['payloads']['image']['expected_sha256']
        execution_file=case/'execution.json'
        if not execution_file.exists():
            marker=case/'source_execution_started.json'
            if marker.exists():record.update(status='typed_skip_interrupted_source_execution_not_repeated');return record
            marker.write_text(enc({'at_utc':now(),'source_code_sha256':sha(code),'capture_sha256':sha((R/'conversion/scripts/matplotlib_plot_capture_v2.py').read_bytes()),'pid':os.getpid(),'birth':birth(os.getpid())})+'\n');shutil.copyfile(R/'conversion/scripts/matplotlib_plot_capture_v2.py',case/'capture.py')
            source=measured('capture',lambda:run(case,[PYTHON,'-I','/work/capture.py'],timeout=150));(case/'stdout.log').write_text(source.stdout);(case/'stderr.log').write_text(source.stderr)
        if not execution_file.exists():record.update(status='typed_skip_source_execution_no_result');return record
        execution=json.loads(execution_file.read_text());record['source_execution_completed']=True;assert sha((case/'source.py').read_bytes())==row['payloads']['code']['expected_sha256'];assert sha((case/'original_reference.png').read_bytes())==row['payloads']['image']['expected_sha256']
        if not execution.get('ok'):record.update(status='typed_skip_source_execution',reason=execution.get('error','source_failed'));return record
        if len(execution['captures'])!=1:record.update(status='typed_skip_ambiguous_multiple_figures',figures=len(execution['captures']));return record
        if execution.get('source_text_glyph_path_events'):record.update(status='typed_skip_source_label_glyph_paths');return record
        capture=execution['captures'][0]
        for name,digest in [('svg','svg_sha256'),('png','png_sha256'),('scene','scene_sha256')]:assert sha((case/capture[name]).read_bytes())==capture[digest],'captured_source_payload_changed'
        scene=json.loads((case/capture['scene']).read_text())
        if '3d' in scene.get('axes_names',[]):record.update(status='typed_skip_3D_data_contract');return record
        with Image.open(case/capture['png']) as im:
            if max(im.size)>8192 or im.width*im.height>64_000_000:record.update(status='typed_skip_full_canvas_resource_bound_no_downsampling');return record
        if (case/capture['svg']).stat().st_size>16*1024**2:record.update(status='typed_skip_complete_SVG_above16MiB_no_point_reduction');return record
        nr=case/'native_v1/report.json'
        if nr.exists():result=json.loads(nr.read_text())
        elif (case/'native_v1').exists():record.update(status='typed_skip_interrupted_native_build');return record
        else:
            def native_build():
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);value=convert(case,browser);browser.close();return value
            result=measured('IR_native',native_build)
        if result['status']!='editable_native_development_candidate':record.update(status='typed_skip_native_domain',reason=result.get('error','native_candidate_failed'));return record
        qr=case/'native_v1/quality/report.json'
        if qr.exists():quality=json.loads(qr.read_text())
        elif (case/'native_v1/quality').exists():record.update(status='typed_skip_interrupted_native_quality');return record
        else:quality=measured('QA',lambda:validate(case))
        record.update(native_objects=result['native_cells'],source_data_vertices=result['source_data_vertices'],quality_report=str(qr.relative_to(R)),profile_gates=quality['profiles'])
        if quality['ok']:
            pair=measured('publication',lambda:profile_record(row,case,result,quality,policy));record.update(status='qualified_'+pair['profile'],qualified_pair=pair);(case/'pair.json').write_text(json.dumps(pair,indent=2)+'\n')
        else:record.update(status='review_source_or_reference_alignment',original_failures=quality['provider_original_reference_gate']['failures'],Agg_failures=quality['fresh_Agg_native_gate']['failures'],SVG_failures=quality['source_SVG_native_gate']['failures'])
        assert sha((case/'source.py').read_bytes())==row['payloads']['code']['expected_sha256'];pins()
    except Exception as e:record.update(status='technical_failure',reason=type(e).__name__+':'+str(e)[:1800],traceback=traceback.format_exc()[-4000:])
    finally:
        record['seconds']=round(time.monotonic()-began,2);record['finished_at_utc']=now();record['finished_epoch']=time.time();(case/'pipeline_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');db.execute('update cases set status=?,record=? where id=?',(record['status'],enc(record),ident));db.commit();db.close();emit('case_finished',id=ident,phase=phase,status=record['status'],seconds=record['seconds'],stage_seconds=record['stage_seconds'])
    return record
def snapshot(phase,finished=False):
    db=connect();rows=[json.loads(r[0]) for r in db.execute('select record from cases')];groups=dict(db.execute('select status,count(*) from cases group by status'));phase_counts={p:dict(db.execute('select status,count(*) from cases where phase=? group by status',(p,))) for p in ['unseen','bulk']};db.close();pairs=[r['qualified_pair'] for r in rows if r.get('qualified_pair')];files={}
    for profile in ['provider_original_reference_aligned','source_replay_aligned']:
        selected=sorted([r for r in pairs if r['profile']==profile],key=lambda r:r['id']);p=D/(profile+'.jsonl');q=p.with_suffix('.tmp');q.write_text(''.join(enc(r)+'\n' for r in selected));os.replace(q,p);files[profile]={'rows':len(selected),'file':str(p),'sha256':sha(p.read_bytes())}
    terminal=[r for r in rows if r.get('finished_epoch')];eligible=[r for r in terminal if r['status'] not in {'typed_skip_static_source_domain','preserved_development_capture_no_reexecution'}];stages={}
    for name in ['data_loading','capture','IR_native','QA','publication']:
        values=sorted(r.get('stage_seconds',{}).get(name) for r in terminal if name in r.get('stage_seconds',{}))
        stages[name]={'n':len(values),'total_worker_seconds':round(sum(values),3),'mean_seconds':round(sum(values)/len(values),3) if values else None,'p90_seconds':round(values[min(len(values)-1,int(len(values)*.9))],3) if values else None}
    last=sorted(terminal,key=lambda r:r['finished_epoch'])[-50:];window=max(r['finished_epoch'] for r in last)-min(r['started_epoch'] for r in last) if last else 0;reasons=collections.Counter()
    for r in eligible:
        if not r.get('qualified_pair'):
            if r.get('reason'):reasons[r['reason'].split(':',2)[0]+':'+r['reason'].split(':',2)[1] if ':' in r['reason'] else r['reason']]+=1
            else:
                for k in ['Agg_failures','SVG_failures']:
                    for fail in r.get(k,[]):reasons[k+':'+fail]+=1
    pass_rate=len(pairs)/max(1,len(eligible));dominant=max(stages,key=lambda n:stages[n]['total_worker_seconds']);analysis=[]
    if len(eligible)>=8 and pass_rate<.25:analysis.append({'cause':'low_closed_gate_pass_rate','eligible_rows':len(eligible),'qualified_fraction':round(pass_rate,4),'largest_failure_clusters':reasons.most_common(6),'action':'Keep failed rows out of both profiles; retain exact capture/geometry/font evidence for the next generic family repair.'})
    if stages[dominant]['n']>=4 and (stages[dominant]['mean_seconds'] or 0)>30:analysis.append({'cause':'dominant_slow_stage','stage':dominant,'mean_seconds':stages[dominant]['mean_seconds'],'action':'Use measured stage timings and failure families; do not repeat source execution or weaken pixel/data gates.'})
    performance={'monotonic_stage_seconds':stages,'elapsed_controller_seconds':round(time.monotonic()-RUN_BEGIN,3),'new_terminal_cases_per_minute':round(max(0,len(terminal)-RUN_BASELINE)/max(.001,time.monotonic()-RUN_BEGIN)*60,3),'rolling_last50_cases_per_minute':round(len(last)/max(1,window)*60,3),'qualified_fraction_of_executed_eligible':round(pass_rate,4),'completed_source_executions':sum(r.get('source_execution_completed',False) for r in terminal),'failure_clusters':reasons.most_common(15),'common_cause_analysis':analysis}
    out={'performance':performance,'schema':'matplotlib_plot_fixed_program_progress_v1','at_utc':now(),'phase':phase,'finished':finished,'input_rows':3557,'accounted_rows':sum(groups.values()),'states':groups,'phase_states':phase_counts,'qualified_pairs':len(pairs),'profiles':files,'source_executions':sum(1 for _ in (D/'cases').glob('*/source_execution_started.json')),'model_calls':0,'all_payloads_on_HKUST':True,'canonical_qualified_ledger_modified':False};atomic(D/'summary.json',out);return out
def main(workers,auto):
    global RUN_BEGIN,RUN_BASELINE
    import fcntl
    lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);policy=pins();db=connect();db.execute('create table if not exists cases(id text primary key,phase text,status text,worker_pid integer,birth text,record text)');db.commit();RUN_BASELINE=db.execute("select count(*) from cases where status!='running'").fetchone()[0];db.close();RUN_BEGIN=time.monotonic()
    pool=json.loads((D/'pool_summary.json').read_text());assert sha((D/'inputs.jsonl').read_bytes())==pool['inputs_sha256'];assert sha((D/'unseen_selected.jsonl').read_bytes())==pool['unseen_selected_sha256'];assert json.loads((D/'controls/real_negative_v1/result.json').read_text())['ok']
    allrows=[json.loads(l) for l in (D/'inputs.jsonl').read_text().splitlines()];unseen=[json.loads(l) for l in (D/'unseen_selected.jsonl').read_text().splitlines()];phases=[('unseen',unseen)]
    if auto:phases.append(('bulk',allrows))
    for phase,rows in phases:
        emit('phase_started',phase=phase,rows=len(rows),workers=workers);snapshot(phase)
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            futures=[executor.submit(worker,(r,phase)) for r in rows];last_snapshot=0;done=0
            for future in concurrent.futures.as_completed(futures):
                future.result();done+=1
                if phase=='unseen' or done%10==0 or time.monotonic()-last_snapshot>=15:snapshot(phase);last_snapshot=time.monotonic()
        out=snapshot(phase,finished=phase=='bulk' or not auto);atomic(D/(phase+'_summary.json'),out);emit('phase_finished',phase=phase,states=out['phase_states'][phase],qualified_pairs=out['qualified_pairs'])
    pins()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--auto-bulk',action='store_true');a=p.parse_args();main(a.workers,a.auto_bulk)
