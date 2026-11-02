"""Same Diagram instance -> genuine IR, original SVG and engine PNG."""
from pathlib import Path
import json,hashlib,subprocess
from plantuml_runtime import JAVA,JAR,JAR_SHA,G
from native_worker import R,W
from sandbox_runner import command,limits
HELPER=W/'scripts/PlantumlEngineSceneV1.java'
def run(work,source,models=False):
 work=Path(work).resolve();assert work.is_relative_to(W);work.mkdir(parents=True,exist_ok=True);assert hashlib.sha256(JAR.read_bytes()).hexdigest()==JAR_SHA
 argv=[JAVA,'-Xmx512m','-XX:+UseSerialGC','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SANDBOX','--class-path','/runtime/plantuml.jar','/runtime/PlantumlEngineSceneV1.java']+(['models'] if models else []);extra=[(JAR,'/runtime/plantuml.jar'),(HELPER,'/runtime/PlantumlEngineSceneV1.java'),(G,G),('/etc/java-11-openjdk','/etc/java-11-openjdk'),('/etc/alternatives','/etc/alternatives')];env={'GRAPHVIZ_DOT':str(G/'bin/dot'),'PATH':str(G/'bin')+':/usr/bin:/bin','PLANTUML_SECURITY_PROFILE':'SANDBOX'}
 p=subprocess.run(command(work,argv,extra,env),input=source,capture_output=True,timeout=100,preexec_fn=limits);(work/'stderr.txt').write_bytes(p.stderr)
 if p.returncode:raise ValueError('same_instance_engine_failed:'+p.stderr.decode(errors='replace')[:1800])
 if models:return [json.loads(x) for x in p.stdout.splitlines()]
 ir=json.loads((work/'engine_ir.json').read_bytes())
 if not ir['cuca_supported']:raise ValueError('typed_non_CucaDiagram_pending:'+ir['diagram_class'])
 after=json.loads((work/'engine_after_png.json').read_bytes())
 if ir!=after:raise ValueError('same_instance_svg_png_semantic_IR_changed')
 return {'ir':ir,'svg':(work/'source.svg').read_bytes(),'png':(work/'source.png').read_bytes(),'same_instance':True,'same_svg_png_semantics':True,'jar_sha256':JAR_SHA,'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest()}
