import json,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');owner=W/'harness_v2_owner.json'
if owner.exists():
 o=json.loads(owner.read_text());p=Path('/proc')/str(o['pid'])/'cmdline';assert not (p.exists() and b'harness_pool_v2.py' in p.read_bytes()),'Harness v2 already running'
rows=json.loads((W/'harness_context_preflight.json').read_text());assert len(rows)==6 and all(r.get('ok') for r in rows);ids=[r['id'] for r in rows];path=W/'harness_v2_smoke_ids.json';path.write_text(json.dumps(ids))
with (W/'harness_v2.log').open('ab') as log:
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/harness_pool_v2.py'),'--workers','4','--ids-file',str(path)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'pid':p.pid,'workers':4,'selected':len(ids)}))
