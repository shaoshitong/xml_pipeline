from pathlib import Path
import subprocess,json,base64
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
names=['svg_source_symbol_viewport_v1.py','svg_source_symbol_viewport_v1.js','svg_dom_v9.js','svg_dom_source_scene_v4.js','svg_source_endpoint_bridge_v3.py','svg_source_use_instance_proof_v4.py','compiler_svg_scene_frontend_v13.py','compiler_svg_general_guard_v9.py','compiler_svg_general_quality_adapter_v10.py','compiler_svg_scene_quality_ro_v14.py','svg_native_symbol_viewport_normal_dev_v1.py']
payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code="""from pathlib import Path
import json,base64,hashlib
D=Path('/backup/shaoshitong/img2code_20261029/conversion/scripts')
payload=json.loads(PAYLOAD)
for name,value in payload.items():
 p=D/name;b=base64.b64decode(value)
 if p.exists():assert p.read_bytes()==b,name
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
print(json.dumps({n:hashlib.sha256((D/n).read_bytes()).hexdigest() for n in payload}))
""".replace('PAYLOAD',repr(json.dumps(payload)))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=45)
print(r.stdout);print(r.stderr);raise SystemExit(r.returncode)
