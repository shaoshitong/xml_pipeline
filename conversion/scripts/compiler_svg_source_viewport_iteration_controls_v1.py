"""Normalize real SOURCE viewport controls and publish only full-QA positives."""
import argparse,fcntl,json,sqlite3
from pathlib import Path
from compiler_types_program_v1 import R,W,asset,checked,immutable,raw,sha
import compiler_svg_source_viewport_frontend_v1 as compiler
import compiler_svg_source_viewport_iteration_case_v1 as case
DIRECTORY=R/'release/compiler_iterations/controls/svg_source_surface_controls_20261101_v1'

def verify_case(record_ref,quality_ref,role):
 _,blob=checked(record_ref);record=json.loads(blob);_,payload=checked(quality_ref);q=json.loads(payload)
 if q.get('input_record_sha256')!=record_ref['sha256']or q['id']!=record['id']:raise ValueError('actual_source_viewport_control_metadata_changed')
 for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_png','source_render_png_sha256'),('source_full_inspection','source_full_inspection_sha256'),('native_full_inspection','native_full_inspection_sha256'),('native_svg_export','native_svg_export_sha256'),('source_viewport_proof','source_viewport_proof_sha256')]:checked({'file':record[field],'sha256':record[digest]},clean=True)
 if q['profile_policy']!=compiler.configuration()['policy']:raise ValueError('source_viewport_control_policy_changed')
 for name,digest in q['implementation_pins'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('source_viewport_control_implementation_changed:'+name)
 if role=='positive':
  case.full_quality(q,record);checked({'file':str(Path(q['evidence_file']).parent/'fresh.png'),'sha256':record['image_sha256']})
 elif role=='negative':
  profile=q.get('checks',{}).get('source',{})
  if q.get('ok')is not False or not q['failures']or profile.get('ok')is not False or not profile.get('failures'):raise ValueError('actual_rehashed_SOURCE_negative_not_rejected')
 else:raise ValueError('unknown_source_viewport_control_role')
 return record,q

def produce(inventory,receipt):
 receipt=Path(receipt).resolve(strict=True)
 if not receipt.is_relative_to(R/'release/compiler_svg_source_viewport_adapter_controls_v1'):raise ValueError('actual_controls_receipt_outside_owner')
 data=json.loads(receipt.read_bytes());config=compiler.configuration()
 if not data.get('passed')or not data.get('frozen')or data.get('configuration')!=config:raise ValueError('actual_source_viewport_controls_not_frozen')
 for name,digest in data['owned_implementation'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('source_viewport_actual_receipt_code_changed:'+name)
 inventory=Path(inventory).resolve(strict=True);summary=json.loads((inventory/'summary.json').read_bytes());qualified=inventory/'qualified.jsonl'
 if summary.get('accepted_integrity_errors')or sha(qualified.read_bytes())!=summary['files']['qualified.jsonl']['sha256']:raise ValueError('qualified_inventory_changed_or_integrity_errors')
 accepted={json.loads(line)['id']for line in qualified.read_bytes().splitlines()if line}
 from compiler_svg_source_viewport_unseen_pool_v1 import supplementary_qualified
 accepted.update(x['id']for x in supplementary_qualified())
 DIRECTORY.mkdir(parents=True,exist_ok=False)
 with(DIRECTORY/'producer.lock').open('a+')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  proof={'schema':'compiler_svg_source_viewport_iteration_controls_v1','producer':asset(__file__),'actual_receipt':asset(receipt),'inventory':asset(inventory/'summary.json'),'frozen_frontend':config,'positives':[],'negatives':[],'positive_cases':[],'negative_cases':[],'model_calls':0,'unseen_consumed':0,'canonical_mutations':0};records=[]
  for item in data['positives']:
   r,q=verify_case(item['record'],item['quality'],'positive');records.append((r,q));row={'id':r['id'],'source_code_sha256':r['source_code_sha256'],'source_image_sha256':r['source_image_sha256'],'candidate':item['record'],'qa':item['quality']};proof['positive_cases'].append(row);proof['positives'].append(item['quality'])
  for item in data['actual_semantic_negatives']:
   r,q=verify_case(item['record'],item['quality'],'negative')
   if not(item['actual_PNG_changed']and item['actual_code_and_PNG_rehashed']):raise ValueError('negative_was_only_forged_metadata')
   row={'name':item['kind'],'id':r['id'],'source_code_sha256':r['source_code_sha256'],'source_image_sha256':r['source_image_sha256'],'candidate':item['record'],'qa':item['quality'],'rehashed_XML_and_actual_native_PNG':True};proof['negative_cases'].append(row);proof['negatives'].append(item['quality'])
   if item['kind']=='wrong_original_viewport':proof['viewport_negative']={**row,'proof':item['receipt']}
  if len(records)<2 or len(proof['negative_cases'])!=4 or not proof.get('viewport_negative'):raise ValueError('source_viewport_controls_incomplete')
  manifests={};preserved=[]
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:
   for r,q in records:
    row=db.execute('select * from jobs where id=?',(r['id'],)).fetchone();s=json.loads(row[4])
    if(s['code_sha256'],s['image_sha256'])!=(r['source_code_sha256'],r['source_image_sha256']):raise ValueError('control_original_identity_changed')
    if r['id']in accepted:preserved.append(r['id'])
    else:manifests[r['id']]=case.publish(r,s,q,Path(q['evidence_file']).parent)
    if db.execute('select * from jobs where id=?',(r['id'],)).fetchone()!=row:raise RuntimeError('infrastructure_control_original_job_changed')
  immutable(DIRECTORY/'qualified.jsonl',b''.join(raw(manifests[i])for i in sorted(manifests)));proof.update(qualified_manifest=asset(DIRECTORY/'qualified.jsonl'),new_unique_qualified=len(manifests),preserved_existing_qualified=preserved)
  if compiler.configuration()!=config:raise RuntimeError('infrastructure_frontend_changed_during_control_publication')
  immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':asset(DIRECTORY/'proof.json'),'positive_controls':len(records),'new_unique_qualified':len(manifests),'semantic_negatives':len(proof['negative_cases']),'viewport_negative':True}),flush=True);return proof
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();produce(a.inventory,a.receipt)
