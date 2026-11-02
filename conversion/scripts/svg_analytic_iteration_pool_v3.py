"""Exhaustive original SVG source audit and unseen typed-source cohort.

No SVG source execution, layout, conversion, rendering or model calls. Existing
qualified assets and queued/running ordinary ordinary jobs are preserved.
The frozen official forward frontend alone defines source applicability.
"""
import argparse
import collections
import hashlib
import importlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import svg_analytic_source_contract_v2 as contract
import compiler_validation_identity_alias_v1 as aliases
import compiler_validation_sealed_cohort_v1 as sealed

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
SCOPE=26754
SEED='hkust-SVG-analytic-endpoint-native-bezier-source-components-global-20261101-v1'
FRONTEND='svg_analytic_source_contract_v2'
DEVELOPMENT=(R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl',
             R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl')


def source_family(code):
    from compiler_svg_general_unseen_pool_v3 import family as actual
    cluster,evidence=actual(code);return cluster,{cluster},evidence


def raw(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def rows(path):
    path=Path(path);path=path if path.is_absolute()else R/path
    path=path.resolve(strict=True)
    if not path.is_relative_to(R.resolve()):raise ValueError('source_manifest_outside_registered_root')
    with path.open()as stream:
        for line in stream:
            if line.strip():yield json.loads(line)


def identity_overlap(identifier,source,development,codes,images):
    return identifier in development or source['code_sha256']in codes or source['image_sha256']in images


def independent_components(records,development,codes,images,excluded):
    """Transitive source-family closure, including non-selected bridge rows."""
    parents=list(range(len(records)));seen={}
    def find(index):
        while parents[index]!=index:parents[index]=parents[parents[index]];index=parents[index]
        return index
    for index,item in enumerate(records):
        for key in item['keys']:
            if key in seen:
                a,b=find(index),find(seen[key]);parents[max(a,b)]=min(a,b)
            else:seen[key]=index
    groups=collections.defaultdict(list)
    for index in range(len(records)):groups[find(index)].append(records[index])
    eligible=[];component_counts=collections.Counter()
    for members in groups.values():
        keys=set().union(*(x['keys']for x in members));pending=[x for x in members if x['pending']]
        contaminated=bool(keys&excluded)or any(identity_overlap(x['request']['id'],x['request']['source'],development,codes,images)for x in members)
        unknown=any(not x['known']for x in members)
        cluster='SVG_analytic_source_component_v1:'+sha(raw(sorted(keys)))
        component_counts['observed_source_components']+=1
        if contaminated:component_counts['development_or_reserved_connected_components']+=1
        if unknown:component_counts['unknown_family_connected_components']+=1
        for offset,item in enumerate(sorted(pending,key=lambda x:sha(raw([SEED,x['request']['id']])))):
            row=item['audit'];row.update(source_component=cluster,component_members=len(members))
            if contaminated:
                row['disposition']='development_or_reserved_identity_overlap'if identity_overlap(item['request']['id'],item['request']['source'],development,codes,images)else'development_or_reserved_SVG_source_family_provenance_overlap'
            elif unknown:row['disposition']='population_family_unknown_component_not_independent'
            elif offset:row['disposition']='duplicate_validation_SVG_source_family_provenance_or_identity'
            else:
                row['disposition']='eligible_unseen_observed_SVG_source_family_provenance_family'
                eligible.append({**item['request'],'audit_cluster':cluster,'cluster':cluster,'cluster_keys':sorted(keys|{cluster})})
    eligible.sort(key=lambda item:sha(raw([SEED,item['id']])))
    return eligible,dict(component_counts)



def normal_candidate_was_called(request,result,attempt):
    from compiler_source_core_attempts_v3 import normal_was_called
    return normal_was_called(request,result,attempt)

def iteration_bookkeeping(configuration,identifiers=None):
    import compiler_source_core_attempts_v3 as history
    from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
    events=history.collect(configuration,root=R,catalog=contract.CATALOG);history.validate(events,configuration,root=R)
    return events,ledger_manifests(root=R,identifiers=identifiers)


def control_qualified(identifiers=None):
    import compiler_types_program_v1 as common
    result=[]
    for path in sorted((R/'release/compiler_iterations/controls').glob('*/proof.json')):
        proof=json.loads(path.read_bytes());ref=proof.get('qualified_manifest')
        if not ref:continue
        target,blob=common.checked(ref)
        result.extend(row for line in blob.splitlines()if line for row in[json.loads(line)]if identifiers is None or row['id']in identifiers)
    return result


def fresh_qualified(configuration):
    import compiler_iteration_inventory_v1 as inventory
    scope_all,_=inventory.read_scope(R);scope={i:s for i,s in scope_all.items()if s['format']=='svg'}
    pointer=json.loads((R/'release/compiler_iterations/current.json').read_bytes());summary=R/pointer['inventory']
    if sha(summary.read_bytes())!=pointer['inventory_sha256']:raise ValueError('latest_audited_inventory_pointer_changed')
    info=json.loads(summary.read_bytes());manifest=summary.parent/'qualified.jsonl'
    if sha(manifest.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('latest_qualified_manifest_changed')
    accepted={x['id']:x for x in rows(manifest)if x['id']in scope}
    _,iterations=iteration_bookkeeping(configuration,set(scope))
    for item in iterations+control_qualified(set(scope)):accepted[item['id']]=item
    hashes={}
    for identifier,item in accepted.items():inventory.check_manifest(R,identifier,scope[identifier],item,hashes)
    return accepted


def all_prior_attempted_ids():
    """Knowledge exclusion only: IDs, never scores/failure reasons or source scope."""
    from compiler_mermaid_alpha_qualifications_v2 import discover_ledger_paths
    ids=set()
    for ledger in discover_ledger_paths(R):
        with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True,timeout=30)as db:
            db.execute('pragma query_only=ON');db.execute('begin')
            columns={row[1]for row in db.execute('pragma table_info(samples)')}
            if{'id','attempts'}<=columns:ids.update(row[0]for row in db.execute('select id from samples where attempts>0'))
    return ids


def development_inputs():return list(DEVELOPMENT)+sorted((R/'release/compiler_iterations/development_seen_v1').glob('*.jsonl'))


def manual_knowledge_catalogs():
    return sorted(path for path in(R/'release/compiler_iterations/source_core_attempts').glob('manual_catalog*.json')if path.is_file()and not(path.stat().st_mode&0o222))


def supplementary_development_rows():
    catalogs=[json.loads(path.read_bytes())for path in manual_knowledge_catalogs()]
    result=[]
    for catalog in catalogs:
        if catalog.get('schema')!='source_core_manual_attempt_catalog_v3':raise ValueError('global_manual_source_knowledge_catalog_schema_changed')
        result.extend(dict(id=row['id'],source_code_sha256=row['source']['code_sha256'],source_image_sha256=row['source']['image_sha256'])for row in catalog['entries'])
    result.extend(dict(id=identifier)for identifier in sorted(all_prior_attempted_ids()))
    return result


def current_selected_exclusion_guard(selected):
    import compiler_validation_cluster_audit_v1 as provenance
    import compiler_svg_general_unseen_pool_v3 as families
    inputs=development_inputs();items=[x for p in inputs for x in rows(p)]+supplementary_development_rows();ids={x['id']for x in items};keys=set()
    for x in items:
        code=x.get('source_code_sha256')or x.get('code_sha256');image=x.get('source_image_sha256')or x.get('image_sha256')
        if code:keys.add('exact_original_code:'+code)
        if image:keys.add('exact_original_image:'+image)
        keys.update(x.get('cluster_keys')or[])
    with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as db:reserved=set(db.execute('select kind,value from reservation_keys'))
    ids.update(value for kind,value in reserved if kind=='id')
    for kind,value in reserved:
        if kind=='code':keys.add('exact_original_code:'+value)
        elif kind=='image':keys.add('exact_original_image:'+value)
        elif kind in('audit_cluster','hard_cluster'):keys.add(value)
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        for identifier in sorted(ids):
            job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
            if not job:continue
            source=json.loads(job[4]);keys.update(('exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']));keys.update(provenance.provenance(source,source['source']))
            if source['format']=='svg':
                try:_,extra,_=source_family(source_text(job,source));keys.update(extra)
                except ValueError:pass
    for item in selected:
        if item['id']in ids or set(item['cluster_keys'])&keys:raise ValueError('selected_source_became_seen_or_reserved_before_seal')
    return dict(source_only=True,selected_current_overlap=0,known_IDs=len(ids),known_source_ids=sorted(ids),exclusion_keys=len(keys),exclusion_keys_sha256=sha(raw(sorted(keys))),registry_snapshot_sha256=sha(raw(sorted(reserved))),inputs={str(p):sha(p.read_bytes())for p in inputs})


def checked_original_code(locator,digest,data_root=R):
    root=Path(data_root).resolve(strict=True);path=(root/locator).resolve(strict=True)
    if not path.is_relative_to(root):raise ValueError('original_source_outside_registered_root')
    payload=path.read_bytes()
    if sha(payload)!=digest:raise ValueError('original_source_hash_changed')
    return payload.decode('utf-8-sig')


def family(code):
    import compiler_svg_general_unseen_pool_v3 as families
    cluster,_,evidence=source_family(code);return cluster,evidence


def source_text(job,source):
    capture=json.loads(job[9])if job[9]else{}
    manifest=json.loads(job[11])if job[11]else{}
    for locator in (manifest.get('source_code'),capture.get('original_source_code')):
        if not locator:continue
        path=(R/locator).resolve()
        if not path.is_relative_to(R.resolve()):continue
        try:blob=path.read_bytes()
        except OSError:continue
        if sha(blob)==source['code_sha256']:return blob.decode('utf-8-sig')
    raise ValueError('authoritative_original_SVG_payload_unreadable_or_changed')


def request_from_job(job,source,unit,snapshot):
    if source!=json.loads(job[4])or source.get('pair_sha256')!=job[0]:raise ValueError('worker_source_requires_complete_canonical_source_record')
    if source.get('format')!='svg'or source.get('category')not in ('scientific_diagram',):raise ValueError('worker_source_outside_SVG_scope')
    if not isinstance(snapshot,dict)or(snapshot.get('id'),snapshot.get('source_code_sha256'),snapshot.get('source_image_sha256'))!=(job[0],source['code_sha256'],source['image_sha256']):raise ValueError('worker_source_capture_snapshot_identity_changed')
    old=json.loads(job[9])if job[9]else{}
    return dict(id=job[0],source=source,compiler_unit=unit,source_capture_snapshot=snapshot,source_record_sha256=sha((job[9]or'').encode()),baseline_code_sha256=old.get('code_sha256'),baseline_image_sha256=old.get('image_sha256'))

def canonical_job(job):
    from svg_analytic_iteration_case_v2 import JOB_COLUMNS
    if len(job)!=len(JOB_COLUMNS):raise ValueError('canonical_job_requires_all13_columns')
    result=dict(zip(JOB_COLUMNS,job))
    source=json.loads(result['input_record'])
    if(source.get('pair_sha256'),source.get('format'),source.get('category'),source.get('source'))!=(result['id'],result['format'],result['category'],result['source']):raise ValueError('canonical_job_source_identity_changed')
    return result


def static_support_from_job(compiler,job):
    """The pool uses the exact canonical dictionary API used by the worker."""
    support=compiler.static_support(canonical_job(job))
    if not isinstance(support,dict)or type(support.get('supported'))is not bool:raise RuntimeError('infrastructure_static_source_contract_not_typed')
    return support


def prepare(output,inventory):
    import compiler_svg_general_unseen_pool_v3 as families
    import svg_analytic_iteration_program_v2 as program
    import compiler_iteration_inventory_v1 as inventory_method
    import compiler_validation_cluster_audit_v1 as provenance
    compiler=importlib.import_module(FRONTEND);config=compiler.configuration()
    output=Path(output).resolve();inventory=Path(inventory).resolve(strict=True)
    if not output.is_relative_to((R/'release/compiler_iterations/source_pools').resolve()):raise ValueError('SVG_analytic_pool_outside_owner')
    controls=program.control_bundle(compiler);program.check_controls(controls)
    scope_all,scope_info=inventory_method.read_scope(R)
    scope={i:x for i,x in scope_all.items()if x['format']=='svg'}
    if len(scope)!=SCOPE:raise ValueError('original_SVG_scope_not_26754')
    info=json.loads((inventory/'summary.json').read_bytes());qualified_path=inventory/'qualified.jsonl'
    if sha(qualified_path.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('qualified_inventory_changed')
    accepted={x['id']:x for x in rows(qualified_path)if x['id']in scope}
    from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot as active_snapshot
    overlap=active_snapshot();active_ids=set(overlap['active'])
    prior_attempts,iteration_qualified=iteration_bookkeeping(config,set(scope))
    prior_ids={item['id']for item in prior_attempts}
    from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
    for item in iteration_qualified+control_qualified(set(scope))+list(rows(controls['qualified_manifest']['file'])):
        if item['id']in scope:accepted[item['id']]=item
    # Full immutable assets are checked; accepting a historical label alone is
    # insufficient. No current source-normal conversion or QA is rerun.
    hashes={}
    for identifier,item in accepted.items():inventory_method.check_manifest(R,identifier,scope[identifier],item,hashes)
    development_paths=development_inputs()
    dev_rows=[x for path in development_paths for x in rows(path)]+supplementary_development_rows()
    development={x['id']for x in dev_rows};development.update(x['id']for x in controls['positive_cases']);development.update(prior_ids)
    with sqlite3.connect('file:'+str(R/'release/compiler_v1/validation_registry.sqlite')+'?mode=ro',uri=True,timeout=30)as registry:
        registry.execute('begin');registry_keys=set(registry.execute('select kind,value from reservation_keys'))
    canonical_registry_keys=aliases.normalize_keys(registry_keys)
    development.update(value for kind,value in canonical_registry_keys if kind=='id')
    excluded_codes={v for k,v in canonical_registry_keys if k=='code'};excluded_images={v for k,v in canonical_registry_keys if k=='image'}
    excluded_keys={v for k,v in canonical_registry_keys if k=='cluster'}
    for item in dev_rows:
        if item.get('source_code_sha256')or item.get('code_sha256'):excluded_codes.add(item.get('source_code_sha256')or item['code_sha256'])
        if item.get('source_image_sha256')or item.get('image_sha256'):excluded_images.add(item.get('source_image_sha256')or item['image_sha256'])
        excluded_keys.update(item.get('cluster_keys')or [])
    database=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
    counters=collections.Counter();unused_cache={}
    def load(identifier):
        job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
        if not job:raise ValueError('canonical_original_job_missing')
        source=json.loads(job[4])
        if (source['pair_sha256'],source['category'],source['format'],source['source'])!=(identifier,job[1],job[2],job[3]):raise ValueError('canonical_original_source_identity_changed')
        if identifier in scope and any(scope[identifier][k]!=source[k]for k in ('category','format','source','code_sha256','image_sha256')):raise ValueError('scope_original_source_digest_changed')
        return job,source
    try:
        # Resolve every all-format dev/reserved source for global exact hashes
        # and explicit document/template provenance. Same-format native graph template and
        # actual native graph families exclude leakage even across different wrappers.
        for identifier in sorted(development):
            try:
                job,source=load(identifier);excluded_codes.add(source['code_sha256']);excluded_images.add(source['image_sha256'])
                excluded_keys.update(provenance.provenance(source,source['source']));counters['all_format_development_or_reserved_sources_loaded']+=1
                if job[2]=='svg':
                    code=source_text(job,source)
                    try:
                        _,keys,_=source_family(code);excluded_keys.update(keys);counters['SVG_exclusion_family_parsed']+=1
                    except Exception as error:counters['SVG_exclusion_family_unknown:'+type(error).__name__]+=1
            except Exception as error:counters['exclusion_source_unknown:'+type(error).__name__]+=1
        output.mkdir(parents=True,exist_ok=False)
        (output/'ordinary_queue_snapshot.json').write_bytes(raw(dict(verified_live_overlap=overlap,source_only_bookkeeping=True,queue_changed=False)))
        (output/'preserved_qualified.jsonl').write_bytes(b''.join(raw(accepted[i])for i in sorted(accepted)))
        (output/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(item)for item in prior_attempts))
        (output/'seen_source_IDs_snapshot.jsonl').write_bytes(b''.join(raw(dict(id=identifier))for identifier in sorted(development)))
        source_records=[];audited=[];population_count=0
        ordered=sorted(scope,key=lambda identifier:sha(raw([SEED,identifier])))
        with(output/'supported_population.jsonl').open('wb')as population:
            for identifier in ordered:
                row=dict(id=identifier,source_format='svg',handler_applicable=False)
                source=scope[identifier];keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']));known=False;item=dict(id=identifier,source=source,compiler_unit=compiler.UNIT)
                try:
                    job,source=load(identifier);code=source_text(job,source)
                    row.update(original_SVG_hash_verified=True,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
                    keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']))
                    known=False
                    try:
                        cluster,family_keys,evidence=source_family(code);keys.update(family_keys);known=True
                        row.update(family=cluster,source_family_evidence=evidence)
                    except Exception as error:row['family_unknown_reason']=str(error)[:700]
                    row['cluster_keys']=sorted(keys)
                    support=static_support_from_job(compiler,job)
                    item=dict(id=identifier,source=source,compiler_unit=compiler.UNIT)
                    if not support['supported']:row.update(disposition='pending_outside_frozen_frontend_source_grammar',reason=support['reasons'])
                    else:
                        row.update(handler_applicable=True,source_capture_snapshot_sha256=sha(raw(support['source_capture_snapshot'])),source_profile='fresh_SVG_original_source_viewport_asset_content_predicate')
                        item=request_from_job(job,source,compiler.UNIT,support['source_capture_snapshot'])
                        if identifier in accepted:row['disposition']='already_qualified_preserved'
                        elif identifier in active_ids:row['disposition']='deferred_birth_verified_active_SVG_conversion_overlap'
                        else:
                            population.write(raw(item));population_count+=1
                            row['disposition']='prior_same_SOURCE_frontend_attempt_pending_next_repair'if identifier in prior_ids else'source_component_inventory_pending'
                    # Every scope row participates as a source-family bridge,
                    # even when this frontend does not support that source.
                    if identifier in accepted:
                        row['prior_source_disposition']=row['disposition'];row['disposition']='already_qualified_preserved'
                except Exception as error:row.update(disposition='pending_source_inventory_diagnosis',reason=str(error)[:1000])
                source_records.append(dict(audit=row,request=item,keys=keys,known=known,pending=row.get('disposition')=='source_component_inventory_pending'))
                if row['handler_applicable']:counters['exact_handler_applicable_all_scope']+=1
                audited.append(row)
        global_bridge_count=0
        for identifier,summary_source in sorted(scope_all.items()):
            if identifier in scope:continue
            bridge_source=summary_source;known=True;keys={'exact_original_code:'+summary_source['code_sha256'],'exact_original_image:'+summary_source['image_sha256']}
            try:
                _,bridge_source=load(identifier);keys.update(provenance.provenance(bridge_source,bridge_source['source']))
            except Exception as error:
                known=False;counters['cross_format_bridge_provenance_unknown:'+type(error).__name__]+=1
            source_records.append(dict(audit={'id':identifier,'cross_format_bridge':True},request={'id':identifier,'source':bridge_source},keys=keys,known=known,pending=False));global_bridge_count+=1
        eligible,component_counts=independent_components(source_records,development,excluded_codes,excluded_images,excluded_keys)
        sealed_components=sealed.build_components(source_records,set(scope))
        if sealed_components['full_scope_records']!=131904 or sealed_components['target_records']!=SCOPE:raise ValueError('SVG_complete_sealed_source_component_coverage_changed')
        (output/'sealed_source_components.json').write_bytes(raw(sealed_components))
        for component in sealed_components['components']:
            for identifier in component['target_ids']:
                # Metadata audit points to the complete component including foreign bridges.
                unused_cache[identifier]=(component['component'],len(component['component_all_ids']))
        for row in audited:
            row['sealed_source_component'],row['sealed_component_all_format_members']=unused_cache[row['id']]
        component_counts.update(sealed_full_scope_records=sealed_components['full_scope_records'],sealed_target_records=sealed_components['target_records'],sealed_all_format_components=sealed_components['full_components'])
        for row in audited:counters[row['disposition']]+=1
        (output/'source_audit.jsonl').write_bytes(b''.join(raw(row)for row in audited))
        selected=eligible[:100]
        for seq,item in enumerate(selected,1):item['seq']=seq
        (output/'selected.jsonl').write_bytes(b''.join(raw(x)for x in selected))
        methods=[Path(__file__),W/'scripts/compiler_source_core_attempts_v3.py',R/contract.CATALOG,W/'scripts/compiler_mermaid_alpha_qualifications_v2.py',W/'scripts/compiler_types_source_ir_v1.py',W/'scripts/native_worker.py',Path(contract.__file__),W/'scripts/compiler_mermaid_alpha_iteration_overlap_v2.py',Path(families.__file__),Path(aliases.__file__),Path(sealed.__file__),W/'scripts/svg_analytic_cohort_refresh_v2.py',W/'scripts/compiler_validation_reservation_v2.py',Path(inventory_method.__file__),Path(provenance.__file__),W/'scripts/compiler_validation_dot_ir_v2.py',W/'scripts/svg_analytic_iteration_case_v2.py']+development_paths+manual_knowledge_catalogs()
        files=('source_audit.jsonl','supported_population.jsonl','selected.jsonl','preserved_qualified.jsonl','ordinary_queue_snapshot.json','prior_candidate_attempts.jsonl','seen_source_IDs_snapshot.jsonl','sealed_source_components.json')
        result=dict(schema='compiler_SVG_analytic_source_pool_v1',global_cross_format_bridge_count=global_bridge_count,seed=SEED,scope=SCOPE,full_scope_manifest=scope_info,
                    compiler_unit=compiler.UNIT,frontend_module=FRONTEND,frozen_implementation=config,
                    source_only=True,SVG_source_execution=False,static_source_family_parser_only=True,conversion_or_rendering=False,model_calls=0,
                    method_pins={str(p.resolve()):sha(p.read_bytes())for p in methods},controls_proof=controls['definition'],
                    development_inputs={str(p):sha(p.read_bytes())for p in development_paths},development_ids_all_formats=len(development),
                    exclusion_source_keys=len(excluded_keys),registry_keys_snapshot_sha256=sha(raw(sorted(registry_keys))),registry_modified=False,
                    audited_scope_rows=SCOPE,counters={**dict(counters),'supported_remaining_population':population_count},
                    source_component_counts=component_counts,
                    prior_same_SOURCE_frontend_distinct_candidate_attempts=len(prior_ids),prior_same_SOURCE_frontend_attempt_events=len(prior_attempts),
                    prior_attempted_IDS_not_reexecuted=sorted(prior_ids),
                    preserved_qualified=len(accepted),preserved_clean_assets_verified=len(hashes),
                    ordinary_queue_never_modified=True,birth_verified_live_queued_or_frozen_pending_excluded=len(set(scope)&active_ids),
                    eligible_observed_families=len(eligible),selected=len(selected),minimum100_met=len(selected)>=100,
                    all_remaining_observed_families_selected=len(selected)==len(eligible),
                    minimum5_incremental_qualified_gate_unchanged=True,
                    limitations=['Complete static SVG XML/reference topology family plus explicit source provenance exclude duplicates; invariant collisions conservatively merge.',
                                 'Unknown source families remain in supported_population and are excluded from independence claims and the unseen cohort.',
                                 'All applicable pending source rows remain in population, including all-core prior-attempt/dev/reserved and unknown families; only qualifications and birth-verified live queued/running or frozen pending manifests are excluded. Dead/unowned stale queues are not excluded.',
                                 'Only bookkeeping qualification/queue state is read to preserve prior work; no QA score, conversion failure reason or per-ID allowlist defines source applicability.',
                                 'The observed source families do not prove hidden generator independence or an unbiased population yield estimate.'],
                    files={name:dict(sha256=sha((output/name).read_bytes()),bytes=(output/name).stat().st_size)for name in files})
        if compiler.configuration()!=config:raise ValueError('frozen_frontend_changed_during_source_audit')
        if sum(1 for _ in rows(output/'source_audit.jsonl'))!=SCOPE:raise ValueError('incomplete_source_scope_audit')
        with(output/'summary.json').open('xb')as stream:stream.write(raw(result))
        print(json.dumps({k:v for k,v in result.items()if k not in ('frozen_implementation','method_pins','development_inputs')},ensure_ascii=False),flush=True)
        return result
    finally:database.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--inventory',type=Path,required=True);args=parser.parse_args();prepare(args.output,args.inventory)
