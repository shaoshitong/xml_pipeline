import json,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');assert json.loads((W/'harness_v3_preflight.json').read_text())['ok']
owner=W/'harness_v3_owner.json'
if owner.exists():
 o=json.loads(owner.read_text());p=Path('/proc')/str(o['pid'])/'cmdline';assert not (p.exists() and b'harness_pool_v3.py' in p.read_bytes()),'Harness v3 already running'
with (W/'harness_v3.log').open('ab') as log:
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/harness_pool_v3.py'),'--workers','8','--seed-all'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'pid':p.pid,'workers':8,'scope':'All currently eligible failures and independent Mermaid v3 mismatches, excluding active or accepted jobs; no automatic final acceptance.'}))
