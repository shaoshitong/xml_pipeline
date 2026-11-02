"""Source-only official semantic graph families; no image or layout input."""
from pathlib import Path
import functools,hashlib,json,uuid,base64
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
INDEX=W/'plantuml_engine_source_model_index_v1/source_index.json'
MANIFEST=INDEX.parent/'build_manifest.json'
POLICY='official_plantuml_semantic_Entity_parent_Link_decor_family_v1'
SUPPORTED_TYPES={'net.sourceforge.plantuml.descdiagram.DescriptionDiagram','net.sourceforge.plantuml.classdiagram.ClassDiagram','net.sourceforge.plantuml.statediagram.StateDiagram'}
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def family_of_model(model):
 import networkx as nx
 from compiler_types_source_ir_v1 import add,link
 from compiler_validation_dot_ir_v2 import invariant
 g=nx.MultiDiGraph();add(g,'ROOT','official_PlantUML_diagram',{'type':model.get('diagram_class'),'cuca':model.get('cuca_supported',False)});entities=model.get('entities',[])+model.get('groups',[]);known={e['uid'] for e in entities}
 if len(known)!=len(entities):raise ValueError('official_source_IR_entity_keys_not_unique')
 def label(v):return bool(v and v not in ('[]','null'))
 for e in entities:
  add(g,('entity',e['uid']),'Entity',{k:e.get(k) for k in ('is_group','kind','hidden','removed')}|{'display_text_present':label(e.get('display'))})
 for e in entities:link(g,('entity',e['parent_uid']) if e.get('parent_uid') in known else 'ROOT',('entity',e['uid']),'actual_Entity_parent')
 for i,e in enumerate(model.get('links',[])):
  if e['entity1_uid'] not in known or e['entity2_uid'] not in known:raise ValueError('official_source_IR_Link_endpoint_not_in_entity_inventory')
  key=('link',i);add(g,key,'actual_Link',{k:e.get(k) for k in ('decor1','decor2','invisible','hidden','removed','constraint','inverted')}|{'port1_present':bool(e.get('port1')),'port2_present':bool(e.get('port2')),'label_present':label(e.get('label'))});link(g,('entity',e['entity1_uid']),key,'actual_Link_entity1');link(g,key,('entity',e['entity2_uid']),'actual_Link_entity2')
 return 'plantuml_official_semantic_source_family_v1:'+invariant(g),{'method':POLICY,'diagram_class':model.get('diagram_class'),'entities':len(model.get('entities',[])),'groups':len(model.get('groups',[])),'links':len(model.get('links',[])),'true_source_engine_semantics':True,'identifier_and_label_values_ignored':True,'source_styles_conservatively_ignored_for_family_exclusion':True,'image_or_reference_score_used':False,'geometry_used_to_infer_connections':False}
@functools.lru_cache(maxsize=1)
def _index():
 m=json.loads(MANIFEST.read_bytes());b=INDEX.read_bytes()
 if sha(b)!=m['index_sha256']:raise ValueError('official_source_static_index_changed')
 return json.loads(b)
@functools.lru_cache(maxsize=256)
def _lookup(code):
 data=code.encode() if isinstance(code,str) else code;digest=sha(data);index=_index()
 if digest in index:return index[digest]
 # Pure official parser fallback for new synthetic fixtures/new original bytes.
 from plantuml_engine_scene_runtime_v7 import run
 model=run(W/'plantuml_engine_source_model_index_v1/adhoc_source_models'/uuid.uuid4().hex,base64.b64encode(data)+b'\n',models=True)[0]
 family,evidence=family_of_model(model);return {'diagram_class':model.get('diagram_class'),'family':family,'evidence':evidence,'source_code_sha256':digest,'fallback_official_source_parser':True}
def source_type(code):return _lookup(code)['diagram_class']
def family(code):
 row=_lookup(code);return row['family'],row['evidence']
def configuration():
 return {'policy':POLICY,'pins':{str(p):sha(p.read_bytes()) for p in (Path(__file__).resolve(),INDEX,MANIFEST)},'supported_types':sorted(SUPPORTED_TYPES),'static_eligibility_not_conversion_or_quality':True}
