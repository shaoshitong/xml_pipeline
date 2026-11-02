import json,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');owner=json.loads((W/'tikz_drawio_owner.json').read_text());proc=Path('/proc')/str(owner['pid'])/'cmdline';assert not (proc.exists() and b'tikz_drawio_batch.py' in proc.read_bytes()),'existing consumer live'
with (W/'tikz_drawio_batch.log').open('ab') as log:
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/tikz_drawio_batch.py'),'--workers','8'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'launched_pid':p.pid,'workers':8}))
