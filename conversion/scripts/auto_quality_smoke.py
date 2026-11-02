import concurrent.futures,json,sqlite3,time
from pathlib import Path
from auto_quality_batch import verify
from native_worker import R,W,now
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);items=[];limits={'literal':4,'mermaid':3,'html':2,'svg':2,'python':1};counts={}
for id,fmt,state,raw,inp in D.execute("select id,format,state,output_record,input_record from jobs where output_record is not null and worker_pid is NULL and state in ('rendered','needs_quality_repair','harness_review_pending') order by coalesce(json_extract(output_record,'$.metrics.original_reference_ssim_512'),0) desc"):
 r=json.loads(raw);key='literal' if r.get('conversion_method')=='source_named_tikz_nodes_and_native_bound_paths_v1' else fmt
 if key not in limits or counts.get(key,0)>=limits[key]:continue
 if key in ('mermaid','html','svg','python') and not r.get('native_embedded_fonts'):continue
 if key in ('svg','python') and not r.get('source_coverage',{}).get('ok'):continue
 items.append((id,state,raw,inp,'graph' if key in ('literal','mermaid') else 'vector'));counts[key]=counts.get(key,0)+1
 if sum(counts.values())==sum(limits.values()):break
out=[]
with concurrent.futures.ProcessPoolExecutor(max_workers=4) as p:
 for item,report,candidate,work in p.map(verify,items):
  out.append(report);print(json.dumps({'id':report['id'],'state':report['state'],'failures':report['failures'],'seconds':report['seconds'],'visual':report['checks'].get('visual')}),flush=True)
x={'at':now(),'selected':counts,'counts':dict(__import__('collections').Counter(r['state'] for r in out)),'records':out,'published':False};(W/'auto_quality_smoke.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
