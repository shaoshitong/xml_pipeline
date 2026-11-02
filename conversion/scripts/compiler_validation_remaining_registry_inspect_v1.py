from pathlib import Path
import sqlite3,json
R=Path('/backup/shaoshitong/img2code_20261029');p=R/'release/compiler_v1/validation_registry.sqlite';d=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=30)
out={'registry':str(p),'tables':{}}
for name,ddl in d.execute('select name,sql from sqlite_master where type="table"').fetchall():
 out['tables'][name]={'columns':[r[1:3] for r in d.execute('pragma table_info('+name+')')],'rows':d.execute('select count(*) from '+name).fetchone()[0],'ddl':ddl}
f=R/'release/manifest.jsonl';r=json.loads(next(f.open()));out['manifest']={'bytes':f.stat().st_size,'keys':sorted(r)}
print(json.dumps(out))
