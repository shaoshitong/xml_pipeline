import unittest
from compiler_native_source_frontend_v2 import normalize_source
from compiler_native_quality_ro_v2 import complete_source

SOURCE='''<mxfile><diagram><mxGraphModel pageWidth="600" pageHeight="400"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" vertex="1" parent="1" value="A"><mxGeometry x="10" y="10" width="50" height="30" as="geometry"/></mxCell><mxCell id="b" vertex="1" parent="1" value="B"><mxGeometry x="100" y="10" width="50" height="30" as="geometry"/></mxCell><mxCell id="e" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'''

def free_source():return SOURCE.replace('target="b"','').replace('<mxGeometry relative="1" as="geometry"/>','<mxGeometry relative="1" as="geometry"><mxPoint as="targetPoint" x="200" y="30"/></mxGeometry>')
class NativeSourceV2Tests(unittest.TestCase):
 def test_named_geometry_preserved(self):
  xml,size=normalize_source(SOURCE);self.assertEqual(size,[600,400]);self.assertIn('x="10"',xml);self.assertIn('source="a"',xml)
 def test_explicit_free_endpoint_is_source_grammar(self):
  xml,_=normalize_source(free_source());self.assertIn('as="targetPoint"',xml)
 def test_named_dangling_terminal_cannot_be_reinterpreted(self):
  with self.assertRaisesRegex(ValueError,'dangling_named_terminal'):normalize_source(free_source().replace('source="a"','source="a" target="missing"'))
 def test_missing_source_point_is_pending(self):
  with self.assertRaisesRegex(ValueError,'missing_or_ambiguous'):normalize_source(SOURCE.replace('target="b"',''))
 def test_nonfinite_source_point_is_pending(self):
  with self.assertRaisesRegex(ValueError,'nonfinite'):normalize_source(free_source().replace('x="200"','x="NaN"'))
 def test_wrapped_cell_ids_are_valid_original_native_identity(self):
  code=SOURCE.replace('<mxCell id="a" vertex="1" parent="1" value="A">','<UserObject id="a" label="A"><mxCell vertex="1" parent="1">').replace('<mxGeometry x="10" y="10" width="50" height="30" as="geometry"/></mxCell>','<mxGeometry x="10" y="10" width="50" height="30" as="geometry"/></mxCell></UserObject>');xml,_=normalize_source(code);self.assertIn('UserObject',xml)
 def test_complete_coverage_requires_exact_original_or_independent_font_delta(self):
  xml,_=normalize_source(SOURCE);coverage={'supported':True,'ok':True,'failures':[],'evidence':{}}
  self.assertTrue(complete_source(coverage,{},SOURCE,xml)['evidence']['complete_source_coverage'])
  with self.assertRaisesRegex(ValueError,'unproven'):complete_source(coverage,{},SOURCE,xml.replace('target="b"','target="a"'))
if __name__=='__main__':unittest.main()
