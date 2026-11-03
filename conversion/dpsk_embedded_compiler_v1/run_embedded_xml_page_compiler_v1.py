#!/usr/bin/env python3
"""Durable cumulative-input + complete-native-page compiler extension.
Old compiler DB/proofs are read-only. No model/network/PDF calls.
"""
from pathlib import Path
import argparse,collections,concurrent.futures as cf,datetime,fcntl,json,os,signal,sqlite3,subprocess,sys,time,traceback,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import embedded_xml_compiler_v1 as C
import embedded_xml_page_core_v1 as P

D=P.D
DB=D/'once.sqlite'
OLDDB=Path(__file__).resolve().parents[1]/'results'/'embedded_XML_compiler_dpsk_v1'/'once.sqlite'
OLD_MANIFEST=Path(__file__).resolve().parents[1]/'results'/'embedded_XML_compiler_dpsk_v1'/'verified_candidates.jsonl'
INVENTORY=C.P/'embedded_XML_image_inventory_incremental_v3/inventory.json'
PREFILTER_DB=C.P/'embedded_XML_parallel_prefilter_v1/files.sqlite'
AUTO414=C.P/'goal500_automatic_admission_v2/accepted_new_pairs.jsonl'
LOCK=D/'program.lock'
POLICY=('cold_full_editor_source_XML_uniform_refresh_validate_fonts_ready_front_two_RAF_v1'
        '__official_local_mathjax_svg_fontCache_none_v1'
        '__identity_view_scale_translate_scroll_before_every_validation_stage_v1'
        '__deterministic_export_local_GUID_allocator_v1'
        '__embedded_native_complete_page_graph_once_v1')
REPLAY_TIMEOUT=330
REPLAY_ALARM=300
MAX_ATTEMPTS=1

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def connect():
    D.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=60);c.execute('pragma journal_mode=WAL');c.execute('pragma synchronous=NORMAL')
    c.execute('create table if not exists cumulative_cases(file text primary key,kind text,origin text,old_case_id text,status text,reason text,record text,updated_at text)')
    c.execute('create table if not exists parent_jobs(id text primary key,file text unique,kind text,purpose text,old_case_id text,status text,attempts integer default 0,reason text,record text,updated_at text)')
    c.execute('create table if not exists page_cases(id text primary key,parent_job_id text,file text,kind text,paper text,page_index integer,page_id text,page_name text,page_graph_sha256 text,page_xml_sha256 text,state text,reason text,record text,updated_at text)')
    c.execute('create table if not exists known_graphs(graph_sha text,source text,path text,alias text,primary key(graph_sha,source,path))')
    c.execute('create table if not exists once_graphs(graph_sha text primary key,case_id text,source text,created_at text)')
    c.execute('create table if not exists graph_aliases(graph_sha text,page_case_id text,parent_job_id text,page_index integer,source_kind text,alias text,created_at text,primary key(graph_sha,page_case_id))')
    c.execute('create table if not exists meta(key text primary key,value text)')
    return c

def meta_get(c,k,default=None):
    r=c.execute('select value from meta where key=?',(k,)).fetchone();return r[0] if r else default
def meta_set(c,k,v): c.execute('insert into meta values(?,?) on conflict(key) do update set value=excluded.value',(k,str(v)))
def update_cumulative(c,file,status=None,reason=None,record=None):
    sets=['updated_at=?'];args=[now()]
    if status is not None:sets.append('status=?');args.append(status)
    if reason is not None:sets.append('reason=?');args.append(str(reason)[:2000])
    if record is not None:sets.append('record=?');args.append(C.dumps(record))
    args.append(file);c.execute('update cumulative_cases set '+','.join(sets)+' where file=?',args)
def update_parent(c,ident,status=None,reason=None,record=None):
    sets=['updated_at=?'];args=[now()]
    if status is not None:sets.append('status=?');args.append(status)
    if reason is not None:sets.append('reason=?');args.append(str(reason)[:2000])
    if record is not None:sets.append('record=?');args.append(C.dumps(record))
    args.append(ident);c.execute('update parent_jobs set '+','.join(sets)+' where id=?',args)
def update_page(c,ident,state=None,reason=None,record=None):
    sets=['updated_at=?'];args=[now()]
    if state is not None:sets.append('state=?');args.append(state)
    if reason is not None:sets.append('reason=?');args.append(str(reason)[:2000])
    if record is not None:sets.append('record=?');args.append(C.dumps(record))
    args.append(ident);c.execute('update page_cases set '+','.join(sets)+' where id=?',args)

def parent_id(file): return C.sha('embedded_native_page_parent_v1|'+file)
def page_id(parent,index,sidecar_sha): return C.sha('embedded_native_page_v1|%s|%d|%s'%(parent,index,sidecar_sha))
def paper_of(file):
    p=Path(file)
    p=(p if p.is_absolute() else C.R/p).resolve()
    return p.relative_to((C.P/'recent_ai_source_expansion_v2/papers').resolve()).parts[0]

# ---------------------------------------------------------------------------
# Known graph ledger: preserve old known/once and add auto414 index
# ---------------------------------------------------------------------------
def hash_graph_file(path):
    try:
        b=(C.R/path).read_bytes() if not Path(path).is_absolute() else Path(path).read_bytes()
        _,_,hs,dh=C.document_graphs(b)
        return path,hs,dh,None
    except Exception as e:return path,[],None,type(e).__name__+':'+str(e)[:300]

