import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('round2_font_repair_v1',Path(__file__).with_name('round2_font_repair_v1.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.w=self.root/'conversion';self.w.mkdir();self.work=self.w/'attempt'
  self.s={'format':'python','code_sha256':'c','image_sha256':'i'};self.job={'id':'id','input_record':json.dumps(self.s)};self.r={'id':'id','source_pair_sha256':'id','source_code_sha256':'c','source_image_sha256':'i','source_format':'python'}
 def tearDown(self):self.tmp.cleanup()
 def repair(self,r=None,j=None,work=None):
  with patch.object(m,'R',self.root),patch.object(m,'W',self.w):return m.repair(r or self.r,j or self.job,work or self.work)
 def test_job_tuple_mapping(self):
  x=m.job_dict(tuple(range(13)));self.assertEqual(x['worker_pid'],12);self.assertEqual(x['input_record'],4)
 def test_job_dict_identity(self):self.assertIs(m.job_dict(self.job),self.job)
 def test_work_outside_root_refused(self):
  r=self.repair(work=self.root/'outside');self.assertFalse(r['ok']);self.assertEqual(r['reason'],'font_work_outside_conversion');self.assertFalse((self.root/'outside').exists())
 def test_wrong_original_id_refused(self):
  r=self.repair(r={**self.r,'id':'different'});self.assertEqual(r['reason'],'font_source_identity_mismatch')
 def test_wrong_source_code_hash_refused(self):
  r=self.repair(r={**self.r,'source_code_sha256':'bad'});self.assertEqual(r['reason'],'font_source_identity_mismatch')
 def test_wrong_source_image_hash_refused(self):
  r=self.repair(r={**self.r,'source_image_sha256':'bad'});self.assertEqual(r['reason'],'font_source_identity_mismatch')
 def test_format_identity_refused(self):
  r=self.repair(r={**self.r,'source_format':'html'});self.assertEqual(r['reason'],'font_format_identity_mismatch')
 def test_failure_reports_no_model_no_db_write(self):
  r=self.repair(r={**self.r,'id':'bad'});self.assertEqual(r['model_calls'],0);self.assertFalse(r['canonical_db_written']);self.assertTrue((self.work/'failure.json').exists())
 def test_immutable_artifact_repeat_same(self):
  p=self.root/'file';m.save(p,b'one');m.save(p,b'one');self.assertEqual(p.read_bytes(),b'one')
 def test_immutable_artifact_replacement_refused(self):
  p=self.root/'file';m.save(p,b'one')
  with self.assertRaises(ValueError):m.save(p,b'two')
 def test_checked_hash_changed(self):
  p=self.root/'file';p.write_bytes(b'one')
  with patch.object(m,'R',self.root):
   with self.assertRaises(ValueError):m.checked('file',m.sha(b'bad'))
 def test_checked_external_symlink_refused(self):
  p=self.root/'file';p.symlink_to('/etc/hosts')
  with patch.object(m,'R',self.root):
   with self.assertRaises(ValueError):m.checked('file','x')
if __name__=='__main__':unittest.main()
