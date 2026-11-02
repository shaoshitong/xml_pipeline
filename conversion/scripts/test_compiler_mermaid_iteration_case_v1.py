import unittest
from unittest.mock import patch
import compiler_mermaid_iteration_case_v1 as c
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
if __name__=='__main__':unittest.main()
