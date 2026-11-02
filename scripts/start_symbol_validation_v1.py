from pathlib import Path
import subprocess,json,base64
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
names=['svg_analytic_source_contract_v4.py','svg_analytic_cohort_refresh_v4.py','svg_analytic_iteration_pool_v5.py','svg_analytic_iteration_case_v4.py','svg_analytic_iteration_batch_v4.py','svg_analytic_iteration_program_v4.py','svg_analytic_iteration_chain_v5.py','derive_symbol_complex_source_pool_v1.py','launch_symbol_validation_after_controls_v1.py']
payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code=r'''from pathlib import Path
import json,base64,subprocess,uuid,os
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
for n,v in json.loads(PAYLOAD).items():
 p=S/n;b=base64.b64decode(v)
 if p.exists():assert p.read_bytes()==b,n
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
work=R/'conversion/symbol_validation_launch_v1'/uuid.uuid4().hex;work.mkdir(parents=True);log=(work/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(S/'launch_symbol_validation_after_controls_v1.py'),'--work',str(work)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
receipt=dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],work=str(work));(work/'launch.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
'''.replace('PAYLOAD',repr(json.dumps(payload)))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/symbol-validation-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
