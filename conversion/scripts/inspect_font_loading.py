import zipfile
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war');s=z.read('js/diagramly/Editor.js').decode()
for target in ['Graph.addFont =','Graph.createFontElement =','Graph.prototype.addExtFont =']:
 i=s.find(target);print(target);print(s[i:i+4500])
