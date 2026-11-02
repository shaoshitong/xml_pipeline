import json
from native_worker import W
id='0001784b9f3b28598732c2dc034369bd2dc5274e31e8a2a945bb3bc4a6fb15c2'
for path in [W/'pdf_native_pilot'/id/'summary.json',W/'pdf_native_connected_pilot'/id/'verification.json']:
 r=json.loads(path.read_text());print(path.name,json.dumps(r['render']))
