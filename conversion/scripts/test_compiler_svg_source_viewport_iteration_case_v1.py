import unittest
from unittest.mock import patch
import compiler_svg_source_viewport_iteration_case_v1 as c
class OriginalResolutionTests(unittest.TestCase):
 def test_stale_locator_falls_back_only_after_both_original_hashes_verified(self):
  old={'code_file':'clean/prior.drawio','code_sha256':'old','image_file':'clean/prior.png','image_sha256':'pixels','original_source_code':'deleted/source','original_reference':'deleted/image'};source={'code_sha256':'source','image_sha256':'reference'};m={'source_code':'clean/auth/source','reference_image':'clean/auth/image'}
  with patch.object(c,'prepare_originals',side_effect=[FileNotFoundError(),{'ok':True}]) as prep,patch.object(c,'checked') as checked:
   self.assertEqual(c.authoritative_originals(old,source,m,'work'),{'ok':True});self.assertEqual(checked.call_args_list[0].args,('clean/auth/source','source'));self.assertEqual(checked.call_args_list[1].args,('clean/auth/image','reference'));fallback=prep.call_args_list[1].args[0];self.assertEqual(fallback,{k:v for k,v in old.items() if not k.startswith('original_')})
 def test_changed_authoritative_bytes_cannot_fall_back_again(self):
  with patch.object(c,'prepare_originals',side_effect=FileNotFoundError()),patch.object(c,'checked',side_effect=ValueError('authoritativehashchanged')):
   with self.assertRaisesRegex(ValueError,'authoritativehashchanged'):c.authoritative_originals({}, {'code_sha256':'c','image_sha256':'i'}, {'source_code':'s','reference_image':'i'},'w')
 def test_without_manifest_stale_input_is_retained_as_failure(self):
  with patch.object(c,'prepare_originals',side_effect=FileNotFoundError()):
   with self.assertRaises(FileNotFoundError):c.authoritative_originals({}, {},None,'w')

class TypedFailureTests(unittest.TestCase):
 def test_false_infrastructure_fields_in_source_detail_are_not_runtime(self):self.assertFalse(c.is_infrastructure({'ok':False,'reason':'source_binding_incomplete','infrastructure_failure':False,'detail':{'infrastructure_failure':True,'error_type':'ImportError'}}))
 def test_QA_type_is_mapped_to_explicit_typed_envelope(self):self.assertTrue(c.quality_runtime_diagnosis({'failures':[{'type':'ImportError','reason':'missing runtime'}]})['infrastructure_failure'])
 def test_regular_QA_source_failure_stays_pending(self):self.assertFalse(c.quality_runtime_diagnosis({'failures':[{'type':'ValueError','reason':'source_profile_failed'}]})['infrastructure_failure'])
 def test_QA_payload_data_are_not_scanned(self):self.assertFalse(c.quality_runtime_diagnosis({'failures':[{'type':'ValueError','reason':'source mismatch','detail':{'infrastructure_failure':True}}]})['infrastructure_failure'])

if __name__=='__main__':unittest.main()
