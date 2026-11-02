from pathlib import Path
import zipfile,json,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war');dest=R/'conversion/runtime/drawio_bundles';dest.mkdir(exist_ok=True)
for name in ['js/elk/drawio-elk.min.js','js/mermaid/drawio-mermaid.min.js']:
 b=z.read(name);(dest/Path(name).name).write_bytes(b);print(json.dumps({'file':name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}))
for name in ['js/diagramly/EditorUi.js','js/diagramly/Editor.js','js/diagramly/Dialogs.js']:
 try:t=z.read(name).decode()
 except KeyError:continue
 for term in ['parseMermaidDiagram =','mxMermaidToDrawio.parseText','mxMermaidToDrawio(']:
  pos=t.find(term)
  if pos>=0:print(json.dumps({'file':name,'term':term,'excerpt':t[max(0,pos-100):pos+5000]}))
