"""Launch exactly one isolated actual normal for the new stroke-support core."""
from pathlib import Path
import json,subprocess
D=Path(__file__).parent
names=['svg_source_stroke_support_v2.py','svg_source_edge_layers_v10.py','compiler_svg_scene_backend_v14.py','compiler_svg_scene_frontend_v19.py','compiler_svg_general_guard_v15.py','svg_rotated_source_visual_scope_v2.py','compiler_svg_general_quality_adapter_v21.py','compiler_svg_scene_quality_ro_v25.py','svg_background_stroke_support_normal_dev_v1.py']
files={n:(D/n).read_text()for n in names}
code='''from pathlib import Path
import json,os,subprocess,sys,uuid,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
'''+ 'files='+repr(files)+'''
for n,s in files.items():
 p=S/n
 if p.exists():assert p.read_text()==s,n
 else:p.write_text(s);p.chmod(0o444)
sys.path.insert(0,str(S));import compiler_svg_general_guard_v15 as core
cfg=core.configuration();identifier='e99263f5c4b6270d48ae6892ef8440c3f3bb6a6280f13094d188f4327b5d6c84'
from compiler_source_core_attempts_v3 import core_identity
identity=core_identity(cfg);claim=R/'conversion'/core.VERSION/'normal_once'/identity['key']/(identifier+'.json');assert not claim.exists(),'normal_already_claimed_never_restart'
parent=R/'conversion/background_stroke_support_normal_development_v1'/uuid.uuid4().hex;parent.mkdir(parents=True);work=parent/identifier;freeze=parent/'freeze.json';freeze.write_text(json.dumps(dict(configuration=cfg,owned={n:hashlib.sha256((S/n).read_bytes()).hexdigest()for n in files}),indent=2));freeze.chmod(0o444)
command=[sys.executable,str(S/'svg_background_stroke_support_normal_dev_v1.py'),identifier,str(work),str(freeze)]
wrapper=parent/'run.py';wrapper.write_text('import subprocess,time,json\\nfrom pathlib import Path\\nt=time.monotonic()\\nr=subprocess.run('+repr(command)+')\\nPath('+repr(str(parent/'timing.json'))+').write_text(json.dumps(dict(elapsed_seconds=time.monotonic()-t,exit_code=r.returncode)))\\n')
log=(parent/'output.log').open('wb');p=subprocess.Popen([sys.executable,str(wrapper)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
print(json.dumps(dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],parent=str(parent),work=str(work),policy=cfg['policy'],source_core=identity,normal_calls_planned=1,model_calls=0,existing_mass_unchanged=True)))
'''
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25)
assert r.returncode==0,r.stderr
d=json.loads(r.stdout);Path('outputs/background-stroke-support-normal-launch.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
