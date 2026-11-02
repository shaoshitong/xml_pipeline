"""Offline corpus compilation, with separately fetched validated bundle dependencies."""
import fcntl,json,os,re,subprocess
from pathlib import Path
from native_worker import W,now
from sandbox_runner import run
RUNTIME=W/'runtime/tectonic';CACHE=RUNTIME/'cache'
ENV={'XDG_CACHE_HOME':str(CACHE),'TECTONIC_CACHE_DIR':str(CACHE)}

def missing_files(text):
 found=set(re.findall(r"File [`']([A-Za-z0-9_.-]+)' not found",text))
 for name in re.findall(r"did not find the tikz library '([A-Za-z0-9_.-]+)'",text):found.add('tikzlibrary'+name+'.code.tex')
 for name in re.findall(r"\[([A-Za-z0-9_.-]+)\]:[^\n]*not loadable",text):found.add(name+'.otf' if not name.endswith('.otf') else name)
 for name in re.findall(r"Font [^\n=]+=?([A-Za-z][A-Za-z0-9_.-]+) at [^\n]*not loadable",text):found.add(name+'.tfm')
 return sorted(x for x in found if len(x)<180 and not x.startswith('.') and x.endswith(('.sty','.cls','.clo','.tex','.fd','.def','.tfm','.otf','.ttf','.map','.enc','.pfb')))

def fetch(name):
 assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,179}',name)
 directory=W/'tex_dependencies';directory.mkdir(exist_ok=True);receipt=directory/(name+'.json')
 with (directory/(name+'.lock')).open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if receipt.exists():return json.loads(receipt.read_text())
  r=subprocess.run([str(RUNTIME/'tectonic'),'-X','bundle','cat',name],env=dict(os.environ,**ENV),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=120)
  result={'name':name,'ok':r.returncode==0,'returncode':r.returncode,'stderr_tail':r.stderr[-2000:],'fetched_at_utc':now(),'source':'configured official Tectonic bundle; no source code execution'};receipt.write_text(json.dumps(result,indent=2)+'\n');return result

def compile_case(directory,max_rounds=12):
 attempts=[];seen=set()
 for number in range(max_rounds):
  r=run(directory,[str(RUNTIME/'tectonic'),'--untrusted','--only-cached','--keep-logs','--keep-intermediates','/work/source.tex'],timeout=150,extra_ro=[(RUNTIME,RUNTIME)],extra_env=ENV);(directory/f'compile_{number}.stdout').write_text(r.stdout);(directory/f'compile_{number}.stderr').write_text(r.stderr);entry={'round':number,'returncode':r.returncode};attempts.append(entry)
  if r.returncode==0:break
  names=[name for name in missing_files(r.stdout+'\n'+r.stderr) if name not in seen];seen.update(names)
  if not names:break
  entry['dependencies']=[fetch(n) for n in names]
  if not any(x['ok'] for x in entry['dependencies']):break
 (directory/'compile_attempts.json').write_text(json.dumps(attempts,indent=2)+'\n');return r,attempts
