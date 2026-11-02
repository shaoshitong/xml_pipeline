import copy
import unittest

from tikz_node_paint_editing_v3 import require_source_proof, sha


def fixture():
    xml = '<mxfile><diagram><mxGraphModel><root/></mxGraphModel></diagram></mxfile>'
    record = dict(source_format='tikz', code_sha256=sha(xml.encode()),
                  source_code_sha256='a' * 64, source_image_sha256='b' * 64)
    evidence = dict(complete_source_coverage=True, candidate_code_sha256=record['code_sha256'],
                    source_code_sha256=record['source_code_sha256'],
                    source_image_sha256=record['source_image_sha256'],
                    source_label_driver_ownership_complete=True,
                    actual_original_PDF_paint_inventory={'complete_actual_PDF_paint_inventory': True})
    profile = dict(profile='compiler_tikz_node_paint_viewport_v2', supported=True, ok=True,
                   failures=[], evidence=evidence)
    return xml, record, profile


class QualitySourceContractTests(unittest.TestCase):
    def test_new_complete_source_schema_reaches_editing_contract(self):
        xml, record, profile = fixture()
        self.assertTrue(require_source_proof(record, profile, xml))

    def test_legacy_profile_name_cannot_impersonate_new_ownership_proof(self):
        xml, record, profile = fixture()
        profile['profile'] = 'compiler_tikz_source_viewport_v1'
        with self.assertRaisesRegex(ValueError, 'wrong_source_frontend'):
            require_source_proof(record, profile, xml)

    def test_incomplete_node_driver_ownership_rejected(self):
        xml, record, profile = fixture()
        profile['evidence'].pop('source_label_driver_ownership_complete')
        with self.assertRaisesRegex(ValueError, 'ownership_not_verified'):
            require_source_proof(record, profile, xml)

    def test_candidate_or_source_revision_change_rejected(self):
        xml, record, profile = fixture()
        for field in ('candidate_code_sha256', 'source_code_sha256', 'source_image_sha256'):
            changed = copy.deepcopy(profile)
            changed['evidence'][field] = 'c' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                require_source_proof(record, changed, xml)


if __name__ == '__main__':
    unittest.main()
