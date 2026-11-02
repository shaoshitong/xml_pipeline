from pathlib import Path
import argparse,hashlib,json,shutil,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_development_20261102_v1';sys.path.insert(0,str(R/'conversion/scripts'))
from sandbox_runner import run,PYTHON
p=argparse.ArgumentParser();p.add_argument('id');args=p.parse_args();case=D/'cases'/args.id;a=json.loads((case/'input_audit.json').read_text());assert a['safe_selfcontained_source'];assert hashlib.sha256((case/'source.py').read_bytes()).hexdigest()==a['source_code_sha256'];marker=case/'execution_once.json'
with marker.open('x') as f:json.dump({'source_code_sha256':a['source_code_sha256'],'sandbox_runner_sha256':hashlib.sha256((R/'conversion/scripts/sandbox_runner.py').read_bytes()).hexdigest(),'capture_sha256':hashlib.sha256((R/'conversion/scripts/matplotlib_plot_capture_v1.py').read_bytes()).hexdigest()},f)
shutil.copyfile(R/'conversion/scripts/matplotlib_plot_capture_v1.py',case/'capture.py');r=run(case,[PYTHON,'-I','/work/capture.py'],timeout=150);(case/'stdout.log').write_text(r.stdout);(case/'stderr.log').write_text(r.stderr);result=json.loads((case/'execution.json').read_text()) if (case/'execution.json').exists() else {'ok':False,'error':r.stderr[-3000:]};print(json.dumps({'id':args.id,'returncode':r.returncode,'execution':result},ensure_ascii=False))
