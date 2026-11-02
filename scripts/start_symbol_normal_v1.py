from pathlib import Path
import subprocess,json
code=r'''from pathlib import Path
import subprocess,json,uuid,os,hashlib,sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S))
import compiler_svg_general_guard_v9 as core
cfg=core.configuration();parent=W/'compiler_svg_scene_frontend_v13/normal_development_v1'/uuid.uuid4().hex;parent.mkdir(parents=True)
owned={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [S/n for n in NAMES]}
freeze=parent/'freeze.json';freeze.write_text(json.dumps(dict(configuration=cfg,owned=owned),sort_keys=True,indent=2));freeze.chmod(0o444)
identifier='6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb';work=parent/identifier
command=['/home/shaoshitong/anaconda3/bin/python',str(S/'svg_native_symbol_viewport_normal_dev_v1.py'),identifier,str(work),str(freeze)]
wrapper=parent/'timed_run.py';wrapper.write_text(chr(10).join(['import subprocess,time,json','from pathlib import Path','t=time.monotonic()','r=subprocess.run('+repr(command)+')','Path('+repr(str(parent/'timing.json'))+').write_text(json.dumps(dict(elapsed_seconds=time.monotonic()-t,exit_code=r.returncode)))','']))
log=(parent/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(wrapper)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
receipt=dict(pid=p.pid,birth_ticks=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19],work=str(work),parent=str(parent),summary=str(work/'summary.json'),frozen_policy=cfg['policy']);print(json.dumps(receipt))
'''
names=['svg_source_symbol_viewport_v1.py','svg_source_symbol_viewport_v1.js','svg_dom_v9.js','svg_dom_source_scene_v4.js','svg_source_endpoint_bridge_v3.py','svg_source_use_instance_proof_v4.py','svg_source_use_instance_proof_v3.py','compiler_svg_scene_frontend_v13.py','compiler_svg_general_guard_v9.py','compiler_svg_general_quality_adapter_v10.py','compiler_svg_scene_quality_ro_v14.py','svg_native_symbol_viewport_normal_dev_v1.py']
code=code.replace('NAMES',repr(names))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=30)
print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/symbol-normal-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
