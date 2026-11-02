import json,sqlite3
from native_worker import W
D=sqlite3.connect(W/'jobs.sqlite');out=[];ids=[]
for source, in D.execute('select distinct source from jobs where format="tikz" and state="tikz_source_rendered" order by source').fetchall():
 rows=D.execute('select id from jobs where format="tikz" and state="tikz_source_rendered" and source=? order by id limit 2',(source,)).fetchall();ids.extend(r[0] for r in rows);out.append({'source':source,'ids':[r[0] for r in rows]})
(W/'tikz_native_smoke_ids.json').write_text(json.dumps(ids));print(json.dumps(out))
