"""Freeze two full-QA regressions, four real negatives and all normal history."""
from pathlib import Path
import hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def put(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b,'closure_collision:'+str(p)
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
def main():
 import compiler_svg_general_guard_v11 as core
 import compiler_svg_general_guard_v10 as previous_core
 import compiler_source_core_attempts_v3 as history
 import svg_analytic_iteration_controls_v6 as checker
 controls=R/'conversion/svg_edge_layers_quality_controls_v1/6bb5ffe01d864e39a2c7f32cfdb4c948';cfg=core.configuration();freeze=json.loads((controls/'freeze.json').read_bytes());assert freeze['generation']==cfg
 for path,digest in freeze['quality']['pins'].items():assert sha(Path(path).read_bytes())==digest
 roots=[R/'conversion/compiler_svg_scene_frontend_v14/normal_development_v1/f4b4a0d4f06844aeb240ab0eea1b1d1e/6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb',R/'conversion/compiler_svg_scene_frontend_v15/normal_development_v1/4ff5a2a54c604af58b5dcfeddd70e371/6bfea54fe17b524d3a15883bce122ceb1592312810394cafa67a9905cc339dce']
 normals=[json.loads((p/'summary.json').read_bytes())for p in roots];assert normals[0]['quality_ok']and normals[0]['source_core']==history.core_identity(previous_core.configuration());assert normals[1]['source_core']==history.core_identity(cfg)
 assert normals[1]['conversion_ok']is False and normals[1]['conversion_reason']=='source_triangle_not_symmetric_about_owner_tangent'
 assert all(n['normal_frontend_calls']==1 and n['canonical_unchanged']for n in normals)
 names=['positive_symbol','positive_existing','negative_text','negative_geometry','negative_opacity','negative_order_v2'];cases={name:json.loads((controls/name/'case/summary.json').read_bytes())for name in names}
 for name,value in cases.items():
  assert value['control_contract_passed']and value['canonical_unchanged']and value['normal_conversion_calls']==0
  checker.check_control_case(value['control'],'positive'if name.startswith('positive')else'negative',cfg)
 root=R/'release/compiler_iterations/controls/svg_source_edge_layers_untouched_use_20261102_v1';root.mkdir(parents=True,exist_ok=True);receipt=root/'normal_history_receipt.json';put(receipt,raw(dict(rows=normals)))
 parent=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_native_symbol_viewport_20261102_v7.json';catalog=json.loads(parent.read_bytes());add=[]
 for index,(normal,work)in enumerate(zip(normals,roots)):
  item=dict(source_core_key=normal['source_core']['key'],id=normal['id'],source=normal['source'],receipt=asset(receipt),rows_key='rows',row_index=index,normal_count_key='normal_frontend_calls',requires_unchanged_canonical=True,frontend=asset(work/'frontend_result.json'))
  assert not any(x['source_core_key']==item['source_core_key']and x['id']==item['id']for x in catalog['entries']);add.append(item)
 catalog={**catalog,'entries':catalog['entries']+add,'preserved_parent_catalog':asset(parent)};catalog_path=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_edge_layers_untouched_use_20261102_v8.json';put(catalog_path,raw(catalog))
 manifest=root/'qualified.jsonl';put(manifest,b''.join(json.dumps(cases[name]['qualified_manifest'],sort_keys=True).encode()+b'\n'for name in names[:2]))
 proof=dict(schema='actual_source_edge_layers_untouched_UA_controls_v1',frozen_frontend=cfg,source_core=history.core_identity(cfg),positive_cases=[cases[name]['control']for name in names[:2]],negative_cases=[cases[name]['control']for name in names[2:]],qualified_manifest=asset(manifest),producer=asset(Path(__file__)),method_pins={str(p):sha(p.read_bytes())for p in[Path(__file__),S/'svg_analytic_iteration_controls_v6.py',S/'strict_native_canvas_evidence_v1.py',S/'svg_source_edge_layers_v2.py',S/'svg_source_use_instance_proof_v6.py']},normal_development_receipt=asset(receipt),retained_failed_initial_negative_fixture=asset(controls/'negative_order/output.log'),initial_fixture_not_counted_as_negative_control=True,current_normal_conversion_failure_preserved=True,new_normal_calls=0,new_QA_calls=0,model_calls=0,goal_complete=False)
 checker.check_controls(proof);target=root/'proof.json';put(target,raw(proof));print(json.dumps(dict(proof=asset(target),catalog=asset(catalog_path),source_core=history.core_identity(cfg),positive_cases=2,actual_XML_PNG_negatives=4,preserved_normal_events=len(normals),normal_reexecution_allowed=False)),flush=True)
if __name__=='__main__':main()
