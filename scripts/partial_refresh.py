"""Refresh the available-data snapshot; never declares collection complete."""
import fcntl,json,os,subprocess,time
from pathlib import Path
root=Path('/backup/shaoshitong/img2code_20261029');scripts=root/'scripts'
import sys;sys.path.insert(0,str(scripts));from collection_supervisor import owned_processes
lock=(root/'supervisor/partial-refresh.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
env=dict(os.environ,PYTHONPATH=str(root/'env'));python='/home/shaoshitong/anaconda3/bin/python'
status=root/'reports/partial_refresh_status.json'
def emit(**item):
    value={'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'pid':os.getpid(),'final_collection':False,**item}
    temp=status.with_suffix('.json.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(status);print(json.dumps(value),flush=True)
for script in ['curate_pairs.py','curate_archives.py','finalize_catalog.py','audit_provenance_qc.py','audit_catalog_content.py']:
    if script=='finalize_catalog.py':
        while owned_processes('curate_derived.py',root) or owned_processes('curate_native_sources.py',root):
            emit(stage='waiting_current_derived_snapshot',pids=owned_processes('curate_derived.py',root)+owned_processes('curate_native_sources.py',root));time.sleep(30)
    if owned_processes(script,root):raise RuntimeError('matching curator already running: '+script)
    emit(stage='started',script=script)
    with (root/'logs'/('partial-refresh-'+script+'.log')).open('w') as log:
        result=subprocess.run([python,str(scripts/script),'--root',str(root)],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    emit(stage='finished_stage',script=script,exit_code=result.returncode)
    if result.returncode:raise SystemExit(result.returncode)
emit(stage='available_snapshot_refreshed',note='Selected bulk and RAP downloads still require completion and a fresh final seven-stage pass.')
