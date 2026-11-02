"""Read-only, bounded proposals for explicit program-scope abandonment.

No apply/publish API exists. A later writer must hold a job transaction and
revalidate all CAS fields, policy pins, payloads and proof files before changing
only the outcome registry. Unsupported never means intrinsically inexpressible.
"""
import argparse,collections,hashlib,importlib,inspect,json,re,sqlite3,sys,time
from pathlib import Path

ROOT=Path('/backup/shaoshitong/img2code_20261029');EXPECTED={'scientific_diagram':107161,'poster':24743}
IDLE=('rendered','needs_quality_repair','harness_review_pending','needs_fallback')
JOB_COLUMNS='state,worker_pid,input_record,output_record,updated_at,error,attempts,source,category,format'
STAGE='tikz_execution_candidates_v1'
STAGE_COLUMNS='id,code_hash,image_hash,source_code_hash,source_image_hash,policy,state,owner_pid,claim_token,run_id,attempts,record,updated_at'
SEMANTIC={'numeric_or_unbound_path_terminal','uncovered_executed_softpath_operations','painted_path_without_named_semantic_operations','painted_path_without_extracted_segments','terminal_is_not_an_extracted_source_node','path_segment_without_named_move','duplicate_executed_node_name','direct_pgf_paint_outside_recorded_tikz_pipeline','edge_label_operation_ambiguous'}
DANGEROUS_SVG={'filter','clip_path','mask','mask_image','evenodd_requires_review','fill_paint_server'}
sha=lambda b:hashlib.sha256(b).hexdigest()
json_sha=lambda x:sha(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
now=lambda:time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())


class Pending(ValueError):pass

def require(condition,reason):
    if not condition:raise Pending(reason)


def exists(db,name):return bool(db.execute("select 1 from sqlite_master where type='table' and name=?",(name,)).fetchone())

def ownership_clear(db,identifier):
    for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
        if not exists(db,table):continue
        columns={r[1] for r in db.execute('pragma table_info('+table+')')}
        condition="state='running'"+(' or worker_pid is not NULL' if 'worker_pid' in columns else '')
        require(not db.execute('select 1 from '+table+' where id=? and ('+condition+')',(identifier,)).fetchone(),'model_owned_or_running')
    for (table,) in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'").fetchall():
        if table in ('jobs','auto_quality_audits_v1','auto_quality_exceptions_v1') or not re.fullmatch(r'[a-zA-Z0-9_]+',table):continue
        columns={r[1] for r in db.execute('pragma table_info('+table+')')}
        if {'id','state'}<=columns:
            require(not db.execute('select 1 from '+table+" where id=? and state in ('running','producing')",(identifier,)).fetchone(),'deterministic_stage_running:'+table)


def context(db,identifier):
    row=db.execute('select '+JOB_COLUMNS+' from jobs where id=?',(identifier,)).fetchone()
    require(row is not None and row[0] in IDLE and row[1] is None and row[3],'not_idle_complete_candidate')
    original,record=json.loads(row[2]),json.loads(row[3]);registry=db.execute('select category,format,source_code_hash,source_image_hash,status,reason,record,updated_at from processing_outcomes_v2 where id=?',(identifier,)).fetchone()
    require(registry is not None and registry[4]=='pending','not_pending_registry')
    require(record.get('id')==record.get('source_pair_sha256')==identifier,'original_id_mismatch')
    require(original.get('pair_sha256')==identifier,'authoritative_pair_id_mismatch')
    require(record.get('source_format')==row[9]==original.get('format') and record.get('category')==row[8]==original.get('category') and record.get('source')==row[7]==original.get('source'),'source_scope_identity_mismatch')
    require(row[8] in EXPECTED,'outside_requested_scope')
    require((record.get('source_code_sha256'),record.get('source_image_sha256'))==(original.get('code_sha256'),original.get('image_sha256'))==registry[2:4],'source_hash_mismatch')
    require(registry[:2]==(row[8],row[9]),'registry_scope_mismatch')
    ownership_clear(db,identifier)
    return row,original,record,registry


