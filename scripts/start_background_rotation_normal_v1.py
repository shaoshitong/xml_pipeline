from pathlib import Path
import subprocess,base64,json
Path('outputs').mkdir(parents=True,exist_ok=True)
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v17.py').exists():D=D.parent/'conversion/scripts'
names=['svg_source_edge_layers_v9.py','compiler_svg_scene_backend_v13.py','compiler_svg_scene_frontend_v17.py','compiler_svg_general_guard_v13.py','compiler_svg_general_quality_adapter_v15.py','compiler_svg_scene_quality_ro_v19.py','svg_source_background_rotation_normal_dev_v1.py']
payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code=r'''from pathlib import Path
import base64,subprocess,json,uuid,os,sys,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts'
for name,value in json.loads(PAYLOAD).items():
 p=S/name;b=base64.b64decode(value)
 if p.exists():assert p.read_bytes()==b,name
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
sys.path.insert(0,str(S));import compiler_svg_general_guard_v13 as compiler
cfg=compiler.configuration();parent=W/compiler.VERSION/'normal_development_v1'/uuid.uuid4().hex;parent.mkdir(parents=True);identifier='957add973f1b7dfb1275150c907ef140763cf2fb0114919a20d5bb687d647c5a';work=parent/identifier;freeze=parent/'freeze.json';freeze.write_text(json.dumps(dict(configuration=cfg,owned={n:hashlib.sha256((S/n).read_bytes()).hexdigest()for n in NAMES}),indent=2));freeze.chmod(0o444)
command=['/home/shaoshitong/anaconda3/bin/python',str(S/'svg_source_background_rotation_normal_dev_v1.py'),identifier,str(work),str(freeze)];wrapper=parent/'run.py';wrapper.write_text(chr(10).join(['import subprocess,time,json','from pathlib import Path','t=time.monotonic()','r=subprocess.run('+repr(command)+')','Path('+repr(str(parent/'timing.json'))+').write_text(json.dumps(dict(elapsed_seconds=time.monotonic()-t,exit_code=r.returncode)))','']));log=(parent/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(wrapper)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));receipt=dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],parent=str(parent),work=str(work),policy=cfg['policy']);print(json.dumps(receipt))
'''.replace('PAYLOAD',repr(json.dumps(payload))).replace('NAMES',repr(names))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25);print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/background-rotation-normal-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
