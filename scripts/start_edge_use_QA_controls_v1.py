from pathlib import Path
Path('outputs').mkdir(parents=True,exist_ok=True)
import subprocess,json,base64
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'
names=['svg_analytic_iteration_controls_v6.py','svg_edge_layers_quality_control_v1.py']
payload={n:base64.b64encode((D/n).read_bytes()).decode()for n in names}
code=r'''from pathlib import Path
import subprocess,json,base64,uuid,os,hashlib,sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts'
for n,b64 in json.loads(PAYLOAD).items():
 p=S/n;b=base64.b64decode(b64)
 if p.exists():assert p.read_bytes()==b,n
 else:
  with p.open('xb')as f:f.write(b)
  p.chmod(0o444)
sys.path.insert(0,str(S));import compiler_svg_general_guard_v11 as core
import compiler_svg_general_quality_adapter_v13 as adapter
parent=W/'svg_edge_layers_quality_controls_v1'/uuid.uuid4().hex;parent.mkdir(parents=True)
freeze=parent/'freeze.json';freeze.write_text(json.dumps(dict(generation=core.configuration(),quality=adapter.configuration()),indent=2));freeze.chmod(0o444)
new=R/'clean/compiler_svg_scene_frontend_v14/6c/6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb/589d0df2a6394945a479028014430f5f/record.json'
old_control=json.loads((W/'svg_actual_shadow_controls_v2/0c186e2d354c4ac5bb01b8da61be6445/positive/case/summary.json').read_text());old=R/old_control['control']['candidate']['file']
rows=[]
for name,role,record in [('positive_symbol','positive',new),('positive_existing','positive',old),('negative_text','negative_text',new),('negative_geometry','negative_geometry',new),('negative_opacity','negative_opacity',new),('negative_order','negative_order',new)]:
 directory=parent/name;directory.mkdir();command=['/home/shaoshitong/anaconda3/bin/python',str(S/'svg_edge_layers_quality_control_v1.py'),'--record',str(record),'--work',str(directory/'case'),'--role',role]
 wrapper=directory/'run.py';wrapper.write_text(chr(10).join(['import subprocess,time,json','from pathlib import Path','t=time.monotonic()','r=subprocess.run('+repr(command)+')','Path('+repr(str(directory/'timing.json'))+').write_text(json.dumps(dict(elapsed_seconds=time.monotonic()-t,exit_code=r.returncode)))','']))
 log=(directory/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(wrapper)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
 rows.append(dict(name=name,pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],work=str(directory)))
receipt=dict(root=str(parent),cases=rows,generation_policy=core.configuration()['policy'],QA_policy=adapter.configuration()['policy'],new_normal_calls=0)
(parent/'launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''.replace('PAYLOAD',repr(json.dumps(payload)))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25)
print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/edge-use-QA-controls-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
