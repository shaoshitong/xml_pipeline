"""Normalize already executed, frozen full native controls; no unseen dispatch."""
import argparse,fcntl,json,sqlite3,sys
from pathlib import Path
from compiler_types_program_v1 import R,W,asset,checked,immutable,raw,sha
import compiler_tikz_source_viewport_v1 as compiler
import compiler_tikz_iteration_case_v2 as case
from compiler_typed_runtime_failure_v1 import is_infrastructure
RECEIPT=R/'release/compiler_tikz_fixed_frame_adapter_controls_v1/758e08da7353401d9c1d0f81ea931b3e/receipt.json'
RECEIPT_SHA='2fbe0ead23d18d180d49f16cd27e4de557e47d1ea1ee6d939db8b662b308616c'
DIRECTORY=R/'release/compiler_iterations/controls/tikz_fixed_inspection_controls_20261101_v1'

def verify_case(row,role):
 _,blob=checked(row['record']);record=json.loads(blob);_,payload=checked(row['quality']);q=json.loads(payload)
 if q.get('input_record_sha256')!=row['record']['sha256'] or q['id']!=record['id']:raise ValueError('actual_control_metadata_QA_identity_changed')
 for field,digest in (('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')):checked({'file':record[field],'sha256':record[digest]},clean=True)
 for item in record[compiler.FIELD]['files'].values():checked(item,clean=True)
 for name,digest in q['implementation_pins'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('actual_control_implementation_changed:'+name)
 if role=='positive':
  case.full_quality(q,record);fresh=Path(q['evidence_file']).parent/'fresh.png';checked({'file':str(fresh),'sha256':record['image_sha256']})
 else:
  profile=q.get('checks',{}).get('source_preliminary',{})
  if q.get('ok')is not False or not any(x.get('reason')=='fresh_source_geometry_text_marker_or_endpoint_changed'for x in profile.get('failures',[])):raise ValueError('actual_rehashed_negative_source_replay_not_rejected')
 return record,q

def produce(inventory):
 if sha(RECEIPT.read_bytes())!=RECEIPT_SHA:raise ValueError('frozen_actual_control_receipt_changed')
 receipt=json.loads(RECEIPT.read_bytes());config=compiler.configuration()
 if config!=receipt['configuration']:raise ValueError('frozen_frontend_changed_before_controls')
 inventory=Path(inventory).resolve(strict=True);summary=json.loads((inventory/'summary.json').read_bytes());accepted=inventory/'qualified.jsonl'
 if summary.get('accepted_integrity_errors')or sha(accepted.read_bytes())!=summary['files']['qualified.jsonl']['sha256']:raise ValueError('verified_inventory_changed_or_integrity_errors')
 accepted_ids={json.loads(line)['id']for line in accepted.read_bytes().splitlines()if line}
 DIRECTORY.mkdir(parents=True,exist_ok=False)
 with(DIRECTORY/'producer.lock').open('a+')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  proof={'schema':'compiler_tikz_iteration_controls_v2','producer':asset(__file__),'actual_receipt':asset(RECEIPT),'inventory':asset(inventory/'summary.json'),'frozen_frontend':config,'positives':[],'negatives':[],'positive_cases':[],'negative_cases':[],'model_calls':0,'unseen_consumed':0,'canonical_mutations':0}
  records=[]
  for item in receipt['positives']:
   record,q=verify_case(item,'positive');records.append((record,q));row={'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':item['record'],'qa':item['quality']};proof['positive_cases'].append(row);proof['positives'].append(item['quality'])
  for item in receipt['actual_semantic_negatives']:
   row={'record':{'file':item['record_file'],'sha256':item['record_sha256']},'quality':{'file':item['quality_report'],'sha256':item['quality_report_sha256']}};record,q=verify_case(row,'negative');proof['negative_cases'].append({'name':item['kind'],'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':row['record'],'qa':row['quality'],'rehashed_XML_and_actual_native_PNG':True});proof['negatives'].append(row['quality'])
  # Re-execute the real viewport omission rejection under these exact pins.
  negative_receipt=Path(receipt['negative_receipt']['file']);checked(receipt['negative_receipt']);bad=negative_receipt.parent/'actual_wrong_viewport.drawio';data=bad.read_bytes()
  if sha(data)!=receipt['actual_viewport_omission_negative']['wrong_viewport_code_sha256']:raise ValueError('actual_wrong_viewport_code_changed')
  from tikz_native_export_frame_v1 import render
  try:render(data.decode(),1,1)
  except Exception as error:
   expected='Declared export viewport does not contain the complete source paint/source page'
   if expected not in str(error)or is_infrastructure(exception=error):raise ValueError('wrong_viewport_not_rejected_by_exact_paint_safety_guard')from error
   evidence={'rejected':True,'expected_reason':expected,'actual_error':str(error),'infrastructure_failure':False,'code_sha256':sha(data),'renderer':asset(W/'rendering_tikz_export_view_v2/remote_render.py')}
  else:raise ValueError('viewport_negative_false_acceptance')
  immutable(DIRECTORY/'actual_viewport_omission.json',raw(evidence));proof['viewport_negative']={'proof':asset(DIRECTORY/'actual_viewport_omission.json'),'code':asset(bad)}
  manifests={};preserved=[]
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:
   for record,q in records:
    job=db.execute('select * from jobs where id=?',(record['id'],)).fetchone();source=json.loads(job[4]);assert source['code_sha256']==record['source_code_sha256']and source['image_sha256']==record['source_image_sha256']
    if record['id']in accepted_ids:preserved.append(record['id'])
    else:manifests[record['id']]=case.publish(record,source,q,Path(q['evidence_file']).parent)
    if db.execute('select * from jobs where id=?',(record['id'],)).fetchone()!=job:raise RuntimeError('infrastructure_canonical_original_changed')
  immutable(DIRECTORY/'qualified.jsonl',b''.join(raw(manifests[i])for i in sorted(manifests)));proof.update(qualified_manifest=asset(DIRECTORY/'qualified.jsonl'),new_unique_qualified=len(manifests),preserved_existing_qualified=preserved)
  if compiler.configuration()!=config:raise RuntimeError('infrastructure_frontend_changed_during_controls')
  immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':asset(DIRECTORY/'proof.json'),'positive_controls':len(records),'new_unique_qualified':len(manifests),'semantic_negatives':len(proof['negative_cases']),'viewport_negative':True}),flush=True);return proof
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,required=True);a=p.parse_args();produce(a.inventory)
