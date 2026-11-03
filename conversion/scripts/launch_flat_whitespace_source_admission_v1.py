"""Once-only source admission for the complete new flat research source scope."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    import compiler_svg_general_guard_v20 as core
    screen=R/'clean/priority_svg_flat_source_screen_v1/da55c2ca71a24d7ab63d36c571ca963c';summary=json.loads((screen/'summary.json').read_text())
    p=screen/'additional_requests.jsonl';assert sha(p.read_bytes())==summary['files'][p.name]['sha256'];requests=[json.loads(l)for l in p.read_text().splitlines()];assert len(requests)==317
    receipt=screen/'source_admission_launch_v1.json';assert not receipt.exists(),'Observe existing owner; never duplicate an existing launch'
    pool=screen/'source_pool_v1';pool.mkdir(exist_ok=False)
    for r in requests:r['compiler_unit']=core.UNIT
    target=pool/'supported_population.jsonl';target.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in requests));target.chmod(0o444)
    script=S/'source_flat_whitespace_admission_v1.py';script.chmod(0o444);root=R/'conversion/source_flat_whitespace_admission_v1'/uuid.uuid4().hex
    result=subprocess.run([sys.executable,str(script),'create','--work',str(root),'--source-pool',str(pool)],capture_output=True,text=True);assert result.returncode==0,result.stderr
    with (root/'run.log').open('wb')as log:
        process=subprocess.Popen([sys.executable,str(script),'run','--work',str(root),'--workers','6','--timeout','120'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
    birth=Path('/proc',str(process.pid),'stat').read_text().rsplit(') ',1)[1].split()[19];out=dict(root=str(root),pid=process.pid,birth_ticks=birth,targets=317,workers=6,input_sha256=sha(target.read_bytes()),normal_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0,goal_complete=False);receipt.write_text(json.dumps(out,indent=2));receipt.chmod(0o444);print(json.dumps(out))
if __name__=='__main__':main()
