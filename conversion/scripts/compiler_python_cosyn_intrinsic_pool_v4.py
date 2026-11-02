"""Exhaustive original Python source audit and unseen typed-source cohort.

No Python execution, layout, conversion, rendering or model calls. Existing
qualified assets and queued/running ordinary Graphviz-v2 jobs are preserved.
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

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
SCOPE=13801
SEED='hkust-Python-CoSyn-intrinsic-integer-viewport-full-global-DOT-AST-provenance-20261101-v2'
FRONTEND='compiler_python_cosyn_intrinsic_frontend_claims_v2'
ORDINARY=R/'release/compiler_v2/graphviz_batch_20261101_v2_renderdomain'
DEVELOPMENT=(R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl',
             R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl')


def raw(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def rows(path):
    with Path(path).open()as stream:
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
        cluster='python_cosyn_intrinsic_source_component_v1:'+sha(raw(sorted(keys)))
        component_counts['observed_source_components']+=1
        if contaminated:component_counts['development_or_reserved_connected_components']+=1
        if unknown:component_counts['unknown_family_connected_components']+=1
        for offset,item in enumerate(sorted(pending,key=lambda x:sha(raw([SEED,x['request']['id']])))):
            row=item['audit'];row.update(source_component=cluster,component_members=len(members))
            if contaminated:
                row['disposition']='development_or_reserved_identity_overlap'if identity_overlap(item['request']['id'],item['request']['source'],development,codes,images)else'development_or_reserved_DOT_template_provenance_overlap'
            elif unknown:row['disposition']='population_family_unknown_component_not_independent'
            elif offset:row['disposition']='duplicate_validation_DOT_template_provenance_or_identity'
            else:
                row['disposition']='eligible_unseen_observed_DOT_template_provenance_family'
                eligible.append({**item['request'],'audit_cluster':cluster,'cluster':cluster,'cluster_keys':sorted(keys|{cluster})})
    eligible.sort(key=lambda item:sha(raw([SEED,item['id']])))
    return eligible,dict(component_counts)


def ordinary_snapshot():
    with sqlite3.connect('file:'+str(ORDINARY/'status.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
        database.execute('begin')
        states=dict(database.execute('select id,status from samples'))
        qualified=[]
        for identifier,payload in database.execute('select id,result from samples where status="qualified"'):
            result=json.loads(payload)
            if result['id']!=identifier or result['status']!='qualified':raise ValueError('ordinary_graphviz_ledger_identity_changed')
            qualified.append(result['manifest'])
    return states,qualified


def normal_candidate_was_called(request,result,attempt):
    from compiler_source_core_attempts_v3 import normal_was_called
    return normal_was_called(request,result,attempt)


def iteration_bookkeeping(configuration):
    import compiler_source_core_attempts_v3 as history
    from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
    events=history.collect(configuration,root=R);history.validate(events,configuration,root=R)
    return events,ledger_manifests(root=R)


def control_qualified():
    import compiler_types_program_v1 as common
    result=[]
    for path in sorted((R/'release/compiler_iterations/controls').glob('*/proof.json')):
        proof=json.loads(path.read_bytes());ref=proof.get('qualified_manifest')
        if not ref:continue
        target,blob=common.checked(ref)
        result.extend(json.loads(line)for line in blob.splitlines()if line)
    return result


def fresh_qualified(configuration):
    import compiler_iteration_inventory_v1 as inventory
    pointer=json.loads((R/'release/compiler_iterations/current.json').read_bytes());summary=R/pointer['inventory']
    if sha(summary.read_bytes())!=pointer['inventory_sha256']:raise ValueError('latest_audited_inventory_pointer_changed')
    info=json.loads(summary.read_bytes());manifest=summary.parent/'qualified.jsonl'
    if sha(manifest.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('latest_qualified_manifest_changed')
    accepted={x['id']:x for x in rows(manifest)}
    _,ordinary=ordinary_snapshot();_,iterations=iteration_bookkeeping(configuration)
    from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
    for item in ordinary+iterations+control_qualified()+ledger_manifests(root=R):accepted[item['id']]=item
    scope,_=inventory.read_scope(R);hashes={}
    for identifier,item in accepted.items():inventory.check_manifest(R,identifier,scope[identifier],item,hashes)
    return accepted


def source_text(job,source):
    capture=json.loads(job[9])if job[9]else{}
    manifest=json.loads(job[11])if job[11]else{}
    for locator in (manifest.get('source_code'),capture.get('original_source_code')):
        if not locator:continue
        path=(R/locator).resolve()
        if not path.is_relative_to((R/'clean').resolve()):continue
        try:blob=path.read_bytes()
        except OSError:continue
        if sha(blob)==source['code_sha256']:return blob.decode('utf-8-sig')
    raise ValueError('authoritative_original_Python_payload_unreadable_or_changed')


def request_from_job(job,source,unit,snapshot):
    if source!=json.loads(job[4])or source.get('pair_sha256')!=job[0]:raise ValueError('worker_source_requires_complete_canonical_source_record')
    if source.get('format')!='python'or source.get('category')not in ('scientific_diagram','poster'):raise ValueError('worker_source_outside_Python_scope')
    if not isinstance(snapshot,dict)or(snapshot.get('id'),snapshot.get('source_code_sha256'),snapshot.get('source_image_sha256'))!=(job[0],source['code_sha256'],source['image_sha256']):raise ValueError('worker_source_capture_snapshot_identity_changed')
    old=json.loads(job[9])if job[9]else{}
    return dict(id=job[0],source=source,compiler_unit=unit,source_capture_snapshot=snapshot,source_record_sha256=sha((job[9]or'').encode()),baseline_code_sha256=old.get('code_sha256'),baseline_image_sha256=old.get('image_sha256'))


def prepare(output,inventory):
    import compiler_graphviz_visibility_iteration_family_v1 as families
    import compiler_python_cosyn_intrinsic_program_v4 as program
    import compiler_iteration_inventory_v1 as inventory_method
    import compiler_validation_cluster_audit_v1 as provenance
    from compiler_graphviz_visibility_scene_v1 import _read
    compiler=importlib.import_module(FRONTEND);config=compiler.configuration()
    output=Path(output).resolve();inventory=Path(inventory).resolve(strict=True)
    if not output.is_relative_to((R/'release/compiler_iterations/source_pools').resolve()):raise ValueError('Python_pool_outside_owner')
    controls=program.control_bundle(compiler);program.check_controls(controls)
    scope_all,scope_info=inventory_method.read_scope(R)
    scope={i:x for i,x in scope_all.items()if x['format']=='python'}
    if len(scope)!=SCOPE:raise ValueError('original_Python_scope_not_13801')
    info=json.loads((inventory/'summary.json').read_bytes());qualified_path=inventory/'qualified.jsonl'
    if sha(qualified_path.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('qualified_inventory_changed')
    accepted={x['id']:x for x in rows(qualified_path)if x['id']in scope}
    ordinary_states,new_qualified=ordinary_snapshot()
    from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot as active_snapshot
    overlap=active_snapshot();active_ids=set(overlap['active'])
    prior_attempts,iteration_qualified=iteration_bookkeeping(config)
    prior_ids={item['id']for item in prior_attempts}
    from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
    for item in new_qualified+iteration_qualified+control_qualified()+ledger_manifests(root=R,identifiers=set(scope))+list(rows(controls['qualified_manifest']['file'])):
        if item['id']in scope:accepted[item['id']]=item
    # Full immutable assets are checked; accepting a historical label alone is
    # insufficient. No current source-normal conversion or QA is rerun.
    hashes={}
    for identifier,item in accepted.items():inventory_method.check_manifest(R,identifier,scope[identifier],item,hashes)
    development_inputs=list(DEVELOPMENT)+sorted((R/'release/compiler_iterations/development_seen_v1').glob('*.jsonl'))
    dev_rows=[x for path in development_inputs for x in rows(path)]
    development={x['id']for x in dev_rows};development.update(x['id']for x in controls['positive_cases']);development.update(prior_ids)
    with sqlite3.connect('file:'+str(R/'release/compiler_v1/validation_registry.sqlite')+'?mode=ro',uri=True,timeout=30)as registry:
        registry.execute('begin');registry_keys=set(registry.execute('select kind,value from reservation_keys'))
    development.update(value for kind,value in registry_keys if kind=='id')
    excluded_codes={v for k,v in registry_keys if k=='code'};excluded_images={v for k,v in registry_keys if k=='image'}
    excluded_keys={v for k,v in registry_keys if k in ('audit_cluster','hard_cluster')}
    for item in dev_rows:
        if item.get('source_code_sha256')or item.get('code_sha256'):excluded_codes.add(item.get('source_code_sha256')or item['code_sha256'])
        if item.get('source_image_sha256')or item.get('image_sha256'):excluded_images.add(item.get('source_image_sha256')or item['image_sha256'])
        excluded_keys.update(item.get('cluster_keys')or [])
    database=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
    counters=collections.Counter();dot_cache={}
    def load(identifier):
        job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
        if not job:raise ValueError('canonical_original_job_missing')
        source=json.loads(job[4])
        if (source['pair_sha256'],source['category'],source['format'],source['source'])!=(identifier,job[1],job[2],job[3]):raise ValueError('canonical_original_source_identity_changed')
        if identifier in scope and any(scope[identifier][k]!=source[k]for k in ('category','format','source','code_sha256','image_sha256')):raise ValueError('scope_original_source_digest_changed')
        return job,source
    def parsed(dot):
        digest=sha(dot)
        if digest not in dot_cache:
            document,payload=families.parse_dot(dot);dot_cache[digest]=(document,sha(payload))
        return dot_cache[digest]
    try:
        # Resolve every all-format dev/reserved source for global exact hashes
        # and explicit document/template provenance. Same-format Python AST and
        # actual DOT families exclude leakage even across different wrappers.
        for identifier in sorted(development):
            try:
                job,source=load(identifier);excluded_codes.add(source['code_sha256']);excluded_images.add(source['image_sha256'])
                excluded_keys.update(provenance.provenance(source,source['source']));counters['all_format_development_or_reserved_sources_loaded']+=1
                if job[2]=='python':
                    code=source_text(job,source);excluded_keys.add(families.python_template(code));counters['Python_exclusion_AST_parsed']+=1
                    try:
                        capture=json.loads(job[9]);dot=_read(capture['source_render_dot']);document,_=parsed(dot)
                        _,keys,_=families.family(code,document);excluded_keys.update(keys);counters['Python_exclusion_actual_DOT_parsed']+=1
                    except Exception as error:counters['Python_exclusion_DOT_unknown:'+type(error).__name__]+=1
            except Exception as error:counters['exclusion_source_unknown:'+type(error).__name__]+=1
        output.mkdir(parents=True,exist_ok=False)
        (output/'ordinary_queue_snapshot.json').write_bytes(raw(dict(directory=str(ORDINARY),ordinary_states=ordinary_states,verified_live_overlap=overlap,source_only_bookkeeping=True,queue_changed=False)))
        (output/'preserved_qualified.jsonl').write_bytes(b''.join(raw(accepted[i])for i in sorted(accepted)))
        (output/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(item)for item in prior_attempts))
        source_records=[];audited=[];population_count=0
        ordered=sorted(scope,key=lambda identifier:sha(raw([SEED,identifier])))
        with(output/'supported_population.jsonl').open('wb')as population:
            for identifier in ordered:
                row=dict(id=identifier,source_format='python',handler_applicable=False)
                source=scope[identifier];keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']));known=False
                item=dict(id=identifier,source=source,compiler_unit=compiler.UNIT)
                try:
                    job,source=load(identifier);code=source_text(job,source)
                    row.update(original_Python_hash_verified=True,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
                    keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']))
                    known=False;document=None
                    try:keys.add(families.python_template(code))
                    except Exception as error:row['AST_family_unknown_reason']=str(error)[:700]
                    capture=json.loads(job[9])if job[9]else{}
                    dot=_read(capture['source_render_dot'])if capture.get('source_render_dot')else None
                    if dot is not None:
                        try:
                            document,json_sha=parsed(dot);cluster,family_keys,evidence=families.family(code,document);keys.update(family_keys);known=True
                            row.update(family=cluster,source_family_evidence=evidence,syntax_only_DOT_json_sha256=json_sha)
                        except Exception as error:row['family_unknown_reason']=str(error)[:700]
                    else:row['family_unknown_reason']='no_actual_Graphviz_DOT_capture'
                    row['cluster_keys']=sorted(keys)
                    support=compiler.static_support(job)
                    item=dict(id=identifier,source=source,compiler_unit=compiler.UNIT)
                    if not support['supported']:row.update(disposition='pending_outside_frozen_frontend_source_grammar',reason=support['reasons'])
                    else:
                        row.update(handler_applicable=True,source_capture_snapshot_sha256=sha(raw(support['source_capture_snapshot'])),source_profile='frozen_original_CoSyn_Graphviz_official_forward_source_predicate')
                        item=request_from_job(job,source,compiler.UNIT,support['source_capture_snapshot'])
                        if identifier in accepted:row['disposition']='already_qualified_preserved'
                        elif identifier in active_ids:row['disposition']='deferred_birth_verified_active_Python_conversion_overlap'
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
            bridge_source=summary_source;known=True
            keys={'exact_original_code:'+summary_source['code_sha256'],'exact_original_image:'+summary_source['image_sha256']}
            try:
                _,bridge_source=load(identifier);keys.update(provenance.provenance(bridge_source,bridge_source['source']))
            except Exception as error:
                known=False;counters['cross_format_bridge_provenance_unknown:'+type(error).__name__]+=1
            source_records.append(dict(audit={'id':identifier,'cross_format_bridge':True},request={'id':identifier,'source':bridge_source},keys=keys,known=known,pending=False));global_bridge_count+=1
        eligible,component_counts=independent_components(source_records,development,excluded_codes,excluded_images,excluded_keys)
        for row in audited:counters[row['disposition']]+=1
        (output/'source_audit.jsonl').write_bytes(b''.join(raw(row)for row in audited))
        selected=eligible[:100]
        for seq,item in enumerate(selected,1):item['seq']=seq
        (output/'selected.jsonl').write_bytes(b''.join(raw(x)for x in selected))
        methods=[Path(__file__),W/'scripts/compiler_source_core_attempts_v3.py',R/'release/compiler_iterations/source_core_attempts/manual_catalog_20261101_v3.json',W/'scripts/compiler_mermaid_alpha_qualifications_v2.py',W/'scripts/compiler_mermaid_alpha_iteration_overlap_v2.py',Path(families.__file__),Path(inventory_method.__file__),Path(provenance.__file__),W/'scripts/compiler_validation_dot_ir_v2.py',W/'scripts/compiler_python_cosyn_intrinsic_case_v3.py']+development_inputs
        files=('source_audit.jsonl','supported_population.jsonl','selected.jsonl','preserved_qualified.jsonl','ordinary_queue_snapshot.json','prior_candidate_attempts.jsonl')
        result=dict(schema='compiler_python_cosyn_intrinsic_source_pool_v2',global_cross_format_bridge_count=global_bridge_count,seed=SEED,scope=SCOPE,full_scope_manifest=scope_info,
                    compiler_unit=compiler.UNIT,frontend_module=FRONTEND,frozen_implementation=config,
                    source_only=True,Python_execution=False,DOT_parser_mode='-Tdot_json syntax only; no layout',conversion_or_rendering=False,model_calls=0,
                    method_pins={str(p.resolve()):sha(p.read_bytes())for p in methods},controls_proof=controls['definition'],
                    development_inputs={str(p):sha(p.read_bytes())for p in development_inputs},development_ids_all_formats=len(development),
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
                    limitations=['Hard Python AST template and typed actual DOT topology/style/ports/cluster invariants plus explicit source provenance exclude duplicates; invariant collisions conservatively merge.',
                                 'Unknown source families remain in supported_population and are excluded from independence claims and the unseen cohort.',
                                 'All applicable pending source rows remain in population, including dev/reserved and unknown families; only qualifications and birth-verified live queued/running or frozen pending manifests are excluded. Dead/unowned stale queues are not excluded.',
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
