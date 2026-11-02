"""Reject semantic alpha/layer/owner loss independently of global image similarity."""
import copy
import unittest
import xml.etree.ElementTree as ET

from mermaid_alpha_background_native_v1 import check_backgrounds, check_layers

XML = '''<mxfile><diagram><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="edge" edge="1" parent="1"/>
<mxCell id="label" vertex="1" value="label" parent="edge"/>
<mxCell id="bg" vertex="1" parent="edge" sourceCssBackground="rgba(232, 232, 232, 0.5)"
 sourceCssBackgroundAlpha="0.5" sourceCssBackgroundOrder="1"
 style="shape=rect;fillColor=#e8e8e8;fillOpacity=50;opacity=100;strokeColor=none;">
<mxGeometry relative="1"/></mxCell></root></mxGraphModel></diagram></mxfile>'''
BINDING = {'background': 'bg', 'label': 'label', 'edge': 'edge', 'native_parent': 'edge',
           'source_alpha': 0.5, 'source_css_color': '#e8e8e8', 'source_css': 'rgba(232, 232, 232, 0.5)',
           'source_order': 1}


def altered(attribute, value):
    root = ET.fromstring(XML)
    root.find(".//mxCell[@id='bg']").set(attribute, value)
    return ET.tostring(root, encoding='unicode')


class AlphaLayerSemantics(unittest.TestCase):
    def test_half_alpha_is_valid(self):
        self.assertTrue(check_backgrounds(XML, [BINDING])['ok'])

    def test_opaque_substitution_is_rejected(self):
        with self.assertRaises(ValueError):
            check_backgrounds(altered('style', 'fillColor=#e8e8e8;fillOpacity=100;strokeColor=none;'), [BINDING])

    def test_whole_cell_opacity_cannot_replace_fill_alpha(self):
        with self.assertRaises(ValueError):
            check_backgrounds(altered('style', 'fillColor=#e8e8e8;fillOpacity=50;opacity=50;strokeColor=none;'), [BINDING])

    def test_color_alpha_and_background_have_independent_identity(self):
        for key, value in [('sourceCssBackground', 'rgb(232, 232, 232)'),
                           ('sourceCssBackgroundAlpha', '0.8'), ('sourceCssBackgroundOrder', '2')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_backgrounds(altered(key, value), [BINDING])

    def test_move_to_unrelated_owner_is_rejected(self):
        with self.assertRaises(ValueError):
            check_backgrounds(altered('parent', '1'), [BINDING])

    def test_hiding_a_layer_is_rejected(self):
        with self.assertRaises(ValueError):
            check_backgrounds(altered('visible', '0'), [BINDING])

    def test_layer_cannot_be_counted_twice(self):
        with self.assertRaises(ValueError):
            check_layers(XML, [BINDING, copy.deepcopy(BINDING)])

    def test_missing_layer_is_rejected(self):
        binding = {**BINDING, 'background': 'gone'}
        with self.assertRaises(ValueError):
            check_layers(XML, [binding])

    def test_invalid_alpha_is_rejected(self):
        for alpha in (float('nan'), -0.1, 1.1):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                check_layers(XML, [{**BINDING, 'source_alpha': alpha}])


if __name__ == '__main__':
    unittest.main()
