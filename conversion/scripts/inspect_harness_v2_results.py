import json,sqlite3
from native_worker import R,W
D=sqlite3.connect(W/'jobs.sqlite');results=[]
for id,state,session,error in D.execute('select id,state,session_dir,error from harness_queue_v2'):
 work=R/session if session else None;r=json.loads((work/'summary.json').read_text()) if work and (work/'summary.json').exists() else {};out_raw=D.execute('select output_record,state,input_manifest from jobs where id=?',(id,)).fetchone();out=json.loads(out_raw[0]) if out_raw[0] else {};item={'id':id,'queue':state,'job_state':out_raw[1],'error':error,'rounds':[{'round':x['round'],'pass':x.get('critic_and_structure_pass'),'error':x.get('error'),'judge':x.get('judge')} for x in r.get('rounds',[])],'baseline':r.get('baseline',{}).get('judge'),'result_state':r.get('result_state'),'vertices':out.get('vertices'),'edges':out.get('edges'),'assets':len(out.get('used_assets',[])),'metrics':out.get('metrics')}
 if id.startswith('004880'):item['source']=(R/json.loads(out_raw[2])['source_code']).read_text()
 results.append(item)
print(json.dumps(results,ensure_ascii=False))
