"""Same Diagram instance -> genuine IR, original SVG and engine PNG."""
from pathlib import Path
import json,hashlib,subprocess
import plantuml_source_runtime_graphviz243_v1 as source_backend
from plantuml_source_runtime_graphviz243_v1 import JAVA,JAR,JAR_SHA
from native_worker import R,W
from sandbox_runner import command,limits
HELPER=W/'scripts/PlantumlEngineSceneV6.java'
AGENT=W/'runtime/plantuml_engine_draw_agent_v3/owner-agent.jar'
def run(work,source,models=False):
 work=Path(work).resolve();assert work.is_relative_to(W);work.mkdir(parents=True,exist_ok=True);assert hashlib.sha256(JAR.read_bytes()).hexdigest()==JAR_SHA
 manifest=json.loads((AGENT.parent/'build_manifest.json').read_bytes());assert hashlib.sha256(AGENT.read_bytes()).hexdigest()==manifest['sha256']
 for path,digest in manifest['sources'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
 argv=[JAVA,'-Xmx512m','-XX:+UseSerialGC','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SANDBOX','--add-exports','java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED','--add-exports','java.base/jdk.internal.org.objectweb.asm.tree=ALL-UNNAMED','-javaagent:/runtime/owner-agent.jar','--class-path','/runtime/plantuml.jar:/runtime/owner-agent.jar','/runtime/PlantumlEngineSceneV6.java']+(['models'] if models else []);extra=[*source_backend.extra_ro(),(AGENT,'/runtime/owner-agent.jar'),(HELPER,'/runtime/PlantumlEngineSceneV6.java')];env=source_backend.environment();source_backend.configuration()
 p=subprocess.run(command(work,argv,extra,env),input=source,capture_output=True,timeout=100,preexec_fn=limits);(work/'stderr.txt').write_bytes(p.stderr)
 if p.returncode:raise ValueError('same_instance_engine_failed:'+p.stderr.decode(errors='replace')[:1800])
 if models:return [json.loads(x) for x in p.stdout.splitlines()]
 ir=json.loads((work/'engine_ir.json').read_bytes())
 if not ir['cuca_supported']:raise ValueError('typed_non_CucaDiagram_pending:'+ir['diagram_class'])
 from PIL import Image
 original=Image.open(work/'source.original.png').convert('RGBA');painted=Image.open(work/'source.png').convert('RGBA')
 if original.size!=painted.size or original.tobytes()!=painted.tobytes():raise ValueError('nonpaint_owner_hook_changed_engine_PNG_pixels')
 paint_stream=json.loads((work/'same_paint_stream.json').read_bytes());assert paint_stream['same_layout_and_paint_call_stream'] and paint_stream['original_PNG_draw_calls']==paint_stream['owned_SVG_draw_calls']==paint_stream['pristine_SVG_draw_calls']
 ownership=json.loads((work/'ownership_instrumentation.json').read_bytes())
 for link in ir['links']:
  actual=ownership['actual_source_link_objects'].get(link['uid'])
  if actual is not None and (actual['entity1_uid']!=link['entity1_uid'] or actual['entity2_uid']!=link['entity2_uid']):raise ValueError('actual_painter_link_object_endpoints_differ_from_model')
 return {'ir':ir,'svg':(work/'source.svg').read_bytes(),'png':(work/'source.png').read_bytes(),'original_svg':(work/'source.original.svg').read_bytes(),'ownership':ownership,'same_paint_stream':paint_stream,'source_backend':source_backend.configuration()['policy'],'pristine_ir':json.loads((work/'engine_pristine.json').read_bytes()),'same_instance':True,'same_phase_pristine_and_owned_engine_semantics':True,'same_phase_pristine_and_owned_engine_PNG_pixels':True,'jar_sha256':JAR_SHA,'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest()}
