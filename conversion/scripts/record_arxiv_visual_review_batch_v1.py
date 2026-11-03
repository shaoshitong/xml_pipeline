"""Apply explicit per-figure decisions after actual contact-sheet inspection."""
from pathlib import Path
import argparse,hashlib,json,os,uuid
p=argparse.ArgumentParser();p.add_argument('--decisions',type=Path,required=True);a=p.parse_args()
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/goal500_progress_v1'
review=json.loads(a.decisions.read_text());folder=R/review['remote_folder']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
approval=json.loads((D/'value_policy_approval.json').read_text())
seen=approval.get('review_evidence',{}).get('additional_individual_review_batches',[])
if any(b['sha256']==sha(a.decisions) for b in seen):
 print(json.dumps(dict(already_applied=True,total_approved_ids=len(approval['reviewed_accepted_goal500_ids']),later_review_decisions_preserved=True)))
 raise SystemExit(0)
assert sha(folder/'review_manifest.json')==review['contact_manifest_sha256']
for f,digest in review['contact_sheets_sha256'].items():assert sha(folder/f)==digest
manifest={r['number']:r for r in json.loads((folder/'review_manifest.json').read_text())}
selected={r['goal500_pair_id']:r for r in map(json.loads,(D/'selected_pending_visual_policy_review.jsonl').read_text().splitlines())}
new=[];held=[]
for decision in review['decisions']:
 row=manifest[decision['number']];actual=selected[row['id']]
 for key in ['code_sha256','image_sha256']:assert row[key]==actual[key]
 if decision['accepted']:new.append(row['id'])
 else:held.append(row['id'])
approval=json.loads((D/'value_policy_approval.json').read_text())
assert approval['source_filter_sha256']==sha(R/'conversion/scripts/priority_source_complexity_filter_v1.py')
assert approval['value_policy_sha256']==sha(D/'value_policy.json')
prior=approval.get('reviewed_accepted_goal500_ids',[]);approval['reviewed_accepted_goal500_ids']=sorted(set(prior+new)-set(held))
approval['reviewed_held_goal500_ids']=sorted((set(approval.get('reviewed_held_goal500_ids',[]))|set(held))-set(new))
evidence=approval.setdefault('review_evidence',{});batches=evidence.setdefault('additional_individual_review_batches',[])
if not any(b['sha256']==sha(a.decisions) for b in batches):
 batches.append(dict(file=str(a.decisions.relative_to(R)),sha256=sha(a.decisions),contact_folder=review['remote_folder'],reviewed=len(review['decisions']),accepted=len(new),held=len(review['decisions'])-len(new)))
path=D/'value_policy_approval.json';temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(approval,indent=2)+'\n');os.replace(temp,path)
print(json.dumps(dict(batch_approved=len(new),total_approved_ids=len(approval['reviewed_accepted_goal500_ids']),unreviewed_future_rows_not_approved=True)))
