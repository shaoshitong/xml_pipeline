import unittest
from drawio_author_native_model_semantics_v1 import compare
A='<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" value="full label" style="html=1;fontStyle=1;" edge="1" source="v"><mxGeometry relative="1" x=".8077" y="-9" as="geometry"><mxPoint x="240" y="-40" as="sourcePoint"/><mxPoint x="400" y="-40" as="targetPoint"/><Array as="points"><mxPoint x="220" y="105"/><mxPoint x="220" y="157"/></Array><mxPoint as="offset"/></mxGeometry></mxCell><mxCell id="v" parent="1" vertex="1"><mxGeometry x="0" y="20" width="30" height="40" as="geometry"/></mxCell></root></mxGraphModel>'
class Semantics(unittest.TestCase):
 def test_same(self):self.assertTrue(compare(A,A)['ok'])
 def test_unique_as_reorder_equivalent(self):
  b=A.replace('<mxPoint as="offset"/>','').replace('<mxGeometry relative="1" x=".8077" y="-9" as="geometry">','<mxGeometry relative="1" x=".8077" y="-9" as="geometry"><mxPoint as="offset"/>');self.assertTrue(compare(A,b)['ok'])
 def test_coordinate_value_change_rejected(self):self.assertFalse(compare(A,A.replace('x="240"','x="241"'))['ok'])
 def test_as_role_change_rejected(self):self.assertFalse(compare(A,A.replace('as="targetPoint"','as="alternateBounds"'))['ok'])
 def test_point_array_order_not_elided(self):self.assertFalse(compare(A,A.replace('<mxPoint x="220" y="105"/><mxPoint x="220" y="157"/>','<mxPoint x="220" y="157"/><mxPoint x="220" y="105"/>'))['ok'])
 def test_duplicate_named_field_rejected(self):
  with self.assertRaisesRegex(ValueError,'ambiguous'):compare(A,A.replace('as="targetPoint"','as="sourcePoint"'))
 def test_unnamed_geometry_child_rejected(self):
  with self.assertRaisesRegex(ValueError,'ambiguous'):compare(A,A.replace(' as="targetPoint"',''))
 def test_text_change_rejected(self):self.assertFalse(compare(A,A.replace('full label','lost label'))['ok'])
 def test_terminal_change_rejected(self):self.assertFalse(compare(A,A.replace('source="v"','target="v"'))['ok'])
 def test_style_change_rejected(self):self.assertFalse(compare(A,A.replace('fontStyle=1','fontStyle=0'))['ok'])
 def test_numeric_spelling_equivalent(self):self.assertTrue(compare(A,A.replace('x=".8077"','x="0.807700"'))['ok'])
 def test_nonfinite_rejected(self):
  with self.assertRaisesRegex(ValueError,'nonfinite'):compare(A,A.replace('x="240"','x="NaN"'))
if __name__=='__main__':unittest.main(verbosity=2)
