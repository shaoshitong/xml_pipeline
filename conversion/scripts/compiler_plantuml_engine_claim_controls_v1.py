"""Immutable ownership controls, additional to all frozen source QA controls."""
from pathlib import Path
import json,hashlib
W=Path('/backup/shaoshitong/img2code_20261029/conversion')
PROOF=W/'plantuml_engine_stale_claim_controls_v1/fixed_20261101_v1/proof.json'
def sha(b):return hashlib.sha256(b).hexdigest()
def configuration():
 verify()
 return {str(PROOF):sha(PROOF.read_bytes())}
def verify():
 from compiler_types_program_v1 import checked
 from compiler_plantuml_engine_iteration_case_v3 import full_quality
 body=json.loads(PROOF.read_bytes())
 if body['schema']!='PlantUML_actual_stale_claim_and_full_quality_controls_v1' or body['canonical_mutations']!=0:raise ValueError('canonical_claim_controls_missing_or_wrong')
 for name,digest in body['implementation_pins'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('claim_control_implementation_changed:'+name)
 for ref in body['assets'].values():checked(ref)
 actual=body['actual_stale_contract']
 if not actual['source_contract']['ok']or not actual['diagnostic']['conversion_allowed']or not actual['diagnostic']['status'].startswith('stale_')or actual['canonical_row_unchanged']is not True:raise ValueError('actual_stale_canonical_contract_not_proven')
 for row in body['positive_full_quality']:
  _,b=checked(row['report']);qa=json.loads(b);_,b=checked(row['candidate']);record=json.loads(b);full_quality(qa,record)
 if not body['positive_full_quality']:raise ValueError('new_claim_RO_complete_QA_positive_missing')
 for row in body['negative_claim_controls']:
  _,b=checked(row['report']);qa=json.loads(b)
  if qa.get('ok')is not False or not any(x['reason']=='deferred_canonical_live_or_uncertain_worker_claim'for x in qa.get('failures',[])):raise ValueError('actual_live_claim_RO_false_acceptance')
 if not body['negative_claim_controls']:raise ValueError('actual_live_claim_RO_negative_missing')
 return body