def read_file(root,path,proofs,digest=None,area=None):
    root=Path(root).resolve();logical=Path(path);resolved=(root/logical).resolve(strict=True)
    if area:require(resolved.is_relative_to((root/area).resolve()),'proof_or_payload_outside_owned_area')
    require(resolved.is_file(),'missing_proof_file')
    before=resolved.stat();blob=resolved.read_bytes();after=resolved.stat()
    require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'file_changed_while_reading')
    actual=sha(blob);require(digest is None or actual==digest,'payload_or_proof_hash_mismatch:'+str(path))
    key=str(resolved.relative_to(root)) if resolved.is_relative_to(root) else str(resolved)
    require(key not in proofs or proofs[key]==actual,'conflicting_proof_hash')
    proofs[key]=actual;return blob


def payloads(root,record,proofs):
    result={}
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:
        require(record.get(key) and record.get(digest),'missing_persisted_source_or_candidate_payload:'+key)
        result[key]=read_file(root,record[key],proofs,record[digest],'clean')
    return result


def valid_qa(row,identifier,record):
    if not row:return False
    state,raw,updated=row;proof=json.loads(raw)
    return state=='repair_required' and proof.get('state')=='repair_required' and proof.get('accepted') is False and proof.get('id')==identifier and bool(proof.get('failures')) and all(proof.get(a)==record.get(b) for a,b in [('input_code_sha256','code_sha256'),('input_image_sha256','image_sha256'),('source_code_sha256','source_code_sha256'),('source_image_sha256','source_image_sha256')])


def qa_row(db,identifier,record,policy):
    return db.execute('select state,record,updated_at from auto_quality_audits_v1 where id=? and code_hash=? and image_hash=? and policy=?',(identifier,record['code_sha256'],record['image_sha256'],policy)).fetchone()


def source_failure(proof):
    source=proof.get('checks',{}).get('source') or {}
    return source.get('supported') is False and source.get('ok') is False and bool(source.get('failures')) and any(str(x).startswith('source_profile_not_implemented:') for x in proof.get('failures',[]))


def failure_proof(db,identifier,record,payload,config,proofs):
    active=qa_row(db,identifier,record,config['policy'])
    if valid_qa(active,identifier,record):
        proof=json.loads(active[1]);require(source_failure(proof),'current_failure_is_not_proved_unsupported_source_semantics')
        return {'kind':'current_policy_failure','policy':config['policy'],'snapshot':list(active),'source_failure':proof['checks']['source']}
    require(record['source_format']=='tikz' and config.get('equivalences'),'no_current_policy_failure_or_reviewed_equivalence')
    import failure_equivalence_tikz_v1 as equivalence
    equivalence.family_assumptions(record);old=None;historical_policy=None
    for candidate_policy in config['equivalences']:
        candidate=qa_row(db,identifier,record,candidate_policy)
        if valid_qa(candidate,identifier,record) and source_failure(json.loads(candidate[1])):
            old=candidate;historical_policy=candidate_policy;break
    require(old is not None,'no_exact_historical_TikZ_failure')
    prior=json.loads(old[1]);require(source_failure(prior),'historical_failure_is_not_unsupported_source')
    from tikz_literal_graph import parse_literal
    try:parse_literal(payload['original_source_code'].decode())
    except ValueError as error:fresh_error=str(error)
    else:raise Pending('literal_grammar_not_an_early_pure_rejection')
    failures=prior['checks']['source']['failures']
    require(any(isinstance(f,dict) and f.get('reason')=='unsupported_source_graph_profile' and f.get('error')==fresh_error for f in failures),'fresh_literal_error_differs_from_historical_failure')
    module=config['module'];xml=payload['code_file'].decode();reference=payload['original_reference']
    module.structure_checks(xml);registered,_=module.registration_record(record,reference,xml);resources=module.resource_checks(Path(config['root']),registered,xml,reference)
    for path in resources['verified_files']:
        # resource_checks already hashes these; capture their immutable CAS bytes.
        read_file(config['root'],path,proofs,area='clean')
    current=module.profile(registered,xml,payload['original_source_code'].decode())
    require(current==prior['checks']['source'],'fresh_source_rejection_differs_from_historical_profile')
    return {'kind':'failure_only_verified_TikZ_equivalence','policy':config['policy'],'historical_policy':historical_policy,'snapshot':list(old),'equivalence_sha256':json_sha(config['equivalences'][historical_policy]),'fresh_literal_rejection':fresh_error,'source_failure':current,'acceptance_certified':False,'fresh_native_render_claimed':False}


