"""Close measured read-only controls and preserve the one consumed normal."""
from pathlib import Path
import argparse,hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S))
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def immutable(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b,'closure_collision:'+str(p)
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
def main():
 import compiler_svg_general_guard_v9 as core
 import compiler_source_core_attempts_v3 as history
 import svg_analytic_iteration_controls_v5 as checker
 parser=argparse.ArgumentParser();parser.add_argument('--controls',type=Path,required=True);parser.add_argument('--normal',type=Path,required=True);args=parser.parse_args()
 cfg=core.configuration();normal=json.loads((args.normal/'summary.json').read_bytes());assert normal['normal_frontend_calls']==1 and normal['canonical_unchanged']and normal['conversion_ok']and normal['source_core']==history.core_identity(cfg)
 freeze=json.loads((args.controls/'freeze.json').read_bytes());assert freeze['generation']==cfg
 for path,digest in freeze['quality']['pins'].items():assert sha(Path(path).read_bytes())==digest
 rows={name:json.loads((args.controls/name/'case/summary.json').read_bytes())for name in ['positive_prior','positive_existing','negative_text','negative_geometry','negative_opacity']}
 for name,r in rows.items():
  assert r['control_contract_passed']and r['canonical_unchanged']and r['normal_conversion_calls']==0
  checker.check_control_case(r['control'],'positive'if name.startswith('positive')else'negative',cfg)
 root=R/'release/compiler_iterations/controls/svg_native_symbol_viewport_20261102_v1';root.mkdir(parents=True,exist_ok=True)
 receipt=root/'normal_history_receipt.json';immutable(receipt,raw(dict(rows=[normal])))
 parent=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_actual_shadow_layout_20261102_v6.json';catalog=json.loads(parent.read_bytes())
 declaration=dict(source_core_key=normal['source_core']['key'],id=normal['id'],source=normal['source'],receipt=asset(receipt),rows_key='rows',row_index=0,normal_count_key='normal_frontend_calls',requires_unchanged_canonical=True,frontend=asset(args.normal/'frontend_result.json'))
 assert not any(row['source_core_key']==declaration['source_core_key']and row['id']==declaration['id']for row in catalog['entries'])
 catalog={**catalog,'entries':catalog['entries']+[declaration],'preserved_parent_catalog':asset(parent)}
 catalog_path=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_native_symbol_viewport_20261102_v7.json';immutable(catalog_path,raw(catalog))
 manifest=root/'qualified.jsonl';immutable(manifest,b''.join(json.dumps(rows[name]['qualified_manifest'],sort_keys=True).encode()+b'\n'for name in ['positive_prior','positive_existing']))
 held_qa=R/'conversion/prototype/candidate_quality_ro_v1/SVG_actual_shadow_positive_4b837efb2b2d45fcac98276257701b6f/report.json'
 held=json.loads(held_qa.read_bytes());assert held['ok']is False and held['checks']['source']['evidence']['checks']['complete_source_compositing_guard']['ok']is True
 assert all(item['reason']=='actual_overlapping_native_source_paint_order_changed'for item in held['checks']['source']['failures'])
 proof=dict(known_development_hold=dict(id=normal['id'],qa=asset(held_qa),reason='two_actual_native_paint_order_changes_preserved_as_pending',qualified=False),schema='actual_SVG_native_symbol_viewport_controls_v1',frozen_frontend=cfg,source_core=history.core_identity(cfg),positive_cases=[rows[name]['control']for name in ['positive_prior','positive_existing']],negative_cases=[rows[name]['control']for name in ['negative_text','negative_geometry','negative_opacity']],qualified_manifest=asset(manifest),producer=asset(Path(__file__)),method_pins={str(p):sha(p.read_bytes())for p in [Path(__file__),S/'svg_analytic_iteration_controls_v5.py',S/'strict_native_canvas_evidence_v1.py',S/'svg_leaf_opacity_proof_v1.py']},new_normal_calls=0,new_QA_calls=0,new_model_calls=0,original_QA_reports_modified=False,goal_complete=False)
 checker.check_controls(proof);target=root/'proof.json';immutable(target,raw(proof))
 print(json.dumps(dict(proof=asset(target),catalog=asset(catalog_path),source_core=history.core_identity(cfg),positive_cases=2,negative_cases=3,normal_source_conversions=1,normal_reexecution_allowed=False)))
if __name__=='__main__':main()
