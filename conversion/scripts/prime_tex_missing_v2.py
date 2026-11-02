import concurrent.futures,json,sqlite3
from native_worker import W,now
from tex_missing_v2 import missing_files
from tectonic_compile import fetch
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True)
rows=d.execute('select id,error from jobs where format="tikz" and state="needs_fallback"').fetchall()
names=sorted({n for _,e in rows for n in missing_files(e or '')})
def safe_fetch(n):
    try:return fetch(n)
    except Exception as e:return {'name':n,'ok':False,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(safe_fetch,names))
ready={r['name'] for r in results if r['ok']}
report={'at':now(),'file_count':len(names),'fetched_count':len(ready),'results':results,'fully_resolved_recorded_dependencies':sum(bool(n:=missing_files(e or '')) and set(n)<=ready for _,e in rows),'goal_complete':False}
(W/'tex_missing_v2_prime.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='results'}|{'failed':[r for r in results if not r['ok']]}),flush=True)
