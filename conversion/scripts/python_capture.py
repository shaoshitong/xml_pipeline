import json,pathlib,sys,traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch
root=pathlib.Path('/work');captured=[];counter=0;original=Figure.savefig
runtime=pathlib.Path('/backup/shaoshitong/img2code_20261029/conversion/runtime')
sys.path.append(str(runtime/'python_packages'))
import os
os.environ['PATH']=str(runtime/'graphviz/bin')+':'+os.environ.get('PATH','')
try:
 import graphviz
 original_pipe=graphviz.Digraph.pipe
 def pipe(self,*args,**kwargs):
  global counter
  index=counter;counter+=1;dot=root/f'figure_{index}.dot';svg=root/f'figure_{index}.svg';dot.write_text(self.source);svg.write_bytes(original_pipe(self,format='svg'));captured.append({'svg':svg.name,'dot':dot.name,'engine':'graphviz','nodes_edges':'SVG graphviz title metadata'});(root/'captures.json').write_text(json.dumps(captured,indent=2));return original_pipe(self,*args,**kwargs)
 graphviz.Digraph.pipe=pipe;graphviz.Graph.pipe=pipe;graphviz.Source.pipe=pipe
except ImportError:pass

def capture(fig,*args,**kwargs):
 global counter
 index=counter;counter+=1;svg=root/f'figure_{index}.svg';png=root/f'figure_{index}.png';metadata=[]
 for n,a in enumerate(fig.findobj()):
  if isinstance(a,FancyArrowPatch):
   a.set_gid(f'img2code_connector_{n}');metadata.append({'gid':a.get_gid(),'type':type(a).__name__,'label':a.get_label()})
 for key in ('format',):kwargs.pop(key,None)
 with matplotlib.rc_context({'svg.fonttype':'none','svg.hashsalt':'img2code'}):
  original(fig,str(svg),format='svg',**kwargs);original(fig,str(png),format='png',**kwargs)
 captured.append({'svg':svg.name,'png':png.name,'connectors':metadata});(root/'captures.json').write_text(json.dumps(captured,indent=2))
Figure.savefig=capture
plt.show=lambda *a,**k:[capture(plt.figure(n)) for n in plt.get_fignums()]
status={}
try:
 source=(root/'source.py').read_text();namespace={'__name__':'__main__','__file__':'/work/source.py'};exec(compile(source,'/work/source.py','exec'),namespace)
 if (root/'data.json').exists() and callable(namespace.get('generate_diagram')):
  image=namespace['generate_diagram'](json.loads((root/'data.json').read_text()))
  if hasattr(image,'save'):image.save(root/'returned_image.png')
 if not captured:
  for n in plt.get_fignums():capture(plt.figure(n))
 status={'ok':bool(captured),'figures':len(captured),'captures':captured}
except BaseException as e:status={'ok':False,'figures':len(captured),'error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc()[-5000:]}
(root/'execution.json').write_text(json.dumps(status,indent=2));print(json.dumps(status));sys.exit(0 if status['ok'] else 1)
