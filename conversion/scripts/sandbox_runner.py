"""Run untrusted drawing source with only explicit read-only runtimes and case files."""
import os,resource,subprocess
from pathlib import Path
PYTHON='/home/shaoshitong/anaconda3/bin/python'
def command(directory,argv,extra_ro=(),extra_env=None):
 cmd=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--clearenv','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64','--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/home','--dir','/home/shaoshitong','--dir','/home/sandbox','--ro-bind','/home/shaoshitong/anaconda3','/home/shaoshitong/anaconda3','--dir','/etc']
 for p in ['/etc/fonts','/etc/ld.so.cache','/etc/localtime']:
  if Path(p).exists():cmd+=['--ro-bind',p,p]
 for src,dest in extra_ro:cmd+=['--ro-bind',str(src),str(dest)]
 cmd+=['--bind',str(directory),'/work','--chdir','/work']
 for k,v in ({'HOME':'/home/sandbox','PATH':'/home/shaoshitong/anaconda3/bin:/usr/bin:/bin','MPLCONFIGDIR':'/tmp/mpl','MPLBACKEND':'Agg','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONNOUSERSITE':'1','LANG':'C.UTF-8','XDG_CACHE_HOME':'/tmp/cache'} | (extra_env or {})).items():cmd+=['--setenv',k,v]
 return cmd+['--']+list(argv)
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(90,100));resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_NOFILE,(512,512))
def run(directory,argv,timeout=120,extra_ro=(),extra_env=None):
 return subprocess.run(command(directory,argv,extra_ro,extra_env),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,preexec_fn=limits)
