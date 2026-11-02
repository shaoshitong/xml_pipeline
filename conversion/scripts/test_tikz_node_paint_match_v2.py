import copy
import unittest

from tikz_node_paint_match_v2 import match_backgrounds

PATH = r'\pgfsyssoftpath@rectcornertoken{0pt}{2pt}\pgfsyssoftpath@rectsizetoken{20pt}{1pt}'
MAPPING = {'matrix': [1, 0, 0, -1, 0, 10]}


def paint():
    return {'mode': 'fillstroke', 'current_softpath': PATH, 'processed_softpath': PATH, 'sequence': 11}


def shape():
    return dict(id='actual-source-rectangle', type='shape', tag='path', attrs={},
                d='M0 8 L20 8 L20 7 L0 7 Z', matrix=[1, 0, 0, 1, 0, 0],
                style={'fill': 'white', 'stroke': 'black'})


class ExecutedNodePaintMatchingTests(unittest.TestCase):
    def test_source_driver_shape_matches_without_text_bbox_or_area_heuristic(self):
        original = shape()
        result, proofs = match_backgrounds({'objects': [original]}, [paint()], MAPPING)
        self.assertEqual(result, [original])
        self.assertEqual(proofs[0]['maximum_corner_error_px'], 0)
        self.assertFalse(proofs[0]['target_pixels_used'])
        self.assertEqual(original, shape())

    def test_reversed_same_contour_preserves_geometry(self):
        obj = shape()
        obj['d'] = 'M20 7 L20 8 L0 8 L0 7 Z'
        self.assertEqual(match_backgrounds({'objects': [obj]}, [paint()], MAPPING)[0], [obj])

    def test_ambiguous_identical_source_paint_cannot_be_guessed(self):
        a, b = shape(), shape()
        b['id'] = 'another-owner'
        with self.assertRaisesRegex(ValueError, 'not_uniquely_matched'):
            match_backgrounds({'objects': [a, b]}, [paint()], MAPPING)

    def test_shift_or_resize_is_not_accepted_as_same_source_rectangle(self):
        for changed in ('M.2 8 L20.2 8 L20.2 7 L.2 7 Z', 'M0 8 L20.2 8 L20.2 7 L0 7 Z'):
            obj = shape()
            obj['d'] = changed
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'not_uniquely_matched'):
                match_backgrounds({'objects': [obj]}, [paint()], MAPPING)

    def test_open_or_curved_actual_shape_cannot_replace_closed_source_rectangle(self):
        for changed in ('M0 8 L20 8 L20 7 L0 7', 'M0 8 C1 8 20 7 0 7 Z'):
            obj = shape()
            obj['d'] = changed
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'not_uniquely_matched'):
                match_backgrounds({'objects': [obj]}, [paint()], MAPPING)

    def test_driver_paint_mode_and_actual_paint_must_agree(self):
        obj = shape()
        obj['style']['fill'] = 'none'
        with self.assertRaisesRegex(ValueError, 'not_uniquely_matched'):
            match_backgrounds({'objects': [obj]}, [paint()], MAPPING)

    def test_named_or_already_consumed_shape_cannot_be_stolen(self):
        with self.assertRaisesRegex(ValueError, 'not_uniquely_matched'):
            match_backgrounds({'objects': [shape()]}, [paint()], MAPPING,
                              excluded=['actual-source-rectangle'])

    def test_preprocessed_path_difference_cannot_be_ignored(self):
        changed = paint()
        changed['current_softpath'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'softpath_differ'):
            match_backgrounds({'objects': [shape()]}, [changed], MAPPING)

    def test_no_source_driver_paint_does_not_invent_background(self):
        self.assertEqual(match_backgrounds({'objects': [shape()]}, [], MAPPING), ([], []))


if __name__ == '__main__':
    unittest.main()
