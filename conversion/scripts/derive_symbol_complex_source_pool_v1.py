"""Reuse sealed source-only complex selection; no source rescan or rendering."""
from pathlib import Path
import hashlib,inspect,json,shutil,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
PARENT=R/'release/compiler_iterations/source_pools/svg_complex_actual_shadow_unseen100_20261102_v6'
RUN='svg_complex_symbol_viewport_unseen100_20261102_v7';OUT=R/'release/compiler_iterations/source_pools'/RUN
sha=lambda b:hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,separators=(',',':'))+'\n').encode()
def rows(p):return[json.loads(b)for b in p.read_bytes().splitlines()if b]
def prepare():
 import compiler_svg_scene_frontend_v12 as old
 import compiler_svg_scene_frontend_v13 as new
 import svg_analytic_source_contract_v3 as old_contract
 import svg_analytic_source_contract_v4 as contract
 import svg_analytic_cohort_refresh_v4 as refresh
 import compiler_validation_identity_alias_v1 as aliases
 # Geometry observer changed; authoritative bytes, static admission and source
 # applicability did not. Verify literal implementations before metadata reuse.
 for name in ('static_support','source_admission','_inputs'):
  assert inspect.getsource(getattr(old,name))==inspect.getsource(getattr(new,name)),name
 info=json.loads((PARENT/'summary.json').read_bytes());assert info['scope']==26754 and info['full_scope_manifest']['unique_scope']==131904
 assert info['frozen_implementation']==old_contract.configuration()
 for name,ref in info['files'].items():assert sha((PARENT/name).read_bytes())==ref['sha256'],name
 for name,digest in info['method_pins'].items():assert sha(Path(name).read_bytes())==digest,name
 cfg=contract.configuration();population=rows(PARENT/'supported_population.jsonl')
 for row in population:row['compiler_unit']=contract.UNIT
 snapshot=refresh.knowledge_snapshot(PARENT,cfg)
 with sqlite3.connect((R/'release/compiler_v1/validation_registry.sqlite').as_uri()+'?mode=ro',uri=True)as db:registry=set(db.execute('select kind,value from reservation_keys'))
 seal=json.loads((PARENT/'sealed_source_components.json').read_bytes());choice=refresh.choose(seal,population,snapshot,aliases.normalize_keys(registry),seed=info['seed'],limit=100);assert choice['selected']
 OUT.mkdir(parents=True,exist_ok=False)
 excluded={'supported_population.jsonl','selected.jsonl','target_selection_snapshot.json','complex_source_policy.json','summary.json'}
 for name in info['files']:
  if name not in excluded:shutil.copyfile(PARENT/name,OUT/name)
 (OUT/'supported_population.jsonl').write_bytes(b''.join(raw(row)for row in population));(OUT/'selected.jsonl').write_bytes(b''.join(raw(row)for row in choice['selected']));(OUT/'target_selection_snapshot.json').write_bytes(raw(choice))
 policy={**info['source_value_policy'],'metadata_only_successor':True,'no_repeated_source_audit_or_raster':True,'unchanged_static_admission_literal_source_checked':True,'parent_complex_pool_summary':dict(file=str((PARENT/'summary.json').relative_to(R)),sha256=sha((PARENT/'summary.json').read_bytes()))};(OUT/'complex_source_policy.json').write_bytes(raw(policy))
 methods={**info['method_pins'],str(Path(__file__).resolve()):sha(Path(__file__).read_bytes())}
 for name in ['svg_analytic_source_contract_v4.py','svg_analytic_cohort_refresh_v4.py','svg_analytic_iteration_pool_v5.py']:
  path=S/name;methods[str(path)]=sha(path.read_bytes())
 files={p.name:dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)for p in OUT.iterdir()if p.is_file()}
 summary={**info,'schema':'complex_priority_SVG_symbol_viewport_source_pool_v1','frontend_module':'svg_analytic_source_contract_v4','frozen_implementation':cfg,'method_pins':methods,'source_value_policy':policy,'files':files,'eligible_observed_families':choice['eligible_observed_families'],'selected':len(choice['selected']),'minimum100_met':len(choice['selected'])>=100,'all_remaining_observed_families_selected':choice['all_remaining_observed_families_selected']}
 (OUT/'summary.json').write_bytes(raw(summary))
 for p in OUT.iterdir():p.chmod(0o444)
 return dict(pool=str(OUT),run_id=RUN,policy=policy,selected=len(choice['selected']),eligible_observed_families=choice['eligible_observed_families'])
if __name__=='__main__':print(json.dumps(prepare()))