def semantic_classes(graph,events):
    failures=graph.get('failures') or [];tags={f.get('reason') for f in failures};require(failures and graph.get('ok') is False,'no_failed_execution_semantics')
    require(tags<=(SEMANTIC|{'node_or_label_event_coverage_incomplete'}),'execution_integrity_or_unknown_failure_not_terminal_semantics')
    fatal_paths={(f.get('picture'),f.get('path')) for f in failures if f.get('reason') in SEMANTIC and f.get('path') is not None}
    duplicate_names={(f.get('picture'),f.get('name')) for f in failures if f.get('reason')=='duplicate_executed_node_name'}
    nodes={e['fields'][2]:e['fields'] for e in events if e['kind']=='node'}
    for failure in failures:
        if failure.get('reason')!='node_or_label_event_coverage_incomplete':continue
        require(not failure.get('extra'),'extra_execution_events_not_semantic_scope_limit')
        for serial in failure.get('missing',[]):
            node=nodes.get(serial);require(node is not None and ((node[0],node[1]) in fatal_paths and node[3]=='label' or (node[0],node[4]) in duplicate_names),'unexplained_missing_execution_event')
    require(tags & SEMANTIC,'no_specific_unsupported_execution_construct')
    return sorted(tags)


def pgf_terminal(db,identifier,record,payload,config,proofs):
    require(config.get('execution_policy'),'execution_policy_not_known')
    row=db.execute('select '+STAGE_COLUMNS+' from '+STAGE+' where id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?',(identifier,record['code_sha256'],record['image_sha256'],record['source_code_sha256'],record['source_image_sha256'],config['execution_policy'])).fetchone()
    require(row is not None and row[6]=='unsupported_source','no_matching_terminal_execution_attempt')
    stage=dict(zip(STAGE_COLUMNS.split(','),row));report=json.loads(stage['record'])
    require(report.get('id')==identifier and report.get('policy')==stage['policy'] and report.get('state')=='unsupported_source' and report.get('accepted') is False and report.get('previous_candidate_retained') is True,'invalid_execution_terminal_receipt')
    require(re.fullmatch('[0-9a-f]{32}',stage['claim_token'] or ''),'invalid_owned_execution_claim_token')
    folder=Path(config['root'])/'conversion/tikz_execution_candidates_v1'/identifier/(record['code_sha256']+'_'+record['image_sha256'][:16])/stage['policy'].rsplit(':',1)[-1]/stage['claim_token']/'proof'
    baseline=json.loads(read_file(config['root'],folder/'baseline_record.json',proofs,area='conversion/tikz_execution_candidates_v1'))
    require(all(baseline.get(key)==record.get(key) for key in ('id','source_pair_sha256','code_sha256','image_sha256','source_code_sha256','source_image_sha256')),'execution_baseline_identity_mismatch')
    read_file(config['root'],folder/'baseline.drawio',proofs,record['code_sha256'],'conversion/tikz_execution_candidates_v1');read_file(config['root'],folder/'baseline.png',proofs,record['image_sha256'],'conversion/tikz_execution_candidates_v1')
    execution=folder/'execution';sidecar=json.loads(read_file(config['root'],execution/'execution_graph.json',proofs,area='conversion/tikz_execution_candidates_v1'))
    require(sidecar.get('source_sha256')==record['source_code_sha256'] and sidecar.get('source_bytes_unchanged') is True and sidecar.get('published') is False,'execution_source_identity_not_proven')
    require(sidecar.get('ok') is False and isinstance(sidecar.get('graph'),dict),'binding_or_marker_failure_requires_separate_repair_not_this_terminal_rule')
    require(all(re.fullmatch('[0-9a-f]{64}',str(sidecar.get(key,''))) for key in ('engine_sha256','hook_sha256','execution_trace_sha256')),'execution_receipt_hashes_missing')
    for mode in ('baseline','instrumented'):
        run=sidecar.get('runs',{}).get(mode) or {};require(run.get('returncode')==0 and re.fullmatch('[0-9a-f]{64}',str(run.get('pdf_sha256',''))),'execution_compile_runtime_failure_or_missing_hash')
        read_file(config['root'],execution/mode/'original_source.tex',proofs,record['source_code_sha256'],'conversion/tikz_execution_candidates_v1')
        read_file(config['root'],execution/mode/'source.pdf',proofs,run.get('pdf_sha256'),'conversion/tikz_execution_candidates_v1')
    pages=sidecar.get('instrumentation_pdf_pixel_equivalence') or [];require(pages and all(p.get('pixel_identical') is True for p in pages),'instrumentation_pixel_equivalence_not_proven')
    read_file(config['root'],sidecar['engine_file'],proofs,sidecar['engine_sha256'],'conversion/runtime')
    read_file(config['root'],execution/'instrumented/tikz_execution_graph_hooks.tex',proofs,sidecar['hook_sha256'],'conversion/tikz_execution_candidates_v1')
    from tikz_execution_graph import parse_events,graph_from_events
    trace=read_file(config['root'],execution/'instrumented/source.iic',proofs,sidecar['execution_trace_sha256'],'conversion/tikz_execution_candidates_v1');events=parse_events(trace.decode());graph=graph_from_events(events)
    require(graph==sidecar['graph'],'execution_trace_does_not_reproduce_recorded_graph')
    classes=semantic_classes(graph,events)
    return {'reason_code':'unsupported_pgf_source_semantics_current_bounded_program','source_construct_classes':classes,'stage_table':STAGE,'stage_snapshot_sha256':json_sha(row),'stage_identity':[stage[k] for k in ('id','code_hash','image_hash','source_code_hash','source_image_hash','policy')],'stage_record':report,'stage_primary_key':stage['claim_token'],'graph_failure_count':len(graph['failures']),'raw_model_xml_patch_cannot_create_missing_source_execution_semantics':True}


