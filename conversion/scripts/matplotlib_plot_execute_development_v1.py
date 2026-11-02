from pathlib import Path
import hashlib,json,shutil,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_development_20261102_v1';sys.path.insert(0,str(R/'conversion/scripts'))
from sandbox_runner import run,PYTHON
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre=D/'sandbox_preflight';pre.mkdir(exist_ok=True)
check="import pathlib,socket,json,matplotlib,numpy;blocked=False\ntry:\n socket.create_connection(('1.1.1.1',80),timeout=1)\nexcept OSError:blocked=True\nprint(json.dumps({'private_visible':pathlib.Path('/backup/shaoshitong/img2code_20261029/conversion/private').exists(),'ssh_visible':pathlib.Path('/home/shaoshitong/.ssh').exists(),'network_blocked':blocked,'cwd':str(pathlib.Path.cwd()),'matplotlib':matplotlib.__version__,'numpy':numpy.__version__}))"
r=run(pre,[PYTHON,'-I','-c',check],timeout=30);assert r.returncode==0,r.stderr;proof=json.loads(r.stdout.strip().splitlines()[-1]);assert proof['network_blocked'] and not proof['private_visible'] and not proof['ssh_visible'] and proof['cwd']=='/work';(D/'sandbox_preflight.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'sandbox_preflight':proof}),flush=True)
cases=json.loads((D/'development_inputs.json').read_text())['cases'];results=[]
for audit in cases:
    case=D/'cases'/audit['id'];assert audit['safe_selfcontained_source'];assert sha(case/'source.py')==audit['source_code_sha256'];marker=case/'execution_once.json'
    if marker.exists():raise ValueError('development source execution once marker already exists')
    marker.write_text(json.dumps({'source_code_sha256':audit['source_code_sha256'],'sandbox_runner_sha256':sha(R/'conversion/scripts/sandbox_runner.py'),'capture_sha256':sha(R/'conversion/scripts/matplotlib_plot_capture_v1.py')})+'\n')
    shutil.copyfile(R/'conversion/scripts/matplotlib_plot_capture_v1.py',case/'capture.py');r=run(case,[PYTHON,'-I','/work/capture.py'],timeout=150);(case/'stdout.log').write_text(r.stdout);(case/'stderr.log').write_text(r.stderr)
    result=json.loads((case/'execution.json').read_text()) if (case/'execution.json').exists() else {'ok':False,'error':r.stderr[-3000:]};result={'id':audit['id'],'stratum':audit['development_stratum'],'returncode':r.returncode,'execution':result};results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
(D/'execution_summary.json').write_text(json.dumps({'cases':results,'model_calls':0,'all_source_executed_inside_existing_bwrap':True},ensure_ascii=False,indent=2)+'\n')
