"""Reasoned outcome decisions after lifetime budget exhaustion; never calls models.

Only the outcome registry is changed. Source files, jobs, queues and history are
preserved. A later qualified deterministic revision can supersede the decision.
"""
import argparse
import datetime
import json
import sqlite3
from pathlib import Path
from model_history_ledger_v1 import lookup_sample_budget

ROOT=Path('/backup/shaoshitong/img2code_20261029')
IDLE=('needs_quality_repair','needs_fallback','rendered','harness_review_pending')


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def prepare(db,identifier,policy,lookup=lookup_sample_budget):
    row=db.execute('select state,worker_pid,input_record,output_record,updated_at from jobs where id=?',(identifier,)).fetchone()
    if not row or row[0] not in IDLE or row[1] is not None or not row[3]:return None,'not_current_idle_failed_candidate'
    original=json.loads(row[2]);record=json.loads(row[3])
    if record.get('id')!=identifier or record.get('source_pair_sha256')!=identifier:return None,'output_origin_mismatch'
    if any(record.get('source_'+key)!=original.get(key) for key in ('code_sha256','image_sha256')):return None,'output_origin_mismatch'
    budget=lookup(identifier)
    if budget.get('original_id')!=identifier:return None,'budget_identity_mismatch'
    if not budget.get('coverage_complete_for_id') or (budget.get('confirmed_calls') or 0)<2:return None,'confirmed_lifetime_budget_not_proven_exhausted'
    if budget.get('remaining_calls')!=0 or not budget.get('history_snapshot_id'):return None,'budget_not_exhausted'
    qa=db.execute('select state,record from auto_quality_audits_v1 where id=? and code_hash=? and image_hash=? and policy=?',
          (identifier,record['code_sha256'],record['image_sha256'],policy)).fetchone()
    if not qa or qa[0]!='repair_required':return None,'no_current_policy_failure_for_this_exact_pair'
    audit=json.loads(qa[1])
    if audit.get('id')!=identifier or audit.get('accepted') or not audit.get('failures') or audit.get('input_code_sha256')!=record['code_sha256'] or audit.get('input_image_sha256')!=record['image_sha256'] or audit.get('source_code_sha256')!=record['source_code_sha256'] or audit.get('source_image_sha256')!=record['source_image_sha256']:return None,'incomplete_or_mismatched_failure_proof'
    registry=db.execute('select status,source_code_hash,source_image_hash from processing_outcomes_v2 where id=?',(identifier,)).fetchone()
    if not registry or registry[0]=='qualified' or registry[1:]!=(original['code_sha256'],original['image_sha256']):return None,'registered_origin_or_status_changed'
    evidence={key:record[key] for key in ('id','source_code_sha256','source_image_sha256','code_file','code_sha256','image_file','image_sha256')}
    evidence.update(reason_code='lifetime_model_budget_exhausted_quality_failed',
       reason_detail='当前版本未通过程序验收，历史模型调用已达到累计两次上限；本轮不再模型重试。',
       confirmed_model_calls=budget['confirmed_calls'],unknown_model_reservations=budget.get('unknown_reservations',0),
       model_lifetime_limit=2,history_snapshot_id=budget['history_snapshot_id'],failed_qa_policy=policy,
       failed_qa_reasons=audit['failures'],abandoned_at=now(),deterministic_recovery_permitted=True)
    return {'id':identifier,'snapshot':row,'audit_snapshot':qa,'policy':policy,'evidence':evidence},None


def apply(db,plan,publish=False):
    db.execute('begin immediate')
    try:
        identifier=plan['id'];e=plan['evidence']
        current=db.execute('select state,worker_pid,input_record,output_record,updated_at from jobs where id=?',(identifier,)).fetchone()
        qa=db.execute('select state,record from auto_quality_audits_v1 where id=? and code_hash=? and image_hash=? and policy=?',
             (identifier,e['code_sha256'],e['image_sha256'],plan['policy'])).fetchone()
        if current!=plan['snapshot'] or qa!=plan['audit_snapshot']:
            db.rollback();return 'stale_revision'
        prior=db.execute('select status,record from processing_outcomes_v2 where id=?',(identifier,)).fetchone()
        if not prior or prior[0]=='qualified':db.rollback();return 'status_changed'
        if prior[0]=='abandoned' and prior[1]:
            old=json.loads(prior[1])
            if all(old.get(key)==e[key] for key in ('code_sha256','image_sha256','history_snapshot_id','failed_qa_policy')):
                db.rollback();return 'already_recorded'
        if publish:
            db.execute("update processing_outcomes_v2 set status='abandoned',reason=?,record=?,updated_at=? where id=? and status!='qualified'",
                       (e['reason_code'],json.dumps(e,ensure_ascii=False),now(),identifier))
        db.commit();return 'abandoned' if publish else 'validated_abandonment_plan'
    except BaseException:db.rollback();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    work=ROOT/'conversion';db=sqlite3.connect(work/'jobs.sqlite',timeout=60)
    policy=json.loads((work/'auto_quality_owner.json').read_text())['policy']
    candidates=json.loads((work/'model_history_ledger_v1/budget_exhausted_current_v3_failed_qa.json').read_text())
    rows=[]
    for item in candidates:
        plan,reason=prepare(db,item['id'],policy)
        stage=apply(db,plan,args.publish) if plan else 'pending'
        rows.append({'id':item['id'],'stage':stage,'reason':reason,'evidence':plan['evidence'] if plan else None})
    result={'at':now(),'policy':policy,'publish':args.publish,'model_calls':0,
        'jobs_queues_source_files_or_history_modified':False,'rows':rows,'goal_complete':False}
    (work/'budget_exhausted_outcomes_v2_latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
