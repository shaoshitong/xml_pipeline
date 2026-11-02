"""Reuse the sealed whole-source audit and freeze current eligible complex inputs."""
from pathlib import Path
import hashlib,inspect,json,os,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
PARENT=R/'release/compiler_iterations/source_pools/svg_complex_background_rotation_cached_unseen_20261102_v9'
RUN='svg_complex_compound_linear_cached_unseen_20261102_v10'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(p):return[json.loads(l)for l in p.read_bytes().splitlines()if l]
def prepare(audit):
    import svg_analytic_source_contract_v7 as contract
    import svg_analytic_cohort_refresh_v7 as refresh
    import compiler_source_core_attempts_v3 as history
    import compiler_validation_identity_alias_v1 as aliases
    import sqlite3
    audit=Path(audit).resolve();assert audit.is_relative_to(R/'conversion/source_compound_linear_admission_v2')
    summary=json.loads((audit/'summary.json').read_bytes());plan=json.loads((audit/'plan.json').read_bytes());cfg=contract.configuration()
    assert summary['finished']and summary['total']==summary['completed']==2365 and plan['configuration']==cfg
    assert sha((R/plan['producer']['file']).read_bytes())==plan['producer']['sha256']
    assert sha((audit/'input.jsonl').read_bytes())==sha((PARENT/'all_complex_raw_supported_population.jsonl').read_bytes())==plan['input_sha256']
    for ref in summary['files'].values():assert sha((R/ref['file']).read_bytes())==ref['sha256']
    admitted={r['id']:r for r in rows(audit/'admitted.jsonl')};assert len(admitted)==841
    for r in admitted.values():assert r['current_source_semantics_recomputed']and r['normal_conversion_calls']==r['candidate_emissions']==r['QA_calls']==0
    info=json.loads((PARENT/'summary.json').read_bytes());assert info['scope']==26754 and info['full_scope_manifest']['unique_scope']==131904
    for name,ref in info['files'].items():assert sha((PARENT/name).read_bytes())==ref['sha256']
    for name,digest in info['method_pins'].items():assert sha(Path(name).read_bytes())==digest
    population=[]
    for row in rows(PARENT/'all_complex_raw_supported_population.jsonl'):
        decision=admitted.get(row['id'])
        if decision:
            assert(row['source']['code_sha256'],row['source']['image_sha256'])==(decision['source_code_sha256'],decision['source_image_sha256']);population.append({**row,'compiler_unit':contract.UNIT})
    assert len(population)==841
    snapshot=refresh.knowledge_snapshot(PARENT,cfg)
    with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as db:keys=aliases.normalize_keys(set(db.execute('select kind,value from reservation_keys')))
    seal=json.loads((PARENT/'sealed_source_components.json').read_bytes());choice=refresh.choose(seal,population,snapshot,keys,seed=info['seed'],limit=100)
    assert choice['selected']and choice['all_remaining_observed_families_selected']
    out=R/'release/compiler_iterations/source_pools'/RUN;out.mkdir(parents=True,exist_ok=False)
    excluded={'summary.json','supported_population.jsonl','selected.jsonl','target_selection_snapshot.json','complex_source_policy.json','prior_candidate_attempts.jsonl'}
    for name in info['files']:
        if name not in excluded and not name.startswith('source_admission_'):os.link(PARENT/name,out/name)
    (out/'supported_population.jsonl').write_bytes(b''.join(raw(r)for r in population));(out/'selected.jsonl').write_bytes(b''.join(raw(r)for r in choice['selected']));(out/'target_selection_snapshot.json').write_bytes(raw(choice))
    (out/'preserved_parent_core18_attempts.jsonl').write_bytes((PARENT/'prior_candidate_attempts.jsonl').read_bytes())
    events=history.collect(cfg,root=R,catalog=contract.CATALOG);history.validate(events,cfg,root=R);(out/'prior_candidate_attempts.jsonl').write_bytes(b''.join(raw(r)for r in events))
    for name in ['admitted.jsonl','unsupported.jsonl','error.jsonl','plan.json','configuration.json','summary.json']:(out/('source_admission_'+name)).write_bytes((audit/name).read_bytes())
    policy={**info['source_value_policy'],'source_semantic_admission_preregistered_before_unseen_selection':True,'source_admission_plan_sha256':sha((audit/'plan.json').read_bytes()),'source_semantically_admitted':841,'prior_source_admitted_preserved':785,'new_source_admitted':56,'source_admission_regressions':0,'current_normal_SOURCE_key':contract.CORE_KEY,'candidate_or_QA_outcomes_used_for_source_eligibility':False,'quality_thresholds_changed':False,'not_a_format_completion':True}
    (out/'complex_source_policy.json').write_bytes(raw(policy));methods={**info['method_pins'],str(Path(__file__).resolve()):sha(Path(__file__).read_bytes())}
    for name in ['svg_analytic_source_contract_v7.py','svg_analytic_cohort_refresh_v7.py','svg_analytic_iteration_pool_v8.py','source_compound_linear_admission_v2.py']:
        p=S/name;methods[str(p)]=sha(p.read_bytes())
    files={p.name:dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)for p in out.iterdir()if p.is_file()}
    final={**info,'schema':'complex_SVG_compound_linear_source_semantic_pool_v1','frontend_module':'svg_analytic_source_contract_v7','frozen_implementation':cfg,'method_pins':methods,'source_value_policy':policy,'files':files,'counters':{**info['counters'],'supported_remaining_population':841},'prior_same_SOURCE_frontend_distinct_candidate_attempts':len(events),'eligible_observed_families':choice['eligible_observed_families'],'selected':len(choice['selected']),'minimum100_met':False,'all_remaining_observed_families_selected':True}
    (out/'summary.json').write_bytes(raw(final))
    for p in out.iterdir():p.chmod(0o444)
    return dict(pool=str(out),run_id=RUN,selected=len(choice['selected']),source_population=841,goal_complete=False)
if __name__=='__main__':print(json.dumps(prepare(Path(sys.argv[1]))))
