"""Reuse a full source audit and retain all bridges, scheduling rich targets first.

Eligibility uses the frozen source-only priority filters, never conversion
scores or per-sample QA failure reasons. Existing renderer/quality gates and
normal-once history remain unchanged.
"""
from pathlib import Path
import collections,hashlib,json,shutil,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
PARENT=R/'release/compiler_iterations/source_pools/svg_actual_shadow_unseen100_20261102_v4'
RUN='svg_complex_actual_shadow_unseen100_20261102_v6'
OUT=R/'release/compiler_iterations/source_pools'/RUN
C=R/'clean/complexity_curation_20261102T054553Z_v1'

def sha(data):return hashlib.sha256(data).hexdigest()
def raw(value):return(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(path):return[json.loads(line)for line in path.read_bytes().splitlines()if line]


def prepare():
    import svg_analytic_source_contract_v3 as contract
    import svg_analytic_cohort_refresh_v3 as refresh
    import compiler_validation_identity_alias_v1 as aliases
    info=json.loads((PARENT/'summary.json').read_text())
    assert info['scope']==26754 and info['full_scope_manifest']['unique_scope']==131904
    assert info['frozen_implementation']==contract.configuration()
    for name,ref in info['files'].items():assert sha((PARENT/name).read_bytes())==ref['sha256'],name
    for name,digest in info['method_pins'].items():assert sha(Path(name).read_bytes())==digest,name
    target_inputs=[C/'priority_sources/index.jsonl',R/'clean/priority_svg_dense_source_screen_v2/new_complex_candidates.jsonl']
    targets={};input_hashes={}
    for position,path in enumerate(target_inputs):
        blob=path.read_bytes();input_hashes[str(path)]=sha(blob)
        for line in blob.splitlines():
            if not line:continue
            row=json.loads(line)
            selected=row.get('status')=='complex_candidate'if position==0 else row.get('source_layout_selected_v2')is True
            if selected and row['source_format']=='svg'and row.get('source_hash_matches_manifest')is True and row.get('read_status')=='read_code_only':
                targets[row['id']]=dict(source_code_sha256=row['source_code_sha256_observed'],source_image_sha256=row['image_sha256_manifest'],selection='frozen_complex_source'if position==0 else'frozen_rich_grouped_or_dense_source')
    full=rows(PARENT/'supported_population.jsonl');population=[]
    for row in full:
        target=targets.get(row['id'])
        if target:
            assert(row['source']['code_sha256'],row['source']['image_sha256'])==(target['source_code_sha256'],target['source_image_sha256'])
            population.append(row)
    assert population,'No applicable priority source targets; preserve the full source audit.'
    snapshot=refresh.knowledge_snapshot(PARENT,contract.configuration())
    with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as db:registry=set(db.execute('select kind,value from reservation_keys'))
    seal=json.loads((PARENT/'sealed_source_components.json').read_text());choice=refresh.choose(seal,population,snapshot,aliases.normalize_keys(registry),seed=info['seed'],limit=100)
    assert choice['selected'],'No independent complex source family remains; investigate source coverage.'
    OUT.mkdir(parents=True,exist_ok=False)
    for name in info['files']:
        if name not in ['supported_population.jsonl','selected.jsonl']:shutil.copyfile(PARENT/name,OUT/name)
    (OUT/'all_supported_source_population.jsonl').write_bytes((PARENT/'supported_population.jsonl').read_bytes())
    (OUT/'supported_population.jsonl').write_bytes(b''.join(raw(row)for row in population))
    (OUT/'selected.jsonl').write_bytes(b''.join(raw(row)for row in choice['selected']))
    policy=dict(schema='priority_complex_source_queue_policy_v1',user_scope='Complex scientific diagrams, posters and scientific visualizations; simple sources remain in the complete audit but are not dispatched in this priority round.',source_only_filters_predate_current_QA=True,inputs=input_hashes,frozen_complex_or_dense_targets=len(targets),all_applicable_source_population=len(full),applicable_complex_target_population=len(population),deferred_other_sources=len(full)-len(population),source_scope=26754,all_format_provenance_scope=131904,quality_thresholds_changed=False,source_family_seal_and_anti_leakage_unchanged=True,full_scope_parent_summary=dict(file=str((PARENT/'summary.json').relative_to(R)),sha256=sha((PARENT/'summary.json').read_bytes())),goal_complete=False)
    (OUT/'complex_source_policy.json').write_bytes(raw(policy));(OUT/'target_selection_snapshot.json').write_bytes(raw(choice))
    target_snapshot=OUT/'frozen_complex_source_targets.jsonl';target_snapshot.write_bytes(b''.join(raw(dict(id=identifier,**targets[identifier]))for identifier in sorted(targets)))
    methods={**info['method_pins'],str(target_snapshot):sha(target_snapshot.read_bytes()),str(Path(__file__).resolve()):sha(Path(__file__).read_bytes())}
    for path in [R/'clean/priority_svg_dense_source_screen_v2/policy.json',S/'priority_source_complexity_filter_v1.py',S/'priority_svg_dense_source_screen_v2.py']:methods[str(path)]=sha(path.read_bytes())
    files={name:dict(sha256=sha(path.read_bytes()),bytes=path.stat().st_size)for path in OUT.iterdir()if path.is_file()for name in[path.name]}
    summary={**info,'schema':'complex_priority_SVG_source_pool_v2','method_pins':methods,'source_value_policy':policy,'counters':{**info['counters'],'supported_remaining_population':len(population),'deferred_nonpriority_source_rows':len(full)-len(population)},'eligible_observed_families':choice['eligible_observed_families'],'selected':len(choice['selected']),'minimum100_met':len(choice['selected'])>=100,'all_remaining_observed_families_selected':choice['all_remaining_observed_families_selected'],'files':files,'selection_scope':'Full source/family audit retained; conversion dispatch prioritizes all applicable frozen complex/dense source candidates.'}
    (OUT/'summary.json').write_bytes(raw(summary))
    for path in OUT.iterdir():path.chmod(0o444)
    return dict(pool=str(OUT),run_id=RUN,policy=policy,selected=len(choice['selected']),eligible_observed_families=choice['eligible_observed_families'])

if __name__=='__main__':print(json.dumps(prepare()),flush=True)
