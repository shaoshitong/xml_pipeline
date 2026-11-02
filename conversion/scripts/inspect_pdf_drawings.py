import json,sys
from pathlib import Path
from native_worker import W
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
for item in json.loads((W/'tikz_pilot.json').read_text())['results']:
 p=pymupdf.open(Path(item['directory'])/'source.pdf')[0];print(json.dumps({'id':item['id'],'drawings':p.get_drawings(extended=True)[:5],'bboxlog':p.get_bboxlog()[:8]},default=lambda x:list(x)))
