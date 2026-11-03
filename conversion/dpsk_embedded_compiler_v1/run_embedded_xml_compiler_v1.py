#!/usr/bin/env python3
"""Durable, bounded runner for the SVG/PNG embedded draw.io compiler."""
from pathlib import Path
import argparse, collections, concurrent.futures as cf, datetime, fcntl, json, os, signal, sqlite3, subprocess, sys, threading, time, zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedded_xml_compiler_v1 as C

D = C.D
DB = D / 'once.sqlite'
LOCK = D / 'program.lock'
POLICY = ('cold_full_editor_source_XML_uniform_refresh_validate_fonts_ready_front_two_RAF_v1'
          '__official_local_mathjax_svg_fontCache_none_v1'
          '__identity_view_scale_translate_scroll_before_every_validation_stage_v1'
          '__deterministic_export_local_GUID_allocator_v1'
          '__embedded_svg_png_metadata_graph_once_v1')
MAX_ATTEMPTS = 1
REPLAY_TIMEOUT = 330
REPLAY_ALARM = 300

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def connect():
    D.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=60)
    c.execute('pragma journal_mode=WAL')
    c.execute('pragma synchronous=NORMAL')
    c.execute('create table if not exists cases(id text primary key, ordinal integer, file text unique, kind text, status text, attempts integer default 0, reason text, record text, updated_at text)')
    c.execute('create table if not exists known_graphs(graph_sha text, source text, path text, alias text, primary key(graph_sha,source,path))')
    c.execute('create table if not exists once_graphs(graph_sha text primary key, case_id text, source text, created_at text)')
    c.execute('create table if not exists meta(key text primary key, value text)')
    return c

def meta_get(c, key, default=None):
    row = c.execute('select value from meta where key=?', (key,)).fetchone()
    return row[0] if row else default

def meta_set(c, key, value):
    c.execute('insert into meta values(?,?) on conflict(key) do update set value=excluded.value', (key, str(value)))

def case_id(path):
    return C.sha('embedded_xml_compiler_v1|' + str(path))

def paper_of(path):
    p = Path(path).resolve(); base = (C.P / 'recent_ai_source_expansion_v2/papers').resolve()
    return p.relative_to(base).parts[0]

def get_case(c, ident):
    row = c.execute('select id,ordinal,file,kind,status,attempts,reason,record,updated_at from cases where id=?', (ident,)).fetchone()
    if not row: raise KeyError(ident)
    keys = ('id','ordinal','file','kind','status','attempts','reason','record','updated_at')
    d = dict(zip(keys, row))
    d['record'] = json.loads(d['record']) if d['record'] else {}
    return d

def update_case(c, ident, status=None, reason=None, record=None):
    sets = ['updated_at=?']; args = [now()]
    if status is not None: sets.append('status=?'); args.append(status)
    if reason is not None: sets.append('reason=?'); args.append(str(reason)[:2000])
    if record is not None: sets.append('record=?'); args.append(C.dumps(record))
    args.append(ident)
    c.execute('update cases set ' + ','.join(sets) + ' where id=?', args)

# ---------------------------------------------------------------------------
# init / known graphs
# ---------------------------------------------------------------------------
def hash_graph_path(path):
    try:
        b = (C.R / path).read_bytes() if not Path(path).is_absolute() else Path(path).read_bytes()
        _, _, hs, dh = C.document_graphs(b)
        return path, hs, dh, None
    except Exception as e:
        return path, [], None, type(e).__name__ + ':' + str(e)[:300]

