"""Same Diagram instance -> genuine IR, original SVG and engine PNG."""
from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET
import plantuml_source_runtime_graphviz243_v1 as source_backend
from plantuml_source_runtime_graphviz243_v1 import JAVA,JAR,JAR_SHA
from native_worker import R,W
from sandbox_runner import command,limits
HELPER=W/'scripts/PlantumlEngineSceneV7.java'
AGENT=W/'runtime/plantuml_engine_draw_agent_v4/owner-agent.jar'
def run(work,source,models=False):
 work=Path(work).resolve();assert work.is_relative_to(W);work.mkdir(parents=True,exist_ok=True);assert hashlib.sha256(JAR.read_bytes()).hexdigest()==JAR_SHA
 manifest=json.loads((AGENT.parent/'build_manifest.json').read_bytes());assert hashlib.sha256(AGENT.read_bytes()).hexdigest()==manifest['sha256']
 for path,digest in manifest['sources'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
 argv=[JAVA,'-Xmx512m','-XX:+UseSerialGC','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SANDBOX','--add-exports','java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED','--add-exports','java.base/jdk.internal.org.objectweb.asm.tree=ALL-UNNAMED','-javaagent:/runtime/owner-agent.jar','--class-path','/runtime/plantuml.jar:/runtime/owner-agent.jar','/runtime/PlantumlEngineSceneV7.java']+(['models'] if models else []);extra=[*source_backend.extra_ro(),(AGENT,'/runtime/owner-agent.jar'),(HELPER,'/runtime/PlantumlEngineSceneV7.java')];env=source_backend.environment();source_backend.configuration()
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
 # Only source PNG canvas determines viewport. Primitive stream and all
 # children remain unchanged; browser proves both clipping and origin below.
 ET.register_namespace('', 'http://www.w3.org/2000/svg')
 viewport=[]
 for name in ('source.svg','source.original.svg'):
  blob=(work/name).read_bytes();(work/(name+'.raw')).write_bytes(blob);root=ET.fromstring(blob)
  before=hashlib.sha256(b''.join(ET.tostring(c) for c in root)).hexdigest()
  prior={k:root.get(k) for k in ('width','height','viewBox','style')}
  w,h=painted.size;root.set('width',str(w));root.set('height',str(h));root.set('viewBox',f'0 0 {w} {h}')
  import re
  style=re.sub(r'(?:^|;)(?:width|height)\s*:[^;]*','',root.get('style',''))
  root.set('style',style.strip(';')+f';width:{w}px;height:{h}px')
  after=hashlib.sha256(b''.join(ET.tostring(c) for c in root)).hexdigest();assert before==after
  (work/name).write_bytes(ET.tostring(root,encoding='utf-8'))
  viewport.append({'file':name,'raw':prior,'canonical':{'width':w,'height':h,'viewBox':[0,0,w,h]},'primitive_bytes_sha256_before':before,'primitive_bytes_sha256_after':after,'scale':[1,1],'translation':[0,0],'source_PNG_canvas_only':True})
 return {'ir':ir,'svg':(work/'source.svg').read_bytes(),'png':(work/'source.png').read_bytes(),'original_svg':(work/'source.original.svg').read_bytes(),'ownership':ownership,'same_paint_stream':paint_stream,'viewport_projection':viewport,'source_backend':source_backend.configuration()['policy'],'pristine_ir':json.loads((work/'engine_pristine.json').read_bytes()),'same_instance':True,'same_phase_pristine_and_owned_engine_semantics':True,'same_phase_pristine_and_owned_engine_PNG_pixels':True,'jar_sha256':JAR_SHA,'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest()}
