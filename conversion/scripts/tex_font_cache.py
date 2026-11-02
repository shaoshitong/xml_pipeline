import concurrent.futures,json,os,re,subprocess,time
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');runtime=W/'runtime/tectonic';env=dict(os.environ,XDG_CACHE_HOME=str(runtime/'cache'),TECTONIC_CACHE_DIR=str(runtime/'cache'));binary=str(runtime/'tectonic');names=set()
names.update(f'lmroman{n}-{style}.otf' for n in [5,6,7,8,9,10,12,17] for style in ['regular','bold','italic'])
names.update(f'lmsans{n}-regular.otf' for n in [8,9,10,12,17])
names.update(f'{family}{n}.{ext}' for family in ['cmr','cmbx','cmmi','cmsy','cmex','cmss','cmtt'] for n in [5,7,10] for ext in ['tfm','pfb'])
print(json.dumps({'selected_fonts':len(names),'names':sorted(names)}),flush=True)
def fetch(name):
 r=subprocess.run([binary,'-X','bundle','cat',name],env=env,cwd=runtime/'warmup',stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=120);return {'name':name,'returncode':r.returncode,'error':r.stderr[-1000:] if r.returncode else None}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(fetch,sorted(names)))
report={'selected':len(names),'failed':[r for r in results if r['returncode']],'ok':bool(names) and not any(r['returncode'] for r in results),'finished_unix':time.time()};(W/'tex_font_cache.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if results:
 r=subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/tikz_pilot.py')],env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=(W/'tikz_pilot.log').open('w'),stderr=subprocess.STDOUT);print(json.dumps({'tikz_pilot_returncode':r.returncode}),flush=True)