def svg_closed_terminal(identifier,record,payload,config,proofs):
    rows=config.get('closed_svg',{});item=rows.get(identifier);require(item is not None,'no_full_fresh_closed_source_scene_receipt')
    require(item.get('cohort')=='closed_current_generic' and item.get('static_kind')=='closed_source_paint_no_declared_relation_or_marker' and not item.get('skipped'),'not_closed_generic_nonmarker_scope')
    require(all(item.get(a)==record.get(b) for a,b in [('input_code_sha256','code_sha256'),('input_image_sha256','image_sha256'),('source_code_sha256','source_code_sha256'),('source_image_sha256','source_image_sha256')]),'closed_scene_receipt_stale')
    proof_path=Path(item['proof']);stored=json.loads(read_file(config['root'],proof_path,proofs,area='conversion/prototype/svg_source_profile_scope_v1'))
    dom=json.loads(read_file(config['root'],proof_path.parent/'fresh_source_dom.json',proofs,area='conversion/prototype/svg_source_profile_scope_v1'))
    import auto_quality_svg_closed_scene_v1 as profile
    from svg_source_scene_dom_v1 import EXTRACTOR
    capture=dom.get('sceneCapture') or {}
    require(all(capture.get(a)==record.get(b) for a,b in [('recordId','id'),('recordCodeSha256','code_sha256'),('sourceCodeSha256','source_code_sha256'),('sourceImageSha256','source_image_sha256')]),'fresh_scene_capture_identity_mismatch')
    require(capture.get('completeOfflineSource') is True and capture.get('sourcePayloadHashesRecheckedAfterCapture') is True and not capture.get('blockedResources'),'source_scene_not_complete_offline')
    read_file(config['root'],Path(profile.__file__),proofs,capture.get('moduleSha256'),'conversion')
    read_file(config['root'],EXTRACTOR,proofs,capture.get('extractorSha256'),'conversion')
    replay=profile.check_scene_coverage(dom,payload['code_file'].decode(),item.get('reference_offset',[0,0]));require(replay==stored,'fresh_scene_pure_replay_differs_from_stored_proof')
    require(replay.get('supported') is False and replay.get('ok') is False,'scene_not_proved_unsupported')
    failures=replay.get('failures') or [];require(any(f.get('reason')=='closed_path_requires_an_explicit_role_or_basic_geometry_proof' for f in failures),'source_roles_not_unproven')
    features=sorted({f.get('issue',{}).get('reason') for f in failures if f.get('reason')=='unresolved_source_feature'});require(set(features)&DANGEROUS_SVG,'no_explicit_unmapped_paint_feature')
    relation=replay.get('evidence',{}).get('source_admission',{}).get('relation_evidence') or {};require(relation.get('declared_nodes')==0 and not any(relation.get(key) for key in ('edge_object_ids','marker_owner_ids','explicit_relation_role_ids')),'active_graph_or_marker_semantics_must_be_retained')
    return {'reason_code':'source_role_unproven_and_paint_features_unmapped_current_bounded_program','source_construct_classes':features,'closed_receipt_sha256':json_sha(item),'scope_note':'Current program support limit only, not an intrinsic impossibility or a static-only classification. Explicit graph/marker cohorts are excluded.'}


