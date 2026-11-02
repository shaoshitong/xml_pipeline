"""Resolve each text run through the pinned PlantUML UFont stack and actual Java font slots."""
import base64,json,subprocess,hashlib
from native_worker import W
from plantuml_runtime import JAVA,JAR,G,JAR_SHA
from sandbox_runner import command,limits

def resolve(page,work):
 specs=page.evaluate('''()=>[...document.querySelectorAll('svg text')].map((e,i)=>({index:i,family:e.getAttribute('font-family')||getComputedStyle(e).fontFamily,style:(+getComputedStyle(e).fontWeight>=600?1:0)+(getComputedStyle(e).fontStyle==='italic'?2:0),size:Math.round(parseFloat(e.getAttribute('font-size')||getComputedStyle(e).fontSize)),text:e.textContent}))''')
 enc=lambda s:base64.b64encode(s.encode()).decode();rows='\n'.join('\t'.join([enc(s['family']),str(s['style']),str(s['size']),enc(s['text'])]) for s in specs)+'\n';helper=W/'runtime/plantuml/ResolvePlantFonts.java'
 argv=[JAVA,'--add-exports','java.desktop/sun.font=ALL-UNNAMED','-Xmx256m','-XX:+UseSerialGC','-Djava.awt.headless=true','--class-path','/runtime/plantuml.jar','/runtime/ResolvePlantFonts.java'];extra=[(JAR,'/runtime/plantuml.jar'),(helper,'/runtime/ResolvePlantFonts.java'),('/etc/java-11-openjdk','/etc/java-11-openjdk'),('/etc/alternatives','/etc/alternatives')];p=subprocess.run(command(work,argv,extra),input=rows,text=True,capture_output=True,timeout=40,preexec_fn=limits)
 if p.returncode:raise ValueError('Java font resolution failed: '+p.stderr[:2000])
 lines=p.stdout.splitlines();assert len(lines)==len(specs),(len(lines),len(specs));results=[]
 for spec,line in zip(specs,lines):
  a=line.split('\t');selected,all_fonts,logical=[base64.b64decode(a[i]).decode() for i in [0,1,3]];results.append({**spec,'selected':selected,'physical_families':all_fonts.split('|'),'missing_glyph_at':int(a[2]),'java_family':logical})
 page.evaluate('''items=>{let texts=[...document.querySelectorAll('svg text')];for(const r of items)texts[r.index].setAttribute('font-family',r.selected);}''',results)
 return {'method':'pinned_PlantUML_UFont_underlying_Java_font_and_physical_glyph_slots','jar_sha256':JAR_SHA,'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'runs':results,'needs_glyph_fallback_review':any(r['missing_glyph_at']!=-1 or len(r['physical_families'])>1 for r in results)}
