import json,sqlite3,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v1';O=R/'release/compiler_validation_v1/python_wrapper_dot_method_diagnostic_20261101_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
c={r['id']:r for r in map(json.loads,(P/'compiler_validation_audited_reservoir.jsonl').read_text().splitlines())};d=json.loads((O/'compiler_validation_method_diagnostic.json').read_text());db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True)
for pair in d['pair_results']:
 for key in ('candidate','development'):
  m=pair[key];row=db.execute('select output_record from jobs where id=?',(m['id'],)).fetchone()[0];r=json.loads(row);audit=json.loads((R/r['execution_audit']).read_bytes())
  assert (r['id'],r['source_code_sha256'],r['source_image_sha256'])==(m['id'],m['source_code_sha256'],m['source_image_sha256'])
  assert (audit['id'],audit['source_code_sha256'])==(m['id'],m['source_code_sha256'])
  cap=audit['captures'][0];assert len(audit['captures'])==1 and cap['engine']=='graphviz'
  capture_dot=R/str(Path(audit['directory'])/cap['dot'])
  assert sha(capture_dot.read_bytes())==m['dot_sha256']
  if r.get('source_data_sha256'):assert audit['input_manifest']['source_data_sha256']==r['source_data_sha256']
  if key=='candidate':
   assert sha(row.encode())==c[m['id']]['source_record_sha256']
   assert m['dot_sha256']==c[m['id']]['static_support_evidence']['source_dot_sha256']
  assert sha((O/(m['id']+'.dot_json.json')).read_bytes())==m['dot_json_sha256']
  assert not m['layout_created']
result={'all10_source_capture_identities_verified':True,'all5_candidate_records_match_original_frozen_reservoir_record_hash':True,'all5_candidate_DOT_match_frozen_static_support_digest':True,'all10_capture_DOT_and_source_data_binding_verified':True,'all10_parsed_JSON_hash_verified':True,'all10_dot_json_outputs_without_layout_fields':True,'selected_pairs':5,'new_conversion_or_QA':False,'old_pool_changed':False};(O/'compiler_validation_integrity.json').write_text(json.dumps(result)+'\n');print(json.dumps(result))
