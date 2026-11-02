from pathlib import Path
Path('outputs').mkdir(parents=True,exist_ok=True)
import base64,subprocess,json
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
names=['svg_source_use_instance_proof_v6.py','compiler_svg_scene_frontend_v15.py','compiler_svg_general_guard_v11.py','compiler_svg_general_quality_adapter_v13.py','compiler_svg_scene_quality_ro_v17.py','svg_source_owned_edge_layers_normal_dev_v2.py','probe_group_use_identity_v2.py'];payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code=r'''from pathlib import Path
import subprocess,json,base64,uuid,os
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
for name,v in json.loads(PAYLOAD).items():
 p=S/name;b=base64.b64decode(v)
 if p.exists():assert p.read_bytes()==b,name
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
root=R/'conversion/source_group_use_regression_v2'/uuid.uuid4().hex;root.mkdir(parents=True);rows=[]
for identifier in ['370f90e239f70d61382140119f4a278bb211fca5fe98c099b8aa729f41a7fe72','94dc3c232823f1a34cb01ffadf3ef9be71d3978e245afe7f346ff4d02cb635f0','6bfea54fe17b524d3a15883bce122ceb1592312810394cafa67a9905cc339dce']:
 log=(root/(identifier+'.log')).open('wb');child=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(S/'probe_group_use_identity_v2.py'),'--id',identifier,'--work',str(root/identifier)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));rows.append(dict(id=identifier,pid=child.pid))
print(json.dumps(dict(root=str(root),cases=rows)))
'''.replace('PAYLOAD',repr(json.dumps(payload)))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/untouched-use-probe-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
