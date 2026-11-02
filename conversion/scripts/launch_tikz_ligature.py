import json,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');f=W/'tikz_ligature_owner.json'
if f.exists():
 owner=json.loads(f.read_text());p=Path('/proc')/str(owner['pid'])/'cmdline';assert not (p.exists() and b'tikz_ligature_repair.py' in p.read_bytes()),'ligature repair already live'
with (W/'tikz_ligature_repair.log').open('ab') as log:
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/tikz_ligature_repair.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'pid':p.pid,'workers':2}))
