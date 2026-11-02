import collections,json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite',timeout=60);result={}
for name in ['text_batch','svg_batch_v2','python_render','python_drawio','tikz_render','html_batch','tex_dependency','harness_pool_retry']:
 o=json.loads((W/(name+'_owner.json')).read_text());p=Path('/proc')/str(o['pid'])/'cmdline';result[name]={'owner':o,'cmd':p.read_bytes().replace(b'\0',b' ').decode() if p.exists() else None}
result['states']=dict(db.execute('select state,count(*) from jobs group by state'));result['python_drawio_events']=sum(1 for _ in (W/'python_drawio_events.jsonl').open());result['html_events']=sum(1 for _ in (W/'html_batch_events.jsonl').open());result['tikz_prepared']=db.execute('select count(*) from tikz_renders where state="tikz_source_rendered"').fetchone()[0];result['tex_dependency_repairs']=db.execute('select count(*) from tikz_dependency_repairs').fetchone()[0];issues=collections.Counter();blocked=collections.Counter()
for raw, in db.execute('select output_record from jobs where format="html" and output_record is not null'):
 o=json.loads(raw);issues.update(i.get('reason',i.get('tag','unknown')) for i in o['unsupported_features']);blocked.update(o['blocked_source_resources'])
result['html_issues']=dict(issues);result['html_blocked']=dict(blocked.most_common(5));print(json.dumps(result))
