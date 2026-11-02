import json
from native_worker import W
from sandbox_runner import run,PYTHON
p=W/'sandbox_selfcheck';p.mkdir(exist_ok=True)
code='import os,json,socket; print(json.dumps({"private_visible":os.path.exists("/backup/shaoshitong/img2code_20261029/conversion/private"),"real_home_visible":os.path.exists("/home/shaoshitong/.ssh"),"net_namespace":os.readlink("/proc/self/ns/net"),"cwd":os.getcwd()}));import matplotlib,numpy,PIL;print("drawing_imports_ok")'
r=run(p,[PYTHON,'-I','-c',code]);out={'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(W/'sandbox_selfcheck.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
