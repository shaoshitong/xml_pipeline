import hashlib,json,subprocess,urllib.request,os,time
from pathlib import Path
from PIL import Image
from native_worker import R,W,now
from sandbox_runner import command,limits
from svg_batch import metric
JAR=W/'runtime/plantuml/plantuml-1.2025.7.jar';JAR.parent.mkdir(exist_ok=True)
URL='https://github.com/plantuml/plantuml/releases/download/v1.2025.7/plantuml-1.2025.7.jar';EXPECTED='4edcdda164a4be2f8f954f82868795500ebd49f42306236bf88eac41f7e217a8'
if not JAR.exists():
 with urllib.request.urlopen(URL,timeout=90) as f:data=f.read()
 assert hashlib.sha256(data).hexdigest()==EXPECTED
 JAR.write_bytes(data)
assert hashlib.sha256(JAR.read_bytes()).hexdigest()==EXPECTED
G=W/'runtime/graphviz';JAVA='/usr/lib/jvm/java-11-openjdk-amd64/bin/java'
extra=[(JAR,'/runtime/plantuml.jar'),(G,G),('/etc/java-11-openjdk','/etc/java-11-openjdk')]
if Path('/etc/alternatives').exists():extra.append(('/etc/alternatives','/etc/alternatives'))
env={'GRAPHVIZ_DOT':str(G/'bin/dot'),'PATH':str(G/'bin')+':/usr/bin:/bin','PLANTUML_SECURITY_PROFILE':'SANDBOX'}
work=W/'plantuml_source_probe';work.mkdir(exist_ok=True);results=[]
for r in json.loads((W/'text_fidelity_selection.json').read_text()):
 if r['format']!='plantuml':continue
 d=work/r['id'];d.mkdir(exist_ok=True);code=(R/r['source_code']).read_bytes();(d/'source.puml').write_bytes(code);ref=(R/r['reference']).read_bytes();metadata=Image.open(R/r['reference']).info.get('plantuml','')
 row={'id':r['id'],'source_sha256':hashlib.sha256(code).hexdigest(),'reference_sha256':hashlib.sha256(ref).hexdigest(),'reference_metadata':metadata,'previous_native_ssim':r['score'],'formats':{}}
 for fmt in ('svg','png'):
  argv=[JAVA,'-Xmx512m','-XX:+UseSerialGC','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SANDBOX','-jar','/runtime/plantuml.jar','-charset','UTF-8','-pipe','-t'+fmt]
  start=time.time()
  try:
   p=subprocess.run(command(d,argv,extra,env),input=code,capture_output=True,timeout=100,preexec_fn=limits)
   (d/(fmt+'.stderr')).write_bytes(p.stderr)
   row['formats'][fmt]={'returncode':p.returncode,'stderr':p.stderr.decode(errors='replace')[-1500:],'seconds':time.time()-start}
   if p.returncode==0:
    (d/('source.'+fmt)).write_bytes(p.stdout)
    if fmt=='png':row['formats'][fmt].update(ssim=metric(ref,p.stdout),size=Image.open(d/'source.png').size)
  except Exception as e:row['formats'][fmt]={'error':repr(e)}
 print(json.dumps(row,ensure_ascii=False),flush=True);results.append(row)
(work/'report.json').write_text(json.dumps({'at':now(),'jar_sha256':EXPECTED,'jar_url':URL,'results':results},ensure_ascii=False,indent=2))
