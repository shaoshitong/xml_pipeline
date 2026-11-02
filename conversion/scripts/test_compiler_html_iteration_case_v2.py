"""Input resource contracts, independent of HTML conversion implementation."""
import tempfile
import unittest
from pathlib import Path

from compiler_html_iteration_case_v2 import candidate_seed


class SourceAssetContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'clean/assets').mkdir(parents=True)
        self.source = dict(code_sha256='a' * 64, image_sha256='b' * 64)
        self.job = ('id', 'poster', 'html', 'dataset')

    def seed(self, manifest=None, source=None):
        return candidate_seed('id', self.job, source or self.source, manifest, self.root)

    def test_canonical_asset_directory_is_bound_without_prior_candidate(self):
        result = self.seed(dict(asset_root='clean/assets'))
        self.assertEqual(result['original_asset_root'], 'clean/assets')
        self.assertEqual(result['source_image_sha256'], self.source['image_sha256'])
        self.assertNotIn('code_file', result)

    def test_source_record_asset_locator_is_supported(self):
        result = self.seed(source=dict(self.source, asset_root='clean/assets'))
        self.assertEqual(result['original_asset_root'], 'clean/assets')

    def test_manifest_asset_binding_precedes_source_fallback(self):
        result = self.seed(dict(asset_root='clean/assets'), dict(self.source, asset_root='wrong'))
        self.assertEqual(result['original_asset_root'], 'clean/assets')

    def test_missing_asset_locator_is_diagnosed_before_frontend(self):
        with self.assertRaisesRegex(ValueError, 'missing_from_authoritative'):
            self.seed({})

    def test_file_cannot_replace_resource_directory(self):
        (self.root / 'clean/file').write_text('data')
        with self.assertRaisesRegex(ValueError, 'not_directory_under_clean'):
            self.seed(dict(asset_root='clean/file'))

    def test_outside_symlink_cannot_be_used_as_clean_assets(self):
        (self.root / 'outside').mkdir()
        (self.root / 'clean/escape').symlink_to(self.root / 'outside', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'not_directory_under_clean'):
            self.seed(dict(asset_root='clean/escape'))


if __name__ == '__main__':
    unittest.main()