def known_path_rows():
    rows=[]; seen=set()
    def add(source, path, alias):
        key=(source,path)
        if key in seen: return
        seen.add(key); rows.append((source,path,str(alias)))
    baseline = C.R / 'clean/accepted_3759_v1/pairs.jsonl'
    for line in baseline.read_text().splitlines():
        if not line.strip(): continue
        o=json.loads(line); add('baseline_3759_v1', o['code_file'], o.get('accepted_baseline_number') or o.get('id'))
    current = C.P / 'goal500_progress_v1/accepted_new_pairs.jsonl'
    for line in current.read_text().splitlines():
        if not line.strip(): continue
        o=json.loads(line); add('goal500_accepted_new_190', o['code_file'], o.get('goal500_pair_id') or o.get('id'))
    direct = C.P / 'direct_author_XML_source_replay_v1/author_native_source_replay.jsonl'
    for line in direct.read_text().splitlines():
        if not line.strip(): continue
        o=json.loads(line); add('direct_author_XML_source_replay_v1', o['code_file'], o.get('id'))
    ledger_seen=set()
    for rel, source in [('new_bulk_200_v1/once.sqlite','new_bulk_200_v1'),
                        ('recent_ai_source_expansion_v2/once.sqlite','recent_ai_source_expansion_v2')]:
        with sqlite3.connect((C.P/rel).as_uri()+'?mode=ro', uri=True) as db:
            db.execute('pragma query_only=ON')
            for (raw,) in db.execute("select record from pdfs where json_extract(record,'$.author_xml_file') is not null"):
                try: o=json.loads(raw)
                except Exception: continue
                p=o.get('author_xml_file')
                if p and p not in ledger_seen:
                    ledger_seen.add(p); add(source, p, o.get('id') or o.get('paper'))
    return rows

def build_known(c, workers=12):
    rows = known_path_rows()
    paths = sorted({p for _,p,_ in rows})
    by_path = collections.defaultdict(list)
    for source,p,alias in rows: by_path[p].append((source,alias))
    C.put_json(D/'known_graph_inputs.json', {'paths': len(paths), 'source_rows': len(rows), 'sources': dict(collections.Counter(s for s,_,_ in rows))})
    results=[]; started=time.monotonic(); done=0
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(hash_graph_path, paths, chunksize=8):
            results.append(res); done+=1
            if done % 500 == 0:
                print(json.dumps({'known_hash_progress': done, 'total': len(paths), 'seconds': round(time.monotonic()-started,1)}), flush=True)
    c.execute('begin immediate'); c.execute('delete from known_graphs')
    inserted=0; errors=[]
    for path, hs, dh, err in results:
        if err: errors.append({'path':path,'error':err}); continue
        for h in hs:
            for source,alias in by_path[path]:
                c.execute('insert or ignore into known_graphs values(?,?,?,?)', (h,source,path,alias)); inserted+=1
    c.commit()
    C.put_json(D/'known_graph_hash_errors.json', errors)
    meta_set(c,'known_built','1'); meta_set(c,'known_graph_input_sha256', C.sha((D/'known_graph_inputs.json').read_bytes())); c.commit()
    print(json.dumps({'known_hashes_inserted':inserted,'errors':len(errors),'seconds':round(time.monotonic()-started,1)}), flush=True)

def known_map(c):
    out={}
    for h,source,path,alias in c.execute('select graph_sha,source,path,alias from known_graphs order by source,path'):
        out.setdefault(h, {'source':source,'path':path,'alias':alias})
    return out

# ---------------------------------------------------------------------------
# extraction phase
# ---------------------------------------------------------------------------
_WORKER_IDENTITY = {}
def extract_one(task):
    file, kind = task
    p = C.R / file
    try:
        e = C.extract_candidate(p, kind)
        rawb = e['raw']
        models, _, native, classify, valuable, _ = C.import_native_modules()
        root, ms = models(rawb)
        features = native(rawb.decode('utf-8-sig'))
        kind_class, class_reasons = classify(features, 'drawio', {})
        is_valuable = bool(kind_class == 'complex_candidate' and len(ms) == 1 and valuable(features))
        page_hashes = [C.page_graph_hash(ms[0])] if len(ms) == 1 else []
        paper = paper_of(p)
        if paper not in _WORKER_IDENTITY:
            _WORKER_IDENTITY[paper] = C.candidate_source_identity(p)
        identity = _WORKER_IDENTITY[paper]
        out = {
            'file': file, 'kind': kind, 'paper': paper,
            'source_sha256': e['source_container_sha256'], 'source_bytes': p.stat().st_size,
            'container_sha256': e['source_container_sha256'],
            'chunk_type': e['chunk_type'], 'key': e['key'], 'steps': e.get('steps',[]),
            'raw_sha256': e['raw_sha256'], 'raw_bytes': e['raw_bytes'],
            'pages': len(ms), 'page_graph_hashes': page_hashes,
            'features': features, 'kind_class': kind_class, 'class_reasons': class_reasons,
            'valuable': is_valuable,
            'paper_identity': {k: identity[k] for k in ('paper','paper_folder','source_root','source_archive_file','source_archive_sha256','source_archive_bytes','source_receipt_file','source_receipt_sha256','original_paper_record_SHA256','paper_metadata')},
        }
        return out
    except Exception as e:
        return {'file': file, 'kind': kind, 'error': type(e).__name__+':'+str(e)[:1000]}

