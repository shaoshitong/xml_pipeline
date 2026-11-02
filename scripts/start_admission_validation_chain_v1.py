from pathlib import Path
Path('outputs').mkdir(parents=True,exist_ok=True)
import base64,subprocess,json
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
names=['svg_analytic_source_contract_v5.py','svg_analytic_cohort_refresh_v5.py','svg_analytic_iteration_pool_v6.py','svg_analytic_iteration_case_v5.py','svg_analytic_iteration_batch_v5.py','svg_analytic_iteration_program_v5.py','svg_analytic_iteration_chain_v6.py','derive_semantic_complex_source_pool_v1.py','launch_after_semantic_admission_v1.py'];payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code=r'''from pathlib import Path
import base64,subprocess,json,uuid,os
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
for name,value in json.loads(PAYLOAD).items():
 p=S/name;b=base64.b64decode(value)
 if p.exists():assert p.read_bytes()==b,name
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
w=R/'conversion/semantic_admission_validation_launch_v1'/uuid.uuid4().hex;w.mkdir(parents=True);log=(w/'output.log').open('wb');audit=R/'conversion/source_semantic_admission_audit_v1/e430695f8e8042d3bf1b4426ca99b423';p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(S/'launch_after_semantic_admission_v1.py'),'--work',str(w),'--audit',str(audit)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));receipt=dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],work=str(w),audit=str(audit));(w/'launch.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
'''.replace('PAYLOAD',repr(json.dumps(payload)));r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/admission-validation-chain-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
