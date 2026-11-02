"""Reuse a signed native source audit; rebuild only full-scope metadata closure.

No source code/PNG bytes, normal conversion, source execution or rendering is
used to rebuild the source closure. Newly qualified native assets, absent from
the current fully audited inventory, are independently hash-checked once.
Full source hashes/parser predicates were proven
by the immutable v5 audit. Full canonical source/capture/baseline metadata must
remain exact, and the unchanged case_v4 physically verifies them before normal.
"""
import collections,hashlib,importlib,json,sqlite3,sys
from pathlib import Path
import compiler_native_materialized_text_node_iteration_pool_v5 as sealed_v5
import compiler_validation_identity_alias_v1 as aliases
import compiler_validation_sealed_cohort_v1 as closure
import compiler_source_core_attempts_v3 as history
import native_source_dynamic_label_guard_v1 as label_guard
R=sealed_v5.R;W=sealed_v5.W;SCOPE=1539;FRONTEND=sealed_v5.FRONTEND
SEED='hkust-native-source-sealed-full-scope-alias-fresh-transaction-20261101-v6'
OLD=R/'release/compiler_iterations/source_pools/native_materialized_text_node_unseen100_20261101_v5'
MANIFEST_SHA='361bce924762d14481da9b541cfbcf0f6879f97618fbc750922ac1c918a70a85'
SEALED={
 'source_audit.jsonl':'3f4e22e1fbd6310a4435aa9f61afe7ce8fa29478d2acd786d1d65018b3c2e590',
 'supported_population.jsonl':'2ceedd09d0645393b3657326002eec19c8041acaa29ef66f964110bae3c431f8',
 'selected.jsonl':'13df08bf1d5c908189d2461e34b39f99e26a875cd82cbead17d70023d9c1dcff',
 'preserved_qualified.jsonl':'230ea2de2f066bb574f520372927ac178602a5c51bac8045533342a201bed578',
 'ordinary_queue_snapshot.json':'bc20d1da5a10c08fa8a9a3a5a6816a3884837e90976b4f4572f46c3193da4993',
 'prior_candidate_attempts.jsonl':'c4d6ee400a5be82fadb778518057cce6893fdcd65ebe16e9f0c713601907f000'}
raw,sha,rows=sealed_v5.raw,sealed_v5.sha,sealed_v5.rows
canonical_job=sealed_v5.canonical_job
static_support_from_job=sealed_v5.static_support_from_job
request_from_job=sealed_v5.request_from_job


def bounded_jobs(db,identifiers):
    values=sorted(set(identifiers))
    for offset in range(0,len(values),400):
        chunk=values[offset:offset+400]
        yield from db.execute('select*from jobs where id in ('+','.join('?'for _ in chunk)+')',chunk)


def verify_request(row,job,configuration=None):
    """Complete canonical contract, reusing source-byte/parser evidence by hash."""
    compiler=importlib.import_module(FRONTEND);configuration=configuration or compiler.configuration()
    if job is None:raise ValueError('sealed_canonical_job_missing')
    canonical_job(job);source=json.loads(job[4]);old=json.loads(job[9])if job[9]else{}
    if row.get('source')!=source or source.get('pair_sha256')!=row.get('id'):raise ValueError('selected_worker_requires_complete_canonical_source_record')
    if source.get('format')!='drawio'or source.get('category')not in ('scientific_diagram','poster')or row.get('compiler_unit')!=compiler.UNIT:raise ValueError('selected_source_outside_native_scope')
    if row.get('source_record_sha256')!=sha((job[9]or'').encode())or(row.get('baseline_code_sha256'),row.get('baseline_image_sha256'))!=(old.get('code_sha256'),old.get('image_sha256')):raise ValueError('selected_baseline_snapshot_changed')
    capture=row.get('source_capture_snapshot')or{};guard=row.get('source_dynamic_label_guard')or{}
    expected=dict(id=job[0],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],input_record_sha256=sha(job[4].encode()),input_manifest_sha256=sha((job[11]or'').encode()))
    if any(capture.get(k)!=v for k,v in expected.items()):raise ValueError('selected_capture_or_full_canonical_source_snapshot_changed')
    if capture.get('schema')!='native_original_payload_and_normalized_XML_snapshot_v1'or not capture.get('normalized_source_sha256')or not capture.get('input_reference_image')or not capture.get('input_source_code'):raise ValueError('selected_native_source_capture_incomplete')
    if any(guard.get(k)!=v for k,v in expected.items()if k!='source_image_sha256')or guard.get('supported')is not True or guard.get('policy')!=label_guard.POLICY or guard.get('runtime_bundle_sha256')!=label_guard.RUNTIME_BUNDLE_SHA256 or guard.get('normal_source_conversion_called')is not False:raise ValueError('selected_signed_dynamic_label_guard_changed')
    return True


