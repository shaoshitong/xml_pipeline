import unittest
from native_font_final_named_style_v1 import restore_style,tokens,FONT_KEYS
class Restore(unittest.TestCase):
 def test_named_token_lost_by_attach_restored(self):self.assertEqual(restore_style('swimlane;childLayout=stackLayout;','childLayout=stackLayout;fontFamily=NativeFace;'),'swimlane;childLayout=stackLayout;fontFamily=NativeFace;')
 def test_leading_reset_preserved(self):self.assertEqual(restore_style(';text;strokeColor=none;','strokeColor=none;fontFamily=NativeFace;'),';text;strokeColor=none;fontFamily=NativeFace;')
 def test_complete_named_order_restored(self):self.assertEqual(restore_style('text;blue;fontSize=12;','fontSize=12;fontFamily=N;'),'text;blue;fontSize=12;fontFamily=N;')
 def test_duplicate_source_nonfont_values_preserved(self):self.assertEqual(restore_style('text;fillColor=red;fillColor=blue;','fillColor=blue;fontFamily=N;'),'text;fillColor=red;fillColor=blue;fontFamily=N;')
 def test_nonfont_value_change_rejected(self):
  with self.assertRaisesRegex(ValueError,'nonfont_style_value'):restore_style('text;fillColor=red;','fillColor=blue;fontFamily=N;')
 def test_added_named_style_rejected(self):
  with self.assertRaisesRegex(ValueError,'named_style'):restore_style('text;','ellipse;fontFamily=N;')
 def test_reordered_remaining_names_rejected(self):
  with self.assertRaisesRegex(ValueError,'named_style'):restore_style('text;blue;','blue;text;fontFamily=N;')
 def test_raw_data_header_preserved(self):self.assertIn('image=data:image/png;base64,xyz',restore_style('text;image=data:image/png;base64,xyz;','image=data:image/png;base64,xyz;fontFamily=N;'))
 def test_empty_default_style_does_not_gain_reset(self):self.assertEqual(restore_style('','fontFamily=N;'),'fontFamily=N')
 def test_internal_and_trailing_empty_tokens_preserved(self):
  source=';text;;blue;;';out=restore_style(source,'fontFamily=N;');self.assertEqual([t for t in tokens(out)if'='not in t],tokens(source))
if __name__=='__main__':unittest.main(verbosity=2)
