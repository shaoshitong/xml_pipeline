"""Compare geometric-only nesting to source paint constraints on saved failures.

This is finite structural diagnosis, not a normal conversion or qualification.
No running implementation or source observation is rewritten.
"""
from pathlib import Path
import copy,hashlib,json,sqlite3,sys,time,types,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S));sys.path.append(str(R/'conversion/prototype'))
def main():
 import compiler_svg_general_guard_v14 as core
 backend=S/'compiler_svg_scene_backend_v13.py';layer=S/'svg_source_edge_layers_v9.py';pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [backend,layer,S/'svg_source_group_nesting_v1.py']}
 diagnostic=layer.read_text().replace("if not applied:raise ValueError('source_layer_interleaving_needs_compound_paint_representation')",'''if not applied:
    import json
    unresolved={key for key in items if degree[key]>0}
    facts=[]
    for a,b in sorted(constraints[parent]):
     if a in unresolved and b in unresolved:
      facts.append(dict(before=a,after=b,before_is_group=a in groups,after_is_group=b in groups,before_parent=cells[a].get('parent'),after_parent=cells[b].get('parent')))
    raise ValueError('cycle_witness:'+json.dumps(dict(parent=parent,unresolved=sorted(unresolved),constraints=facts[:24])))''')
 assert diagnostic!=layer.read_text();name='source_compound_cycle_diagnostic_ephemeral';module=types.ModuleType(name);module.__file__=str(layer);exec(compile(diagnostic,str(layer),'exec'),module.__dict__);sys.modules[name]=module
 source=backend.read_text().replace('from svg_source_edge_layers_v9 import repair','from '+name+' import repair');variants={}
 for flat in [False,True]:
  text=source
  if flat:
   before="xml,nesting=nest_source_groups(ET.tostring(tree,encoding='unicode'))"
   text=text.replace(before,"xml,nesting=ET.tostring(tree,encoding='unicode'),dict(diagnostic_geometric_group_nesting_omitted=True)");assert text!=source
  namespace=dict(__name__='compound_ancestry_diagnostic_'+str(flat),__file__=str(backend));exec(compile(text,str(backend),'exec'),namespace);variants[flat]=namespace
 run=R/'release/compiler_iterations/runs/svg_complex_background_rotation_cached_unseen_20261102_v9_mass'
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:results=[json.loads(x[0])for x in d.execute("select result from samples where status='abandoned' order by seq")]
 targets=[r for r in results if r.get('reason')=='source_layer_interleaving_needs_compound_paint_representation'][:3];assert len(targets)==3
 cached={r['id']:r for r in map(json.loads,(R/'conversion/source_cached_admission_v1/2d47ad593b4545038329916ff229a8ea/admitted.jsonl').read_text().splitlines())}
 output=R/'conversion/compound_group_ancestry_diagnostic_v1'/uuid.uuid4().hex;output.mkdir(parents=True);rows=[]
 from PIL import Image
 for target in targets:
  row=cached[target['id']];ref=row['cached_DOM'];p=R/ref['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256'];dom=json.loads(p.read_bytes());size=Image.open(Path(row['source_observation_work'])/'browser_source.png').size
  for flat,backend_module in variants.items():
   t=time.monotonic();r=dict(id=target['id'],omit_geometric_group_nesting=flat,source_DOM=ref)
   try:
    xml,stats=backend_module['build'](copy.deepcopy(dom),size);p=output/(target['id']+('_flat'if flat else'_nested')+'.xml');p.write_text(xml)
    order=core.paint_order(dom,xml,size);r.update(structural_passed=True,actual_native_source_paint_order=order,xml_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),xml_file=str(p.relative_to(R)))
   except Exception as e:
    message=str(e);r.update(structural_passed=False,reason=message[:5000])
   r['elapsed_seconds']=time.monotonic()-t;rows.append(r)
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in pins.items())
 summary=dict(root=str(output),results=rows,method_pins=pins,new_normal_calls=0,new_QA_calls=0,browser_source_recaptures=0,model_calls=0,qualification_claimed=False,source_parentage_and_running_core_unchanged=True)
 (output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