def extract_phase(c, workers=12):
    pending = c.execute("select id,file,kind from cases where status='queued_extract' order by ordinal").fetchall()
    if not pending:
        print(json.dumps({'extract': 'nothing_pending'})); return
    known = known_map(c)
    started=time.monotonic(); done=0; stats=collections.Counter()
    tasks = [(f,k) for _,f,k in pending]
    ids = [i for i,_,_ in pending]
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        for ident, res in zip(ids, pool.map(extract_one, tasks, chunksize=4)):
            done += 1
            rec = {'extraction': res, 'updated_at': now()}
            if res.get('error'):
                update_case(c, ident, 'skipped_extract_error', 'extract_error:'+res['error'], rec); stats['skipped_extract_error']+=1
            else:
                pages = res['pages']
                if pages != 1:
                    update_case(c, ident, 'skipped_multi_page_document', 'multi_page_document_requires_deterministic_page_selection:pages=%d'%pages, rec); stats['skipped_multi_page_document']+=1
                elif not res['valuable']:
                    update_case(c, ident, 'skipped_below_value_policy', 'value_policy:%s:%s'%(res['kind_class'],','.join(res['class_reasons'])), rec); stats['skipped_below_value_policy']+=1
                else:
                    h = res['page_graph_hashes'][0]
                    dup = known.get(h)
                    own = c.execute('select case_id,source from once_graphs where graph_sha=?', (h,)).fetchone()
                    if dup or own:
                        if own: source='own:'+own[0]
                        else: source=dup['source']+':'+dup['path']
                        rec['duplicate'] = {'graph_sha256': h, 'source': source, 'known': dup}
                        update_case(c, ident, 'skipped_duplicate_graph', 'duplicate_graph:'+source, rec); stats['skipped_duplicate_graph']+=1
                    else:
                        c.execute('insert into once_graphs values(?,?,?,?)', (h, ident, res['file'], now()))
                        rec['graph_sha256'] = h
                        update_case(c, ident, 'eligible', 'unique_single_page_complex_candidate', rec); stats['eligible']+=1
            if done % 100 == 0:
                c.commit(); print(json.dumps({'extract_progress':done,'total':len(tasks),'stats':dict(stats),'seconds':round(time.monotonic()-started,1)}), flush=True)
    c.commit(); meta_set(c,'extract_complete','1'); meta_set(c,'extract_counts',C.dumps(dict(stats))); c.commit()
    print(json.dumps({'extract_done':done,'stats':dict(stats),'seconds':round(time.monotonic()-started,1)}), flush=True)

# ---------------------------------------------------------------------------
# replay phase
# ---------------------------------------------------------------------------
def claim(c, ident):
    c.execute('begin immediate')
    n = c.execute("update cases set status='attempt_started',attempts=attempts+1,reason='replay_claimed',updated_at=? where id=? and status='eligible' and attempts<?", (now(), ident, MAX_ATTEMPTS)).rowcount
    c.commit()
    return n == 1

def spawn_case(ident):
    folder = D/'cases'/ident
    folder.mkdir(parents=True, exist_ok=True)
    log = (folder/'worker.log').open('ab')
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--case', ident], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        child.wait(timeout=REPLAY_TIMEOUT)
    except subprocess.TimeoutExpired:
        try: os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait(timeout=5)
    finally:
        log.close()
    p = folder/'record.json'
    if p.exists():
        try: return json.loads(p.read_text())
        except Exception as e: return {'id':ident,'status':'failed_worker_record_invalid','reason':type(e).__name__+':'+str(e)[:300]}
    return {'id':ident,'status':'failed_worker_no_record','exit':child.returncode,'reason':'worker produced no terminal record'}

