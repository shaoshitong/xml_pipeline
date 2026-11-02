import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('canvas',Path(__file__).with_name('round2_canvas_repair_v1.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CanvasTests(unittest.TestCase):
 def source(self):return {'code_sha256':'code','image_sha256':'image'}
 def job(self):return {'id':'id','format':'html','category':'poster','source':'data','input_record':json.dumps(self.source())}
 def record(self):return {'id':'id','source_pair_sha256':'id','source_format':'html','category':'poster','source':'data','source_code_sha256':'code','source_image_sha256':'image'}
 def test_identity(self):self.assertEqual(m.validate_identity(self.record(),self.job()),self.source())
 def test_source_hash_change(self):
  r=self.record();r['source_code_sha256']='other'
  with self.assertRaises(ValueError):m.validate_identity(r,self.job())
 def test_wrong_id(self):
  r=self.record();r['id']='other'
  with self.assertRaises(ValueError):m.validate_identity(r,self.job())
 def test_wrong_format(self):
  r=self.record();r['source_format']='svg'
  with self.assertRaises(ValueError):m.validate_identity(r,self.job())
 def test_wrong_category(self):
  r=self.record();r['category']='web'
  with self.assertRaises(ValueError):m.validate_identity(r,self.job())
 def test_selector_fail_only(self):self.assertFalse(m.eligible_failure({'status':'qualified','detail':m.REASONS[0]}))
 def test_selector_canvas(self):self.assertTrue(m.eligible_failure({'status':'abandoned','detail':[m.REASONS[0]]}))
 def test_selector_runtime_not_canvas(self):self.assertFalse(m.eligible_failure({'status':'abandoned','detail':'missing native runtime'}))
 def test_immutable_artifacts(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x';m._write(p,b'a');m._write(p,b'a')
   with self.assertRaises(ValueError):m._write(p,b'b')
 def test_job_tuple(self):
  j=self.job();row=tuple(j.get(k) for k in m.JOB_COLUMNS);self.assertEqual(m.validate_identity(self.record(),row),self.source())
if __name__=='__main__':unittest.main()
