import zipfile
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war')
for n in z.namelist():
 if n.endswith('mxMarker.js'):
  s=z.read(n).decode();print(n);print(s[:20000])
