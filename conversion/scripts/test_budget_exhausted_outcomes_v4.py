import json, unittest
from unittest.mock import patch
import budget_exhausted_outcomes_v4 as module


class BudgetFaultGuardTests(unittest.TestCase):
    def test_source_interface_errors_are_recovery_cases(self):
        for error in ("KeyError('source_render_svg')", "AssertionError('missing pinned source layout variant')", 'unexpected validator error'):
            self.assertTrue(module.validator_fault(['source_coverage_failure: ' + json.dumps([{'reason': 'source_profile_validation_error', 'error': error}])]))

    def test_mixed_visual_and_validator_failure_is_not_terminated(self):
        self.assertTrue(module.validator_fault(['raster_anomaly: actual_failure', 'KeyError(outside_page_pixel_audit)']))

    def test_malformed_failure_report_is_not_a_verdict(self):
        self.assertTrue(module.validator_fault(['source_coverage_failure: broken-json']))
        self.assertTrue(module.validator_fault(['source_coverage_failure: {}']))

    def test_genuine_content_or_visual_failures_remain_eligible(self):
        self.assertFalse(module.validator_fault(['raster_anomaly: local_text_line_ssim_below_0.55']))
        self.assertFalse(module.validator_fault(['source_coverage_failure: ' + json.dumps([{'reason': 'source_content_mismatch'}])]))

    def test_prepare_preserves_original_rejection(self):
        with patch.object(module, 'prior_prepare', return_value=(None, 'budget_not_exhausted')):
            self.assertEqual(module.prepare(None, 'id', 'policy'), (None, 'budget_not_exhausted'))

    def test_prepare_refuses_validator_fault_plan(self):
        plan = {'evidence': {'failed_qa_reasons': ['KeyError(source_render_svg)']}}
        with patch.object(module, 'prior_prepare', return_value=(plan, None)):
            self.assertEqual(module.prepare(None, 'id', 'policy'), (None, 'validator_interface_error_requires_program_recovery'))

    def test_prepare_keeps_genuine_exact_revision_plan(self):
        plan = {'evidence': {'failed_qa_reasons': ['raster_anomaly: local_fail']}}
        with patch.object(module, 'prior_prepare', return_value=(plan, None)):
            self.assertEqual(module.prepare(None, 'id', 'policy'), (plan, None))


if __name__ == '__main__':
    unittest.main()
