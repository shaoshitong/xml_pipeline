import json,sys,zipfile
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');R=W.parent;sys.path.append(str(W/'runtime/python_packages'));import pymupdf
for item in json.loads((W/'tikz_pilot.json').read_text())['results']:
 doc=pymupdf.open(Path(item['directory'])/'source.pdf');p=doc[0];print(json.dumps({'id':item['id'],'fonts':p.get_fonts(full=True),'text':p.get_text()[:1300],'span_fonts':sorted({s['font'] for b in p.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']}),'svg_head':(Path(item['directory'])/'page0.svg').read_text()[:1800]}))
z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war');hits=[]
for name in z.namelist():
 if name.endswith('.js') and not '.min.' in name and name.startswith('js/'):
  s=z.read(name).decode(errors='replace')
  if 'customFonts' in s:
   start=0
   while True:
    i=s.find('customFonts',start)
    if i<0:break
    hits.append({'file':name,'snippet':s[max(0,i-130):i+380]});start=i+11
    if len(hits)>25:break
  if len(hits)>25:break
print(json.dumps({'custom_font_hits':hits}))
