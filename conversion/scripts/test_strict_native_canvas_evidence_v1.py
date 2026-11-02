import copy
import unittest
from strict_native_canvas_evidence_v1 import validate


class EvidenceTests(unittest.TestCase):
    def good(self):
        return {'selected_image': 'declared_first_page', 'output_size': [800, 1350],
                'content_outside_declared_canvas': False, 'probe_includes_actual_dom_paint_bounds': True,
                'outside_page_pixel_audit': {'audit_always_performed': True, 'minimum_probe_margin': 32,
                    'nonwhite_outside_pixels': 0, 'offset': [39, 39],
                    'padded_native_render_size': [878, 1421], 'white_threshold': 255}}

    def test_actual_strict_probe_suffices_without_clip_fallback(self):
        self.assertTrue(validate(self.good(), 800, 1350))

    def test_missing_or_weak_pixel_and_DOM_proofs_reject(self):
        for key, value in [('audit_always_performed', False), ('white_threshold', 254),
                           ('nonwhite_outside_pixels', 1), ('minimum_probe_margin', 16),
                           ('padded_native_render_size', [850, 1400]), ('offset', [0, 0])]:
            sample = self.good()
            sample['outside_page_pixel_audit'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(sample, 800, 1350)
        sample = self.good()
        sample['probe_includes_actual_dom_paint_bounds'] = False
        with self.assertRaises(ValueError):
            validate(sample, 800, 1350)


if __name__ == '__main__':
    unittest.main()
