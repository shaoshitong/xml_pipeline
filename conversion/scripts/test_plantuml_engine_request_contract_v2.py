import copy,json,sqlite3,tempfile,unittest,hashlib
from pathlib import Path
import compiler_plantuml_engine_request_contract_v2 as c
class Contract(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.db=Path(self.t.name)/'fixture.sqlite';self.source={'pair_sha256':'a'*64,'category':'scientific_diagram','format':'plantuml','source':'fixture','code_sha256':'b'*64,'image_sha256':'c'*64,'image_info':{'width':100,'height':80},'metadata':{'annotation':'preserve all canonical fields'}};self.existing={'code_sha256':'d'*64,'image_sha256':'e'*64,'complete':'snapshot'};self.output=json.dumps(self.existing)
  with sqlite3.connect(self.db)as db:db.execute('create table jobs (id text primary key,input_record text,output_record text,category text,format text,source text,worker_pid integer,state text,updated_at text)');db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?)',(self.source['pair_sha256'],json.dumps(self.source),self.output,'scientific_diagram','plantuml','fixture',None,'pending','2026-11-01T00:00:00+00:00'))
  self.row={'id':self.source['pair_sha256'],'source':copy.deepcopy(self.source),'compiler_unit':'fixture-unit','source_record_sha256':c.sha(self.output.encode()),'baseline_code_sha256':self.existing['code_sha256'],'baseline_image_sha256':self.existing['image_sha256']}
 def tearDown(self):self.t.cleanup()
 def valid(self,row=None):return c.validate([row or self.row],self.db,'fixture-unit')
 def test_full_canonical_and_baseline_pass_readonly(self):
  before=self.db.read_bytes();r=self.valid();self.assertTrue(r['ok']);self.assertEqual(before,self.db.read_bytes())
 def test_five_field_scope_digest_rejected(self):
  r=copy.deepcopy(self.row);r['source']={k:self.source[k]for k in ('category','format','source','code_sha256','image_sha256')}
  with self.assertRaisesRegex(ValueError,'full_canonical_source_mismatch'):self.valid(r)
 def test_missing_nested_metadata_rejected(self):
  r=copy.deepcopy(self.row);del r['source']['metadata']
  with self.assertRaisesRegex(ValueError,'full_canonical_source_mismatch'):self.valid(r)
 def test_nested_source_edit_rejected(self):
  r=copy.deepcopy(self.row);r['source']['image_info']['width']=101
  with self.assertRaisesRegex(ValueError,'full_canonical_source_mismatch'):self.valid(r)
 def test_missing_source_record_sha_rejected(self):
  r=copy.deepcopy(self.row);del r['source_record_sha256']
  with self.assertRaisesRegex(ValueError,'snapshot_field_missing'):self.valid(r)
 def test_stale_output_record_sha_rejected(self):
  r=copy.deepcopy(self.row);r['source_record_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'output_record_snapshot_changed'):self.valid(r)
 def test_stale_baseline_code_rejected(self):
  r=copy.deepcopy(self.row);r['baseline_code_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'candidate_baseline_changed'):self.valid(r)
 def test_stale_baseline_image_rejected(self):
  r=copy.deepcopy(self.row);r['baseline_image_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'candidate_baseline_changed'):self.valid(r)
 def test_selected_population_source_mismatch_rejected(self):
  folder=Path(self.t.name)/'pool';folder.mkdir();r=copy.deepcopy(self.row);r['seq']=1;p=copy.deepcopy(self.row);p['source']={k:self.source[k]for k in ('category','format','source','code_sha256','image_sha256')};(folder/'selected.jsonl').write_text(json.dumps(r)+'\n');(folder/'supported_population.jsonl').write_text(json.dumps(p)+'\n')
  with self.assertRaisesRegex(ValueError,'selected_population_snapshot_mismatch'):c.validate_pool(folder,self.db,'fixture-unit')
 def test_complete_selected_population_pass(self):
  folder=Path(self.t.name)/'pool';folder.mkdir();r=copy.deepcopy(self.row);r['seq']=1;(folder/'selected.jsonl').write_text(json.dumps(r)+'\n');(folder/'supported_population.jsonl').write_text(json.dumps(self.row)+'\n');self.assertTrue(c.validate_pool(folder,self.db,'fixture-unit')['ok'])
 def test_empty_baseline_must_still_snapshot(self):
  with sqlite3.connect(self.db)as db:db.execute('update jobs set output_record=null')
  r=copy.deepcopy(self.row);r.update(source_record_sha256=c.sha(b''),baseline_code_sha256=None,baseline_image_sha256=None);self.assertTrue(self.valid(r)['ok'])
 def test_nonempty_baseline_whitespace_change_detected(self):
  with sqlite3.connect(self.db)as db:db.execute('update jobs set output_record=?',(' '+self.output,))
  with self.assertRaisesRegex(ValueError,'output_record_snapshot_changed'):self.valid()
 @unittest.skipUnless(Path('/proc').is_dir(),'actual Linux proc control runs remotely')
 def test_actual_live_claim_is_per_target_deferral_not_pool_failure(self):
  import os,datetime
  with sqlite3.connect(self.db)as db:db.execute('update jobs set worker_pid=?,updated_at=?',(os.getpid(),datetime.datetime.now(datetime.timezone.utc).isoformat()))
  r=self.valid();self.assertTrue(r['ok']);self.assertEqual(r['deferred_live_or_uncertain_ids'],[self.row['id']]);self.assertFalse(r['canonical_claims_readonly'][0]['conversion_allowed'])
 def test_definitely_absent_claim_is_allowed_without_mutating_row(self):
  with sqlite3.connect(self.db)as db:db.execute('update jobs set worker_pid=?',(2147483647,))
  before=self.db.read_bytes();r=self.valid();self.assertTrue(r['ok']);self.assertEqual(r['stale_claim_ids'],[self.row['id']]);self.assertEqual(before,self.db.read_bytes())
 def test_owner_diagnostics_do_not_mask_exact_source_change(self):
  import os
  with sqlite3.connect(self.db)as db:db.execute('update jobs set worker_pid=?',(os.getpid(),))
  r=copy.deepcopy(self.row);r['source']['metadata']['annotation']='bad'
  with self.assertRaisesRegex(ValueError,'full_canonical_source_mismatch'):self.valid(r)
if __name__=='__main__':unittest.main(verbosity=2)
