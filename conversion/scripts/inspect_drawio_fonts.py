import json,zipfile
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war')
for name in ['js/diagramly/Editor.js','js/viewer-static.js','js/diagramly/Graph.js','js/diagramly/GraphViewer.js']:
 if name not in z.namelist():continue
 s=z.read(name).decode(errors='replace');hits=[]
 for target in ['Graph.isAllowedFontUrl =','Graph.prototype.addExtFont =','fontSource','extFonts','data-font-src']:
  at=0
  for _ in range(3):
   i=s.find(target,at)
   if i<0:break
   hits.append(s[max(0,i-180):i+1400]);at=i+len(target)
 print(json.dumps({'file':name,'hits':hits}))
