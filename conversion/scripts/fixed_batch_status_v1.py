"""Read-only progress with bounded SQLite admission and labelled snapshot fallback."""
import argparse,datetime,json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
def status(run):
 run=Path(run);r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run':str(run),'model_calls':0}
 try:
  d=sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True,timeout=30)
  try:
   d.execute('begin');m={k:json.loads(v) for k,v in d.execute('select key,value from metadata')}
   r.update(total=m['total'],full_scope=m['full_scope'],finished=m.get('finished',False),counts=dict(d.execute('select status,count(*) from samples group by status')),dispatch_attempt_counts=dict(d.execute('select attempts,count(*) from samples group by attempts')),live_ledger_read=True);d.rollback()
  finally:d.close()
 except sqlite3.OperationalError as e:
  if 'locked' not in str(e).lower() and 'busy' not in str(e).lower():raise
  p=run/'summary.json' if (run/'summary.json').exists() else run/'progress.json';r.update(json.loads(p.read_bytes()));r.update(query_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),live_ledger_read=False,ledger_busy=True)
 live=False;owner={}
 try:
  owner=json.loads((run/'owner.json').read_bytes());p=Path('/proc',str(owner['pid']));f=(p/'stat').read_text().rsplit(') ',1)[1].split()
  live=f[0]!='Z' and int(f[19])==int(owner['start_ticks']) and str(R/'conversion/scripts/fixed_batch_pipeline_v1.py').encode() in (p/'cmdline').read_bytes().split(b'\0')
 except (OSError,KeyError,ValueError):pass
 r.update(supervisor_live=live,supervisor_pid=owner.get('pid'),workers=owner.get('workers'),infrastructure_stop_recorded=(run/'infrastructure_stop.json').exists());return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run-id',default='initial_screen_20261031_1717');a=p.parse_args()
 if not all(c.isalnum() or c in '-_' for c in a.run_id):p.error('Invalid run ID')
 print(json.dumps(status(R/'release/fixed_batch_v1'/a.run_id),ensure_ascii=False))
