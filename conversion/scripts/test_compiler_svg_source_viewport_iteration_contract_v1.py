"""Full-source constructor/snapshot checks before any program/run directory."""
import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import compiler_svg_source_viewport_iteration_program_v1 as program
import compiler_svg_source_viewport_unseen_pool_v1 as pool
class CanonicalContractTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.db=Path(self.tmp.name)/'jobs.sqlite';self.source={'pair_sha256':'id','category':'scientific_diagram','format':'svg','source':'dataset','code_sha256':'code','image_sha256':'image','metadata':{'source_svg_sha256':'code','literal':'retained'}};self.old={'code_sha256':'priorcode','image_sha256':'priorimage'};self.job=('id','scientific_diagram','svg','dataset',json.dumps(self.source),'pending',None,0,None,json.dumps(self.old),None,None,None)
  with sqlite3.connect(self.db)as d:d.execute('create table jobs (id text primary key,category,format,source,input_record,state,route,attempts,updated_at,output_record,error,input_manifest,worker_pid)');d.execute('insert into jobs values (?,?,?,?,?,?,?,?,?,?,?,?,?)',self.job)
 def row(self):return pool.request_from_job(self.job,self.source,'unit')
 def test_constructor_keeps_complete_nested_canonical_source(self):self.assertEqual(self.row()['source'],self.source);self.assertTrue(program.validate_source_requests([self.row()],database=self.db))
 def test_five_field_identity_summary_is_not_worker_source(self):
  r=self.row();r['source']={k:self.source[k]for k in ('category','format','source','code_sha256','image_sha256')}
  with self.assertRaisesRegex(ValueError,'requires_complete_canonical'):program.validate_source_requests([r],database=self.db)
 def test_constructor_rejects_identity_summary_before_worker(self):
  with self.assertRaisesRegex(ValueError,'complete_canonical_source'):pool.request_from_job(self.job,{'format':'svg'},'unit')
 def test_nested_source_metadata_cannot_be_dropped(self):
  r=self.row();r['source']=dict(r['source']);r['source'].pop('metadata')
  with self.assertRaisesRegex(ValueError,'requires_complete_canonical'):program.validate_source_requests([r],database=self.db)
 def test_baseline_record_exact_raw_snapshot_is_required(self):
  r=self.row();r['source_record_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'baseline_record_snapshot'):program.validate_source_requests([r],database=self.db)
 def test_baseline_code_and_image_hashes_must_both_match(self):
  for field in ('baseline_code_sha256','baseline_image_sha256'):
   r=self.row();r[field]='wrong'
   with self.assertRaisesRegex(ValueError,'baseline_asset_snapshot'):program.validate_source_requests([r],database=self.db)
 def test_wrong_format_is_rejected_even_with_complete_source(self):
  r=self.row()
  with self.assertRaisesRegex(ValueError,'outside_original_scope'):program.validate_source_requests([r],fmt='mermaid',database=self.db)
 def test_all_population_rows_are_checked(self):
  a=self.row();b=copy.deepcopy(a);b['source_record_sha256']='bad'
  with self.assertRaisesRegex(ValueError,'baseline_record_snapshot'):program.validate_source_requests([a,b],database=self.db)
class NewlyQualifiedTests(unittest.TestCase):
 def row(self):return {'id':'x','source_code_sha256':'c','source_image_sha256':'i',**{k:v for k,v in [('code_file','code'),('code_sha256','ch'),('image_file','image'),('image_sha256','ih'),('metadata_file','meta'),('metadata_sha256','mh'),('original_source_code','source'),('original_reference','reference')]}}
 def test_new_qualification_requires_all_five_clean_assets(self):
  import compiler_svg_source_viewport_unseen_pool_v1 as p
  with patch.object(p,'supplementary_qualified',return_value=[self.row()]),patch.object(program.common,'checked')as checked:
   self.assertEqual(set(program.refreshed_qualified([{'id':'x','source':{'code_sha256':'c','image_sha256':'i'}}])),{'x'});self.assertEqual(checked.call_count,5);self.assertTrue(all(c.kwargs['clean']for c in checked.call_args_list))
 def test_conflicting_original_identity_is_not_reused(self):
  import compiler_svg_source_viewport_unseen_pool_v1 as p
  with patch.object(p,'supplementary_qualified',return_value=[self.row()]):
   with self.assertRaisesRegex(ValueError,'original_identity_changed'):program.refreshed_qualified([{'id':'x','source':{'code_sha256':'different','image_sha256':'i'}}])
if __name__=='__main__':unittest.main()
