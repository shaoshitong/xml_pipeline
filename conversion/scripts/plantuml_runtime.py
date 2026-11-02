"""Pinned PlantUML subprocess with isolated file/network access."""
import hashlib,json,subprocess
from pathlib import Path
from native_worker import W
from sandbox_runner import command,limits
JAR=W/'runtime/plantuml/plantuml-1.2025.7.jar';JAR_SHA='4edcdda164a4be2f8f954f82868795500ebd49f42306236bf88eac41f7e217a8'
JAVA='/usr/lib/jvm/java-11-openjdk-amd64/bin/java';G=W/'runtime/graphviz'
def run(work,code,fmt):
 assert hashlib.sha256(JAR.read_bytes()).hexdigest()==JAR_SHA
 extra=[(JAR,'/runtime/plantuml.jar'),(G,G),('/etc/java-11-openjdk','/etc/java-11-openjdk'),('/etc/alternatives','/etc/alternatives')];env={'GRAPHVIZ_DOT':str(G/'bin/dot'),'PATH':str(G/'bin')+':/usr/bin:/bin','PLANTUML_SECURITY_PROFILE':'SANDBOX'}
 argv=[JAVA,'-Xmx512m','-XX:+UseSerialGC','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SANDBOX','-jar','/runtime/plantuml.jar','-charset','UTF-8','-pipe','-t'+fmt]
 p=subprocess.run(command(work,argv,extra,env),input=code,capture_output=True,timeout=100,preexec_fn=limits);(work/(fmt+'.stderr')).write_bytes(p.stderr)
 if p.returncode:raise ValueError('PlantUML '+fmt+' failed: '+p.stderr.decode(errors='replace')[:1500])
 return p.stdout
