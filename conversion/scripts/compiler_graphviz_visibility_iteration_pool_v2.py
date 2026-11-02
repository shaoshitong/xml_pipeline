"""Exhaustive original Python source audit and unseen typed-source cohort.

No Python execution, layout, conversion, rendering or model calls. Existing
qualified assets and queued/running ordinary Graphviz-v2 jobs are preserved.
Only explicit invisible-edge source semantics enter this handler's population.
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
SEED='hkust-Python-explicit-invisible-edge-actual-DOT-AST-provenance-unseen-20261101-v2'
FRONTEND='compiler_graphviz_visibility_frontend_v1'
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
        cluster='python_graphviz_nonpainting_source_component_v1:'+sha(raw(sorted(keys)))
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


def iteration_bookkeeping(configuration):
    """Read accepted rows and actual candidate attempts, never their QA scores.

    Baseline-only checks and finite development controls are not production
    compiler attempts. Historical rows remain byte-for-byte untouched; exact
    JSON row bytes and frontend result artifacts are carried into the new pool.
    """
    import compiler_graphviz_visibility_iteration_case_v2 as typed
    names=('scene','backend','text','reproduction','domain','quality','case','frontend','quality_ro')
    source_pins={str(W/'scripts'/('compiler_graphviz_visibility_'+name+'_v1.py')):configuration['pins'][str(W/'scripts'/('compiler_graphviz_visibility_'+name+'_v1.py'))]for name in names}
    qualified=[];events=[]
    for ledger in sorted((R/'release/compiler_iterations/runs').glob('*/status.sqlite')):
        directory=ledger.parent;freeze_path=directory/'freeze.json'
        freeze=json.loads(freeze_path.read_bytes())if freeze_path.exists()else{}
        same_source_frontend=all(freeze.get('pins',{}).get(path)==digest for path,digest in source_pins.items())
        with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True,timeout=30)as database:
            database.execute('begin');metadata={key:json.loads(value)for key,value in database.execute('select key,value from metadata')}
            for identifier,payload in database.execute('select id,result from samples where status="qualified"'):
                value=json.loads(payload)
                if value['id']!=identifier:raise ValueError('iteration_qualified_identity_changed')
                if value.get('manifest'):qualified.append(value['manifest'])
            if not same_source_frontend or metadata.get('mode')not in ('validation','batch'):continue
            for identifier,status,attempts,request_json,result_json in database.execute('select id,status,attempts,source,result from samples where attempts=1 and status in ("qualified","abandoned")'):
                request=json.loads(request_json)
                if request.get('compiler_unit')!=configuration['unit']or request.get('evaluation_phase')=='baseline':continue
                result=json.loads(result_json);source=request['source']
                if result['id']!=identifier or (result['source_code_sha256'],result['source_image_sha256'])!=(source['code_sha256'],source['image_sha256']):raise ValueError('prior_SOURCE_frontend_attempt_identity_changed')
                evidence=result.get('evidence_directory');frontend_path=R/evidence/'frontend_result.json'if evidence else None
                frontend_ref=None;diagnosis=None;actual_attempt=None
                if frontend_path and frontend_path.is_file():
                    blob=frontend_path.read_bytes();actual_attempt=json.loads(blob);frontend_ref=dict(file=str(frontend_path),sha256=sha(blob))
                    diagnosis=typed.infrastructure_diagnosis(actual_attempt)
                events.append(dict(id=identifier,status=status,source=source,source_frontend_pins=source_pins,run=str(directory),
                                   raw_request_json=request_json,raw_request_sha256=sha(request_json.encode()),raw_result_json=result_json,raw_result_sha256=sha(result_json.encode()),
                                   original_infrastructure_flag=result.get('infrastructure_failure'),corrected_frontend_infrastructure_diagnosis=diagnosis,
                                   actual_frontend_result=frontend_ref,actual_frontend_attempt=actual_attempt,
                                   normal_candidate_already_attempted=True,production_reexecution_allowed=False,
                                   interpretation='Original ledger and diagnostics retained unchanged. A failed source attempt stays pending for a changed source compiler; orchestration repair alone does not retry it.'))
    return events,qualified


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


def prepare(output,inventory):
    import compiler_graphviz_visibility_iteration_family_v1 as families
    import compiler_graphviz_visibility_iteration_program_v3 as program
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
    prior_attempts,iteration_qualified=iteration_bookkeeping(config)
    prior_ids={item['id']for item in prior_attempts}
    for item in new_qualified+iteration_qualified+list(rows(controls['qualified_manifest']['file'])):
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
        (output/'ordinary_queue_snapshot.json').write_bytes(raw(dict(directory=str(ORDINARY),states=ordinary_states,source_only_bookkeeping=True,queue_changed=False)))
        (output/'preserved_qualified.jsonl').write_bytes(b''.join(raw(accepted[i])for i in sorted(accepted)))
        (output/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(item)for item in prior_attempts))
        source_records=[];audited=[];population_count=0
        ordered=sorted(scope,key=lambda identifier:sha(raw([SEED,identifier])))
        with(output/'supported_population.jsonl').open('wb')as population:
            for identifier in ordered:
                row=dict(id=identifier,source_format='python',handler_applicable=False)
                try:
                    job,source=load(identifier);code=source_text(job,source)
                    row.update(original_Python_hash_verified=True,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
                    capture=json.loads(job[9])if job[9]else{}
                    dot=_read(capture['source_render_dot'])if capture.get('source_render_dot')else None
                    # This exact cheap negative screen is source syntax only;
                    # every possible explicit-invis input still receives the
                    # pinned frontend's complete static source/capture checks.
                    if dot is None:row['disposition']='pending_no_existing_Graphviz_capture'
                    elif not re.search(rb'\bstyle\s*=\s*(?:"[^"\n]*\binvis\b[^"\n]*"|invis\b)',dot):
                        row.update(disposition='outside_explicit_nonpainting_handler',source_DOT_sha256=sha(dot))
                    else:
                        support=compiler.static_support(job)
                        if not support['supported']:row.update(disposition='pending_outside_frozen_frontend_source_grammar',reason=support['reasons'])
                        else:
                            document,json_sha=parsed(dot)
                            try:profile=families.explicit_nonpainting_profile(document)
                            except ValueError as error:row.update(disposition='outside_exact_nonpainting_source_profile',reason=str(error))
                            else:
                                row.update(handler_applicable=True,source_profile=profile,syntax_only_DOT_json_sha256=json_sha,
                                           source_capture_snapshot_sha256=sha(raw(support['source_capture_snapshot'])))
                                baseline=json.loads(job[9])if job[9]else{}
                                item=dict(id=identifier,source=source,compiler_unit=compiler.UNIT,source_capture_snapshot=support['source_capture_snapshot'],
                                          source_record_sha256=sha((job[9]or'').encode()),baseline_code_sha256=baseline.get('code_sha256'),baseline_image_sha256=baseline.get('image_sha256'))
                                keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']))
                                known=False
                                try:
                                    keys.add(families.python_template(code))
                                    cluster,family_keys,evidence=families.family(code,document);keys.update(family_keys);known=True
                                    row.update(family=cluster,source_family_evidence=evidence,cluster_keys=sorted(keys))
                                except Exception as error:row.update(family_unknown_reason=str(error)[:700])
                                if identifier in accepted:row['disposition']='already_qualified_preserved'
                                elif ordinary_states.get(identifier)in ('queued','running'):row['disposition']='deferred_current_ordinary_Graphviz_v2_queue'
                                else:
                                    population.write(raw(item));population_count+=1
                                    row['disposition']='prior_same_SOURCE_frontend_attempt_pending_next_repair'if identifier in prior_ids else'source_component_inventory_pending'
                                source_records.append(dict(audit=row,request=item,keys=keys,known=known,pending=row['disposition']=='source_component_inventory_pending'))
                    if identifier in accepted:
                        row['prior_source_disposition']=row['disposition'];row['disposition']='already_qualified_preserved'
                except Exception as error:row.update(disposition='pending_source_inventory_diagnosis',reason=str(error)[:1000])
                if row['handler_applicable']:counters['exact_handler_applicable_all_scope']+=1
                audited.append(row)
        eligible,component_counts=independent_components(source_records,development,excluded_codes,excluded_images,excluded_keys)
        for row in audited:counters[row['disposition']]+=1
        (output/'source_audit.jsonl').write_bytes(b''.join(raw(row)for row in audited))
        selected=eligible[:100]
        for seq,item in enumerate(selected,1):item['seq']=seq
        (output/'selected.jsonl').write_bytes(b''.join(raw(x)for x in selected))
        methods=[Path(__file__),Path(families.__file__),Path(inventory_method.__file__),Path(provenance.__file__),W/'scripts/compiler_validation_dot_ir_v2.py',W/'scripts/compiler_graphviz_visibility_iteration_case_v2.py']+development_inputs
        files=('source_audit.jsonl','supported_population.jsonl','selected.jsonl','preserved_qualified.jsonl','ordinary_queue_snapshot.json','prior_candidate_attempts.jsonl')
        result=dict(schema='compiler_graphviz_visibility_source_pool_v2',seed=SEED,scope=SCOPE,full_scope_manifest=scope_info,
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
                    ordinary_queue_never_modified=True,ordinary_queued_running_excluded=sum(1 for i in scope if ordinary_states.get(i)in ('queued','running')),
                    eligible_observed_families=len(eligible),selected=len(selected),minimum100_met=len(selected)>=100,
                    all_remaining_observed_families_selected=len(selected)==len(eligible),
                    minimum5_incremental_qualified_gate_unchanged=True,
                    limitations=['Hard Python AST template and typed actual DOT topology/style/ports/cluster invariants plus explicit source provenance exclude duplicates; invariant collisions conservatively merge.',
                                 'Unknown source families remain in supported_population and are excluded from independence claims and the unseen cohort.',
                                 'All applicable pending source rows remain in population, including dev/reserved families; existing qualifications and the ordinary queued/running Graphviz-v2 rows are preserved and excluded.',
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
