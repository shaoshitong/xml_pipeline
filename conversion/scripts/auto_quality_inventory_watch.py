import fcntl,json,os,sqlite3,time
from pathlib import Path
from auto_quality_inventory_v2 import refresh,ROOT
W=ROOT/'conversion';lock=(W/'auto_quality_inventory_watch.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
(W/'auto_quality_inventory_owner.json').write_text(json.dumps({'pid':os.getpid(),'interval_seconds':60,'at':time.time()}))
while True:
 try:
  r=refresh();print(json.dumps({'at':r['observed_at_utc'],'totals':r['totals'],'seconds':r['elapsed_seconds'],'parsed_changed_payloads':r['incremental']['large_payloads_parsed'],'throughput':r['throughput']}),flush=True)
 except sqlite3.OperationalError as exc:print(json.dumps({'at':time.time(),'retryable_database_error':repr(exc)}),flush=True)
 time.sleep(60)