def replay_phase(c, ids, workers=2):
    if not ids:
        print(json.dumps({'replay':'no_eligible_cases'})); return []
    claimed=[]; results=[]; started=time.monotonic()
    for ident in ids:
        if claim(c, ident): claimed.append(ident)
    print(json.dumps({'replay_claimed':len(claimed),'workers':workers}), flush=True)
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(spawn_case, claimed):
            ident = res.get('id')
            if res.get('status') == 'verified_embedded_native_source_replay' and res.get('pair'):
                update_case(c, ident, 'verified', 'strict_embedded_native_source_replay_verified', {'verified': res}); status='verified'
            else:
                update_case(c, ident, 'failed_replay', (res.get('reason') or res.get('status') or 'unknown_failure'), {'review': res}); status='failed_replay'
            c.commit(); results.append(res)
            publish(c)
            print(json.dumps({'replay_result':ident,'status':status,'reason':res.get('reason')}), flush=True)
    print(json.dumps({'replay_done':len(results),'seconds':round(time.monotonic()-started,1)}), flush=True)
    return results

def pilot_ids(c, limit):
    rows = c.execute("select id,file,kind,record from cases where status='eligible' order by ordinal").fetchall()
    picked=[]; seen=set()
    def add(row):
        if row and row[0] not in seen:
            seen.add(row[0]); picked.append(row)
    def chunk(row):
        try: return json.loads(row[3])['extraction']['chunk_type']
        except Exception: return ''
    first_svg = next((r for r in rows if r[2].startswith('SVG')), None)
    first_ztxt = next((r for r in rows if chunk(r)=='zTXt'), None)
    first_itext = next((r for r in rows if chunk(r)=='tEXt'), None)
    for r in (rows[0] if rows else None, first_svg, first_ztxt, first_itext): add(r)
    for r in rows: add(r)
    return [r[0] for r in picked[:limit]]