def validate_metadata_requests(requests):
    by_id={row['id']:row for row in requests}
    if len(by_id)!=len(requests):raise ValueError('duplicate_source_request_ID')
    compiler=importlib.import_module(FRONTEND);config=compiler.configuration();found=set()
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:
        db.execute('begin')
        for job in bounded_jobs(db,by_id):verify_request(by_id[job[0]],job,config);found.add(job[0])
    if found!=set(by_id):raise ValueError('sealed_canonical_source_request_missing')
    return dict(complete_canonical_source=True,source_record_and_baseline_exact=True,source_capture_exact=True,source_signed_dynamic_guard_exact=True,rows=len(found),physical_source_rehashes=0,unchanged_worker_full_source_hash_before_normal=True)


def load_inventory():
    import compiler_iteration_inventory_v1 as inventory
    pointer=R/'release/compiler_iterations/current.json';value=json.loads(pointer.read_bytes());summary=R/value['inventory'];blob=summary.read_bytes()
    if sha(blob)!=value['inventory_sha256']:raise ValueError('current_qualified_inventory_pointer_changed')
    info=json.loads(blob)
    if info['scope']['manifest_sha256']!=MANIFEST_SHA or info['scope']['unique_scope']!=131904 or info.get('accepted_integrity_errors')!=[]:raise ValueError('current_full_scope_inventory_not_independently_verified')
    path=summary.parent/'qualified.jsonl';blob=path.read_bytes()
    if sha(blob)!=info['files']['qualified.jsonl']['sha256']:raise ValueError('current_qualified_manifest_changed')
    accepted={row['id']:row for row in map(json.loads,blob.splitlines())if row}
    return accepted,dict(pointer=dict(file=str(pointer),sha256=sha(pointer.read_bytes())),summary=dict(file=str(summary),sha256=sha(summary.read_bytes())),qualified=dict(file=str(path),sha256=sha(blob)),qualified_total=len(accepted),integrity_errors=0)


def fresh_state(scope,configuration,*,ignore_runs=()):
    """Fresh bookkeeping, not conversion/quality re-evaluation of sealed assets."""
    import compiler_iteration_inventory_v1 as inventory
    import compiler_validation_cluster_audit_v1 as provenance
    from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot
    from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
    accepted_all,inventory_receipt=load_inventory();verified_native={i:x for i,x in accepted_all.items()if i in scope and scope[i]['format']=='drawio'}
    known_manifest_hashes={sha(raw(x))for x in accepted_all.values()};new_hashes={};observed=ledger_manifests(root=R)
    for item in observed:
        identifier=item['id']
        if identifier not in scope:continue
        source=scope[identifier]
        if(item['source_code_sha256'],item['source_image_sha256'])!=(source['code_sha256'],source['image_sha256']):raise ValueError('fresh_qualified_source_identity_changed')
        if source['format']=='drawio':
            if sha(raw(item))not in known_manifest_hashes:inventory.check_manifest(R,identifier,source,item,new_hashes)
            verified_native[identifier]=item
        # Foreign qualified rows are a conservative exclusion only; never newly
        # published or counted as accepted without independent asset checking.
        accepted_all.setdefault(identifier,item)
    prior=history.collect(configuration,root=R);history.validate(prior,configuration,root=R)
    overlap=snapshot(ignore_runs=ignore_runs);development_inputs=list(sealed_v5.DEVELOPMENT)+sorted((R/'release/compiler_iterations/development_seen_v1').glob('*.jsonl'))
    dev=[x for path in development_inputs for x in rows(path)];pairs=[];ids=set(accepted_all)|set(overlap['active'])|{x['id']for x in prior}
    for x in dev:
        if x.get('id'):ids.add(x['id'])
        for kind,names in [('code',('source_code_sha256','code_sha256')),('image',('source_image_sha256','image_sha256'))]:
            for name in names:
                if x.get(name):pairs.append((kind,x[name]))
        pairs.extend(('hard_cluster',key)for key in x.get('cluster_keys')or[])
        if x.get('audit_cluster'):pairs.append(('audit_cluster',x['audit_cluster']))
    pairs.extend(('id',identifier)for identifier in ids)
    # Only bounded lookups for development outside goal scope. Inside scope the
    # complete sealed component already holds every source/provenance alias.
    outside=ids-set(scope)
    if outside:
        with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:
            for job in bounded_jobs(db,outside):
                source=json.loads(job[4]);pairs.extend([('code',source['code_sha256']),('image',source['image_sha256'])]);pairs.extend(('hard_cluster',key)for key in provenance.provenance(source,source['source']))
    return dict(exclusion_keys=aliases.normalize_keys(pairs),accepted_native=verified_native,prior=prior,overlap=overlap,receipt=dict(inventory=inventory_receipt,development_inputs={str(p):sha(p.read_bytes())for p in development_inputs},prior_events=len(prior),qualified_native=len(verified_native),qualified_exclusion_ids=len(accepted_all),new_native_distinct_assets_verified=len(new_hashes),birth_verified_live_ids=len(overlap['active']),metadata_only_source_refresh=True,source_audit_code_or_reference_bytes_read=0))


