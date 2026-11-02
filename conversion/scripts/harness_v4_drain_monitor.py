"""Let paid v4 requests finish, then retire only a verified idle old pool."""
import json,os,signal,sqlite3,subprocess,time
from pathlib import Path
from native_worker import W,now
old=json.loads((W/'harness_v5_transition.json').read_text())['previous_v4_pid'];(W/'harness_v4_drain_monitor_owner.json').write_text(json.dumps({'pid':os.getpid(),'legacy_pid':old,'at':now()}));D=sqlite3.connect(W/'jobs.sqlite',timeout=60)
def command(pid):
 p=Path('/proc')/str(pid)/'cmdline'
 try:return p.read_bytes().replace(b'\0',b' ').decode()
 except FileNotFoundError:return ''
while True:
 rows=D.execute("select id,session_dir from harness_queue_v3 where state='running' and worker_pid=?",(old,)).fetchall();cmd=command(old);live='harness_pool_v4.py' in cmd
 if rows:
  if not live:
   result={'at':now(),'status':'legacy_process_terminal_with_owned_rows_requires_recovery','legacy_pid':old,'orphaned':rows};break
  time.sleep(15);continue
 assert not D.execute("select 1 from harness_queue_v3 where state='held_for_font_v4' limit 1").fetchone(),'Old pool can still claim work'
 if live:
  time.sleep(1);assert not D.execute("select 1 from harness_queue_v3 where state='running' and worker_pid=?",(old,)).fetchone();assert command(old)==cmd,'Process identity changed';os.kill(old,signal.SIGTERM)
  for _ in range(30):
   if 'harness_pool_v4.py' not in command(old):break
   time.sleep(1)
  assert 'harness_pool_v4.py' not in command(old),'Idle legacy process did not exit'
 with (W/'harness_v4_final_provenance_audit.log').open('wb') as log:subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/audit_harness_provenance.py')],stdout=log,stderr=log,check=True)
 audit=json.loads((W/'harness_provenance_audit.json').read_text());result={'at':now(),'status':'drained_with_provenance_followup' if audit['affected'] else 'drained_and_source_provenance_audited','legacy_pid':old,'stopped_verified_idle_pool':live,'v4_published':audit['v4_published'],'affected':audit['affected']};break
(W/'harness_v4_drain_monitor_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