def build_ledgers(c,workers=8):
    if meta_get(c,'ledgers_built')=='1': return
    started=time.monotonic()
    # Copy preserved compiler ledgers read-only.
    if OLDDB.exists():
        old=sqlite3.connect(OLDDB.as_uri()+'?mode=ro',uri=True);old.execute('pragma query_only=ON')
        known=[(h,s,p,a) for h,s,p,a in old.execute('select graph_sha,source,path,alias from known_graphs')]
        c.executemany('insert or ignore into known_graphs values(?,?,?,?)',known)
        once=[(h,cid,src,at) for h,cid,src,at in old.execute('select graph_sha,case_id,source,created_at from once_graphs')]
        c.executemany('insert or ignore into once_graphs values(?,?,?,?)',once)
        old.close();c.commit()
        C.put_json(D/'preserved_ledger_import.json',{'old_database':str(OLDDB),'known_rows':len(known),'once_rows':len(once),'old_manifest':str(OLD_MANIFEST),'old_manifest_sha256':C.sha(OLD_MANIFEST.read_bytes()) if OLD_MANIFEST.exists() else None})
    # Add coordinator's accepted414 native graphs.
    rows=[]
    if AUTO414.exists():
        for line in AUTO414.read_text().splitlines():
            if not line.strip():continue
            o=json.loads(line);p=o.get('code_file')
            if p:rows.append((p,o.get('id') or o.get('goal500_pair_id') or o.get('paper') or p))
    paths=sorted({p for p,_ in rows});by=collections.defaultdict(list)
    for p,a in rows:by[p].append(a)
    results=[];done=0
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(hash_graph_file,paths,chunksize=4):
            results.append(res);done+=1
            if done%100==0:print(json.dumps({'auto414_hash_progress':done,'total':len(paths)}),flush=True)
    errors=[];inserted=0
    for path,hs,dh,err in results:
        if err:errors.append({'path':path,'error':err});continue
        for h in hs:
            for alias in by[path]:
                c.execute('insert or ignore into known_graphs values(?,?,?,?)',(h,'goal500_auto414',path,alias));inserted+=1
    c.commit();C.put_json(D/'known_graph_hash_errors.json',errors)
    C.put_json(D/'ledger_build_summary.json',{'old_known_rows':c.execute("select count(*) from known_graphs where source!='goal500_auto414'").fetchone()[0],
        'auto414_paths':len(paths),'auto414_graph_hashes_inserted':inserted,'auto414_errors':len(errors),
        'known_total':c.execute('select count(*) from known_graphs').fetchone()[0],
        'once_total':c.execute('select count(*) from once_graphs').fetchone()[0],
        'seconds':time.monotonic()-started,'errors':errors[:20],'CPU_host':'HKUST3'})
    meta_set(c,'ledgers_built','1');c.commit()
    print(json.dumps({'ledgers_built':True,'known':c.execute('select count(*) from known_graphs').fetchone()[0],'once':c.execute('select count(*) from once_graphs').fetchone()[0],'errors':len(errors),'seconds':round(time.monotonic()-started,1)}),flush=True)

