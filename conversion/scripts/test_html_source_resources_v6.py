import tempfile,unittest
from pathlib import Path
from html_source_resources_v6 import resource_inventory,asset_contract,verify_served
class ResourceTests(unittest.TestCase):
 def test_no_fetch_allows_None(self):
  with tempfile.TemporaryDirectory() as d:
   a,p=asset_contract('<html><body>Hello</body></html>',None,Path(d));self.assertIsNone(a);self.assertTrue(p['missing_directory_allowed']);self.assertEqual(p['resource_count'],0)
 def test_cleaned_empty_directory_not_recreated(self):
  with tempfile.TemporaryDirectory() as d:
   a,p=asset_contract('<p>Hello</p>','clean/removed_empty',Path(d));self.assertFalse(a.exists());self.assertTrue(p['missing_directory_allowed'])
 def test_inline_data_image_needs_no_directory(self):
  with tempfile.TemporaryDirectory() as d:
   a,p=asset_contract('<img src="data:image/png;base64,aGVsbG8=">',None,Path(d));self.assertEqual(p['inline_data_resources'],1);self.assertFalse(p['requires_asset_directory'])
 def test_anchor_navigation_not_fetch_dependency(self):self.assertEqual(resource_inventory('<a href="https://example.com">link</a>')['resource_count'],0)
 def test_missing_actual_image_is_never_empty_asset(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'required_asset_directory_missing'):asset_contract('<img src="images/x.png">',None,Path(d))
 def test_missing_existing_directory_resource_fails(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'required_asset_directory_missing'):asset_contract('<link rel="stylesheet" href="a.css">','clean/missing',Path(d))
 def test_css_URL_escaped_function_proves_fetch(self):self.assertTrue(resource_inventory('<p style="cursor:u\\72l(abc.png)">x</p>')['requires_asset_directory'])
 def test_css_URL_string_data_is_inline(self):self.assertFalse(resource_inventory('<style>body{cursor:url("data:image/png;base64,aGVsbG8=")}</style>')['requires_asset_directory'])
 def test_CSS_import_string_proves_fetch(self):self.assertTrue(resource_inventory('<style>@import "local.css";</style>')['requires_asset_directory'])
 def test_srcset_explicit_pending(self):
  with self.assertRaisesRegex(ValueError,'srcset_pending'):resource_inventory('<img srcset="x.png 1x, y.png 2x">')
 def test_base_explicit_pending(self):
  with self.assertRaisesRegex(ValueError,'base_URL_pending'):resource_inventory('<base href="https://example.com/">')
 def test_html_comments_not_dependencies(self):self.assertEqual(resource_inventory('<!-- <img src="x"> --><p>url(y)</p>')['resource_count'],0)
 def test_css_comments_not_dependencies(self):self.assertEqual(resource_inventory('<style>/*url(x)*/body{color:red}</style>')['resource_count'],0)
 def test_style_attribute_entity_decoded(self):self.assertTrue(resource_inventory('<p style="cursor:url(&quot;x.png&quot;)">x</p>')['requires_asset_directory'])
 def test_existing_real_directory_supported(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'clean/assets';p.mkdir(parents=True);a,r=asset_contract('<img src="x.png">','clean/assets',Path(d));self.assertEqual(a,p);self.assertFalse(r['missing_directory_allowed']);self.assertTrue(r['requires_asset_directory'])
 def test_escape_outside_clean_rejected_even_if_unused(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'not_in_clean'):asset_contract('<p>x</p>','../escape',Path(d))
 def test_unknown_actual_fetch_rejected(self):
  with self.assertRaisesRegex(ValueError,'uninventoried'):verify_served({'http://source.invalid/x':b'x'},None,{'requires_asset_directory':False})
 def test_declared_resource_actual_fetch_needs_original_directory(self):
  with self.assertRaisesRegex(ValueError,'served_without_original'):verify_served({'http://source.invalid/x':b'x'},None,{'requires_asset_directory':True})
 def test_tinycss_bad_url_not_silently_ignored(self):
  with self.assertRaisesRegex(ValueError,'CSS_parse_pending'):resource_inventory('<style>p{cursor:url(bad"url)}</style>')
if __name__=='__main__':unittest.main()
