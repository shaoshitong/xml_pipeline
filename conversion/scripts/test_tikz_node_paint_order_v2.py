import unittest
import xml.etree.ElementTree as ET

from tikz_node_paint_order_v2 import verify


def model():
    root = ET.Element('root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    ET.SubElement(root, 'mxCell', id='edge', parent='1', edge='1')
    ET.SubElement(root, 'mxCell', id='label', parent='edge', vertex='1',
                  style='group;fillColor=none;strokeColor=none;')
    ET.SubElement(root, 'mxCell', id='background', parent='label', vertex='1')
    ET.SubElement(root, 'mxCell', id='text', parent='label', vertex='1')
    ET.SubElement(root, 'mxCell', id='peer', parent='1', vertex='1')
    return root


def objects(order):
    return [{'id': name} for name in order]


class SourcePaintOrderTests(unittest.TestCase):
    def verify(self, order, markers=()):
        return verify(model(), objects(order), markers, [{'label_group': 'label'}])

    def test_complete_label_block_hierarchy_retains_source_order(self):
        result = self.verify(['edge', 'background', 'text', 'peer'])
        self.assertTrue(result['exact_source_peer_paint_order'])
        self.assertEqual(result['source_order_sha256'], result['native_model_DFS_order_sha256'])

    def test_independent_occluding_peer_between_shaft_and_label_rejected(self):
        with self.assertRaisesRegex(ValueError, 'order_changed'):
            self.verify(['edge', 'peer', 'background', 'text'])

    def test_source_label_before_shaft_cannot_be_reparented_across_peer(self):
        with self.assertRaisesRegex(ValueError, 'order_changed'):
            self.verify(['background', 'text', 'peer', 'edge'])

    def test_source_marker_lowering_has_explicit_contiguous_role(self):
        marker = {'source_object': 'marker', 'edge': 'edge', 'side': 'end'}
        result = self.verify(['edge', 'marker', 'background', 'text', 'peer'], [marker])
        self.assertEqual(len(result['lowered_marker_roles']), 1)
        with self.assertRaisesRegex(ValueError, 'marker_paint_block_interleaved'):
            self.verify(['edge', 'peer', 'marker', 'background', 'text'], [marker])

    def test_missing_original_paint_object_rejected(self):
        with self.assertRaisesRegex(ValueError, 'order_changed'):
            self.verify(['edge', 'background', 'text', 'peer', 'lost'])

    def test_added_container_paint_rejected(self):
        root = model()
        next(cell for cell in root if cell.get('id') == 'label').set('value', 'extra')
        with self.assertRaisesRegex(ValueError, 'would_add_paint'):
            verify(root, objects(['edge', 'background', 'text', 'peer']), [], [{'label_group': 'label'}])


if __name__ == '__main__':
    unittest.main()