def prepare(db,identifier,config,terminal_verifier=None):
    require(not db.in_transaction,'planner_requires_fresh_autocommit_reads')
    row,original,record,registry=context(db,identifier);require(identifier not in config.get('model_allowlist',[]),'authorized_localized_model_case_reserved')
    require(record['source_format'] in ('tikz','svg'),'format_reserved_for_other_deterministic_stages')
    proofs=dict(config.get('pinned_files',{}));data=payloads(config['root'],record,proofs);qa=failure_proof(db,identifier,record,data,config,proofs)
    terminal=(terminal_verifier or (pgf_terminal if record['source_format']=='tikz' else svg_closed_terminal))
    reason=terminal(db,identifier,record,data,config,proofs) if record['source_format']=='tikz' else terminal(identifier,record,data,config,proofs)
    cas={'job_snapshot_sha256':json_sha(row),'registry_snapshot_sha256':json_sha(registry),'qa_snapshot_sha256':json_sha(qa['snapshot']),'qa_policy':qa.get('historical_policy',config['policy']),'active_policy':config['policy'],'active_owner_sha256':config['owner_sha256'],'execution_owner_sha256':config.get('execution_owner_sha256'),'terminal_snapshot_sha256':reason.get('stage_snapshot_sha256'),'proof_files':proofs}
    evidence={key:record[key] for key in ('id','source_pair_sha256','source_code_sha256','source_image_sha256','code_file','code_sha256','image_file','image_sha256')}
    evidence.update(reason,reason_detail='当前原始source已完成有界程序检查，但所需source语义/paint映射超出冻结规则；局部XML补丁不能补出可验证source证据。保留原始数据和现有候选，后续明确的新确定性规则可恢复。',abandonment_is_not_conversion_success=True,deterministic_recovery_permitted=True,new_model_calls=0,qa_failure_certificate={key:value for key,value in qa.items() if key!='snapshot'})
    plan={'id':identifier,'prepared_at':now(),'proposal_only':True,'evidence':evidence,'cas':cas,'apply_available':False}
    require(revalidate(db,plan,config,check_files=True)=='current','candidate_changed_during_read_only_planning')
    return plan


def revalidate(db,plan,config,check_files=True):
    try:
        identifier=plan['id'];row,_,record,registry=context(db,identifier);cas=plan['cas']
        require(json_sha(row)==cas['job_snapshot_sha256'] and json_sha(registry)==cas['registry_snapshot_sha256'],'job_or_registry_snapshot_changed')
        require(config['policy']==cas['active_policy'] and config['owner_sha256']==cas['active_owner_sha256'],'active_quality_policy_changed')
        qa=qa_row(db,identifier,record,cas['qa_policy']);require(qa is not None and json_sha(qa)==cas['qa_snapshot_sha256'],'failure_audit_snapshot_changed')
        if cas.get('terminal_snapshot_sha256'):
            stage=db.execute('select '+STAGE_COLUMNS+' from '+STAGE+' where id=? and code_hash=? and image_hash=? and source_code_hash=? and source_image_hash=? and policy=?',(identifier,record['code_sha256'],record['image_sha256'],record['source_code_sha256'],record['source_image_sha256'],config['execution_policy'])).fetchone()
            require(stage is not None and json_sha(stage)==cas['terminal_snapshot_sha256'],'execution_terminal_snapshot_changed')
        if check_files:
            proofs={}
            for path,digest in cas['proof_files'].items():read_file(config['root'],path,proofs,digest)
            read_file(config['root'],'conversion/auto_quality_owner.json',proofs,cas['active_owner_sha256'])
            if cas.get('execution_owner_sha256'):read_file(config['root'],'conversion/tikz_execution_candidate_watch_v1_owner.json',proofs,cas['execution_owner_sha256'])
        return 'current'
    except (ValueError,OSError,KeyError,TypeError):return 'stale_or_ineligible'