def fresh_qualified(configuration):
    import compiler_iteration_inventory_v1 as inventory
    scope,_=inventory.read_scope(R)
    return fresh_state(scope,configuration)['accepted_native']


def sealed_source():
    compiler=importlib.import_module(FRONTEND);info=json.loads((OLD/'summary.json').read_bytes())
    if info['frozen_implementation']!=compiler.configuration()or info['full_scope_manifest']['manifest_sha256']!=MANIFEST_SHA:raise ValueError('sealed_native_frontend_or_manifest_changed')
    for name,digest in SEALED.items():
        if sha((OLD/name).read_bytes())!=digest or info['files'][name]['sha256']!=digest:raise ValueError('sealed_native_source_evidence_changed:'+name)
    for name,digest in info['method_pins'].items():
        if sha(Path(name).read_bytes())!=digest:raise ValueError('sealed_native_source_method_changed:'+name)
    if info.get('audited_scope_rows')!=1539 or info.get('model_calls')!=0 or info.get('conversion_or_rendering')is not False:raise ValueError('sealed_native_source_scope_contract_changed')
    return info


def prepare(output,inventory=None):
    import compiler_iteration_inventory_v1 as inventory_method
    import compiler_validation_cluster_audit_v1 as provenance
    compiler=importlib.import_module(FRONTEND);config=compiler.configuration();oldinfo=sealed_source();output=Path(output).resolve()
    if not output.is_relative_to((R/'release/compiler_iterations/source_pools').resolve())or output.exists():raise ValueError('new_native_pool_directory_required')
    scope,scope_info=inventory_method.read_scope(R)
    if scope_info['manifest_sha256']!=MANIFEST_SHA or len(scope)!=131904:raise ValueError('full_goal_manifest_changed')
    target={i for i,s in scope.items()if s['format']=='drawio'}
    if len(target)!=SCOPE:raise ValueError('native_source_scope_changed')
    oldaudit={x['id']:x for x in rows(OLD/'source_audit.jsonl')};population=list(rows(OLD/'supported_population.jsonl'));pop={x['id']:x for x in population}
    if set(oldaudit)!=target or len(pop)!=len(population):raise ValueError('sealed_native_source_metadata_incomplete')
    records=[];canonical_found=set();metadata_receipts=[];unknown=collections.Counter()
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:
        db.execute('begin')
        for job in bounded_jobs(db,scope):
            identifier=job[0];canonical_found.add(identifier);source=json.loads(job[4]);canonical_job(job)
            if any(scope[identifier][k]!=source.get(k)for k in ('category','format','source','code_sha256','image_sha256')):raise ValueError('full_scope_canonical_digest_changed:'+identifier)
            keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']));known=True
            if identifier in target:
                audit=oldaudit[identifier];known=bool(audit.get('family')and audit.get('original_native_drawio_hash_verified')and audit.get('source_code_sha256')==source['code_sha256']and audit.get('source_image_sha256')==source['image_sha256'])
                if not known:unknown[audit.get('family_unknown_reason')or'old_verified_native_family_unavailable']+=1
                keys.update(audit.get('cluster_keys')or[])
                if audit.get('source_component'):keys.add(audit['source_component'])
                if identifier in pop:verify_request(pop[identifier],job,config)
                metadata_receipts.append(dict(id=identifier,input_record_sha256=sha(job[4].encode()),input_manifest_sha256=sha((job[11]or'').encode()),output_record_sha256=sha((job[9]or'').encode()),source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],sealed_family=audit.get('family'),known=known))
            records.append(dict(id=identifier,source=scope[identifier],keys=sorted(keys),known=known))
    if canonical_found!=set(scope):raise ValueError('full_goal_scope_canonical_metadata_missing')
    graph=closure.build_components(records,target);state=fresh_state(scope,config)
    # Conservative previous development contamination is retained even if a
    # legacy development key is absent from a newer metadata file.
    extra=[('hard_cluster',a['source_component'])for a in oldaudit.values()if a.get('source_component')and str(a.get('disposition','')).startswith('development_or_reserved')]
    exclusions=state['exclusion_keys']|aliases.normalize_keys(extra)
    with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:registry_keys=aliases.normalize_keys(db.execute('select kind,value from reservation_keys'))
    pending=[x for x in population if x['id']not in state['accepted_native']and x['id']not in state['overlap']['active']and x['id']not in {a['id']for a in state['prior']}]
    choice=closure.select(graph['components'],pending,exclusions|registry_keys,seed=SEED,limit=100)
    output.mkdir(parents=True,exist_ok=False)
    contents={'source_audit.jsonl':(OLD/'source_audit.jsonl').read_bytes(),'supported_population.jsonl':b''.join(raw(x)for x in population),'selected.jsonl':b''.join(raw(x)for x in choice['selected']),'preserved_qualified.jsonl':b''.join(raw(state['accepted_native'][i])for i in sorted(state['accepted_native'])),'prior_candidate_attempts.jsonl':b''.join(raw(x)for x in state['prior']),'ordinary_queue_snapshot.json':raw(dict(verified_live_overlap=state['overlap'],source_only_bookkeeping=True,queue_changed=False)),'sealed_components.json':raw(graph),'canonical_source_metadata.jsonl':b''.join(raw(x)for x in metadata_receipts),'fresh_exclusions.json':raw(dict(keys=sorted(exclusions),receipt=state['receipt']))}
    for name,data in contents.items():
        with(output/name).open('xb')as stream:stream.write(data)
    methods=dict(oldinfo['method_pins'])
    for module in(sys.modules[__name__],aliases,closure):methods[str(Path(module.__file__).resolve())]=sha(Path(module.__file__).read_bytes())
    result={**oldinfo,'seed':SEED,'schema':'compiler_native_sealed_full_goal_metadata_source_pool_v6','full_scope_manifest':scope_info,'sealed_source_audit':dict(directory=str(OLD),summary_sha256=sha((OLD/'summary.json').read_bytes()),files=SEALED),'metadata_refresh':dict(full_goal_scope_rows=len(records),bounded_SQL_batch_size=400,full_canonical_table_scanned=False,code_or_PNG_bytes_read=0,source_static_support_recomputed=False,unknown_native_families=dict(unknown),complete_source_contract_validated_rows=len(population),unchanged_worker_full_source_hash_before_normal=True),'method_pins':methods,'fresh_bookkeeping':state['receipt'],'source_component_counts':dict(full_scope_components=graph['full_components'],native_touching_components=len(graph['components']),full_goal_scope_rows=graph['full_scope_records']),'selected':len(choice['selected']),'eligible_observed_families':choice['eligible_observed_families'],'all_remaining_observed_families_selected':choice['all_remaining_observed_families_selected'],'minimum100_met':len(choice['selected'])>=100,'preserved_qualified':len(state['accepted_native']),'prior_same_SOURCE_frontend_distinct_candidate_attempts':len({x['id']for x in state['prior']}),'prior_same_SOURCE_frontend_attempt_events':len(state['prior']),'files':{name:dict(sha256=sha(data),bytes=len(data))for name,data in contents.items()},'reservation_selection_rechecked_under_write_transaction':True,'registry_modified':False,'model_calls':0}
    with(output/'summary.json').open('xb')as stream:stream.write(raw(result))
    print(json.dumps(dict(source_pool=str(output),scope=1539,full_scope_metadata=len(records),selected=result['selected'],eligible=result['eligible_observed_families'],model_calls=0)),flush=True)
    return result
