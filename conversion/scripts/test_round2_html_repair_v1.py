import importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('round2html',Path(__file__).with_name('round2_html_repair_v1.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
XML='<mxfile><diagram><mxGraphModel pageWidth="100" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>'
class HtmlTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.work=self.root/'conversion/work';self.work.mkdir(parents=True)
  self.r={'id':'id','source_format':'html','category':'poster','source_code_sha256':'c','source_image_sha256':'i','code_file':'code','code_sha256':'x','image_file':'image','image_sha256':'p','original_source_code':'source','original_reference':'reference','automatic_quality_policy':'old','automatic_quality_audit':'old','accepted_at_utc':'old','source_coverage_automatic':{'old':True},'_verified_reference_registration':{'old':True}}
  self.job={'id':'id','input_record':json.dumps({'code_sha256':'c','image_sha256':'i'})}
  self.proof={'new_editable_text_fragments':[{'cell':'2'}],'paint_order_changed':False}
  def save(p,b):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  self.mods={'fixed_batch_case_v1':types.SimpleNamespace(checked=lambda *a:XML.encode(),save=save,raw=lambda x:json.dumps(x).encode()),'html_source_repair_v2':types.SimpleNamespace(propose=lambda *a:(XML,self.proof)),'native_worker':types.SimpleNamespace(native=types.SimpleNamespace(native_job=lambda *a:{'ok':True,'png':b'png','native_render':{}}))}
 def tearDown(self):self.tmp.cleanup()
 def runrepair(self,r=None,work=None):
  with patch.dict(sys.modules,self.mods),patch.object(m,'R',self.root),patch.object(m,'W',self.root/'conversion'):return m.repair(r or self.r,self.job,work or self.work)
 def test_success_pending_and_stale_flags_removed(self):
  x=self.runrepair();self.assertTrue(x['ok']);out=x['record'];self.assertEqual(out['quality_state'],'pending_round2_full_qa')
  for key in ['automatic_quality_policy','automatic_quality_audit','accepted_at_utc','source_coverage_automatic','_verified_reference_registration']:self.assertNotIn(key,out)
  self.assertTrue((self.root/out['code_file']).is_file());self.assertEqual(x['model_calls'],0)
 def test_wrong_id(self):self.assertIn('identity_mismatch',self.runrepair({**self.r,'id':'bad'})['detail'])
 def test_wrong_source_hash(self):self.assertIn('identity_mismatch',self.runrepair({**self.r,'source_code_sha256':'bad'})['detail'])
 def test_canvas_lineage_refused(self):self.assertIn('unregistered_baseline',self.runrepair({**self.r,'auto_quality_canvas_repair':{'proof':'old'}})['detail'])
 def test_no_change_does_not_create_candidate(self):
  self.proof.update(new_editable_text_fragments=[],paint_order_changed=False);self.assertIn('no_change_required',self.runrepair()['detail']);self.assertFalse((self.root/'clean').exists())
 def test_work_outside_conversion(self):self.assertIn('outside_owned',self.runrepair(work=self.root)['detail'])
 def test_selector_target(self):self.assertTrue(m.eligible_failure({'detail':['poster_object_coverage_mismatch']}))
 def test_selector_unrelated(self):self.assertFalse(m.eligible_failure({'detail':['missing_cache']}))
if __name__=='__main__':unittest.main()
