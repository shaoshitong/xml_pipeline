import sys,json
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');sys.path[:0]=[str(W/'scripts'),str(W/'prototype')]
import mermaid_page_metadata_supervisor_v1b as m
assert Path(m.base.__file__)==W/'scripts/mermaid_page_metadata_batch_v1.py'
receipt=m.private_smoke(limit=2)
print(json.dumps({'receipt':receipt['scope']+'/receipt.json','ok':receipt['ok'],'selected_ids':receipt['selected_ids'],'canonical_unchanged':receipt['canonical_job_outcome_queues_unchanged'],'private_restored':receipt['private_jobs_outcomes_queues_restored'],'triggers_copied':receipt['actual_job_triggers_copied'],'stage_rows':receipt['stage_rows'],'transaction_seconds':[r.get('transaction_seconds') for r in receipt['summary']['results']],'validation_policy':receipt['summary']['validation_policy'],'supervisor_policy':receipt['summary']['supervisor_policy'],'published':0,'accepted':0,'model_calls':0}),flush=True)
