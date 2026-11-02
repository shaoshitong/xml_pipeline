"""One bounded read-only second-round status query; never invokes a model."""
import argparse,json
from pathlib import Path
from fixed_batch_status_v1 import status as ledger_status
R=Path('/backup/shaoshitong/img2code_20261029')
def status(run):
 run=Path(run);r=ledger_status(run);live=False;owner={}
 try:
  owner=json.loads((run/'owner.json').read_bytes());p=Path('/proc',str(owner['pid']));f=(p/'stat').read_text().rsplit(') ',1)[1].split()
  live=f[0]!='Z' and int(f[19])==int(owner['start_ticks']) and str(R/'conversion/scripts/round2_pipeline_v1.py').encode() in (p/'cmdline').read_bytes().split(b'\0')
 except (OSError,ValueError,KeyError):pass
 r.update(round=2,input_universe=131904,supervisor_live=live,workers=owner.get('workers'),goal_completion_is_launch_not_full_processing=True)
 if (run/'targets_status.json').exists():r['target_manifest']=json.loads((run/'targets_status.json').read_bytes())
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run-id',default='repair_pass_20261101_0627');a=p.parse_args()
 if not all(c.isalnum() or c in '-_' for c in a.run_id):p.error('Invalid run ID')
 print(json.dumps(status(R/'release/round2_fixed_v1'/a.run_id),ensure_ascii=False))
