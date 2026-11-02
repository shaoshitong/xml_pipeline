import unittest
from compiler_mermaid_unseen_pool_v1 import family,identity_overlap,extract_hashes
class SourcePoolTests(unittest.TestCase):
 def test_text_and_identifier_renaming_do_not_create_independent_families(self):
  a='graph TD\nA[Alpha] --> B[Beta]\nB --> C[Gamma]';b='graph TD\nX[Completely new labels] --> Y[Second]\nY --> Z[Third]';self.assertEqual(family(a)[0],family(b)[0])
 def test_real_topology_change_is_distinct(self):
  a='graph TD\nA[Alpha] --> B[Beta]\nB --> C[Gamma]';b='graph TD\nA[Alpha] --> B[Beta]\nA --> C[Gamma]';self.assertNotEqual(family(a)[0],family(b)[0])
 def test_source_styles_and_direction_are_preserved_in_family(self):
  a='graph TD\nA[Alpha] --> B[Beta]';self.assertNotEqual(family(a)[0],family(a+'\nstyle A fill:#ff0000')[0]);self.assertNotEqual(family(a)[0],family(a.replace('graph TD','graph LR'))[0])
 def test_unknown_statement_not_silently_dropped(self):
  with self.assertRaises(Exception):family('graph TD\nA[A] --> B[B]\nclick A callback')
 def test_code_or_image_overlap_excludes_new_id(self):
  s={'code_sha256':'c','image_sha256':'i'};self.assertTrue(identity_overlap('new',s,set(),{'c'},set()));self.assertTrue(identity_overlap('new',s,set(),set(),{'i'}));self.assertFalse(identity_overlap('new',s,set(),set(),set()))
 def test_hash_aliases_support_all_format_development_rows(self):
  self.assertEqual(extract_hashes({'source_code_sha256':'a','source_image_sha256':'b'}),('a','b'));self.assertEqual(extract_hashes({'code_sha256':'a','image_sha256':'b'}),('a','b'))
if __name__=='__main__':unittest.main()
