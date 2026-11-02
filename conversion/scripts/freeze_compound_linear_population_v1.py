"""Freeze hash-bound source eligibility and audit freshness without reserving it."""
from pathlib import Path
import hashlib,json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return[json.loads(l)for l in p.read_bytes().splitlines()if l]
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def raw(x):return(json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def main():
    audit=Path(sys.argv[1]).resolve();assert audit.is_relative_to(R/'conversion/source_compound_linear_admission_v2')
    summary=json.loads((audit/'summary.json').read_bytes());assert summary['finished']and summary['total']==summary['completed']==2365
    for ref in summary['files'].values():assert sha((R/ref['file']).read_bytes())==ref['sha256']
    admitted={r['id']:r for r in rows(audit/'admitted.jsonl')}
    old={r['id']for r in rows(R/'conversion/source_cached_admission_v1/2d47ad593b4545038329916ff229a8ea/admitted.jsonl')}
    assert len(old)==785 and old<=set(admitted)and len(admitted)==841
    import compiler_svg_general_guard_v17 as core
    import compiler_svg_general_guard_v14 as prior_core
    import compiler_source_core_attempts_v3 as history
    import svg_analytic_cohort_refresh_v6 as refresh
    import compiler_validation_identity_alias_v1 as aliases
    pool=R/'release/compiler_iterations/source_pools/svg_complex_background_rotation_cached_unseen_20261102_v9'
    config=core.configuration();assert config==json.loads((audit/'configuration.json').read_bytes())
    original=rows(pool/'all_complex_raw_supported_population.jsonl');population=[]
    for row in original:
        decision=admitted.get(row['id'])
        if decision:
            assert(row['source']['code_sha256'],row['source']['image_sha256'])==(decision['source_code_sha256'],decision['source_image_sha256'])
            population.append({**row,'compiler_unit':core.UNIT})
    assert len(population)==841
    snapshot=refresh.knowledge_snapshot(pool,prior_core.configuration())
    events=history.collect(config,root=R,catalog='release/compiler_iterations/source_core_attempts/manual_catalog_svg_compound_linear_20261102_v12.json');history.validate(events,config,root=R)
    assert len(events)==1
    # Global seen/identity exclusions already include every immutable manual
    # catalogue. Replace only the per-core reporting field, not the exclusions.
    assert events[0]['id']in snapshot['known_source_ids'];snapshot['same_core_normal_events']=events
    with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as db:keys=aliases.normalize_keys(set(db.execute('select kind,value from reservation_keys')))
    info=json.loads((pool/'summary.json').read_bytes());seal=json.loads((pool/'sealed_source_components.json').read_bytes());choice=refresh.choose(seal,population,snapshot,keys,seed=info['seed'],limit=100)
    root=R/'conversion/compound_linear_population_freeze_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    (root/'population.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in population));(root/'selection.json').write_bytes(raw(choice));(root/'knowledge_snapshot.json').write_bytes(raw(snapshot));(root/'configuration.json').write_bytes(raw(config))
    out=dict(root=str(root),source_admission_summary=asset(audit/'summary.json'),population=asset(root/'population.jsonl'),selection=asset(root/'selection.json'),knowledge_snapshot=asset(root/'knowledge_snapshot.json'),source_configuration=asset(root/'configuration.json'),sealed_components=asset(pool/'sealed_source_components.json'),source_population=841,prior_source_population=785,newly_source_admitted=56,source_admission_regressions=0,eligible_unseen_families=choice['eligible_observed_families'],selected=len(choice['selected']),reservations_written=False,normal_calls=0,QA_calls=0,model_calls=0,goal_complete=False)
    (root/'summary.json').write_bytes(raw(out))
    for p in root.iterdir():p.chmod(0o444)
    print(json.dumps(out))
if __name__=='__main__':main()
