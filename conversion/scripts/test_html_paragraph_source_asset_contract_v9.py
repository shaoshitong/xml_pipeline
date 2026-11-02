import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import html_paragraph_source_contract_v9 as contract
import html_paragraph_iteration_pool_v9 as pool

class SourceAssetSnapshotTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.assets=self.root/'clean/assets';self.assets.mkdir(parents=True)
  p=patch.object(contract,'R',self.root);p.start();self.addCleanup(p.stop)
 def test_nested_asset_bytes_are_part_of_content_seal(self):
  (self.assets/'nested').mkdir();p=self.assets/'nested/image.dat';p.write_bytes(b'original');a=contract.asset_snapshot('clean/assets');p.write_bytes(b'changed');b=contract.asset_snapshot('clean/assets');self.assertNotEqual(a,b);self.assertEqual(a['files'],1)
 def test_asset_addition_and_removal_change_seal(self):
  a=contract.asset_snapshot('clean/assets');p=self.assets/'image.dat';p.write_bytes(b'x');b=contract.asset_snapshot('clean/assets');self.assertNotEqual(a,b);p.unlink();self.assertEqual(a,contract.asset_snapshot('clean/assets'))
 def test_asset_rename_changes_seal_without_pixel_inspection(self):
  p=self.assets/'one';p.write_bytes(b'x');a=contract.asset_snapshot('clean/assets');p.rename(self.assets/'two');self.assertNotEqual(a,contract.asset_snapshot('clean/assets'))
 def test_external_symlink_is_typed_pending(self):
  outside=self.root/'outside';outside.write_bytes(b'x');(self.assets/'link').symlink_to(outside)
  with self.assertRaisesRegex(ValueError,'symlink_requires_later_source_repair'):contract.asset_snapshot('clean/assets')
 def test_asset_directory_must_stay_under_registered_clean(self):
  with self.assertRaisesRegex(ValueError,'not_registered_clean_directory'):contract.asset_snapshot('.')
 def test_missing_optional_assetroot_is_explicit(self):self.assertIsNone(contract.asset_snapshot(None))
 def test_all_original_HTML_family_keys_are_source_only(self):
  a,keys,evidence=pool.source_family('<div style="font-size:12px">Alice</div>');b,_,_=pool.source_family('<div style="font-size:24px">Bob</div>');self.assertEqual(a,b);self.assertEqual(keys,{a});self.assertTrue(evidence['source_only'])
 def test_asset_order_does_not_change_snapshot(self):
  (self.assets/'b').write_bytes(b'B');(self.assets/'a').write_bytes(b'A');a=contract.asset_snapshot('clean/assets');self.assertEqual(a,contract.asset_snapshot('clean/assets'))
if __name__=='__main__':unittest.main()
