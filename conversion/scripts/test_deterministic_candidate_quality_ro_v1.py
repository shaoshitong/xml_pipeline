"""Negative boundaries for the independent candidate QA entry point."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import deterministic_candidate_quality_ro_v1 as quality


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.original = {'pair_sha256': 'a' * 64, 'source': 'dataset', 'category': 'poster',
                         'format': 'html', 'code_sha256': 'b' * 64, 'image_sha256': 'c' * 64}
        self.job = {'id': 'a' * 64, 'source': 'dataset', 'category': 'poster', 'format': 'html',
                    'input_record': json.dumps(self.original)}
        self.record = {'id': 'a' * 64, 'source_pair_sha256': 'a' * 64, 'source': 'dataset',
                       'category': 'poster', 'source_format': 'html', 'format': 'drawio',
                       'source_code_sha256': 'b' * 64, 'source_image_sha256': 'c' * 64}

    def test_real_source_identity_is_returned(self):
        self.assertEqual(quality.identity(self.record, self.job), self.original)

    def test_other_pair_category_format_or_source_hash_is_never_accepted(self):
        for key in self.record:
            changed = copy.deepcopy(self.record)
            changed[key] = 'another_value'
            with self.subTest(key=key), self.assertRaises(ValueError):
                quality.identity(changed, self.job)

    def test_out_of_scope_job_is_not_authorized_by_candidate_category(self):
        self.job['category'] = 'chart'
        with self.assertRaisesRegex(ValueError, 'outside_requested_scope'):
            quality.identity(self.record, self.job)


class RequiredEvidenceTests(unittest.TestCase):
    def test_source_browser_closes_even_if_source_verifier_fails(self):
        class Plugin:
            closed = False

            def check_source(self, *args, **kwargs):
                raise ValueError('unknown_source_role')

            def close_worker_runtime(self):
                self.closed = True

        plugin = Plugin()
        with self.assertRaisesRegex(ValueError, 'unknown_source_role'):
            quality.source_profile(plugin, {}, '', '', Path('/tmp'))
        self.assertTrue(plugin.closed)

    def test_fresh_native_evidence_is_passed_to_source_verifier(self):
        class Plugin:
            def check_source(self, record, xml, source, root, native_info=None):
                return native_info

        native = {'actual_text_positions': [{'cell': 'source_label'}]}
        self.assertIs(quality.source_profile(Plugin(), {}, '', '', Path('/tmp'), native), native)

    def test_supported_without_complete_source_evidence_cannot_pass(self):
        good = {'supported': True, 'ok': True, 'profile': 'named_source_rule',
                'evidence': {'complete_source_coverage': True, 'required_text_cell_ids': ['text1']}, 'failures': []}
        quality.source_gate(good)
        for key, value in [('supported', False), ('supported', 1), ('ok', False),
                           ('failures', ['omitted_source_marker']), ('profile', ''), ('evidence', None)]:
            bad = {**good, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                quality.source_gate(bad)

    def test_marker_only_pass_cannot_substitute_for_whole_source_coverage(self):
        good = {'supported': True, 'ok': True, 'profile': 'named_source_rule',
                'evidence': {'complete_source_coverage': True, 'required_text_cell_ids': []}}
        for evidence in ({}, {'complete_source_coverage': False, 'required_text_cell_ids': []},
                         {'complete_source_coverage': True, 'required_text_cell_ids': None},
                         {'complete_source_coverage': True, 'required_text_cell_ids': ['text', 'text']}):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                quality.source_gate({**good, 'evidence': evidence})

    def test_actual_text_requires_actual_custom_font_glyphs(self):
        text = {'actual_text_positions': [{'id': 'text'}]}
        with self.assertRaisesRegex(ValueError, 'no_physical_font'):
            quality.actual_fonts(text)
        actual = {**text, 'actual_platform_font_usage': [{'fonts': [{'glyphCount': 4, 'isCustomFont': False}]}]}
        with self.assertRaisesRegex(ValueError, 'requires_embedding'):
            quality.actual_fonts(actual)
        actual['actual_platform_font_usage'][0]['fonts'][0]['isCustomFont'] = True
        self.assertEqual(quality.actual_fonts(actual)['actual_custom_font_glyphs'], 4)

    def test_zero_glyph_face_is_not_evidence_for_text(self):
        with self.assertRaisesRegex(ValueError, 'no_physical_font'):
            quality.actual_fonts({'actual_text_positions': [{}], 'actual_platform_font_usage': [
                {'fonts': [{'glyphCount': 0, 'isCustomFont': True}]}]})

    def test_modified_pinned_dependency_cannot_reuse_quality_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / 'profile.py'
            module.write_bytes(b'original')
            pins = {str(module): quality.sha(module.read_bytes())}
            quality.pins_unchanged(pins)
            module.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'implementation_changed'):
                quality.pins_unchanged(pins)

    def test_empty_or_relative_profile_pin_set_is_rejected(self):
        for pins in ({}, {'profile.py': 'a' * 64}, {'/tmp/example': 'not_a_digest'}):
            with self.subTest(pins=pins), self.assertRaises(ValueError):
                quality.pins_unchanged(pins)


if __name__ == '__main__':
    unittest.main()
