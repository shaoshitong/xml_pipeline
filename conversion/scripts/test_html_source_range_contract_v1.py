import copy
import unittest

from html_source_range_contract_v1 import evaluate


class SelectionSlotContractTests(unittest.TestCase):
    def rows(self):
        return [dict(dx=.3, dy=.6, dw=0., dh=0.) for _ in range(4)]

    def test_uniform_unmodified_glyphs_supply_one_placement(self):
        proof = evaluate(self.rows(), 24.)
        self.assertTrue(proof['ok'])
        self.assertFalse(proof['aligned'])
        self.assertEqual(proof['translation'], dict(dx=.3, dy=.6))
        self.assertTrue(proof['does_not_prove_paint_equality'])

    def test_leading_slot_must_preserve_its_right_edge(self):
        rows = self.rows()
        rows[0].update(dx=1.05, dw=-.75)
        proof = evaluate(rows, 24.)
        self.assertTrue(proof['ok'])
        self.assertEqual(proof['boundary_slot_exceptions'][0]['index'], 0)
        rows[0]['dw'] = -.2
        self.assertFalse(evaluate(rows, 24.)['ok'])

    def test_trailing_selection_advance_requires_the_same_left_cursor(self):
        rows = self.rows()
        rows[-1]['dw'] = -.22
        self.assertTrue(evaluate(rows, 24.)['ok'])
        rows[-1]['dx'] += 1.
        self.assertFalse(evaluate(rows, 24.)['ok'])

    def test_interior_displacement_or_advance_is_never_a_boundary_exception(self):
        for field in ('dx', 'dw'):
            rows = self.rows()
            rows[1][field] += 1.
            self.assertFalse(evaluate(rows, 24.)['ok'])

    def test_no_glyph_can_change_baseline_or_range_height(self):
        for index in (0, 1, 3):
            for field in ('dy', 'dh'):
                rows = self.rows()
                rows[index][field] += 1.
                self.assertFalse(evaluate(rows, 24.)['ok'])

    def test_one_em_bound_does_not_admit_arbitrarily_large_boundary_changes(self):
        rows = self.rows()
        rows[-1]['dw'] = 100.
        self.assertFalse(evaluate(rows, 24.)['ok'])

    def test_empty_nonfinite_or_missing_observations_are_rejected(self):
        self.assertFalse(evaluate([], 24.)['ok'])
        for value in (float('nan'), float('inf'), None):
            rows = self.rows()
            rows[0]['dx'] = value
            self.assertFalse(evaluate(rows, 24.)['ok'])
        self.assertFalse(evaluate(self.rows(), 0)['ok'])

    def test_output_never_modifies_the_original_observations(self):
        rows = self.rows()
        original = copy.deepcopy(rows)
        evaluate(rows, 24.)
        self.assertEqual(rows, original)

    def test_aligned_is_distinct_from_a_valid_translation_plan(self):
        rows = [dict(dx=0., dy=0., dw=0., dh=0.) for _ in range(4)]
        self.assertTrue(evaluate(rows, 24.)['aligned'])
        for row in rows:
            row['dx'] = 9.
        self.assertFalse(evaluate(rows, 24.)['ok'])


if __name__ == '__main__':
    unittest.main()
