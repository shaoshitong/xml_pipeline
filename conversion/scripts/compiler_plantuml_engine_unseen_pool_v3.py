"""Full source inventory with transitive ID/image/code/family/provenance exclusion.

All originals participate as bridges, including unsupported, accepted and live
sources. Unknown families stay in bulk population without independence claims.
No source layout, conversion, reference-pixel metric or model call occurs.
"""
import argparse
import collections
import importlib
import json
from pathlib import Path
import sqlite3

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
SCOPE=7463
SEED='hkust-official-plantuml-engine-full-canonical-contract-20261101-unseen-actual-claim-v3'
FRONTEND='compiler_plantuml_engine_candidate_v1'
DEVELOPMENT=(R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl',
             R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl')

def raw(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()
def rows(path):
    with Path(path).open()as stream:
        for line in stream:
            if line.strip():yield json.loads(line)


def family(code):
    from plantuml_engine_source_model_index_v1 import family as official_family
    return official_family(code)


def identity_overlap(identifier,source,development,codes,images):
    return identifier in development or source['code_sha256']in codes or source['image_sha256']in images


def independent_components(records,development,codes,images,excluded):
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
    eligible=[];counts=collections.Counter()
    for members in groups.values():
        keys=set().union(*(x['keys']for x in members))
        candidates=[x for x in members if x['pending']]
        contaminated=bool(keys&excluded)or any(identity_overlap(x['request']['id'],x['request']['source'],development,codes,images)for x in members)
        unknown=any(not x['known']for x in members)
        cluster='plantuml_engine_source_component_v1:'+sha(raw(sorted(keys)))
        counts['observed_source_components']+=1
        if contaminated:counts['development_or_reserved_connected_components']+=1
        if unknown:counts['unknown_family_connected_components']+=1
        for offset,item in enumerate(sorted(candidates,key=lambda x:sha(raw([SEED,x['request']['id']])))):
            row=item['audit'];row.update(source_component=cluster,component_members=len(members))
            if contaminated:row['disposition']='development_or_reserved_transitive_identity_family_provenance_overlap'
            elif unknown:row['disposition']='population_family_unknown_component_not_independent'
            elif offset:row['disposition']='duplicate_validation_source_component'
            else:
                row['disposition']='eligible_unseen_observed_source_component'
                eligible.append({**item['request'],'audit_cluster':cluster,'cluster':cluster,'cluster_keys':sorted(keys|{cluster})})
    eligible.sort(key=lambda item:sha(raw([SEED,item['id']])))
    return eligible,dict(counts)


def source_text(job,source):
    manifest=json.loads(job[11])if job[11]else{}
    previous=json.loads(job[9])if job[9]else{}
    for locator in (manifest.get('source_code'),previous.get('original_source_code')):
        if not locator:continue
        path=(R/locator).resolve()
        if not path.is_relative_to(R.resolve()):continue
        try:blob=path.read_bytes()
        except OSError:continue
        if sha(blob)==source['code_sha256']:return blob.decode('utf-8-sig')
    raise ValueError('authoritative_original_PlantUML_source_unreadable_or_changed')


def qualified_rows():
    from compiler_types_program_v1 import checked
    root=R/'release/compiler_iterations';pointer=json.loads((root/'current.json').read_bytes())
    _,blob=checked({'file':pointer['inventory'],'sha256':pointer['inventory_sha256']});summary=json.loads(blob)
    path,_=checked({'file':pointer['qualified_manifest'],'sha256':summary['files']['qualified.jsonl']['sha256']})
    result={item['id']:item for item in rows(path)}
    for floor in (root/'controls',root/'runs'):
        for path in sorted(floor.glob('*/qualified.jsonl')):
            for item in rows(path):result[item['id']]=item
    return result


def prior_candidate_attempts():
    """Same frozen source frontend is never reexecuted by orchestration changes."""
    result=[]
    for ledger in sorted((R/'release/compiler_iterations/runs').glob('*/status.sqlite')):
        freeze_path=ledger.parent/'freeze.json'
        if not freeze_path.exists():continue
        freeze=json.loads(freeze_path.read_bytes())
        pin=str(W/'scripts'/('compiler_plantuml_engine_candidate_v1.py'))
        if freeze.get('pins',{}).get(pin)!=sha(Path(pin).read_bytes()):continue
        with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True,timeout=30)as database:
            for identifier,body,result_body in database.execute('select id,source,result from samples where attempts=1'):
                request=json.loads(body)
                result_payload=json.loads(result_body)if result_body else{}
                evidence=result_payload.get('evidence_directory')
                frontend_exists=bool(evidence and (R/evidence/'frontend_result.json').is_file())
                if not was_normal_candidate_attempt(request,result_payload,frontend_exists):continue
                result.append({'id':identifier,'ledger':str(ledger),'request_sha256':sha(body.encode()),'source':request['source']})
    from compiler_plantuml_engine_once_v1 import claims
    compiler=importlib.import_module(FRONTEND);pin=str(Path(compiler.__file__).resolve());current_sha=sha(Path(pin).read_bytes())
    for claim in claims(compiler):result.append({'id':claim['id'],'claim':claim,'source_frontend_claimed_before_call':True})
    # An already running/finished exact case preflight is a normal C attempt.
    for directory in sorted((W/'compiler_iterations').glob('plantuml_engine_direct_case_interface_*')):
        request=directory/'request.json'
        if not request.is_file():continue
        q=json.loads(request.read_bytes())
        if q.get('pins',{}).get(pin)!=current_sha:continue
        w=Path(q['work']);r=json.loads((w/'result.json').read_bytes())if(w/'result.json').exists()else{}
        if was_normal_candidate_attempt(q,r,(w/'frontend_result.json').is_file()):result.append({'id':q['id'],'request':str(request),'source':q['source'],'normal_exact_case_preflight':True})
    # Real API entries from this unpublished development version also count;
    # pure source preparation/reverification/negative controls never do.
    for protocol in sorted((W/compiler.VERSION/'finite_development').glob('*/protocol.json')):
        spec=json.loads(protocol.read_bytes())
        if spec.get('configuration',{}).get('pins',{}).get(pin)!=current_sha:continue
        for directory in protocol.parent.iterdir():
            if directory.is_dir()and len(directory.name)==64 and all(c in '0123456789abcdef'for c in directory.name):
                result.append({'id':directory.name,'development_protocol':str(protocol),'actual_API_work_entered_or_conservatively_ambiguous':True})
    return result


def was_normal_candidate_attempt(request,result,frontend_exists):
    if request.get('evaluation_phase')in ('baseline','control_positive')or request.get('existing_development_candidate')or request.get('negative_control'):
        return False
    if frontend_exists:return True
    if (result.get('error_type')=='ValueError'and result.get('reason')=='retryable_iteration_case_failure'and
            result.get('detail')in ('deferred_birth_verified_active_conversion_overlap','deferred_same_frozen_source_frontend_already_claimed','deferred_canonical_live_or_uncertain_worker_claim')):
        # The two explicit guards run before the normal frontend call.
        return False
    # An interrupted spawn without definitive pre-call evidence is ambiguous;
    # conservatively never execute that original twice under this source core.
    return True


def prepare(output,inventory):
    import compiler_plantuml_engine_iteration_program_v3 as program
    import compiler_mermaid_alpha_iteration_overlap_v1 as overlap_method
    import compiler_iteration_inventory_v1 as inventory_method
    import compiler_validation_cluster_audit_v1 as provenance
    compiler=importlib.import_module(FRONTEND);config=compiler.configuration();unit=compiler.UNITS['plantuml']
    output=Path(output).resolve();inventory=Path(inventory).resolve(strict=True)
    if not output.is_relative_to((R/'release/compiler_iterations/source_pools').resolve()):raise ValueError('PlantUML_pool_outside_owner')
    controls=program.control_bundle(compiler);program.check_controls(controls)
    scope_all,scope_info=inventory_method.read_scope(R);scope={i:x for i,x in scope_all.items()if x['format']=='plantuml'}
    if len(scope)!=SCOPE:raise ValueError('original_PlantUML_scope_not_7463')
    info=json.loads((inventory/'summary.json').read_bytes());qualified_path=inventory/'qualified.jsonl'
    if sha(qualified_path.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('qualified_inventory_changed')
    accepted={x['id']:x for x in rows(qualified_path)if x['id']in scope}
    for identifier,item in qualified_rows().items():
        if identifier in scope:accepted[identifier]=item
    hashes={}
    for identifier,item in accepted.items():inventory_method.check_manifest(R,identifier,scope[identifier],item,hashes)
    active=overlap_method.snapshot();active_ids=set(active['active'])
    prior=prior_candidate_attempts();prior_ids={item['id']for item in prior}
    development_inputs=list(DEVELOPMENT)+sorted((R/'release/compiler_iterations/development_seen_v1').glob('*.jsonl'))
    dev_rows=[item for path in development_inputs for item in rows(path)]
    development={item['id']for item in dev_rows}|{item['id']for item in controls['positive_cases']}|prior_ids
    with sqlite3.connect('file:'+str(R/'release/compiler_v1/validation_registry.sqlite')+'?mode=ro',uri=True,timeout=30)as registry:
        registry.execute('begin');registry_keys=set(registry.execute('select kind,value from reservation_keys'))
    development.update(value for kind,value in registry_keys if kind=='id')
    codes={v for k,v in registry_keys if k=='code'};images={v for k,v in registry_keys if k=='image'}
    excluded={v for k,v in registry_keys if k in ('audit_cluster','hard_cluster')}
    excluded.update(p['source_family']for p in controls['positive_cases']if p.get('source_family'))
    for item in dev_rows+controls['positive_cases']:
        c=item.get('source_code_sha256')or item.get('code_sha256');i=item.get('source_image_sha256')or item.get('image_sha256')
        if c:codes.add(c)
        if i:images.add(i)
        excluded.update(item.get('cluster_keys')or [])
    database=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
    counters=collections.Counter();cache={}
    def load(identifier):
        job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
        if not job:raise ValueError('canonical_original_job_missing')
        source=json.loads(job[4])
        if (source['pair_sha256'],source['category'],source['format'],source['source'])!=(identifier,job[1],job[2],job[3]):raise ValueError('canonical_original_source_identity_changed')
        if identifier in scope and any(scope[identifier][k]!=source[k]for k in ('category','format','source','code_sha256','image_sha256')):raise ValueError('scope_original_source_digest_changed')
        return job,source
    def parsed(code):
        digest=sha(code.encode())
        if digest not in cache:cache[digest]=family(code)
        return cache[digest]
    try:
        for identifier in sorted(development):
            try:
                job,source=load(identifier);codes.add(source['code_sha256']);images.add(source['image_sha256'])
                excluded.update(provenance.provenance(source,source['source']));counters['all_format_development_or_reserved_sources_loaded']+=1
                if source['format']=='plantuml':
                    key,_=parsed(source_text(job,source));excluded.add(key);counters['same_format_exclusion_family_parsed']+=1
            except Exception as error:counters['exclusion_source_unknown:'+type(error).__name__]+=1
        output.mkdir(parents=True,exist_ok=False)
        (output/'live_overlap_snapshot.json').write_bytes(raw(active))
        (output/'preserved_qualified.jsonl').write_bytes(b''.join(raw(accepted[i])for i in sorted(accepted)))
        (output/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(item)for item in prior))
        audited=[];records=[];population_count=0
        with(output/'supported_population.jsonl').open('wb')as population:
            for identifier in sorted(scope,key=lambda i:sha(raw([SEED,i]))):
                source=scope[identifier];keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(source,source['source']))
                row=dict(id=identifier,source_format='plantuml',handler_applicable=False,disposition='pending_source_inventory_diagnosis')
                item=dict(id=identifier,source=source,compiler_unit=unit);known=False
                try:
                    job,source=load(identifier);item['source']=source;code=source_text(job,source)
                    try:
                        key,evidence=parsed(code);keys.add(key);known=True;row.update(family=key,source_family_evidence=evidence)
                    except Exception as error:row['source_family_unknown_reason']=str(error)[:700]
                    from compiler_plantuml_engine_canonical_claim_v1 import diagnose
                    claim=diagnose(compiler.source.base._job(job));row['canonical_claim']=claim
                    support=compiler.static_support(compiler.source.base._job(job))
                    if not support['supported']:row.update(disposition='pending_outside_frozen_frontend_source_grammar',reason=support['reasons'])
                    else:
                        row['handler_applicable']=True;previous=json.loads(job[9])if job[9]else{}
                        item.update(source_record_sha256=sha((job[9]or'').encode()),baseline_code_sha256=previous.get('code_sha256'),baseline_image_sha256=previous.get('image_sha256'))
                        if identifier in accepted:row['disposition']='already_qualified_preserved'
                        elif identifier in active_ids:row['disposition']='deferred_birth_verified_active_conversion_overlap'
                        elif not claim['conversion_allowed']:row['disposition']='deferred_canonical_live_or_uncertain_worker_claim'
                        elif identifier in prior_ids:row['disposition']='same_source_frontend_already_attempted_pending_next_repair'
                        else:population.write(raw(item));population_count+=1;row['disposition']='source_component_inventory_pending'
                except Exception as error:row.update(reason=str(error)[:1000])
                row.update(cluster_keys=sorted(keys),source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
                if row['handler_applicable']:counters['exact_handler_applicable_all_scope']+=1
                # Unsupported/unreadable/accepted/live sources remain real
                # transitive bridges; unreadable families cannot prove novelty.
                records.append(dict(audit=row,request=item,keys=keys,known=known,pending=row['disposition']=='source_component_inventory_pending'))
                audited.append(row)
        foreign_bridge_count=0;foreign_seen=set()
        for original in rows(R/'release/manifest.jsonl'):
            ident=original.get('pair_sha256')
            if ident not in scope_all or ident in scope or ident in foreign_seen:continue
            foreign_seen.add(ident)
            source=scope_all[ident];keys={'exact_original_code:'+source['code_sha256'],'exact_original_image:'+source['image_sha256']}|set(provenance.provenance(original,source['source']))
            records.append(dict(audit={'id':ident,'source_format':source['format'],'cross_format_identity_bridge_only':True},request={'id':ident,'source':source},keys=keys,known=True,pending=False));foreign_bridge_count+=1
        counters['cross_format_exact_identity_provenance_bridge_rows']=foreign_bridge_count
        eligible,components=independent_components(records,development,codes,images,excluded)
        for row in audited:counters[row['disposition']]+=1
        selected=eligible[:100]
        for seq,item in enumerate(selected,1):item['seq']=seq
        (output/'source_audit.jsonl').write_bytes(b''.join(raw(row)for row in audited))
        (output/'selected.jsonl').write_bytes(b''.join(raw(item)for item in selected))
        methods=[Path(__file__),Path(overlap_method.__file__),Path(inventory_method.__file__),Path(provenance.__file__),W/'scripts/plantuml_engine_source_model_index_v1.py',W/'scripts/compiler_plantuml_engine_once_v1.py',W/'scripts/compiler_validation_dot_ir_v2.py',W/'scripts/compiler_types_source_ir_v1.py',W/'scripts/compiler_native_languages_v1.py']+development_inputs
        from compiler_plantuml_engine_request_contract_v2 import validate_pool
        source_contract=validate_pool(output,expected_unit=unit)
        (output/'source_request_contract.json').write_bytes(raw(source_contract))
        methods.extend([W/'scripts/compiler_plantuml_engine_request_contract_v2.py',W/'scripts/compiler_plantuml_engine_canonical_claim_v1.py',W/'scripts/compiler_plantuml_engine_claim_controls_v1.py'])
        files=('source_request_contract.json','source_audit.jsonl','selected.jsonl','supported_population.jsonl','live_overlap_snapshot.json','preserved_qualified.jsonl','prior_candidate_attempts.jsonl')
        result=dict(schema='compiler_plantuml_engine_source_pool_v3',seed=SEED,scope=SCOPE,full_scope_manifest=scope_info,compiler_unit=unit,frontend_module=FRONTEND,frozen_implementation=config,
                    method_pins={str(p.resolve()):sha(p.read_bytes())for p in methods},controls_proof=controls['definition'],source_only=True,conversion_or_rendering=False,reference_pixel_metrics=False,model_calls=0,
                    development_inputs={str(p):sha(p.read_bytes())for p in development_inputs},registry_keys_snapshot_sha256=sha(raw(sorted(registry_keys))),registry_modified=False,full_source_request_contract=source_contract,
                    audited_scope_rows=len(audited),counters={**dict(counters),'supported_remaining_population':population_count},source_component_counts=components,
                    prior_same_frontend_normal_attempts=len(prior_ids),eligible_observed_families=len(eligible),selected=len(selected),minimum100_met=len(selected)>=100,all_remaining_observed_families_selected=len(selected)==len(eligible),
                    preserved_qualified=len(accepted),preserved_clean_assets_verified=len(hashes),birth_verified_active_scope_excluded=len(set(scope)&active_ids),
                    limitations=['Observed graph invariants conservatively merge colliding families; hidden generator independence and population yield are not proven.',
                                 'All 7463 PlantUML originals participate in complete source-family/identity/provenance closure; all other 124441 scope sources also participate as exact code/image/provenance bridges. Unknown PlantUML families cannot claim independence.',
                                 'Unknown families remain bulk candidates but are excluded from independence claims.',
                                 'Live pending rows excluded now remain pending for later changed-source versions; per-target live overlap is checked again before conversion.'],
                    files={name:dict(sha256=sha((output/name).read_bytes()),bytes=(output/name).stat().st_size)for name in files})
        if len(audited)!=SCOPE or compiler.configuration()!=config:raise ValueError('source_scope_or_frozen_frontend_changed_during_audit')
        with(output/'summary.json').open('xb')as stream:stream.write(raw(result))
        print(json.dumps({k:v for k,v in result.items()if k not in ('frozen_implementation','method_pins','development_inputs')},ensure_ascii=False),flush=True)
        return result
    finally:database.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--inventory',type=Path,required=True)
    args=parser.parse_args();prepare(args.output,args.inventory)
