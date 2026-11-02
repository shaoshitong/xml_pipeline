from pathlib import Path
import sys,json,os,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import initial_conversion_process_v1 as process
work=W/'tikz_node_paint_controls_runner_v1'/uuid.uuid4().hex
result=process.run([sys.executable,'-B',str(W/'scripts/compiler_tikz_node_paint_controls_v1.py')],work,600,env={**os.environ,'PYTHONPATH':str(W/'scripts')+':'+str(R/'env'),'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
proof={key:result.get(key)for key in('ok','returncode','deadline_exceeded','cleanup_complete','root_process','seconds','stdout_file','stderr_file')};proof['normal_frontend_calls']=0
if result['ok']:proof['controls']=json.loads(Path(result['stdout_file']).read_text().splitlines()[-1])
(work/'summary.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof),flush=True)
