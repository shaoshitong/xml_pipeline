import json,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');f=W/'mermaid_semantic_v3_owner.json'
if f.exists():
 o=json.loads(f.read_text());p=Path('/proc')/str(o['pid'])/'cmdline';assert not(p.exists() and b'mermaid_semantic_audit_v3.py' in p.read_bytes()),'v3 audit already active'
assert json.loads((W/'mermaid_groups_v3_tests.json').read_text())['ok']
with (W/'mermaid_semantic_v3.log').open('ab') as log:
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/mermaid_semantic_audit_v3.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'pid':p.pid,'purpose':'full Mermaid source node/edge/text/group-membership audit','automatic_acceptance':False}))