# ---------------------------------------------------------------------------
# one replay worker
# ---------------------------------------------------------------------------
def work_case(ident):
    folder = D/'cases'/ident; folder.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGALRM, lambda *_:(_ for _ in ()).throw(TimeoutError('bounded_embedded_XML_replay_%ds'%REPLAY_ALARM)))
    signal.alarm(REPLAY_ALARM)
    renderer=None; started=time.monotonic(); record={'id':ident,'status':'pending_embedded_XML_replay','at_utc':now(),'new_PDF_import_calls':0,'new_model_calls':0,'new_source_downloads':0,'policy':POLICY}
    try:
        c=connect(); case=get_case(c,ident); c.close()
        ex=case['record']['extraction']; source_file=C.R/case['file']; kind=case['kind']
        if C.sha(source_file.read_bytes()) != ex['source_sha256']: raise ValueError('original_container_hash_changed')
        extracted=C.extract_candidate(source_file, kind)
        if extracted['raw_sha256'] != ex['raw_sha256'] or extracted['raw_bytes'] != ex['raw_bytes']:
            raise ValueError('extracted_author_XML_bytes_changed_between_extraction_and_replay')
        rawb=extracted['raw']; source_bytes=source_file.read_bytes()
        identity=C.candidate_source_identity(source_file)
        if identity['paper'] != ex['paper'] or identity['paper_metadata'] != ex['paper_identity']['paper_metadata']:
            raise ValueError('paper_metadata_changed_between_extraction_and_replay')
        # Static dependency inventory; no source XML rewrite.
        models, dependencies, native, classify, valuable, _ = C.import_native_modules()
        with zipfile.ZipFile(C.WAR) as war:
            dep=dependencies(rawb, source_file, source_file, war)
        allowed_relative={'author_adjacent_file','source_only_relative_asset_needs_portable_closure'}
        unresolved=[a for a in dep['issues'] if a.get('status') not in allowed_relative]
        static=C.static_diagnostics_with_assets(rawb, ex['features'], dep['models'], dep)
        package_manifest=None
        if unresolved or static['failures']:
            raise ValueError('static_QA_failed:'+','.join(static['failures'] or sorted({a.get('status','?') for a in unresolved})))
        relative=any(a.get('status') in allowed_relative for a in dep['assets'])
        asset_files=[a.get('file') for a in dep['assets'] if a.get('file')]
        if relative:
            from arxiv_author_native_asset_package_v1 import package
            code, assets, package_manifest = package(rawb, dep, folder/'standalone_asset_package')
            code=Path(code); assets={k:Path(v) for k,v in assets.items()}
            for a in package_manifest.get('resource_dependencies', []): asset_files.append(a.get('original_asset_file'))
            with zipfile.ZipFile(C.WAR) as war:
                closed=dependencies(rawb, code, code.parent/'no_original_directory.pdf', war)
            if closed['issues']: raise ValueError('packaged_resource_closure_failed:'+','.join(sorted({a.get('status','?') for a in closed['issues']})))
            if code.read_bytes() != rawb: raise ValueError('packaged_author_XML_bytes_changed')
            dep['asset_map']=assets
        else:
            code=folder/'code'/'author.drawio'; C.atomic_put(code, rawb, exclusive=False); assets=dep['asset_map']
        if code.read_bytes() != rawb: raise ValueError('sidecar_author_XML_bytes_changed')
        # Source archive membership: container and every adjacent/original asset.
        archive_proof=C.verify_source_archive_members(identity, source_file, [C.R/a for a in asset_files if a])
        C.put_json(folder/'archive_membership.json', archive_proof)
        import arxiv_author_native_font_replay_v2 as fonts
        (C.D/'font_dependencies').mkdir(parents=True, exist_ok=True)
        fonts.D=C.D
        from arxiv_math_stable_export_renderer_v1 import MathSynced
        renderer=MathSynced(assets)
        official=C.official_decode_agreement(renderer, source_bytes, kind, rawb)
        C.put_json(folder/'official_decoder_agreement.json', official)
        out=folder/'synced_source_replay'
        proof=renderer.replay(rawb, out)
        C.put_json(folder/'source_normalized_verification.json', {'source_sha256':ex['source_sha256'],'extracted_raw_sha256':ex['raw_sha256'],'sidecar_code_sha256':C.sha(code.read_bytes()),'sidecar_bytes_equal_extracted':code.read_bytes()==rawb})
        static2=C.static_diagnostics_with_assets(rawb, ex['features'], dep['models'], dep)
        render_qa=C.render_diagnostics(proof, out/'official.png', dep, package_manifest)
        ok=bool(static2['ok'] and render_qa['ok'] and official and proof.get('ok'))
        reason='strict_render_static_asset_edit_restore_and_official_decoder_checks_passed' if ok else 'validation_failed:'+','.join(sorted(set(static2['failures']+render_qa['failures'])))
        png=out/'official.png'
        pair=None
        if ok:
            pid=C.sha(C.dumps({'source':case['file'],'container_sha256':ex['source_sha256'],'author_sha256':ex['raw_sha256'],'policy':POLICY}))
            pair={
                'id':pid,'raw_source_pair_id':case['id'],'raw_source_pair_ids':[case['id']],
                'source':'arxiv_embedded_native_drawio','paper':identity['paper'],'paper_metadata':identity['paper_metadata'],
                'profile':'author_native_source_replay','format':'drawio','category':'scientific_diagram',
                'code_file':str(code.relative_to(C.R)),'code_sha256':C.sha(rawb),
                'image_file':str(png.relative_to(C.R)),'image_sha256':C.sha(png.read_bytes()),
                'original_container_file':case['file'],'original_container_sha256':ex['source_sha256'],
                'original_author_XML':str(code.relative_to(C.R)),'original_author_XML_sha256':ex['raw_sha256'],
                'paired_code_XML_bytes_equal_extracted_author_XML':True,
                'source_origin_kind':'png_embedded_native_XML_metadata' if kind.startswith('PNG') else 'svg_content_attribute_native_XML',
                'embedded_XML_provenance':{k:ex.get(k) for k in ('chunk_type','key','steps','raw_sha256','raw_bytes','container_sha256','pages')},
                'official_decoder_agreement':str((folder/'official_decoder_agreement.json').relative_to(C.R)),
                'official_decoder_agreement_sha256':C.sha((folder/'official_decoder_agreement.json').read_bytes()),
                'source_archive_file':identity['source_archive_file'],'source_archive_sha256':identity['source_archive_sha256'],
                'source_receipt_file':identity['source_receipt_file'],'source_receipt_sha256':identity['source_receipt_sha256'],
                'archive_membership_proof':str((folder/'archive_membership.json').relative_to(C.R)),
                'archive_membership_proof_sha256':C.sha((folder/'archive_membership.json').read_bytes()),
                'native_replay_proof':str((out/'synced_replay_proof.json').relative_to(C.R)),
                'native_replay_proof_sha256':C.sha((out/'synced_replay_proof.json').read_bytes()),
                'asset_package':package_manifest,
                'font_dependencies':proof.get('font_observations',{}).get('font_assets',[]),
                'renderer_policy':POLICY,'base_validation_thresholds_unchanged':True,
                'static_QA':static2,'render_QA':render_qa,
                'original_PDF_file':None,'original_PDF_sha256':None,
                'original_PDF_fidelity':'not_assessed_embedded_metadata',
                'actual_paper_PDF_figure_usage':'not_certified',
                'whole_figure_wrapper':False,'standalone_image_assets_complete':True,
                'quality_state':'verified_embedded_native_source_replay_candidate',
                'quality_views':['arxiv_embedded_native_source_replay_candidate'],
                'accepted_authoritative':False,'authoritative_index_updated':False,
                'new_PDF_import_calls':0,'new_model_calls':0,'new_source_downloads':0,
                'original_source_payloads_unchanged':True,'official_WAR_sha256':C.sha(C.WAR.read_bytes()),
            }
        record.update(status='verified_embedded_native_source_replay' if ok else 'failed_validation', reason=reason,
                      pair=pair, static_QA=static2, render_QA=render_qa,
                      official_decoder_agreement=official, source_identity=identity,
                      asset_audit={k:v for k,v in dep.items() if k not in ('models','asset_map')},
                      package_manifest=package_manifest,
                      source_hashes_unchanged_after=(C.sha(source_file.read_bytes())==ex['source_sha256']),
                      seconds=time.monotonic()-started, finished_utc=now())
        if not record['source_hashes_unchanged_after']: raise ValueError('original_source_hash_changed')
        if C.sha((C.R/identity['source_archive_file']).read_bytes()) != identity['source_archive_sha256']: raise ValueError('source_archive_hash_changed')
        if C.sha((C.R/identity['source_receipt_file']).read_bytes()) != identity['source_receipt_sha256']: raise ValueError('source_receipt_hash_changed')
    except Exception as e:
        record.update(status='failed_replay', reason=type(e).__name__+':'+str(e)[:2000])
    finally:
        if renderer:
            try: renderer.close()
            except Exception: pass
        signal.alarm(0); record['seconds']=time.monotonic()-started; record['finished_utc']=now()
        C.put_json(folder/'record.json', record)
    return record

