import unittest

from compiler_native_source_frontend_v1 import normalize_source
from compiler_native_quality_ro_v1 import complete_source
from compiler_iteration_native_pool_v1 import family


SOURCE = '''<mxfile><diagram><mxGraphModel pageWidth="600" pageHeight="400"><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="a" vertex="1" parent="1" value="A" style="fillColor=red;"><mxGeometry x="10" y="10" width="50" height="30" as="geometry"/></mxCell>
<mxCell id="b" vertex="1" parent="1" value="B" style="fillColor=blue;"><mxGeometry x="100" y="10" width="50" height="30" as="geometry"/></mxCell>
<mxCell id="e" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>'''


class NativeSourceTests(unittest.TestCase):
    def test_named_connectors_and_original_geometry_preserved(self):
        xml, size = normalize_source(SOURCE)
        self.assertEqual(size, [600, 400])
        self.assertIn('x="10"', xml)
        self.assertIn('source="a" target="b"', xml)

    def test_missing_or_free_endpoint_stays_outside_this_version(self):
        for code in (SOURCE.replace('target="b"', 'target="missing"'), SOURCE.replace('target="b"', '')):
            with self.assertRaisesRegex(ValueError, 'pending_next_version'):
                normalize_source(code)

    def test_template_family_merges_incidental_coordinate_and_label_changes(self):
        self.assertEqual(family(SOURCE)[0], family(SOURCE.replace('x="10"', 'x="20"').replace('value="A"', 'value="Different"'))[0])
        self.assertNotEqual(family(SOURCE)[0], family(SOURCE.replace('fillColor=red', 'fillColor=green'))[0])

    def test_complete_original_graph_passes_but_changed_graph_requires_font_proof(self):
        xml, _ = normalize_source(SOURCE)
        coverage = dict(supported=True, ok=True, failures=[], evidence={})
        self.assertTrue(complete_source(coverage, {}, SOURCE, xml)['evidence']['complete_source_coverage'])
        with self.assertRaisesRegex(ValueError, 'unproven'):
            complete_source(coverage, {}, SOURCE, xml.replace('target="b"', 'target="a"'))


if __name__ == '__main__':
    unittest.main()
