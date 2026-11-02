"""Freeze already-seen generic SVG positive, actual corruptions and calibration.

No new source IDs, reservations or canonical writes. Old v5 assets are reused,
but every actual negative is independently reverified with the stronger guard.
"""
import fcntl,json,sqlite3,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_svg_general_guard_v1 as compiler
import compiler_svg_general_iteration_case_v1 as case
from compiler_types_program_v1 import asset,checked,immutable,raw,sha,atomic
from compiler_svg_scene_quality_ro_v5 import verify
DIRECTORY=R/'release/compiler_iterations/controls/svg_general_scene_v5_guard_controls_20261101_v1'
DEVELOPMENT=W/'compiler_svg_scene_frontend_v5/development_run_v5/case_0/report.json'
PROBE=W/'compiler_svg_general_guard_v1/positive_probe.json'

def main():
 config=compiler.configuration();prior=json.loads(DEVELOPMENT.read_bytes());probe=json.loads(PROBE.read_bytes());recordfile=Path(probe['candidate']);record=json.loads(recordfile.read_bytes());qa=json.loads(Path(probe['qa']).read_bytes())
 case.full_quality(qa,record)
 if qa['profile_policy']!=config['policy']:raise ValueError('guard_positive_does_not_bind_current_policy')
 DIRECTORY.mkdir(parents=True,exist_ok=False)
 with (DIRECTORY/'producer.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  calibration=W/'native_marker_exact_grid_calibration_v1'
  proof={'schema':'compiler_svg_general_iteration_controls_v1','producer':asset(__file__),'development':asset(DEVELOPMENT),'positive_probe':asset(PROBE),'frozen_frontend':config,'positives':[asset(probe['qa'])],'negatives':[],'positive_cases':[{'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':asset(recordfile),'qa':asset(probe['qa'])}],'negative_cases':[],'model_calls':0,'unseen_consumed':0,'canonical_mutations':0,'calibration':{n:asset(calibration/n) for n in ('preregistered_plan.json','report.json')}}
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:source=json.loads(db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0])
  manifest=case.publish(record,source,qa,Path(probe['qa']).parent);immutable(DIRECTORY/'qualified.jsonl',raw(manifest));proof['qualified_manifest']=asset(DIRECTORY/'qualified.jsonl')
  for negative in prior['negative_results']:
   name=negative['mutation'];digest=negative['qa']['input_record_sha256'];parent=R/'clean/compiler_svg_scene_frontend_v5/controls'/record['id']/name
   matches=[p for p in parent.glob('*/record.json') if sha(p.read_bytes())==digest]
   if len(matches)!=1:raise ValueError('development_negative_record_identity_ambiguous:'+name)
   candidate=matches[0];rr=json.loads(candidate.read_bytes());work=W/'prototype/candidate_quality_ro_v1'/('svg_general_guard_control_'+name+'_'+uuid.uuid4().hex);q=verify(rr['id'],candidate,R,Path(compiler.__file__),work)
   profile=q.get('checks',{}).get('source_preliminary') or q.get('checks',{}).get('source') or {}
   if q.get('ok') is not False or not q.get('failures') or profile.get('ok') is not False or not profile.get('failures'):
    atomic(DIRECTORY/'rejected_controls.json',{'name':name,'qa':q});raise ValueError('negative_not_rejected_by_original_source:'+name)
   proof['negatives'].append(asset(q['evidence_file']));proof['negative_cases'].append({'name':name,'id':rr['id'],'source_code_sha256':rr['source_code_sha256'],'source_image_sha256':rr['source_image_sha256'],'candidate':asset(candidate),'qa':asset(q['evidence_file']),'rehashed_XML_and_actual_native_PNG':True,'intended_fresh_source_rejection':True});atomic(DIRECTORY/'progress.json',{'positive':1,'negative':len(proof['negatives']),'model_calls':0,'unseen_consumed':0});print(json.dumps({'control':name,'ok':q['ok'],'fresh_source_rejected':True}),flush=True)
  if compiler.configuration()!=config:raise ValueError('guard_changed_during_controls')
  immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':str(DIRECTORY/'proof.json'),'qualified_development_controls':1,'actual_negatives':len(proof['negatives']),'model_calls':0,'heldout_dispatched':False}),flush=True)
if __name__=='__main__':main()