def configuration(root=ROOT):
    root=Path(root).resolve();work=root/'conversion';sys.path[:0]=[str(work/'scripts'),str(work/'prototype')]
    import failure_equivalence_tikz_v1 as equivalence
    import auto_quality_batch_v3 as old
    module,owner,digest=equivalence.active_module(work);certificates={old.POLICY:equivalence.prove_modules(old,module,owner['policy'],equivalence.OLD_POLICY)}
    prior_modules=[old]
    prior4=importlib.import_module('auto_quality_batch_v4')
    if prior4.POLICY!=module.POLICY:
        certificates={prior4.POLICY:equivalence.prove_modules(prior4,module,owner['policy']),**certificates};prior_modules.append(prior4)
    execution_path=work/'tikz_execution_candidate_watch_v1_owner.json';execution=json.loads(execution_path.read_text());policy=json.loads((work/'model_usage_policy_v2.json').read_text())
    for filename,expected in execution['implementation'].items():
        path=Path(filename) if Path(filename).is_absolute() else work/'scripts'/filename
        require(sha(path.read_bytes())==expected,'execution_implementation_pin_changed:'+filename)
    closed_path=work/'prototype/svg_source_profile_scope_v1/closed_scene_cohort_v1/cohort_report.json';closed=json.loads(closed_path.read_text()) if closed_path.exists() else {'records':[]}
    pins={}
    for filename,expected in {**{name:digest for prior in prior_modules for name,digest in prior.IMPLEMENTATION.items()},**execution['implementation']}.items():
        path=Path(filename) if Path(filename).is_absolute() else work/'scripts'/filename
        key=str(path.resolve().relative_to(root)) if path.resolve().is_relative_to(root) else str(path.resolve());pins[key]=expected
    for function in (module.verify,module.profile,module.registration_record):
        path=Path(inspect.getsourcefile(function)).resolve();pins[str(path.relative_to(root))]=sha(path.read_bytes())
    for control_module in (sys.modules[__name__],equivalence):
        path=Path(control_module.__file__).resolve();pins[str(path.relative_to(root))]=sha(path.read_bytes())
    pins['conversion/model_usage_policy_v2.json']=sha((work/'model_usage_policy_v2.json').read_bytes())
    if closed_path.exists():pins[str(closed_path.relative_to(root))]=sha(closed_path.read_bytes())
    return {'pinned_files':pins,'root':str(root),'module':module,'policy':owner['policy'],'owner_sha256':digest,'execution_policy':execution['policy'],'execution_owner_sha256':sha(execution_path.read_bytes()),'equivalences':certificates,'model_allowlist':policy.get('authorized_model_sample_ids',[]),'closed_svg':{row['id']:row for row in closed['records']},'model_policy_sha256':sha((work/'model_usage_policy_v2.json').read_bytes())}


def inventory(db,config):
    current_fail={(r[0],r[1],r[2]) for r in db.execute("select id,code_hash,image_hash from auto_quality_audits_v1 where policy=? and state='repair_required'",(config['policy'],))}
    inherited_fail=set()
    for policy in config['equivalences']:
        inherited_fail.update((r[0],r[1],r[2]) for r in db.execute("select id,code_hash,image_hash from auto_quality_audits_v1 where policy=? and state='repair_required'",(policy,)))
    execution={}
    for identifier,ch,ih,state in db.execute('select id,code_hash,image_hash,state from '+STAGE+' where policy=?',(config['execution_policy'],)):
        execution[(identifier,ch,ih)]=state
    active_triangles=set();census=Path(config['root'])/'conversion/prototype/svg_source_profile_scope_v1/marker_family_census_v1.json'
    if census.exists():
        for row in json.loads(census.read_text())['records']:
            if any(owner.get('kind')=='closed_triangle' for owner in row.get('owners',[])):active_triangles.add(row['id'])
    buckets=collections.Counter();formats=collections.Counter();candidates=[];stage_counts=collections.Counter()
    sql='''select j.id,j.format,j.state,j.worker_pid,j.output_record is not null,o.status,k.code_hash,k.image_hash,k.seen_payload_version,d.payload_version
      from jobs j join processing_outcomes_v2 o on o.id=j.id left join auto_quality_inventory_rows_v2 k on k.id=j.id left join auto_quality_dirty_v2 d on d.id=j.id'''
    for identifier,fmt,state,worker,has_payload,status,ch,ih,seen,version in db.execute(sql):
        formats[fmt]+=1;key=(identifier,ch,ih)
        if state=='accepted':bucket='qualified_or_waiting_registry_sync'
        elif status=='abandoned':bucket='explicit_abandonment_already_registered'
        elif worker is not None or state not in IDLE and has_payload:bucket='active_or_nonidle_do_not_abandon'
        elif not has_payload:bucket='initial_conversion_not_complete_do_not_abandon'
        elif seen!=version:bucket='wait_exact_inventory_refresh'
        elif fmt=='html':bucket='reserved_active_HTML_v5a_v3c_or_clip_runtime_fix'
        elif fmt=='svg' and identifier in active_triangles:bucket='reserved_active_SVG_triangle_marker_rule'
        elif fmt=='tikz':
            stage=execution.get(key);stage_counts[(stage or 'no_exact_stage',key in current_fail,key in inherited_fail)]+=1
            if stage=='unsupported_source' and (key in current_fail or key in inherited_fail):bucket='PGF_terminal_needs_full_readonly_proof';candidates.append(identifier)
            elif stage=='running':bucket='active_execution_stage_do_not_abandon'
            elif stage in ('failed_retained_prior','publication_failed'):bucket='execution_runtime_binding_or_marker_failure_needs_classification'
            elif stage=='unsupported_source':bucket='terminal_source_attempt_needs_current_failure_certificate'
            else:bucket='await_bounded_execution_or_nonapplicability_certificate'
        elif fmt=='svg' and identifier in config['closed_svg'] and config['closed_svg'][identifier].get('cohort')=='closed_current_generic':
            bucket='fresh_closed_SVG_terminal_needs_current_policy_proof'
            if key in current_fail:candidates.append(identifier)
        elif key in current_fail or key in inherited_fail:bucket='failed_candidate_needs_corresponding_terminal_stage_proof'
        else:bucket='candidate_awaits_fixed_program_QA'
        buckets[bucket]+=1
    return {'total':sum(buckets.values()),'dispositions':dict(buckets),'formats':dict(formats),'execution_current_revision_statuses':[{'stage':s,'has_current_failure':current,'has_reusable_predecessor_failure':prior,'count':n} for (s,current,prior),n in stage_counts.items()],'active_triangle_static_membership_count':len(active_triangles),'candidate_ids':sorted(set(candidates))}


