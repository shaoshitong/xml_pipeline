import subprocess,json
from pathlib import Path
from native_worker import W
from sandbox_runner import command,limits
work=W/'plantuml_source_probe';java='/usr/lib/jvm/java-11-openjdk-amd64/bin/java'
(work/'FontProbe.java').write_text('import java.awt.*; public class FontProbe {public static void main(String[] args) {for(String name:args){Font f=new Font(name,Font.PLAIN,12); System.out.println(name+"|"+f.getFamily()+"|"+f.getFontName());}}}')
args=command(work,[java,'-Xmx256m','-XX:+UseSerialGC','/work/FontProbe.java','sans-serif','SansSerif','Consolas','Arial'],[('/etc/java-11-openjdk','/etc/java-11-openjdk'),('/etc/alternatives','/etc/alternatives')]);p=subprocess.run(args,capture_output=True,text=True,timeout=30,preexec_fn=limits);print(json.dumps({'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}));(work/'java_font_resolution.json').write_text(json.dumps({'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}))
