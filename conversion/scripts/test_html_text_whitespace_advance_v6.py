import copy
import unittest

import html_text_whitespace_advance_v6 as whitespace
from test_html_text_whitespace_advance_v5 import fixture


class SourceWhitespaceContracts(unittest.TestCase):
    def test_single_source_space_can_have_a_real_different_advance(self):
        dom, before, xml = fixture()
        dom['objects'][0]['actualSourceGlyphs'][1]['raw'] = ' '
        plan = whitespace.plan(dom, before, xml)
        self.assertEqual(plan['eligible_count'], 1)
        self.assertEqual(plan['objects'][0]['targets'][0]['extra_advance'], 4)
        self.assertTrue(plan['requires_independent_exact_full_source_paint'])

    def test_negative_space_advance_is_source_measured_and_keeps_logical_text(self):
        dom, before, xml = fixture()
        dom['objects'][0]['actualSourceGlyphs'][1]['width'] = 2
        dom['objects'][0]['actualSourceGlyphs'][2]['x'] = 17
        plan = whitespace.plan(dom, before, xml)
        self.assertEqual(plan['eligible_count'], 1)
        candidate, proof = whitespace.propose(xml, plan)
        self.assertIn('word-spacing:-2px', candidate)
        after = copy.deepcopy(before)
        chars = after['actual_text_positions'][0]['runs'][0]['chars']
        chars[1]['width'] -= 2
        chars[2]['x'] -= 2
        self.assertTrue(whitespace.verify(xml, candidate, proof, dom, before, after)['ok'])

    def test_whole_source_text_node_can_have_an_extra_fallback_not_in_this_fragment(self):
        dom, before, xml = fixture()
        dom['objects'][0]['actualSourcePhysicalFonts']['fonts'].append(
            dict(postScriptName='OtherSourceFragmentFace', glyphCount=3))
        plan = whitespace.plan(dom, before, xml)
        self.assertEqual(plan['eligible_count'], 1)
        self.assertEqual(plan['objects'][0]['native_physical_faces'], ['FixtureFace'])

    def test_a_native_face_absent_from_the_actual_source_is_rejected(self):
        dom, before, xml = fixture()
        before['actual_platform_font_usage'][0]['fonts'][0]['postScriptName'] = 'WrongFace'
        plan = whitespace.plan(dom, before, xml)
        self.assertEqual(plan['eligible_count'], 0)
        self.assertTrue(plan['unsupported'])

    def test_baseline_or_height_changes_are_never_explained_by_spaces(self):
        for field in ('y', 'height'):
            dom, before, xml = fixture()
            dom['objects'][0]['actualSourceGlyphs'][0][field] += 1
            self.assertEqual(whitespace.plan(dom, before, xml)['eligible_count'], 0)

    def test_actual_kerning_font_count_or_vertical_side_effects_still_fail(self):
        for field in ('y', 'width', 'fonts'):
            dom, before, xml = fixture()
            candidate, proof = whitespace.propose(xml, whitespace.plan(dom, before, xml))
            after = copy.deepcopy(before)
            chars = after['actual_text_positions'][0]['runs'][0]['chars']
            chars[1]['width'] += 4
            chars[2]['x'] += 4
            if field == 'fonts':
                after['actual_platform_font_usage'][0]['fonts'][0]['glyphCount'] += 1
            else:
                chars[0][field] += 1
            with self.assertRaises(AssertionError):
                whitespace.verify(xml, candidate, proof, dom, before, after)


if __name__ == '__main__':
    unittest.main()
