"""Retain every original target; admit additive flat sources before fresh selection."""
from pathlib import Path
import hashlib,json,os,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
PARENT=R/'release/compiler_iterations/source_pools/svg_complex_resolved_geometry_cached_unseen_20261102_v11'
RUN='svg_complex_source_whitespace_cached_unseen_20261103_v12'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(p):return[json.loads(x)for x in p.read_bytes().splitlines()if x]
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def prepare(additive):
    import svg_whitespace_source_contract_v1 as contract
    import svg_whitespace_cohort_refresh_v1 as refresh
    import compiler_source_core_attempts_v3 as history
    import compiler_validation_identity_alias_v1 as aliases
    import prove_svg_whitespace_source_admission_equivalence_v1 as equivalence
    # This proves the source predicates, not conversion/QA compatibility.
    import ast
    old=S/'compiler_svg_scene_frontend_v22.py';new=S/'compiler_svg_scene_frontend_v24.py';a,b=equivalence.functions(old),equivalence.functions(new)
    assert sorted(k for k in a if a[k]!=b.get(k))==['_apply_offsets','_preserve_source_whitespace','convert']
    assert equivalence.functions(S/'compiler_svg_general_guard_v18.py')==equivalence.functions(S/'compiler_svg_general_guard_v20.py')
    cfg=contract.configuration();inputs={};admitted={};summaries=[];counts={}
    prior_audits=[R/'conversion/source_resolved_geometry_admission_v1/66a1afa4a59e41f2af612d04b6d2636d',R/'conversion/source_resolved_geometry_admission_fork_v3/49b1e0f29af24202a8b6af5043c1017c']
    for audit in prior_audits+[Path(additive)]:
        summary=json.loads((audit/'summary.json').read_bytes());assert summary['finished']and summary['completed']==summary['total']
        configuration=json.loads((audit/'configuration.json').read_bytes())
        if audit==Path(additive):assert configuration==cfg
        else:
            import compiler_svg_general_guard_v18 as previous
            assert configuration==previous.configuration()
        plan=json.loads((audit/'plan.json').read_bytes());assert plan['input_sha256']==sha((audit/'input.jsonl').read_bytes())
        for ref in summary['files'].values():assert sha((R/ref['file']).read_bytes())==ref['sha256']
        for r in rows(audit/'input.jsonl'):assert r['id']not in inputs;inputs[r['id']]={**r,'compiler_unit':contract.UNIT}
        for r in rows(audit/'admitted.jsonl'):
            assert r['normal_conversion_calls']==r['candidate_emissions']==r['QA_calls']==0
            source=inputs[r['id']]['source'];assert(source['code_sha256'],source['image_sha256'])==(r['source_code_sha256'],r['source_image_sha256']);admitted[r['id']]=r
        summaries.append(asset(audit/'summary.json'));counts[str(audit)]=summary['counts']
    assert len(inputs)==3047
    prior=rows(PARENT/'all_complex_raw_supported_population.jsonl');assert len(prior)==2730 and {r['id']for r in prior}<=inputs.keys()
    info=json.loads((PARENT/'summary.json').read_bytes());assert info['scope']==26754 and info['full_scope_manifest']['unique_scope']==131904
    for name,ref in info['files'].items():assert sha((PARENT/name).read_bytes())==ref['sha256']
    for name,digest in info['method_pins'].items():assert sha(Path(name).read_bytes())==digest
    out=R/'release/compiler_iterations/source_pools'/RUN;out.mkdir(parents=True,exist_ok=False)
    excluded={'summary.json','supported_population.jsonl','selected.jsonl','target_selection_snapshot.json','complex_source_policy.json','prior_candidate_attempts.jsonl','all_complex_raw_supported_population.jsonl','current_knowledge_snapshot.json'}
    for name in info['files']:
        if name not in excluded and not name.startswith('source_admission_'):os.link(PARENT/name,out/name)
    population=[inputs[k]for k in sorted(admitted)]
    (out/'all_complex_raw_supported_population.jsonl').write_bytes(b''.join(raw(inputs[k])for k in sorted(inputs)))
    (out/'supported_population.jsonl').write_bytes(b''.join(raw(r)for r in population))
    snapshot=refresh.knowledge_snapshot(out,cfg)
    with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as db:keys=aliases.normalize_keys(set(db.execute('select kind,value from reservation_keys')))
    seal=json.loads((out/'sealed_source_components.json').read_bytes());choice=refresh.choose(seal,population,snapshot,keys,seed=info['seed'],limit=100)
    (out/'selected.jsonl').write_bytes(b''.join(raw(r)for r in choice['selected']));(out/'target_selection_snapshot.json').write_bytes(raw(choice));(out/'current_knowledge_snapshot.json').write_bytes(raw(snapshot))
    events=history.collect(cfg,root=R,catalog=contract.CATALOG);history.validate(events,cfg,root=R);(out/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(r)for r in events))
    screen=R/'clean/priority_svg_flat_source_screen_v1/da55c2ca71a24d7ab63d36c571ca963c'
    policy={**info['source_value_policy'],'additive_flat_rule':asset(screen/'policy.json'),'original_targets_retained':2730,'additional_flat_targets':317,'source_admission_summaries':summaries,'source_admission_counts':counts,'source_admitted':len(admitted),'unchanged_source_admission_AST_producer':asset(Path(equivalence.__file__)),'old_source_predicates_AST_equal':True,'candidate_or_QA_outcomes_used_for_source_eligibility':False,'quality_thresholds_changed':False,'strict_scientific_value_review_still_required':True}
    (out/'complex_source_policy.json').write_bytes(raw(policy));methods={**info['method_pins'],str(Path(__file__).resolve()):sha(Path(__file__).read_bytes())}
    for name in ['svg_whitespace_source_contract_v1.py','svg_whitespace_cohort_refresh_v1.py','svg_whitespace_iteration_pool_v1.py','source_flat_whitespace_admission_v1.py','screen_flat_research_svg_sources_v1.py','prove_svg_whitespace_source_admission_equivalence_v1.py']:
        p=S/name;methods[str(p)]=sha(p.read_bytes())
    files={p.name:dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)for p in out.iterdir()if p.is_file()}
    final={**info,'schema':'complex_SVG_source_whitespace_source_semantic_pool_v1','frontend_module':'svg_whitespace_source_contract_v1','frozen_implementation':cfg,'method_pins':methods,'source_value_policy':policy,'files':files,'counters':{**info['counters'],'supported_remaining_population':len(population),'all_complex_raw_supported':len(inputs)},'prior_same_SOURCE_frontend_distinct_candidate_attempts':len(events),'eligible_observed_families':choice['eligible_observed_families'],'selected':len(choice['selected']),'minimum100_met':len(choice['selected'])>=100,'all_remaining_observed_families_selected':choice['all_remaining_observed_families_selected']}
    (out/'summary.json').write_bytes(raw(final))
    for p in out.iterdir():p.chmod(0o444)
    return dict(pool=str(out),run_id=RUN,selected=len(choice['selected']),source_population=len(population),all_targets=len(inputs),goal_complete=False)
if __name__=='__main__':print(json.dumps(prepare(sys.argv[1])))
