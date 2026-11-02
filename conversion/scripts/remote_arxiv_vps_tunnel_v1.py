"""Task-scoped HKUST3 -> existing VPS SSH SOCKS; no Mac in the data path."""
from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'conversion/private_arxiv_transport_v3'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,x):
 q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(x,indent=2)+'\n');os.replace(q,p)
def birth(pid):
 p=Path('/proc',str(pid),'stat')
 if not p.exists():return None
 s=p.read_text().split(') ',1)[1].split()
 return s[19] if s[0]!='Z' else None
def run():
 cfg=json.loads((D/'config.json').read_text());stop=False;p=None
 def stopping(a,b):
  nonlocal stop
  stop=True
 signal.signal(signal.SIGTERM,stopping);signal.signal(signal.SIGINT,stopping)
 cmd=['ssh','-F','/dev/null','-T','-N','-S','none','-oControlMaster=no','-oBatchMode=yes',
      '-oIdentitiesOnly=yes','-oIdentityAgent=none','-oConnectTimeout=8','-oExitOnForwardFailure=yes',
      '-oServerAliveInterval=15','-oServerAliveCountMax=2','-oStrictHostKeyChecking=yes',
      '-oUserKnownHostsFile='+str(D/'known_hosts'),'-i',str(D/'id_ed25519'),
      '-D','127.0.0.1:'+str(cfg['SOCKS_port']),cfg['SSH_user']+'@'+cfg['VPS_host']]
 try:
  while not stop:
   if p is None or p.poll() is not None:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL)
   atomic(D/'status.json',{'at_utc':now(),'supervisor_pid':os.getpid(),'child_pid':p.pid,
      'child_birth_ticks':birth(p.pid),'child_returncode':p.poll(),'proxy_URL':cfg['proxy_URL'],
      'route':'arxiv -> VPS -> HKUST3','Mac_in_data_path':False,'agent_required':False})
   for _ in range(10):
    if stop:break
    time.sleep(1)
 finally:
  if p is not None and p.poll() is None:p.terminate();p.wait(timeout=10)
  atomic(D/'terminal.json',{'at_utc':now(),'stopped':True,'supervisor_pid':os.getpid()})
def launch():
 receipt=D/'launch.json'
 if receipt.exists():
  old=json.loads(receipt.read_text())
  if birth(old['pid'])==old['birth_ticks']:print(json.dumps({'already_running':True,**old}));return
 with (D/'program.log').open('ab') as log:
  p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 row={'at_utc':now(),'pid':p.pid,'birth_ticks':birth(p.pid),'command':[sys.executable,str(Path(__file__).resolve()),'run'],
      'route':'arxiv -> VPS -> HKUST3','Mac_in_data_path':False,'private_key_never_transferred':True}
 atomic(receipt,row);print(json.dumps(row))
if __name__=='__main__':
 if sys.argv[1]=='run':run()
 elif sys.argv[1]=='launch':launch()
