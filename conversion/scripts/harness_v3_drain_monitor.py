"""One-time recovery sweep after the confirmed legacy Harness owner finishes."""
import json,os,sqlite3,subprocess,time
from pathlib import Path
from native_worker import W,now
owner=json.loads((W/'harness_v3_owner.json').read_text());pid=owner['pid'];me={'pid':os.getpid(),'legacy_pid':pid,'at':now()};(W/'harness_v3_drain_monitor_owner.json').write_text(json.dumps(me))
while True:
 p=Path('/proc')/str(pid)/'cmdline';cmd=p.read_bytes() if p.exists() else b''
 if b'harness_pool_v3.py' not in cmd:break
 time.sleep(15)
D=sqlite3.connect(W/'jobs.sqlite');running=D.execute("select id from harness_queue_v3 where state='running' and worker_pid=?",(pid,)).fetchall()
if running:
 out={**me,'at':now(),'status':'legacy_owner_terminal_with_unfinished_records','needs_recovery':[r[0] for r in running]}
else:
 with (W/'harness_v3_drain_recovery.log').open('ab') as log:
  for name in ['inspect_harness_font_loss.py','requeue_harness_font_losses.py']:subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts'/name)],stdout=log,stderr=log,check=True)
 out={**me,'at':now(),'status':'final_legacy_output_font_audit_complete','requeue':json.loads((W/'harness_v3_font_recovery_requeue.json').read_text())}
(W/'harness_v3_drain_monitor_result.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
