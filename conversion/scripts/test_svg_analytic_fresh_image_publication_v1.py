import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import svg_analytic_iteration_case_v1 as case
class FreshImagePublicationTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve();self.clean=self.root/'clean/candidate';self.clean.mkdir(parents=True);self.directory=self.root/'conversion/QA';self.directory.mkdir(parents=True);self.code=self.clean/'candidate.drawio';self.code.write_bytes(b'synthetic XML placeholder');image=Image.new('RGBA',(8,8),(50,100,200,200));a=io.BytesIO();image.save(a,format='PNG',compress_level=0);self.original=a.getvalue();self.old=self.clean/'old.png';self.old.write_bytes(self.original);b=io.BytesIO();image.save(b,format='PNG',compress_level=9);self.fresh=b.getvalue();self.record=dict(code_file=str(self.code.relative_to(self.root)),code_sha256=case.sha(self.code.read_bytes()),image_file=str(self.old.relative_to(self.root)),image_sha256=case.sha(self.original));self.report=dict(ok=True,checks=dict(render=dict(image_sha256=case.sha(self.fresh))));(self.directory/'fresh.png').write_bytes(self.fresh)
  p=patch.object(case,'R',self.root);p.start();self.addCleanup(p.stop)
  p=patch.object(case,'checked',side_effect=lambda file,digest:self.read(file,digest));p.start();self.addCleanup(p.stop)
 def read(self,file,digest):
  b=(self.root/file).read_bytes();self.assertEqual(case.sha(b),digest);return b
 def test_different_codec_same_RGBA_gets_new_immutable_clean_path(self):
  self.assertNotEqual(self.original,self.fresh);out=case.stage_fresh_image(self.record,self.report,self.directory);self.assertNotEqual(out['image_file'],self.record['image_file']);self.assertEqual((self.root/out['image_file']).read_bytes(),self.fresh);self.assertEqual(self.old.read_bytes(),self.original);self.assertEqual(self.record['image_sha256'],case.sha(self.original))
 def test_same_fresh_bytes_reuse_original_path(self):
  (self.directory/'fresh.png').write_bytes(self.original);self.report['checks']['render']['image_sha256']=case.sha(self.original);self.assertIs(case.stage_fresh_image(self.record,self.report,self.directory),self.record)
 def test_RGBA_change_cannot_be_published_as_codec_difference(self):
  x=io.BytesIO();Image.new('RGBA',(8,8),(51,100,200,200)).save(x,format='PNG');bad=x.getvalue();(self.directory/'fresh.png').write_bytes(bad);self.report['checks']['render']['image_sha256']=case.sha(bad)
  with self.assertRaisesRegex(ValueError,'pixels_changed'):case.stage_fresh_image(self.record,self.report,self.directory)
 def test_failed_QA_and_unbound_fresh_hash_cannot_create_new_assets(self):
  self.report['ok']=False
  with self.assertRaisesRegex(ValueError,'successful_independent'):case.stage_fresh_image(self.record,self.report,self.directory)
  self.report['ok']=True;self.report['checks']['render']['image_sha256']='other'
  with self.assertRaisesRegex(RuntimeError,'fresh_QA_image_changed'):case.stage_fresh_image(self.record,self.report,self.directory)
if __name__=='__main__':unittest.main()
