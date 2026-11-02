from pathlib import Path
import json,base64,subprocess
p=Path(__file__).with_name('scidiagram_source_preflight_v1.py');b64=base64.b64encode(p.read_bytes()).decode();code=r'''from pathlib import Path
import base64,subprocess,json,uuid,os
R=Path('/backup/shaoshitong/img2code_20261029');script=R/'conversion/scripts/scidiagram_source_preflight_v1.py';b=base64.b64decode(DATA)
if script.exists():assert script.read_bytes()==b
else:
 with script.open('xb')as f:f.write(b)
 script.chmod(0o444)
w=R/'conversion/scidiagram_source_preflight_v1'/uuid.uuid4().hex;w.mkdir(parents=True);root=R/'clean/priority_scidiagram_source_preflight_v1'/uuid.uuid4().hex;log=(w/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(script),str(root)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));receipt=dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],work=str(w),results=str(root));(w/'launch.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
'''.replace('DATA',repr(b64));r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/scidiagram-source-preflight-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
