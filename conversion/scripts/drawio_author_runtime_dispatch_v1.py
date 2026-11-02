"""Finite real semantic-negative then existing-positive controller proof."""
from pathlib import Path
import json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from compiler_types_program_v1 import raw,sha,asset,immutable,checked
ROOT=W/'drawio_author_runtime_dispatch_v1'
def proof_path(pool):return ROOT/Path(pool).name/'proof.json'
def verify_reference(ref):
 import drawio_author_iteration_batch_v1 as controller
 import drawio_author_iteration_case_v1 as case
 _,payload=checked(ref);proof=json.loads(payload)
 if proof['schema']!='actual_author_native_semantic_failure_then_complete_existing_positive_dispatch_v1'or not all(proof[k]is True for k in ('each_attempted_once','ordinary_semantic_failure_does_not_stop_next_case','canonical_unchanged','no_normal_frontend_calls')):raise ValueError('author_runtime_dispatch_controls_incomplete')
 for name,digest in proof['implementation_pins'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('author_runtime_dispatch_implementation_changed')
 state=controller.snapshot(Path(proof['run']))
 if state['infrastructure_stop']or not state['metadata'].get('finished')or state['dispatch_attempt_counts']!={1:2}:raise ValueError('author_runtime_dispatch_not_terminal_once')
 if len(proof['cases'])!=2:raise ValueError('author_runtime_dispatch_not_two_cases')
 for row in proof['cases']:
  _,blob=checked(row['result']);result=json.loads(blob)
  if result['id']!=row['id']or result.get('infrastructure_failure'):raise ValueError('author_runtime_dispatch_case_identity_or_infrastructure')
  if row['seq']==1:
   if result['status']!='abandoned'or result.get('negative_false_acceptance')or result['reason']!='negative_correctly_rejected':raise ValueError('author_runtime_semantic_negative_not_rejected')
  elif row['seq']==2:
   if result['status']!='qualified':raise ValueError('author_runtime_next_complete_positive_failed')
   _,data=checked(row['candidate']);record=json.loads(data);_,data=checked(row['quality']);case.full_quality(json.loads(data),record)
  else:raise ValueError('author_runtime_dispatch_sequence_invalid')
 return ref

def verify_existing(pool):return verify_reference(asset(proof_path(pool)))
def main(pool):
 import drawio_author_iteration_program_v1 as program
 import drawio_author_iteration_batch_v1 as controller
 import drawio_author_source_once_v1 as once
 pool=Path(pool).resolve();owner=proof_path(pool).parent
 if(owner/'proof.json').exists():verify_existing(pool);return json.loads((owner/'proof.json').read_bytes())
 owner.mkdir(parents=True,exist_ok=False);compiler,_=program.case.bindings('drawio');freeze=program.template(pool);controls=program.control_bundle(compiler);program.check_controls(controls)
 negative=next(row for row in controls['negative_cases']if row['name']=='deleted_source_text');positive=next(row for row in controls['positive_cases']if row['id']!=negative['id']);targets=[];canonical={}
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:
  for seq,control in enumerate((negative,positive),1):
   job=db.execute('select*from jobs where id=?',(control['id'],)).fetchone();canonical[control['id']]=job;source=json.loads(job[4]);old=json.loads(job[9])if job[9]else{};support=compiler.static_support(dict(zip(program.case.JOB_COLUMNS,job)))
   if not support['supported']:raise ValueError('runtime_control_original_outside_source_profile')
   row={'id':control['id'],'seq':seq,'source':source,'compiler_unit':compiler.UNIT,'source_capture_snapshot':support['source_capture_snapshot'],'source_record_sha256':sha((job[9]or'').encode()),'baseline_code_sha256':old.get('code_sha256'),'baseline_image_sha256':old.get('image_sha256'),'cluster':'existing_consumed_author_runtime_dispatch_control','evaluation_phase':'control_negative'if seq==1 else'control_positive'}
   if seq==1:row.update(negative_control=True,development_candidate=control['candidate']['file'])
   else:row['existing_development_candidate']=control['candidate']['file']
   targets.append(row)
 payload=b''.join(raw(row)for row in targets);immutable(owner/'input.jsonl',payload);freeze={**freeze,'input_sha256':sha(payload)};immutable(owner/'freeze.json',raw(freeze));run=controller.FLOOR/('author_native_dispatch_'+pool.name);controller.create(run,owner/'input.jsonl',owner/'freeze.json','development');before=once.claims(compiler);results=program.run_phase(run,1,900,owner);after=once.claims(compiler);cases=[]
 for row in targets:
  work=W/'compiler_iterations'/run.name/(f"{row['seq']:06d}_"+row['id']);result=results[row['id']];candidate=work/'candidate_record.json';entry={'id':row['id'],'seq':row['seq'],'result':asset(work/'result.json'),'candidate':asset(candidate),'normal_frontend_result_exists':(work/'frontend_result.json').exists()}
  if result.get('quality_report'):entry['quality']=asset(R/result['quality_report'])
  cases.append(entry)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:unchanged=all(db.execute('select*from jobs where id=?',(i,)).fetchone()==row for i,row in canonical.items())
 proof={'schema':'actual_author_native_semantic_failure_then_complete_existing_positive_dispatch_v1','run':str(run),'source_pool':str(pool),'cases':cases,'each_attempted_once':controller.snapshot(run)['dispatch_attempt_counts']=={1:2},'ordinary_semantic_failure_does_not_stop_next_case':results[targets[0]['id']]['status']=='abandoned'and results[targets[1]['id']]['status']=='qualified','canonical_unchanged':unchanged,'no_normal_frontend_calls':before==after and not any(r['normal_frontend_result_exists']for r in cases),'implementation_pins':freeze['pins'],'freeze':asset(owner/'freeze.json'),'input':asset(owner/'input.jsonl'),'model_calls':0,'evidence_file':str(owner/'proof.json')};immutable(owner/'proof.json',raw(proof));verify_existing(pool);return proof
if __name__=='__main__':print(json.dumps(main(Path(sys.argv[1]))))
