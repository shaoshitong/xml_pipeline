"""Finite engine model API probe on consumed source and synthetic grammars."""
import sys,json,subprocess,uuid,hashlib,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from plantuml_runtime import JAVA,JAR,JAR_SHA,G
from sandbox_runner import command,limits
helper=W/'scripts/PlantumlEngineIRProbeV1.java';owner=W/'plantuml_engine_ir_probe_v1'/uuid.uuid4().hex;owner.mkdir(parents=True)
consumed=R/'clean/compiler_plantuml_natural_candidate_v9/05/05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798/5372837b2a2b44b3b7ab815a3318c01c'
fixtures={'consumed_flat_05d':(consumed/'original_source.puml').read_text(),'synthetic_nested_component':'@startuml\nskinparam componentStyle rectangle\npackage "Layer" as P {\ncomponent "Frontend" as F\nnode "Server" as S\nF -[#red]-> S : request\n}\n@enduml','synthetic_state':'@startuml\nstate A {\nstate B\n}\n[*] --> A\nA --> [*]\n@enduml','synthetic_class':'@startuml\nclass Child extends Parent\nChild *-- "1" Item : owns\n@enduml','synthetic_activity':'@startuml\nstart\n:Read;\nif (ok?) then (yes)\n:Accept;\nelse (no)\n:Reject;\nendif\nstop\n@enduml'}
results=[]
for name,code in fixtures.items():
 work=owner/name;work.mkdir();argv=[JAVA,'-Xmx512m','-XX:+UseSerialGC','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SANDBOX','--class-path','/runtime/plantuml.jar','/runtime/PlantumlEngineIRProbeV1.java'];extra=[(JAR,'/runtime/plantuml.jar'),(helper,'/runtime/PlantumlEngineIRProbeV1.java'),(G,G),('/etc/java-11-openjdk','/etc/java-11-openjdk'),('/etc/alternatives','/etc/alternatives')];env={'GRAPHVIZ_DOT':str(G/'bin/dot'),'PATH':str(G/'bin')+':/usr/bin:/bin','PLANTUML_SECURITY_PROFILE':'SANDBOX'};p=subprocess.run(command(work,argv,extra,env),input=code.encode(),capture_output=True,timeout=60,preexec_fn=limits);(work/'stderr.txt').write_bytes(p.stderr);row={'fixture':name,'returncode':p.returncode}
 if p.returncode:row['error']=p.stderr.decode(errors='replace')[:1600]
 else:
  data=json.loads(p.stdout);(work/'engine_ir.json').write_bytes(p.stdout);row.update(diagram_class=data['diagram_class'],entities=len(data['entities']),groups=len(data['groups']),links=len(data['links']),engine_parent_edges=sum(x['parent_uid'] in {g['uid'] for g in data['groups']} for x in data['entities']+data['groups']),cuca_supported=data['cuca_supported'])
  if name=='consumed_flat_05d':
   svg=E.fromstring((consumed/'source.svg').read_bytes());native_entities={e.get('data-uid'):e for e in svg.iter() if e.get('class')=='entity'};native_links={e.get('data-uid'):e for e in svg.iter() if e.get('class')=='link'};row['actual_source_svg_entity_uids_match']=set(native_entities)=={x['uid'] for x in data['entities']};row['actual_source_svg_link_uids_match']=set(native_links)=={x['uid'] for x in data['links']};row['all_source_connections_refer_to_model_uid']=all(x['entity1_uid'] in native_entities and x['entity2_uid'] in native_entities for x in data['links'])
 results.append(row);print(json.dumps(row),flush=True)
report={'schema':'plantuml_engine_ir_api_finite_probe_v1','jar_sha256':JAR_SHA,'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'cases':results,'consumed_corpus_cases':1,'synthetic_cases':4,'new_heldout_consumed':0,'models':0,'target_conversions':0,'source_geometry_rendering':0,'canonical_mutations':0,'not_yet_a_complete_compiler':'This only proves semantic IR/UID APIs. Same-instance SVG binding, all paint/glyph/native editing proof and ActivityDiagram3 instruction IR remain to implement.'};(owner/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(owner/'report.json')}),flush=True)
