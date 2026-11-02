import json
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');s=json.loads((R/'conversion/html_pilot.json').read_text());d=json.loads((Path(s['directory'])/'dom.json').read_text());print(json.dumps({'document_size':[d['width'],d['height']],'objects_outside':[{k:o.get(k) for k in ('id','type','x','y','w','h','text','fontSize')} for o in d['objects'] if o['x']<0 or o['y']<0 or o['x']+o['w']>4800 or o['y']+o['h']>2880]},ensure_ascii=False))
