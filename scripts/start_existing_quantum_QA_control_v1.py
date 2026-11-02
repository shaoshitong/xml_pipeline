import json,subprocess
from pathlib import Path
code=r'''from pathlib import Path
import subprocess,os,json
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts'
parent=W/'svg_native_symbol_quality_controls_v1/ac7eaf1787c2464dabdeeb4f82e85018';d=parent/'positive_prior';d.mkdir(exist_ok=False)
normal=json.loads((W/'compiler_svg_scene_frontend_v12/normal_development_v5/7a070524878d4c838af26b32466a54c6/0dc3f8bb2a134a79aba055dc8cc6686f7d097b187bd08267a5bdc4f8d8bd633e/summary.json').read_bytes());record=normal['candidate_file'];command=['/home/shaoshitong/anaconda3/bin/python',str(S/'svg_native_symbol_quality_control_v1.py'),'--record',record,'--work',str(d/'case'),'--role','positive'];wrapper=d/'run.py';wrapper.write_text(chr(10).join(['import subprocess,time,json','from pathlib import Path','t=time.monotonic()','r=subprocess.run('+repr(command)+')','Path('+repr(str(d/'timing.json'))+').write_text(json.dumps(dict(elapsed_seconds=time.monotonic()-t,exit_code=r.returncode)))','']));log=(d/'output.log').open('wb');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(wrapper)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'));print(json.dumps(dict(pid=p.pid,work=str(d),normal_conversion_calls=0)))
'''
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20);print(r.stdout);print(r.stderr);raise SystemExit(r.returncode)
