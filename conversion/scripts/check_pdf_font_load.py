import json
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');r=json.loads((W/'pdf_native_pilot.json').read_text())['results'][0];print(json.dumps(r.get('render')));print(json.dumps(r.get('conversion')))