def run(root=ROOT,limit=16):
    require(1<=limit<=64,'finite_plan_limit_must_be_1_to_64');config=configuration(root);work=Path(config['root'])/'conversion';db=sqlite3.connect('file:'+str(work/'jobs.sqlite')+'?mode=ro',uri=True,timeout=60,isolation_level=None)
    require(dict(db.execute('select category,count(*) from jobs group by category'))==EXPECTED,'full_input_scope_changed')
    listing=inventory(db,config);plans=[];deferred=collections.Counter();details=[]
    for identifier in listing['candidate_ids']:
        if len(plans)>=limit:break
        try:
            plan=prepare(db,identifier,config);plans.append(plan);print(json.dumps({'stage':'proposal_only','id':identifier,'reason':plan['evidence']['reason_code'],'failure':plan['evidence']['qa_failure_certificate']['kind']}),flush=True)
        except Exception as error:
            reason=str(error);deferred[reason]+=1
            if len(details)<100:details.append({'id':identifier,'reason':reason[:1000]})
    db.close();result={'at':now(),'scope_inputs':131904,'expected_categories':EXPECTED,'policy':config['policy'],'execution_policy':config['execution_policy'],'read_only':True,'proposal_only':True,'apply_available':False,'model_calls':0,'new_production_reservations':0,'inventory':{k:v for k,v in listing.items() if k!='candidate_ids'},'precheck_candidate_count':len(listing['candidate_ids']),'full_proposals':len(plans),'finite_limit':limit,'deferred_proof_reasons':dict(deferred),'deferred_examples':details,'equivalence_certificates':config['equivalences'],'plans':plans,'completion_rule':'qualified + explicit abandoned =131904, pending0','goal_complete':False,'required_before_any_future_apply':['Hold a canonical jobs writer transaction; reread all job/registry/QA/stage snapshots and owner/policy/payload/proof hashes.','Recheck every model and deterministic-stage ownership guard and any explicit active recovery allowlist.','Only update the outcome registry, never jobs/source/candidate/history; abandonment is not a conversion success.','All producers must skip abandoned same revisions unless an explicit new bounded generic recovery rule admits them, or old repair producers may reopen the same work.','Unsupported here describes frozen verified program scope, not an intrinsic inability to represent this source in drawio.']}
    path=work/'bounded_program_terminal_planner_v1_report.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    summary={k:v for k,v in result.items() if k not in ('plans','equivalence_certificates','deferred_examples')};summary['report']=str(path);print(json.dumps({'stage':'complete','summary':summary},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--limit',type=int,default=16);args=parser.parse_args();run(args.root,args.limit)
