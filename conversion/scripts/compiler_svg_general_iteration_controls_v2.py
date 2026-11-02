"""Bind completed, actual coordinate controls into immutable release evidence.

Does not reserve validation samples or start validation/mass jobs. Reads signed
full-QA development evidence and publishes only already proven clean pairs.
"""
import argparse,json,sqlite3,sys
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_svg_general_guard_v2 as compiler
import compiler_svg_general_iteration_case_v2 as case
from compiler_types_program_v1 import asset,checked,immutable,raw,sha
DIRECTORY=R/'release/compiler_iterations/controls/svg_general_scene_v6_coordinate_controls_20261101_v1'

def main(receipt,development):
 receipt=Path(receipt).resolve(strict=True);development=Path(development).resolve(strict=True)
 controls=json.loads(receipt.read_bytes());dev=json.loads(development.read_bytes());config=compiler.configuration()
 if controls.get('passed') is not True or controls.get('configuration_unchanged') is not True or dev.get('configuration_unchanged') is not True:raise ValueError('actual_source_coordinate_controls_incomplete')
 proof={'schema':'compiler_svg_general_iteration_controls_v2','producer':asset(__file__),'development':asset(development),'actual_controls_receipt':asset(receipt),'frozen_frontend':config,'positives':[],'negatives':[],'positive_cases':[],'negative_cases':[],'model_calls':0,'unseen_consumed':0,'canonical_mutations':0,'calibration':{n:asset(W/'native_marker_exact_grid_calibration_v1'/n) for n in ('preregistered_plan.json','report.json')}}
 positives=[(Path(row['record_file']),Path(row['full_quality']['report'])) for row in dev['results'] if (row.get('full_quality') or {}).get('ok')]
 regression=controls['existing_positive']
 if regression['ok']:positives.append((R/regression['record']['file'],R/regression['quality_report']['file']))
 if not positives:raise ValueError('no_actual_positive_control')
 manifests=[];seen=set();DIRECTORY.mkdir(parents=True,exist_ok=False)
 for rp,qp in positives:
  record=json.loads(rp.read_bytes());qa=json.loads(qp.read_bytes())
  if record['id'] in seen:continue
  seen.add(record['id']);case.full_quality(qa,record)
  if qa['profile_policy']!=config['policy'] or qa['input_record_sha256']!=sha(rp.read_bytes()):raise ValueError('positive_not_bound_to_frozen_frontend_and_metadata')
  proof['positives'].append(asset(qp));proof['positive_cases'].append({'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':asset(rp),'qa':asset(qp)})
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:source=json.loads(db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0])
  manifests.append(case.publish(record,source,qa,qp.parent))
 for row in controls['negative_controls']:
  _,payload=checked(row['record']);record=json.loads(payload);_,payload=checked(row['quality_report']);qa=json.loads(payload);profile=qa.get('checks',{}).get('source',{})
  if not row['rejected'] or not row['fresh_actual_png'] or not row['rehashed_candidate'] or qa['ok'] or not qa['failures'] or profile.get('ok') is not False or not profile.get('failures'):raise ValueError('negative_not_rejected_by_complete_current_source_proof:'+row['variant'])
  if qa['profile_policy']!=config['policy'] or qa['input_record_sha256']!=row['record']['sha256']:raise ValueError('negative_not_bound_to_frozen_frontend_and_metadata')
  proof['negatives'].append(row['quality_report']);proof['negative_cases'].append({'name':row['variant'],'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':row['record'],'qa':row['quality_report'],'rehashed_XML_and_actual_native_PNG':True,'intended_fresh_source_rejection':True})
 immutable(DIRECTORY/'qualified.jsonl',b''.join(raw(row) for row in manifests));proof['qualified_manifest']=asset(DIRECTORY/'qualified.jsonl')
 if compiler.configuration()!=config:raise ValueError('compiler_changed_during_control_publication')
 immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':str(DIRECTORY/'proof.json'),'positive_controls':len(proof['positives']),'negative_controls':len(proof['negatives']),'unseen_consumed':0,'mass_started':False}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--development',type=Path,required=True);args=parser.parse_args();main(args.receipt,args.development)