# ---------------------------------------------------------------------------
# publication / status
# ---------------------------------------------------------------------------
def counters(c):
    states=dict(c.execute('select status,count(*) from cases group by status'))
    reasons=dict(c.execute("select reason,count(*) from cases where status not in ('eligible','verified') and reason is not null group by reason"))
    recs=[json.loads(r[0]) for r in c.execute("select record from cases where status='verified' and record is not null")]
    pairs=[]
    for rec in recs:
        v=rec.get('verified') or {}
        if v.get('pair'): pairs.append(v['pair'])
    duplicates=0
    for (recraw,) in c.execute('select record from cases'):
        if not recraw: continue
        try:
            if json.loads(recraw).get('duplicate'): duplicates+=1
        except Exception:
            pass
    return {'states':states,'reasons':reasons,'verified_candidates':len(pairs),'duplicate_cases':duplicates}

def publish(c):
    rows=c.execute("select id,record from cases where status='verified' order by ordinal").fetchall()
    pairs=[]
    for ident,recraw in rows:
        try: r=json.loads(recraw); p=r.get('verified',{}).get('pair') or r.get('pair')
        except Exception: p=None
        if p: pairs.append(p)
    path=D/'verified_candidates.jsonl'
    tmp=path.with_name(path.name+'.tmp'); tmp.write_text(''.join(C.dumps(p)+'\n' for p in pairs)); os.replace(tmp,path)
    cnt=counters(c)
    status={'schema':'embedded_svg_png_xml_compiler_status_v1','task':'dpsk_svg_png_compiler_20261103',
            'state':'batch_running','updated_at':now(),'policy':POLICY,'inventory':str((C.P/'embedded_XML_image_inventory_v2/inventory.json').relative_to(C.R)),
            'inventory_candidates':c.execute('select count(*) from cases').fetchone()[0],
            **cnt,
            'verified_candidates_manifest':str(path.relative_to(C.R)),'verified_candidates_manifest_sha256':C.sha(path.read_bytes()),
            'database':str(DB.relative_to(C.R)),'proof_root':str(D.relative_to(C.R)),
            'authoritative_190_index_modified':False,'old3759_baseline_modified':False,
            'sources_modified':False,'new_PDF_import_calls':0,'new_model_calls':0,'new_source_downloads':0,
            'notes':'Embedded author XML candidates only; separate from authoritative current190 index.'}
    C.put_json(D/'status.json', status)
    C.put_json(Path(__file__).resolve().parents[1]/'status.json', status)
    return status

