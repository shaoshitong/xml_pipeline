import concurrent.futures,json,sqlite3
from pathlib import Path
from auto_quality_batch_v2 import verify
from native_worker import R,W,now
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);cases=json.loads((W/'auto_quality_canvas_repair_preflight_tests.json').read_text())['cases'];items=[]
for case in cases:
 r=json.loads((R/case['contract']['origin_record']).read_text());state,inp=D.execute('select state,input_record from jobs where id=?',(r['id'],)).fetchone();items.append((r['id'],state,json.dumps(r,ensure_ascii=False),inp,'graph' if r['source_format']=='mermaid' else 'vector'))
results=[]
with concurrent.futures.ProcessPoolExecutor(max_workers=3) as p:
 for item,report,out,work in p.map(verify,items):
  results.append(report);print(json.dumps({'id':report['id'],'state':report['state'],'failures':report['failures'],'checks':list(report['checks']),'seconds':report['seconds']}),flush=True)
r={'at':now(),'records':results,'source_and_registration_and_fresh_canvas_pass':all(x['checks'].get('source',{}).get('ok') and x['checks'].get('render',{}).get('strict_outside_page_pixels')==0 for x in results),'published':False};(W/'auto_quality_v2_preflight.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
