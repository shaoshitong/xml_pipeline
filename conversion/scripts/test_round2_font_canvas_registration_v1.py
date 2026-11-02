import importlib.util,tempfile,types,sys,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('round2_font_canvas_registration_v1',Path(__file__).with_name('round2_font_canvas_registration_v1.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_require_rejects_false(self):
  with self.assertRaises(ValueError):m.require(False,'failure')
 def test_owned_evidence_rejects_outside(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);owned=root/'owned';owned.mkdir();outside=root/'outside';outside.write_text('x')
   with self.assertRaises(ValueError):m.read_owned(outside,owned,{})
 def test_owned_evidence_rejects_symlink_escape(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);owned=root/'owned';owned.mkdir();outside=root/'outside';outside.write_text('x');(owned/'link').symlink_to(outside)
   with self.assertRaises(ValueError):m.read_owned(owned/'link',owned,{})
 def test_owned_evidence_binds_actual_sha(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'x';p.write_bytes(b'actual');checks={};self.assertEqual(m.read_owned(p,Path(tmp),checks),b'actual');self.assertEqual(checks[str(p.resolve())],m.sha(b'actual'))
 def test_nonfont_canvas_uses_unchanged_registration(self):
  stub=types.ModuleType('auto_quality_common_v4');stub.registration_record=lambda r,ref,xml:('old',r)
  with patch.dict(sys.modules,{'auto_quality_common_v4':stub}):self.assertEqual(m.registration_record({'auto_quality_canvas_repair':{}},b'a','xml')[0],'old')
 def test_html_glyph_delegates_to_full_v4(self):
  calls=[];stub=types.ModuleType('auto_quality_common_v4');stub.registration_record=lambda r,ref,xml:(calls.append((r,ref,xml)) or ('glyph',r))
  record={'source_format':'html','html_actual_text_alignment':{'frozen':'proof'}}
  with patch.dict(sys.modules,{'auto_quality_common_v4':stub}):self.assertEqual(m.registration_record(record,b'ref','xml')[0],'glyph')
  self.assertEqual(calls,[(record,b'ref','xml')])
 def test_html_layout_delegates_to_full_v4(self):
  calls=[];stub=types.ModuleType('auto_quality_common_v4');stub.registration_record=lambda r,ref,xml:(calls.append((r,ref,xml)) or ('layout',r))
  record={'source_format':'html','html_text_layout_v5':{'frozen':'proof'}}
  with patch.dict(sys.modules,{'auto_quality_common_v4':stub}):self.assertEqual(m.registration_record(record,b'ref','xml')[0],'layout')
  self.assertEqual(calls,[(record,b'ref','xml')])
 def test_fresh_contract_drops_untrusted_verified_fields(self):
  record={'auto_quality_canvas_repair':{'proof':'p'},'round2_font_repair':{'ok':True},'_verified_forged':'bad','id':'id'}
  contract={'same_renderer_font_delta_verified':True,'output_page':[10,20]}
  stub=types.ModuleType('auto_quality_canvas_repair');stub.validate_registration=lambda *args:(_ for _ in ()).throw(AssertionError('font delta'))
  with patch.dict(sys.modules,{'auto_quality_canvas_repair':stub}),patch.object(m,'_verify',return_value=contract):r,c=m.registration_record(record,b'reference','xml')
  self.assertNotIn('_verified_forged',r);self.assertEqual(r['_verified_reference_registration'],contract);self.assertNotIn('font_only_delta_verified',c)
 def test_proof_failure_not_silently_fallback(self):
  record={'auto_quality_canvas_repair':{'proof':'p'},'round2_font_repair':{'ok':True}}
  stub=types.ModuleType('auto_quality_canvas_repair');stub.validate_registration=lambda *args:(_ for _ in ()).throw(AssertionError('font delta'))
  with patch.dict(sys.modules,{'auto_quality_canvas_repair':stub}),patch.object(m,'_verify',side_effect=ValueError('forged')):
   with self.assertRaisesRegex(ValueError,'forged'):m.registration_record(record,b'reference','xml')
 def test_font_before_canvas_retains_full_v4_registration(self):
  canvas=types.ModuleType('auto_quality_canvas_repair');canvas.validate_registration=lambda *args:{'current_verified':True}
  old=types.ModuleType('auto_quality_common_v4');old.registration_record=lambda *args:('already-current',{})
  record={'auto_quality_canvas_repair':{'proof':'p'},'round2_font_repair':{'ok':True}}
  with patch.dict(sys.modules,{'auto_quality_canvas_repair':canvas,'auto_quality_common_v4':old}),patch.object(m,'_verify') as verify:
   self.assertEqual(m.registration_record(record,b'reference','xml')[0],'already-current');verify.assert_not_called()
 def test_non_assertion_canvas_evidence_error_not_masked(self):
  canvas=types.ModuleType('auto_quality_canvas_repair');canvas.validate_registration=lambda *args:(_ for _ in ()).throw(ValueError('corrupt proof'))
  record={'auto_quality_canvas_repair':{'proof':'p'},'round2_font_repair':{'ok':True}}
  with patch.dict(sys.modules,{'auto_quality_canvas_repair':canvas}),patch.object(m,'_verify') as verify:
   with self.assertRaisesRegex(ValueError,'corrupt proof'):m.registration_record(record,b'reference','xml')
   verify.assert_not_called()
if __name__=='__main__':unittest.main()
