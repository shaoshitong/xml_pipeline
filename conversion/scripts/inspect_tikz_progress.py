import json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';d=sqlite3.connect(W/'jobs.sqlite',timeout=60);owner=json.loads((W/'tikz_render_owner.json').read_text());p=Path('/proc')/str(owner['pid'])/'cmdline';print(json.dumps({'owner':owner,'command':p.read_bytes().replace(b'\0',b' ').decode() if p.exists() else '', 'states':dict(d.execute('select state,count(*) from jobs where format="tikz" group by state')),'dependencies':[{'name':x.name,**json.loads(x.read_text())} for x in (W/'tex_dependencies').glob('*.json')]}))
