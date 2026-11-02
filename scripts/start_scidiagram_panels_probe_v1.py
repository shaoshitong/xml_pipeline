from pathlib import Path
import json,base64,subprocess
D=Path(__file__).parent;names=['scidiagram_panel_assets_v1.py','compiler_scidiagram_source_frontend_v1.py','probe_scidiagram_panels_v1.py'];payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code=r'''from pathlib import Path
import base64,subprocess,json,os,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
for name,value in json.loads(PAYLOAD).items():
 p=S/name;b=base64.b64decode(value)
 if p.exists():assert p.read_bytes()==b,name
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
w=R/'conversion/scidiagram_panel_probe_launch_v1'/uuid.uuid4().hex;w.mkdir(parents=True);log=(w/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(S/'probe_scidiagram_panels_v1.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));print(json.dumps(dict(pid=p.pid,work=str(w))))
'''.replace('PAYLOAD',repr(json.dumps(payload)));r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/scidiagram-panel-probe-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