# ---------------------------------------------------------------------------
# init and CLI
# ---------------------------------------------------------------------------
def init_inventory(c):
    invp=C.P/'embedded_XML_image_inventory_v2/inventory.json'
    data=invp.read_bytes(); inv=json.loads(data); h=C.sha(data)
    if not inv.get('scan_complete') or not inv.get('directory_walk_complete'): raise ValueError('inventory_scan_not_complete')
    meta_set(c,'inventory_sha256',h); c.commit()
    existing=c.execute('select count(*) from cases').fetchone()[0]
    if existing:
        print(json.dumps({'init':'cases_present','cases':existing,'inventory_sha256':h})); return
    rows=[]
    for i,x in enumerate(inv['candidates']):
        rows.append((case_id(x['file']),i,x['file'],x['kind'],'queued_extract'))
    c.executemany('insert or ignore into cases(id,ordinal,file,kind,status,updated_at) values(?,?,?,?,?,?)', [(a,b,d,e,f,now()) for a,b,d,e,f in rows])
    c.commit()
    C.put_json(D/'inventory_snapshot.json', {'inventory_file':str(invp.relative_to(C.R)),'inventory_sha256':h,'cases':len(rows),'at_utc':now()})
    print(json.dumps({'init':'cases_inserted','cases':len(rows),'inventory_sha256':h}), flush=True)

def acquire_lock():
    D.mkdir(parents=True,exist_ok=True)
    f=(D/'program.lock').open('a'); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); return f

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--case')
    ap.add_argument('command',nargs='?',default='status',choices=['init','extract','pilot','batch','status','verify'])
    ap.add_argument('--workers',type=int,default=12)
    ap.add_argument('--replay-workers',type=int,default=2)
    ap.add_argument('--limit',type=int,default=8)
    args=ap.parse_args()
    if args.case:
        r=work_case(args.case); print(json.dumps({'id':args.case,'status':r.get('status'),'reason':r.get('reason')},ensure_ascii=False)); return
    lock=acquire_lock(); c=connect()
    try:
        if args.command=='init': init_inventory(c)
        elif args.command=='extract':
            init_inventory(c)
            if meta_get(c,'known_built')!='1': build_known(c,workers=args.workers)
            extract_phase(c,workers=args.workers)
            publish(c)
        elif args.command=='pilot':
            init_inventory(c)
            if meta_get(c,'known_built')!='1': build_known(c,workers=args.workers)
            if c.execute("select count(*) from cases where status='queued_extract'").fetchone()[0]: extract_phase(c,workers=args.workers)
            ids=pilot_ids(c,args.limit)
            print(json.dumps({'pilot_ids':ids,'count':len(ids)}))
            C.put_json(D/'pilot_plan.json', {'ids':ids,'count':len(ids),'at_utc':now()})
            replay_phase(c,ids,workers=args.replay_workers); publish(c)
        elif args.command=='batch':
            init_inventory(c)
            if meta_get(c,'known_built')!='1': build_known(c,workers=args.workers)
            if c.execute("select count(*) from cases where status='queued_extract'").fetchone()[0]: extract_phase(c,workers=args.workers)
            while True:
                ids=[r[0] for r in c.execute("select id from cases where status='eligible' order by ordinal limit ?", (max(2,args.replay_workers*4),))]
                if not ids: break
                replay_phase(c,ids,workers=args.replay_workers)
            publish(c)
        elif args.command=='verify':
            publish(c)
        else:
            publish(c); print(json.dumps(json.loads((D/'status.json').read_text()),indent=2))
    finally:
        c.close(); lock.close()

if __name__=='__main__': main()
