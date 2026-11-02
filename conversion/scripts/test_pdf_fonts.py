import json,sys
from pathlib import Path
from native_worker import W
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
from pdf_fonts import build_fonts
for item in json.loads((W/'tikz_pilot.json').read_text())['results']:
 doc=pymupdf.open(Path(item['directory'])/'source.pdf');fonts,traces=build_fonts(doc,doc[0],W/'pdf_native_pilot'/item['id']/'fonts');print(json.dumps({'id':item['id'],'fonts':[{k:v for k,v in f.items() if k not in ['uri','glyph_advances']} for f in fonts.values()],'traces':len(traces),'chars':sum(len(t['clusters']) for t in traces)}))
