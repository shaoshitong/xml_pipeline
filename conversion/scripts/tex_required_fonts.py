import concurrent.futures,json,os,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');T=W/'runtime/tectonic';env=dict(os.environ,XDG_CACHE_HOME=str(T/'cache'),TECTONIC_CACHE_DIR=str(T/'cache'));names=[f'{f}{n}.{e}' for f in ['cmmib','cmbsy'] for n in [5,7,10] for e in ['tfm','pfb']]+['lmsans10-bold.otf','lmsans10-oblique.otf','lmsans10-boldoblique.otf','lmroman10-bolditalic.otf']
def fetch(name):
 r=subprocess.run([str(T/'tectonic'),'-X','bundle','cat',name],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=120);return {'name':name,'returncode':r.returncode,'error':r.stderr[-500:] if r.returncode else None}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(fetch,names))
(W/'tex_required_fonts.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results),flush=True)
r=subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/tikz_pilot.py')],env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=(W/'tikz_pilot.log').open('w'),stderr=subprocess.STDOUT);print(json.dumps({'pilot_exit_code':r.returncode}),flush=True)
