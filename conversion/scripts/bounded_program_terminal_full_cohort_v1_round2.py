"""Finite all-current-stage wrapper around the unchanged reviewed v1 planner."""
import sys,json,sqlite3,collections,time,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import bounded_program_terminal_planner_v1 as planner
config=planner.configuration(R);db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=60,isolation_level=None)
listing=planner.inventory(db,config)
rows=db.execute('''select t.id,t.state,j.state from tikz_execution_candidates_v1 t join jobs j on j.id=t.id join processing_outcomes_v2 o on o.id=j.id where t.policy=? and o.status='pending' and t.code_hash=json_extract(j.output_record,'$.code_sha256') and t.image_hash=json_extract(j.output_record,'$.image_sha256') and t.source_code_hash=json_extract(j.input_record,'$.code_sha256') and t.source_image_hash=json_extract(j.input_record,'$.image_sha256') order by t.id''',(config['execution_policy'],)).fetchall()
ids=sorted({r[0] for r in rows}|{r['id'] for r in config['closed_svg'].values() if r.get('cohort')=='closed_current_generic'})
print(json.dumps({'stage':'full_cohort_snapshot','at':planner.now(),'matching_current_execution_rows':len(rows),'closed_generic_fresh_cases':sum(r.get('cohort')=='closed_current_generic' for r in config['closed_svg'].values()),'unique_total':len(ids),'policy':config['policy']}),flush=True)
started=time.monotonic();plans=[];records=[];deferred=collections.Counter();snapshots=collections.Counter()
for index,identifier in enumerate(ids,1):
 try:
  plan=planner.prepare(db,identifier,config);plans.append(plan);result={'id':identifier,'status':'proposal_only','plan_index':len(plans)-1,'reason':plan['evidence']['reason_code']};snapshots['proposal_only']+=1
 except Exception as error:
  reason=str(error);deferred[reason]+=1;result={'id':identifier,'status':'pending_or_excluded','reason':reason[:2000]};snapshots['pending_or_excluded']+=1
 records.append(result)
 if index%50==0:print(json.dumps({'stage':'full_cohort_progress','at':planner.now(),'checked':index,'total':len(ids),'proposals':len(plans),'deferred':index-len(plans)}),flush=True)
# A plan may have become stale while later cases were examined. Keep the
# historical proposal but mark it, and never let the summary imply applicability.
validation=collections.Counter();per_plan=[]
for plan in plans:
 status=planner.revalidate(db,plan,config,check_files=True);validation[status]+=1;per_plan.append({'id':plan['id'],'status':status})
db.close()
result={'at':planner.now(),'seconds':round(time.monotonic()-started,3),'read_only':True,'model_calls':0,'apply_available':False,'scope_inputs':131904,'policy':config['policy'],'execution_policy':config['execution_policy'],'matching_execution_snapshot_rows':len(rows),'total_unique_cases_examined':len(ids),'inventory':{k:v for k,v in listing.items() if k!='candidate_ids'},'outcomes':dict(snapshots),'full_proposals':len(plans),'end_revalidation':dict(validation),'per_plan_end_revalidation':per_plan,'deferred_reasons':dict(deferred),'records':records,'plans':plans,'equivalence_certificates':config['equivalences'],'module_sha256':{name:hashlib.sha256((W/'scripts'/name).read_bytes()).hexdigest() for name in ('bounded_program_terminal_planner_v1.py','failure_equivalence_tikz_v1.py','test_bounded_program_terminal_planner_v1.py')},'wrapper_sha256':sys.argv[1] if len(sys.argv)>1 else None,'no_fixed_16_or_64_case_truncation':True,'goal_complete':False,'round':'round2_fresh_pending_only_after_first_215_committed','interpretation':'All exact currently pending stage cases in the snapshot were inspected once. Cases without current-policy failure or a proved equivalent historical failure remain pending with a specific reason; no status was changed.'}
target=W/'bounded_program_terminal_full_cohort_v1_round2_report.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');temp.replace(target)
summary={k:v for k,v in result.items() if k not in ('records','plans','equivalence_certificates','per_plan_end_revalidation')};summary['report']=str(target);summary['report_sha256']=hashlib.sha256(target.read_bytes()).hexdigest();summary['construct_classes_per_proposal']=dict(collections.Counter(tag for plan in plans for tag in plan['evidence']['source_construct_classes']));summary['reason_codes']=dict(collections.Counter(plan['evidence']['reason_code'] for plan in plans));print(json.dumps({'stage':'complete','summary':summary},ensure_ascii=False),flush=True)
