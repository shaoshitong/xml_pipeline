"""Finite, full-history reasoned outcome pass. No model dispatch or retries."""
import argparse,json,sqlite3
from pathlib import Path
from budget_exhausted_outcomes_v2 import ROOT,prepare,apply,now


def candidates(path):
    data=json.loads(Path(path).read_text())
    if isinstance(data,dict):
        for key in ('records','rows','samples'):
            if key in data:data=data[key];break
    assert isinstance(data,list),'History exhausted-ID list has an unknown schema'
    ids=[item if isinstance(item,str) else item['id'] for item in data]
    assert len(ids)==len(set(ids)),'Duplicate history original IDs'
    return ids


def main(publish=False):
    work=ROOT/'conversion';db=sqlite3.connect(work/'jobs.sqlite',timeout=60)
    policy=json.loads((work/'auto_quality_owner.json').read_text())['policy']
    ids=candidates(work/'model_history_ledger_v1/at_least_two_unqualified.json')
    rows=[]
    for identifier in ids:
        plan,reason=prepare(db,identifier,policy)
        stage=apply(db,plan,publish) if plan else 'pending_or_previously_recorded'
        rows.append({'id':identifier,'stage':stage,'reason':reason,'evidence':plan['evidence'] if plan else None})
    result={'at':now(),'policy':policy,'publish':publish,'history_ids_examined':len(ids),'model_calls':0,'jobs_queues_source_files_or_history_modified':False,'rows':rows,'goal_complete':False}
    (work/'budget_exhausted_outcomes_v3_latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args();main(a.publish)
