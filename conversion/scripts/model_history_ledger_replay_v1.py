"""Replay sanitized metadata, with optional same-byte failed-parser recovery.

No SDK/API import. Reads metadata only and writes the independent history ledger.
The original jobs, histories and processing outcomes are never modified.
"""
import argparse,hashlib,json
from pathlib import Path
import model_history_ledger_v1 as h


def main(args):
 root=Path(args.root);directory=root/'conversion/model_history_ledger_v1';path=directory/'scanned_metadata.json';data=json.loads(path.read_bytes());collector=h.Collector();collector.merge(data);jobs=h.load_jobs(root)
 repaired=[]
 if args.repair_failed:
  failed={p['artifact'] for p in collector.problems if p.get('reason')=='artifact_read_failed'}
  for name in failed:
   artifact=next(a for a in collector.artifacts if a['artifact']==name);p=Path(name)
   if h.sha(p.read_bytes())!=artifact.get('sha256'):raise RuntimeError('failed source bytes changed; fresh inventory required')
  collector.problems=[p for p in collector.problems if p.get('artifact') not in failed];collector.artifacts=[a for a in collector.artifacts if a['artifact'] not in failed]
  h.scan_paths(collector,sorted(failed),h.IdentityResolver(root,jobs),progress=False);repaired=sorted(failed)
  if collector.problems:raise RuntimeError('parser recovery remains incomplete')
  path.write_text(json.dumps(collector.serialize(),separators=(',',':'))+'\n')
 # Verify unchanged byte versions for every remote metadata artifact. Local
 # projected inputs are pinned in the scanned snapshot and are not copied here.
 remote_verified=0;local_projected=0
 for a in collector.artifacts:
  p=Path(a['artifact'])
  if not str(p).startswith(str(root)+'/'):
   local_projected+=1;continue
  stat=p.stat()
  if stat.st_size!=a['size'] or stat.st_mtime_ns!=a['mtime_ns']:raise RuntimeError('metadata version changed; fresh scan required: '+str(p))
  if a.get('sha256') and h.sha(p.read_bytes())!=a['sha256']:raise RuntimeError('metadata bytes changed; fresh scan required: '+str(p))
  remote_verified+=1
 summaries=[]
 for index in range(2):
  fresh=h.Collector();fresh.merge(collector.serialize());reconciled=h.reconcile(fresh);summary,exhausted=h.persist(args.db,fresh,reconciled,jobs,inventory_complete=True);summaries.append(summary)
  if index==1:h.write_reports(root,fresh,reconciled,summary,exhausted)
 keys=('history_snapshot_id','unique_responses','confirmed_response_calls','unresolved_request_reservations','historical_unique_response_tokens','proven_blocked_local_requests','aggregate_only_unknown_multiplicity','unknown_response_usage')
 assert all(summaries[0][k]==summaries[1][k] for k in keys),'non-idempotent ledger replay'
 evidence={'history_snapshot_id':summary['history_snapshot_id'],'same_byte_failed_artifacts_recovered':repaired,'remote_metadata_versions_verified':remote_verified,'local_projected_artifacts_pinned':local_projected,'two_reimports_same_snapshot_and_call_token_totals':True,'comparison_fields':keys,'new_model_calls_performed':0,'original_histories_jobs_and_outcomes_modified':False}
 (directory/'replay_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps({'evidence':evidence,'summary':{k:v for k,v in summary.items() if k not in ('event_type_counts','source_read_problems','unattributed_control_observations')}}))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(h.ROOT));p.add_argument('--db',default=h.DEFAULT_DB);p.add_argument('--repair-failed',action='store_true');main(p.parse_args())
