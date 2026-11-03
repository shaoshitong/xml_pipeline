"""Record the two individually inspected method/framework figures, never future rows."""
from pathlib import Path
import datetime,hashlib,json
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/goal500_progress_v1'
ids=['1ee38d062bab5c40b1fab2ca562588babc46206774bc467cbee6ab81e708c8f0','8db2ef1af950672faa40a06fe25debb224cbc1ffe04cd5998154b83728404de2']
rows=[json.loads(l) for l in (D/'selected_pending_visual_policy_review.jsonl').read_text().splitlines()]
assert set(ids)<=set(r['goal500_pair_id'] for r in rows)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
evidence=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),contact_sheet='new_complex_contact_v1.jpg',contact_sheet_sha256=sha(D/'new_complex_contact_v1.jpg'),accepted_panels=[1,3],held_panels=[2,4,5],findings={'1':'Complete recurrent-attention hybrid language-model method with context, pathway and training comparisons.','3':'Complete circuit-graph encoder pretraining and task-finetuning framework.','2,4,5':'Dialogue/story examples held; not a sufficiently complex method or system framework.'},review_does_not_assert_original_PDF_fidelity=True)
approval=dict(approved=True,source_filter_sha256=sha(R/'conversion/scripts/priority_source_complexity_filter_v1.py'),value_policy_sha256=sha(D/'value_policy.json'),reviewed_accepted_goal500_ids=ids,review_evidence=evidence)
(D/'value_policy_approval.json').write_text(json.dumps(approval,indent=2)+'\n')
print(json.dumps(dict(individually_reviewed_accepted=len(ids),future_candidates_not_autoapproved=True)))
