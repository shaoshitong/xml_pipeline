import json,sys
from pathlib import Path
from native_worker import R,W
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
it=json.loads((W/'tikz_pilot.json').read_text())['results'][0];page=pymupdf.open(Path(it['directory'])/'source.pdf')[0]
print(json.dumps(page.get_drawings(),default=lambda x:list(x)))
