from pathlib import Path
import sys,json,os,uuid,datetime
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import initial_conversion_process_v1 as process
root=W/'tikz_node_paint_normal_development_v2/67924c6fa8f74a1bb3893d9af058df0d'
work=W/'tikz_node_paint_QA5_existing_dev_run_v1'/uuid.uuid4().hex;work.mkdir(parents=True,exist_ok=False)
ids=('8689389d1f64000151962180f407dadaaef208bb7dfcf18b5746f14d9826cd17','0593a28ecc6e324f9bd19cdd673619ddf61a96328c03b396f26ec8dfc3f5e693')
rows=[]
precision=process.run([sys.executable,'-B',str(W/'scripts/tikz_node_paint_editing_precision_actual_controls_v1.py')],work/'editing_precision_controls',600,env={**os.environ,'PYTHONPATH':str(W/'scripts')+':'+str(R/'env'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
if not precision['ok']:
 print(json.dumps(dict(stage='editing_precision_control_requires_generic_repair',process=precision,normal_frontend_calls=0,goal_complete=False)),flush=True);raise RuntimeError('editing_precision_control_failed')
precision_ref=json.loads(Path(precision['stdout_file']).read_text().splitlines()[-1]);assert Path(precision_ref['file']).exists()
for identifier in ids:
 child=root/identifier
 if(child/'QA5_existing_candidate_summary.json').exists():raise FileExistsError('QA5_existing_already_called:'+identifier)
 result=process.run([sys.executable,'-B',str(W/'scripts/tikz_node_paint_QA5_existing_dev.py'),str(child)],work/identifier,600,env={**os.environ,'PYTHONPATH':str(W/'scripts')+':'+str(R/'env'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
 row={key:result.get(key)for key in ('ok','returncode','deadline_exceeded','cleanup_complete','root_process','seconds')};row['id']=identifier
 if(child/'QA5_existing_candidate_summary.json').exists():row['quality']=json.loads((child/'QA5_existing_candidate_summary.json').read_bytes())
 rows.append(row);print(json.dumps(row),flush=True)
summary=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),work=str(work),results=rows,editing_precision_controls=precision_ref,normal_frontend_calls=0,model_calls=0,goal_complete=False)
with(work/'summary.json').open('xb')as stream:stream.write((json.dumps(summary,indent=2)+'\n').encode())
print(json.dumps(summary),flush=True)
