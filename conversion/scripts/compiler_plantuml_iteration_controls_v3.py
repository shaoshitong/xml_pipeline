"""Publish fully verified consumed controls; no reservation or batch launch."""
import argparse,json,sqlite3,sys
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_plantuml_natural_candidate_v10 as compiler
import compiler_plantuml_iteration_case_v3 as case
from compiler_types_program_v1 import asset,checked,immutable,raw,sha
DIRECTORY=R/'release/compiler_iterations/controls/plantuml_textlength_full_source_label_controls_20261101_v1'

def main(report_file):
 from PIL import Image
 from plantuml_marker_calibration_proof_v1 import PLAN,REPORT,verified
 from plantuml_marker_grid_rule_v1 import POLICY
 report_file=Path(report_file).resolve(strict=True);report=json.loads(report_file.read_bytes());config=compiler.configuration();calibration=verified()
 if report.get('passed') is not True or report.get('configuration_unchanged') is not True or report['configuration']!=config:raise ValueError('finite_control_frontend_or_quality_identity_changed')
 positives=[row for row in report['positives'] if (row.get('full_quality') or {}).get('ok')];negatives=report['negatives']
 if not positives or len(negatives)!=7 or not all(row['rejected'] and row['fresh_source_rejected'] for row in negatives):raise ValueError('actual_full_quality_controls_incomplete')
 if not next(row['full_closed_paint_lower_bound_exceeds_one_pixel'] for row in negatives if row['name']=='oversized_native_marker'):raise ValueError('physical_greater_than_one_pixel_negative_not_proven')
 proof={'schema':'compiler_plantuml_iteration_controls_v3','producer':asset(__file__),'development':asset(report_file),'frozen_frontend':config,'positives':[],'positive_cases':[],'negatives':[],'negative_cases':[],'marker_raster_policy':POLICY,'calibration_summary':{k:v for k,v in calibration.items() if k!='pins'},'calibration':{'preregistered_plan.json':asset(PLAN),'report.json':asset(REPORT)},'model_calls':0,'unseen_consumed':0,'canonical_mutations':0};manifests=[]
 # Validate every candidate/proof before any publication directory is created.
 for row in positives:
  _,blob=checked(row['record']);record=json.loads(blob);_,blob=checked(row['full_quality']['report']);qa=json.loads(blob);case.full_quality(qa,record)
  if qa['input_record_sha256']!=row['record']['sha256'] or qa['profile_policy']!=config['policy']:raise ValueError('positive_metadata_or_policy_binding_changed')
 for row in negatives:
  _,blob=checked(row['candidate']);record=json.loads(blob);_,blob=checked(row['qa']);qa=json.loads(blob);profile=qa.get('checks',{}).get('source',{})
  if qa['ok'] is not False or not qa['failures'] or profile.get('ok') is not False or not profile.get('failures') or qa['input_record_sha256']!=row['candidate']['sha256'] or qa['profile_policy']!=config['policy']:raise ValueError('negative_full_source_rejection_or_binding_changed')
  for path,digest in qa['implementation_pins'].items():
   if sha(Path(path).read_bytes())!=digest:raise ValueError('negative_implementation_changed:'+path)
  stored=Image.open(R/record['image_file']).convert('RGBA');fresh=Image.open(Path(row['qa']['file']).parent/'fresh_native.png').convert('RGBA')
  if stored.size!=fresh.size or stored.tobytes()!=fresh.tobytes():raise ValueError('negative_png_not_actual_fresh_native_pixels')
 DIRECTORY.mkdir(parents=True,exist_ok=False)
 for row in positives:
  record=json.loads(checked(row['record'])[1]);qa=json.loads(checked(row['full_quality']['report'])[1]);proof['positives'].append(row['full_quality']['report']);proof['positive_cases'].append({'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':row['record'],'qa':row['full_quality']['report']})
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:source=json.loads(db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0])
  manifests.append(case.publish(record,source,qa,Path(row['full_quality']['report']['file']).parent))
 for row in negatives:
  record=json.loads(checked(row['candidate'])[1]);proof['negatives'].append(row['qa']);proof['negative_cases'].append({'name':row['name'],'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':row['candidate'],'qa':row['qa'],'rehashed_XML_and_actual_native_PNG':True,'actual_source_rejection':True,'full_closed_paint_lower_bound_exceeds_one_pixel':row['full_closed_paint_lower_bound_exceeds_one_pixel']})
 immutable(DIRECTORY/'qualified.jsonl',b''.join(raw(row) for row in manifests));proof['qualified_manifest']=asset(DIRECTORY/'qualified.jsonl')
 if compiler.configuration()!=config:raise ValueError('compiler_changed_during_control_publication')
 immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':str(DIRECTORY/'proof.json'),'positive_controls':len(positives),'actual_negative_controls':len(negatives),'unseen_consumed':0,'validation_reserved':False,'mass_started':False}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args();main(args.report)