# ---------------------------------------------------------------------------
# Cumulative adapter
# ---------------------------------------------------------------------------
def prefilter_map():
    if not PREFILTER_DB.exists():return {}
    db=sqlite3.connect(PREFILTER_DB.as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON')
    out={file:(status,json.loads(rec)) for file,status,rec in db.execute('select file,status,record from files')}
    db.close();return out

def init_cumulative(c):
    inv=json.loads(INVENTORY.read_text());inv_sha=C.sha(INVENTORY.read_bytes())
    meta_set(c,'inventory_file',str(INVENTORY));meta_set(c,'inventory_sha256',inv_sha);c.commit()
    existing={r[0] for r in c.execute('select file from cumulative_cases')}
    old={}
    if OLDDB.exists():
        olddb=sqlite3.connect(OLDDB.as_uri()+'?mode=ro',uri=True);olddb.execute('pragma query_only=ON')
        for ident,file,kind,status,reason,recraw in olddb.execute('select id,file,kind,status,reason,record from cases'):
            old[file]=(ident,kind,status,reason,json.loads(recraw) if recraw else {})
        olddb.close()
    pf=prefilter_map();added=0;parents=0
    for row in inv['candidates']:
        file=row['file'];kind=row['kind']
        if file in existing:continue
        if file in old:
            oldid,okind,status,reason,record=old[file]
            origin='frozen_v2_compiler'
            if status=='skipped_multi_page_document':
                state='old_multi_page_held';purpose='frozen_multi_page'
            elif status=='skipped_extract_error' and ('incorrect header check' in (reason or '') or 'zTXt' in (reason or '')):
                state='old_repair_retry_queued';purpose='frozen_repair_retry'
            else:
                state='imported_'+status;purpose=None
            c.execute('insert into cumulative_cases values(?,?,?,?,?,?,?,?)',(file,kind,origin,oldid,state,reason or '',C.dumps(record),now()))
            if purpose:
                pid=parent_id(file)
                c.execute('insert or ignore into parent_jobs(id,file,kind,purpose,old_case_id,status,attempts,reason,record,updated_at) values(?,?,?,?,?,?,?,?,?,?)',(pid,file,kind,purpose,oldid,'queued_extract',0,'',C.dumps({'purpose':purpose,'old_case_id':oldid,'old_reason':reason}),now()));parents+=1
        else:
            origin='incremental_v3'
            pst,prec=pf.get(file,('missing','{}'));record={'prefilter':prec,'prefilter_status':pst}
            purpose=None
            if pst=='provisional_valuable_single_page_XML':state='new_single_page_queued';purpose='new_single_page'
            elif pst=='multi_page_held_before_inflate':state='new_multi_page_queued';purpose='new_multi_page'
            elif pst=='pending_metadata_prefilter':state='new_repair_retry_queued';purpose='new_repair_retry'
            elif pst=='below_existing_value_policy':state='skipped_below_value_policy_prefilter'
            elif pst=='exact_XML_already_processed':state='skipped_exact_XML_prefilter'
            else:state='new_pending_extract_queued';purpose='new_pending_extract'
            c.execute('insert into cumulative_cases values(?,?,?,?,?,?,?,?)',(file,kind,origin,None,state,'',C.dumps(record),now()))
            if purpose:
                pid=parent_id(file)
                c.execute('insert or ignore into parent_jobs(id,file,kind,purpose,old_case_id,status,attempts,reason,record,updated_at) values(?,?,?,?,?,?,?,?,?,?)',(pid,file,kind,purpose,None,'queued_extract',0,'',C.dumps({'purpose':purpose,'prefilter':prec,'prefilter_status':pst}),now()));parents+=1
        added+=1
    c.commit();meta_set(c,'cumulative_initialized','1');c.commit()
    print(json.dumps({'cumulative_added':added,'parent_jobs_added':parents,'cumulative_total':c.execute('select count(*) from cumulative_cases').fetchone()[0],'parent_jobs_total':c.execute('select count(*) from parent_jobs').fetchone()[0]}),flush=True)

# ---------------------------------------------------------------------------
# Parent extraction + page isolation
# ---------------------------------------------------------------------------
_WORKER_IDENTITY={}
def extract_parent_job(job):
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded_parent_page_extract_120s')));signal.alarm(120)
    started=time.monotonic();out=dict(id=job['id'],file=job['file'],kind=job['kind'],purpose=job['purpose'],status='pending_parent_extract',at_utc=now())
    try:
        source=C.R/job['file'];paper=paper_of(job['file'])
        if paper not in _WORKER_IDENTITY: _WORKER_IDENTITY[paper]=C.candidate_source_identity(source)
        identity=_WORKER_IDENTITY[paper]
        e=P.extract_full_v2(source,job['kind']);full=e['raw'];doc=P.parse_full_pages(full)
        base=D/'parents'/job['id'];base.mkdir(parents=True,exist_ok=True)
        fullpath=base/'full_embedded_author.drawio'
        if fullpath.exists():assert fullpath.read_bytes()==full
        else:C.atomic_put(fullpath,full)
        pages=[]
        for pg in doc['pages']:
            side=pg['page_sidecar_XML']
            pfile=base/('page_%04d_%s.drawio'%(pg['page_index'],pg['page_sidecar_sha256'][:16]))
            if pfile.exists():assert pfile.read_bytes()==side
            else:C.atomic_put(pfile,side)
            row={k:v for k,v in pg.items() if k!='page_sidecar_XML'}
            row['page_sidecar_file']=str(pfile.relative_to(C.R))
            models,_,native,classify,valuable,_=C.import_native_modules()
            _,ms=models(side)
            assert len(ms)==1
            features=native(side.decode('utf-8-sig'));kind_class,reasons=classify(features,'drawio',{})
            is_valuable=bool(kind_class=='complex_candidate' and len(ms)==1 and valuable(features))
            import arxiv_native_framework_layout_gate_v1 as gate
            layout=gate.check(side)
            static=C.static_diagnostics(side,features,ms)
            row.update(features=features,kind_class=kind_class,class_reasons=reasons,valuable=is_valuable,
                       layout_gate=layout,static_diagnostics=static)
            pages.append(row)
        out.update(status='parent_extracted',full_embedded_XML_file=str(fullpath.relative_to(C.R)),
                   full_embedded_XML_sha256=C.sha(full),full_embedded_XML_bytes=len(full),
                   source_sha256=e['source_sha256'],source_bytes=e['source_bytes'],
                   extraction={k:e.get(k) for k in ('chunk_type','key','steps','compression_mode','inflate_attempts','text_charset','source_container_sha256','official_decoder','decoder_adapter')},
                   paper_identity={k:identity[k] for k in ('paper','paper_folder','source_root','source_archive_file','source_archive_sha256','source_archive_bytes','source_receipt_file','source_receipt_sha256','original_paper_record_SHA256','paper_metadata')},
                   pages=pages,page_count=len(pages),root_kind=doc['root_kind'])
        if job['purpose']=='frozen_repair_retry':
            out['repair_evidence']={'old_case_id':job.get('old_case_id'),'old_failure_reason':job.get('old_reason'),
                'retry_count':1,'decoder_adapter':e.get('decoder_adapter'),'compression_mode':e.get('compression_mode'),
                'inflate_attempts':e.get('inflate_attempts'),'steps':e.get('steps'),'old_ledger_unmodified':True,
                'new_full_embedded_XML_sha256':C.sha(full),'page_count':len(pages),'at_utc':now()}
            C.put_json(base/'zTXt_repair_evidence.json',out['repair_evidence'])
    except Exception as ex:out.update(status='failed_parent_extract',reason=type(ex).__name__+':'+str(ex)[:900]+'|'+traceback.format_exc()[-1200:])
    finally:
        signal.alarm(0);out['seconds']=time.monotonic()-started;out['finished_utc']=now()
    return out

def page_decide(c,parent,row,known,own):
    pid=parent['id'];file=parent['file'];side_sha=row['page_sidecar_sha256'];graph=row['page_graph_sha256']
    ident=page_id(pid,row['page_index'],side_sha)
    paper=parent['paper_identity']['paper'] if parent.get('paper_identity') else None
    rec={'parent_job_id':pid,'file':file,'kind':parent['kind'],'paper':paper,'page_index':row['page_index'],
         'page_id':row.get('page_id'),'page_name':row.get('page_name'),'page_graph_sha256':graph,'page_xml_sha256':side_sha,
         'parent_full_embedded_XML_file':parent['full_embedded_XML_file'],'parent_full_embedded_XML_sha256':parent['full_embedded_XML_sha256'],
         'page':row,'parent_purpose':parent.get('purpose'),'source_identity':parent.get('paper_identity')}
    state='held_below_value_policy';reason='page_value_policy:%s:%s'%(row.get('kind_class'),','.join(row.get('class_reasons') or []))
    if row.get('page_extraction_kind')=='compressed_zlib_wrapper_URI_decoded_not_official':
        state='held_unsupported_official_page_compression';reason='official_Graph.decompress_requires_raw_deflate'
    elif not row.get('valuable'):
        pass
    elif not (row.get('static_diagnostics') or {}).get('ok'):
        state='held_static_diagnostics';reason='page_static_QA:'+','.join((row.get('static_diagnostics') or {}).get('failures',[]))
    elif not (row.get('layout_gate') or {}).get('ok'):
        state='held_layout_gate';reason='layout_gate:%s:%s'%((row.get('layout_gate') or {}).get('policy'),','.join((row.get('layout_gate') or {}).get('reasons',[])))
    else:
        dup=known.get(graph);ownhit=own.get(graph)
        if dup or ownhit:
            source='own:'+ownhit if ownhit else dup['source']+':'+dup['path']
            state='skipped_duplicate_page_graph';reason='duplicate_page_graph:'+source;rec['duplicate']={'graph_sha256':graph,'source':source,'known':dup}
        else:
            state='eligible';reason='unique_complete_native_page_complex_candidate';own[graph]=ident
            c.execute('insert or ignore into once_graphs values(?,?,?,?)',(graph,ident,file,now()))
    c.execute('insert or replace into page_cases(id,parent_job_id,file,kind,paper,page_index,page_id,page_name,page_graph_sha256,page_xml_sha256,state,reason,record,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (ident,pid,file,parent['kind'],paper,row['page_index'],row.get('page_id'),row.get('page_name'),graph,side_sha,state,reason,C.dumps(rec),now()))
    c.execute('insert or ignore into graph_aliases values(?,?,?,?,?,?,?)',(graph,ident,pid,row['page_index'],'embedded_native_complete_page',file,now()))
    return ident,state

def extract_phase(c,workers=8):
    jobs=[dict(zip(('id','file','kind','purpose','old_case_id','record'),r)) for r in c.execute("select id,file,kind,purpose,old_case_id,record from parent_jobs where status='queued_extract' order by file")]
    for j in jobs:
        rec=json.loads(j['record']) if j['record'] else {}
        j['old_reason']=rec.get('old_reason');j['prefilter']=rec.get('prefilter')
    if not jobs:print(json.dumps({'extract':'nothing_pending'}));return
    known={}
    for h,source,path,alias in c.execute('select graph_sha,source,path,alias from known_graphs'):
        known.setdefault(h,{'source':source,'path':path,'alias':alias})
    own={h:cid for h,cid in c.execute('select graph_sha,case_id from once_graphs')}
    started=time.monotonic();stats=collections.Counter();pages_total=0;done=0
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        for job,res in zip(jobs,pool.map(extract_parent_job,jobs,chunksize=1)):
            done+=1
            if res.get('status')!='parent_extracted':
                update_parent(c,res['id'],'failed_parent_extract',res.get('reason',''),{'extraction':res});update_cumulative(c,res['file'],'parent_extract_failed',res.get('reason',''),{'parent_extraction':res});stats['failed_parent_extract']+=1;c.commit();continue
            update_parent(c,res['id'],'extracted','complete_pages_isolated',{'extraction':res})
            cum=c.execute('select status from cumulative_cases where file=?',(res['file'],)).fetchone()
            if cum:
                newstate='old_multi_page_pages_extracted' if res.get('purpose')=='frozen_multi_page' else ('old_repair_retry_pages_extracted' if res.get('purpose')=='frozen_repair_retry' else 'new_pages_extracted')
                update_cumulative(c,res['file'],newstate,'',{'parent_extraction':{k:res.get(k) for k in ('full_embedded_XML_file','full_embedded_XML_sha256','page_count','purpose')}})
            for row in res['pages']:
                ident,state=page_decide(c,res,row,known,own);pages_total+=1;stats[state]+=1
            c.commit()
            if done%10==0:publish(c);print(json.dumps({'extract_progress':done,'total':len(jobs),'pages':pages_total,'stats':dict(stats),'seconds':round(time.monotonic()-started,1)}),flush=True)
    c.commit();meta_set(c,'extract_complete','1');c.commit();publish(c)
    print(json.dumps({'extract_done':done,'pages':pages_total,'stats':dict(stats),'seconds':round(time.monotonic()-started,1)}),flush=True)

# ---------------------------------------------------------------------------
# Replay of one complete native page
# ---------------------------------------------------------------------------
def get_page(c,ident):
    r=c.execute('select id,parent_job_id,file,kind,paper,page_index,page_id,page_name,page_graph_sha256,page_xml_sha256,state,reason,record,updated_at from page_cases where id=?',(ident,)).fetchone()
    if not r:raise KeyError(ident)
    d=dict(zip(('id','parent_job_id','file','kind','paper','page_index','page_id','page_name','page_graph_sha256','page_xml_sha256','state','reason','record','updated_at'),r))
    d['record']=json.loads(d['record']) if d['record'] else {};return d

def get_parent(c,ident):
    r=c.execute('select id,file,kind,purpose,old_case_id,status,attempts,reason,record,updated_at from parent_jobs where id=?',(ident,)).fetchone()
    if not r:raise KeyError(ident)
    d=dict(zip(('id','file','kind','purpose','old_case_id','status','attempts','reason','record','updated_at'),r))
    d['record']=json.loads(d['record']) if d['record'] else {};return d

def _page_assets(dep):
    return [a.get('file') for a in dep.get('assets',[]) if a.get('file')]

def work_page(ident):
    folder=D/'cases'/ident;folder.mkdir(parents=True,exist_ok=True)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded_complete_page_replay_%ds'%REPLAY_ALARM)));signal.alarm(REPLAY_ALARM)
    renderer=None;started=time.monotonic()
    record={'id':ident,'status':'pending_complete_page_replay','at_utc':now(),'policy':POLICY,
            'new_PDF_import_calls':0,'new_model_calls':0,'new_source_downloads':0,'CPU_host':'HKUST3'}
    try:
        c=connect();pc=get_page(c,ident);parent=get_parent(c,pc['parent_job_id']);c.close()
        prec=parent['record']['extraction'];pmeta=pc['record']['page']
        fullpath=C.R/prec['full_embedded_XML_file'];full_raw=fullpath.read_bytes()
        if C.sha(full_raw)!=prec['full_embedded_XML_sha256']:raise ValueError('parent_full_embedded_XML_changed')
        source=C.R/pc['file'];source_bytes=source.read_bytes()
        if C.sha(source_bytes)!=prec['source_sha256']:raise ValueError('original_container_hash_changed')
        e=P.extract_full_v2(source,parent['kind'])
        if e['raw_sha256']!=prec['full_embedded_XML_sha256'] or e['raw']!=full_raw:raise ValueError('embedded_XML_bytes_changed_between_extract_and_replay')
        fresh=P.parse_full_pages(full_raw)
        if pc['page_index']<0 or pc['page_index']>=len(fresh['pages']):raise ValueError('selected_page_index_out_of_range')
        fresh_page=fresh['pages'][pc['page_index']]
        sidecar_file=C.R/pmeta['page_sidecar_file'];sidecar=sidecar_file.read_bytes()
        if C.sha(sidecar)!=pc['page_xml_sha256'] or sidecar!=fresh_page['page_sidecar_XML']:
            raise ValueError('page_identity_or_sidecar_bytes_changed')
        if fresh_page.get('page_id')!=pc.get('page_id') or fresh_page.get('page_name')!=pc.get('page_name'):
            raise ValueError('page_id_or_name_changed')
        if fresh_page['page_graph_sha256']!=pc['page_graph_sha256']:raise ValueError('page_graph_hash_changed')
        identity=C.candidate_source_identity(source)
        if identity['paper']!=pc['paper']:raise ValueError('paper_identity_changed')
        models,dependencies,native,classify,valuable,_=C.import_native_modules()
        _,ms=models(sidecar)
        if len(ms)!=1:raise ValueError('sidecar_not_one_complete_mxGraphModel')
        features=native(sidecar.decode('utf-8-sig'));kind_class,class_reasons=classify(features,'drawio',{})
        if kind_class!='complex_candidate' or not valuable(features):raise ValueError('page_value_policy_not_met_on_replay:%s:%s'%(kind_class,class_reasons))
        import arxiv_native_framework_layout_gate_v1 as gate
        layout=gate.check(sidecar)
        if not layout.get('ok'):raise ValueError('layout_gate_failed:'+','.join(layout.get('reasons',[])))
        with zipfile.ZipFile(C.WAR) as war:dep=dependencies(sidecar,source,source,war)
        allowed={'author_adjacent_file','source_only_relative_asset_needs_portable_closure'}
        unresolved=[a for a in dep['issues'] if a.get('status') not in allowed]
        static=C.static_diagnostics_with_assets(sidecar,features,dep['models'],dep)
        if unresolved or static['failures']:
            raise ValueError('page_static_QA_failed:'+','.join(static['failures'] or sorted({a.get('status','?') for a in unresolved})))
        relative=any(a.get('status') in allowed for a in dep['assets'])
        asset_files=_page_assets(dep);package_manifest=None
        if relative:
            from arxiv_author_native_asset_package_v1 import package
            code,assets,package_manifest=package(sidecar,dep,folder/'standalone_asset_package');code=Path(code);assets={k:Path(v) for k,v in assets.items()}
            for a in package_manifest.get('resource_dependencies',[]):asset_files.append(a.get('original_asset_file'))
            with zipfile.ZipFile(C.WAR) as war:closed=dependencies(sidecar,code,code.parent/'no_original_directory.pdf',war)
            if closed['issues']:raise ValueError('packaged_page_resource_closure_failed:'+','.join(sorted({a.get('status','?') for a in closed['issues']})))
            dep['asset_map']=assets
        else:
            code=folder/'code'/'author_page.drawio';C.atomic_put(code,sidecar)
        if code.read_bytes()!=sidecar:raise ValueError('page_sidecar_code_bytes_changed')
        archive_proof=C.verify_source_archive_members(identity,source,[C.R/a for a in asset_files if a])
        C.put_json(folder/'archive_membership.json',archive_proof)
        import arxiv_author_native_font_replay_v2 as fonts
        (D/'font_dependencies').mkdir(parents=True,exist_ok=True);fonts.D=D
        from arxiv_math_stable_export_renderer_v1 import MathSynced
        renderer=MathSynced(dep['asset_map'])
        full_decode=C.official_decode_agreement(renderer,source_bytes,parent['kind'],full_raw)
        C.put_json(folder/'official_full_decoder_agreement.json',full_decode)
        page_decode=P.official_page_decode_agreement(renderer,full_raw,pmeta|{'page_sidecar_XML':sidecar})
        C.put_json(folder/'official_page_decoder_comparison.json',page_decode)
        selection_parent=dict(prec);selection_parent['full_embedded_XML']=full_raw
        selection_page=dict(pmeta);selection_page['page_sidecar_XML']=sidecar
        selection=P.page_selection_proof(selection_parent,selection_page)
        C.put_json(folder/'page_selection_proof.json',selection)
        repair_evidence=None
        if parent.get('purpose')=='frozen_repair_retry':
            repair_evidence={'schema':'embedded_zTXt_raw_deflate_repair_evidence_v1','old_case_id':parent.get('old_case_id'),
                'old_failure_reason':parent['record'].get('old_reason'),'retry_count':1,
                'decoder_adapter':e.get('decoder_adapter'),'compression_mode':e.get('compression_mode'),
                'inflate_attempts':e.get('inflate_attempts'),'steps':e.get('steps'),
                'old_ledger_unmodified':True,'new_full_embedded_XML_sha256':C.sha(full_raw),
                'selected_page_index':pc['page_index'],'selected_page_XML_sha256':C.sha(sidecar),'at_utc':now()}
            C.put_json(folder/'zTXt_repair_evidence.json',repair_evidence)
        out=folder/'synced_source_replay';proof=renderer.replay(sidecar,out)
        static2=C.static_diagnostics_with_assets(sidecar,features,dep['models'],dep)
        render_qa=C.render_diagnostics(proof,out/'official.png',dep,package_manifest)
        ok=bool(static2['ok'] and layout.get('ok') and render_qa['ok'] and proof.get('ok') and full_decode and page_decode)
        reason='strict_complete_page_render_static_archive_font_official_decoder_edit_restore_checks_passed' if ok else 'page_validation_failed:'+','.join(sorted(set(static2['failures']+render_qa['failures'])))
        pair=None
        if ok:
            pid=C.sha(C.dumps({'page_case_id':ident,'parent':parent['id'],'page_index':pc['page_index'],'sidecar':C.sha(sidecar),'policy':POLICY}))
            page_selection_sha=C.sha((folder/'page_selection_proof.json').read_bytes())
            full_decode_sha=C.sha((folder/'official_full_decoder_agreement.json').read_bytes())
            page_decode_sha=C.sha((folder/'official_page_decoder_comparison.json').read_bytes())
            pair={
                'id':pid,'raw_source_pair_id':ident,'raw_source_pair_ids':[ident],
                'parent_source_pair_id':parent.get('old_case_id'),'parent_job_id':parent['id'],
                'source':'arxiv_embedded_native_drawio','source_origin_kind':'embedded_native_complete_page',
                'paper':identity['paper'],'paper_metadata':identity['paper_metadata'],'profile':'author_native_source_replay',
                'format':'drawio','category':'scientific_diagram',
                'code_file':str(code.relative_to(C.R)),'code_sha256':C.sha(sidecar),
                'image_file':str((out/'official.png').relative_to(C.R)),'image_sha256':C.sha((out/'official.png').read_bytes()),
                'original_container_file':pc['file'],'original_container_sha256':prec['source_sha256'],
                'original_author_XML':prec['full_embedded_XML_file'],'original_author_XML_sha256':prec['full_embedded_XML_sha256'],
                'original_page_author_XML':str(sidecar_file.relative_to(C.R)),'original_page_author_XML_sha256':C.sha(sidecar),
                'selected_page_index':pc['page_index'],'selected_page_id':pc.get('page_id'),'selected_page_name':pc.get('page_name'),
                'selected_page_XML_sha256':C.sha(sidecar),'selected_page_extraction_kind':pmeta.get('page_extraction_kind'),
                'selected_page_model_canonical_sha256':pmeta.get('page_model_canonical_sha256'),
                'selected_page_graph_sha256':pc['page_graph_sha256'],
                'paired_code_XML_bytes_equal_selected_page_XML':True,
                'paired_code_XML_bytes_equal_full_embedded_XML':C.sha(sidecar)==prec['full_embedded_XML_sha256'],
                'full_embedded_XML_bytes_preserved':True,'full_original_parent_mxfile_immutable':True,
                'page_selection_proof':str((folder/'page_selection_proof.json').relative_to(C.R)),'page_selection_proof_sha256':page_selection_sha,
                'official_full_decoder_agreement':str((folder/'official_full_decoder_agreement.json').relative_to(C.R)),'official_full_decoder_agreement_sha256':full_decode_sha,
                'official_page_decoder_comparison':str((folder/'official_page_decoder_comparison.json').relative_to(C.R)),'official_page_decoder_comparison_sha256':page_decode_sha,
                'native_replay_proof':str((out/'synced_replay_proof.json').relative_to(C.R)),'native_replay_proof_sha256':C.sha((out/'synced_replay_proof.json').read_bytes()),
                'archive_membership_proof':str((folder/'archive_membership.json').relative_to(C.R)),'archive_membership_proof_sha256':C.sha((folder/'archive_membership.json').read_bytes()),
                'source_archive_file':identity['source_archive_file'],'source_archive_sha256':identity['source_archive_sha256'],
                'source_receipt_file':identity['source_receipt_file'],'source_receipt_sha256':identity['source_receipt_sha256'],
                'asset_package':package_manifest,'font_dependencies':proof.get('font_observations',{}).get('font_assets',[]),
                'renderer_policy':POLICY,'base_validation_thresholds_unchanged':True,
                'static_QA':static2,'render_QA':render_qa,'layout_gate':layout,
                'page_model_identity':{'canonical_sha256':pmeta.get('page_model_canonical_sha256'),'graph_sha256':pc['page_graph_sha256'],'cell_count':pmeta.get('cell_count'),'vertex_count':pmeta.get('vertex_count'),'edge_count':pmeta.get('edge_count')},
                'repair_evidence':repair_evidence,
                'original_PDF_file':None,'original_PDF_sha256':None,
                'original_PDF_fidelity':'not_assessed_embedded_page_metadata','actual_paper_PDF_figure_usage':'not_certified',
                'whole_figure_wrapper':False,'standalone_image_assets_complete':True,
                'quality_state':'verified_embedded_native_complete_page_candidate',
                'quality_views':['arxiv_embedded_native_complete_page_candidate'],
                'accepted_authoritative':False,'authoritative_index_updated':False,
                'new_PDF_import_calls':0,'new_model_calls':0,'new_source_downloads':0,
                'original_source_payloads_unchanged':True,'official_WAR_sha256':C.sha(C.WAR.read_bytes()),
            }
        after_source=C.sha(source.read_bytes())==prec['source_sha256']
        after_full=C.sha(fullpath.read_bytes())==prec['full_embedded_XML_sha256']
        after_side=C.sha(sidecar_file.read_bytes())==pc['page_xml_sha256']
        if not (after_source and after_full and after_side):raise ValueError('original_source_or_full_or_sidecar_hash_changed_after_replay')
        if C.sha((C.R/identity['source_archive_file']).read_bytes())!=identity['source_archive_sha256']:raise ValueError('source_archive_hash_changed')
        if C.sha((C.R/identity['source_receipt_file']).read_bytes())!=identity['source_receipt_sha256']:raise ValueError('source_receipt_hash_changed')
        record.update(status='verified_embedded_native_complete_page_replay' if ok else 'failed_page_validation',reason=reason,pair=pair,
                      page_model_identity={'canonical_sha256':pmeta.get('page_model_canonical_sha256'),'graph_sha256':pc['page_graph_sha256'],'cell_count':pmeta.get('cell_count'),'vertex_count':pmeta.get('vertex_count'),'edge_count':pmeta.get('edge_count')},
                      static_QA=static2,render_QA=render_qa,layout_gate=layout,official_full_decoder_agreement=full_decode,
                      official_page_decoder_comparison=page_decode,page_selection_proof=selection,
                      source_identity=identity,repair_evidence=repair_evidence,
                      asset_audit={k:v for k,v in dep.items() if k not in ('models','asset_map')},package_manifest=package_manifest,
                      source_hashes_unchanged_after=True,full_embedded_XML_unchanged_after=after_full,page_sidecar_unchanged_after=after_side,
                      seconds=time.monotonic()-started,finished_utc=now())
    except Exception as e:
        record.update(status='failed_page_replay',reason=type(e).__name__+':'+str(e)[:2200])
    finally:
        if renderer:
            try:renderer.close()
            except Exception:pass
        signal.alarm(0);record['seconds']=time.monotonic()-started;record['finished_utc']=now()
        C.put_json(folder/'record.json',record)
    return record

# ---------------------------------------------------------------------------
# Durable page batch
# ---------------------------------------------------------------------------
def claim_page(c,ident):
    c.execute('begin immediate')
    n=c.execute("update page_cases set state='attempt_started',reason='page_replay_claimed',updated_at=? where id=? and state='eligible' and (record is null or json_extract(record,'$.attempts') is null)",(now(),ident)).rowcount
    c.commit();return n==1

def spawn_page(ident):
    folder=D/'cases'/ident;folder.mkdir(parents=True,exist_ok=True)
    log=(folder/'worker.log').open('ab')
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',ident],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:child.wait(timeout=REPLAY_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=5)
    finally:log.close()
    p=folder/'record.json'
    if p.exists():
        try:return json.loads(p.read_text())
        except Exception as e:return {'id':ident,'status':'failed_page_record_invalid','reason':type(e).__name__+':'+str(e)[:300]}
    return {'id':ident,'status':'failed_page_worker_no_record','exit':child.returncode,'reason':'worker produced no terminal record'}

def replay_pages(c,ids,workers=2):
    claimed=[]
    for ident in ids:
        if claim_page(c,ident):claimed.append(ident)
    print(json.dumps({'page_replay_claimed':len(claimed),'workers':workers}),flush=True)
    results=[];started=time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(spawn_page,claimed):
            ident=res.get('id')
            if res.get('status')=='verified_embedded_native_complete_page_replay' and res.get('pair'):
                update_page(c,ident,'verified','strict_complete_page_replay_verified',{'verified':res});state='verified'
            else:
                update_page(c,ident,'failed_page_replay',res.get('reason') or res.get('status') or 'unknown_failure',{'review':res});state='failed_page_replay'
            c.commit();results.append(res);publish(c)
            print(json.dumps({'page_replay_result':ident,'state':state,'reason':res.get('reason')}),flush=True)
    print(json.dumps({'page_replay_done':len(results),'seconds':round(time.monotonic()-started,1)}),flush=True)
    return results

def pilot_ids(c,limit):
    rows=c.execute("select p.id,p.parent_job_id,p.page_index,p.record,j.purpose from page_cases p join parent_jobs j on j.id=p.parent_job_id where p.state='eligible' order by p.parent_job_id,p.page_index").fetchall()
    picked=[];seen=set()
    def add(r):
        if r and r[0] not in seen:seen.add(r[0]);picked.append(r)
    add(rows[0] if rows else None)
    add(next((r for r in rows if r[4]=='frozen_repair_retry'),None))
    add(next((r for r in rows if r[2]>0),None))
    add(next((r for r in rows if r[4]=='new_single_page'),None))
    for r in rows:add(r)
    return [r[0] for r in picked[:limit]]

# ---------------------------------------------------------------------------
# Publication / status
# ---------------------------------------------------------------------------
def counters(c):
    states=dict(c.execute('select state,count(*) from page_cases group by state'))
    reasons=dict(c.execute("select reason,count(*) from page_cases where state not in ('eligible','verified') and reason is not null group by reason"))
    pages=[json.loads(r[0]) for r in c.execute("select record from page_cases where state='verified' and record is not null")]
    pairs=[]
    for rec in pages:
        v=rec.get('verified') or {}
        if v.get('pair'):pairs.append(v['pair'])
    return {'page_states':states,'page_reasons':reasons,'verified_page_candidates':len(pairs),
            'cumulative_states':dict(c.execute('select status,count(*) from cumulative_cases group by status')),
            'parent_states':dict(c.execute('select status,count(*) from parent_jobs group by status')),
            'aliases':c.execute('select count(*) from graph_aliases').fetchone()[0],
            'known_graphs':c.execute('select count(*) from known_graphs').fetchone()[0],
            'once_graphs':c.execute('select count(*) from once_graphs').fetchone()[0]}

def publish(c):
    rows=c.execute("select p.id,p.record from page_cases p where p.state='verified'").fetchall();pairs=[]
    for ident,recraw in rows:
        try:r=json.loads(recraw);p=r.get('verified',{}).get('pair') or r.get('pair')
        except Exception:p=None
        if p:pairs.append(p)
    path=D/'verified_pages.jsonl';tmp=path.with_name(path.name+'.tmp');tmp.write_text(''.join(C.dumps(p)+'\n' for p in pairs));os.replace(tmp,path)
    cnt=counters(c)
    status={'schema':'embedded_native_page_compiler_status_v1','task':'dpsk_svg_png_compiler_20261103_continuation',
            'state':'batch_running','phase':'complete_native_page_extension','updated_at':now(),'CPU_host':'HKUST3',
            'policy':POLICY,'output_root':str(D.relative_to(Path(__file__).resolve().parents[1])),
            'inventory_v3':str(INVENTORY.relative_to(C.R)),'inventory_sha256':C.sha(INVENTORY.read_bytes()),
            'inventory_candidates':c.execute('select count(*) from cumulative_cases').fetchone()[0],
            'old_compiler_namespace':str(OLDDB.parent.relative_to(Path(__file__).resolve().parents[1])),
            'old_compiler_manifest':str(OLD_MANIFEST.relative_to(Path(__file__).resolve().parents[1])) if OLD_MANIFEST.exists() else None,
            'old_compiler_manifest_sha256':C.sha(OLD_MANIFEST.read_bytes()) if OLD_MANIFEST.exists() else None,
            'authoritative_414_untouched':True,'old_compiler_core_untouched':True,
            'verified_pages_manifest':str(path.relative_to(Path(__file__).resolve().parents[1])),'verified_pages_manifest_sha256':C.sha(path.read_bytes()),
            'database':str(DB.relative_to(Path(__file__).resolve().parents[1])),'proof_root':str(D.relative_to(Path(__file__).resolve().parents[1])),
            'old3759_baseline_modified':False,'authoritative_414_modified':False,'sources_modified':False,
            'new_PDF_import_calls':0,'new_model_calls':0,'new_source_downloads':0,
            'notes':'Complete native page sidecars are separate from full parent embedded mxfile bytes. Candidate exports only; coordinator must review and add support before counting.',
            **cnt}
    C.put_json(D/'status.json',status);C.put_json(Path(__file__).resolve().parents[1]/'status_page_compiler.json',status)
    return status

def acquire_lock():
    D.mkdir(parents=True,exist_ok=True);f=LOCK.open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);return f

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case');ap.add_argument('command',nargs='?',default='status',choices=['init','extract','pilot','batch','status','verify']);ap.add_argument('--workers',type=int,default=8);ap.add_argument('--replay-workers',type=int,default=2);ap.add_argument('--limit',type=int,default=8);a=ap.parse_args()
    if a.case:
        r=work_page(a.case);print(json.dumps({'id':a.case,'status':r.get('status'),'reason':r.get('reason')},ensure_ascii=False));return
    lock=acquire_lock();c=connect()
    try:
        if a.command in ('init','extract','pilot','batch'):
            build_ledgers(c,workers=a.workers);init_cumulative(c);publish(c)
        if a.command in ('extract','pilot','batch'):
            extract_phase(c,workers=a.workers);publish(c)
        if a.command=='pilot':
            if c.execute("select count(*) from parent_jobs where status='queued_extract'").fetchone()[0]:extract_phase(c,workers=a.workers)
            ids=pilot_ids(c,a.limit);print(json.dumps({'pilot_page_ids':ids,'count':len(ids)}));C.put_json(D/'pilot_plan.json',{'ids':ids,'count':len(ids),'at_utc':now()});replay_pages(c,ids,workers=a.replay_workers);publish(c)
        elif a.command=='batch':
            if c.execute("select count(*) from parent_jobs where status='queued_extract'").fetchone()[0]:extract_phase(c,workers=a.workers)
            while True:
                ids=[r[0] for r in c.execute("select id from page_cases where state='eligible' order by parent_job_id,page_index limit ?",(max(2,a.replay_workers*4),))]
                if not ids:break
                replay_pages(c,ids,workers=a.replay_workers)
            publish(c)
        elif a.command=='verify':publish(c)
        else:
            publish(c);print(json.dumps(json.loads((D/'status.json').read_text()),indent=2))
    finally:c.close();lock.close()

if __name__=='__main__':main()
