from pathlib import Path
Path('outputs').mkdir(parents=True,exist_ok=True)
import json,base64,subprocess
p=Path(__file__).with_name('svg_source_semantic_admission_audit_v1.py')
if not p.exists():p=Path(__file__).parent.parent/'conversion/scripts'/p.name
payload=base64.b64encode(p.read_bytes()).decode()
code=r'''from pathlib import Path
import json,base64,subprocess,sys,uuid,os
R=Path('/backup/shaoshitong/img2code_20261029');script=R/'conversion/scripts/svg_source_semantic_admission_audit_v1.py';b=base64.b64decode(DATA)
if script.exists():assert script.read_bytes()==b
else:
 with script.open('xb')as f:f.write(b)
 script.chmod(0o444)
work=R/'conversion/source_semantic_admission_audit_v1'/uuid.uuid4().hex
made=subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(script),'create','--work',str(work),'--source-pool',str(R/'release/compiler_iterations/source_pools/svg_complex_symbol_viewport_unseen100_20261102_v7')],capture_output=True,text=True);assert made.returncode==0,made.stderr
log=(work/'controller.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(script),'run','--work',str(work),'--workers','12','--timeout','120'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));receipt=dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],work=str(work),source_targets=json.loads(made.stdout)['targets'],candidate_emissions=0,normal_calls=0);(work/'launch.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
'''.replace('DATA',repr(payload));r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/source-semantic-admission-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
