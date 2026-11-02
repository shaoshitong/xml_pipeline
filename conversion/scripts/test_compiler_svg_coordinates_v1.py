import copy,unittest,xml.etree.ElementTree as E
from unittest.mock import patch
from test_compiler_svg_scene_backend_v4 import fixture
import compiler_svg_scene_backend_v5 as backend
import compiler_svg_explicit_coordinates_v1 as coverage

class SourceCoordinateTests(unittest.TestCase):
 def assert_coverage(self,dom,xml):self.assertTrue(coverage.verify(dom,xml,(140,60))['ok'],coverage.verify(dom,xml,(140,60)))
 def free(self):
  dom=fixture();dom['objects']=dom['objects'][2:];return dom
 def test_original_free_endpoints_are_editable_native_coordinates(self):
  dom=self.free();xml,_=backend.build(dom,(140,60));cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};self.assertIsNone(cells['shaft'].get('source'));self.assertIsNone(cells['shaft'].get('target'));self.assertIsNotNone(cells['shaft'].find("mxGeometry/mxPoint[@as='sourcePoint']"));self.assertNotIn('head',cells);self.assert_coverage(dom,xml)
 def test_ambiguous_endpoint_is_free_without_inventing_owner(self):
  dom=fixture();node=copy.deepcopy(dom['objects'][1]);node['id']='competing';dom['objects'].insert(2,node);xml,_=backend.build(dom,(140,60));edge=next(c for c in E.fromstring(xml).iter('mxCell') if c.get('id')=='shaft');self.assertEqual(edge.get('source'),'node_source_a');self.assertIsNone(edge.get('target'));self.assert_coverage(dom,xml)
 def test_source_geometry_mutation_and_missing_endpoints_are_rejected(self):
  dom=self.free();xml,_=backend.build(dom,(140,60))
  for operation in ('move','remove','bind'):
   tree=E.fromstring(xml);edge=next(c for c in tree.iter('mxCell') if c.get('id')=='shaft');g=edge.find('mxGeometry');point=g.find("mxPoint[@as='targetPoint']")
   if operation=='move':point.set('x',str(float(point.get('x'))+1))
   elif operation=='remove':g.remove(point)
   else:edge.set('target','invented')
   self.assertFalse(coverage.verify(dom,E.tostring(tree,encoding='unicode'),(140,60))['ok'])
 def test_all_source_closed_paint_is_retained(self):
  dom=fixture();xml,_=backend.build(dom,(140,60));self.assert_coverage(dom,xml);tree=E.fromstring(xml);shape=next(c for c in tree.iter('mxCell') if c.get('id')=='a');shape.set('style',shape.get('style').replace('fillColor=#ffffff','fillColor=#ff0000'));self.assertFalse(coverage.verify(dom,E.tostring(tree,encoding='unicode'),(140,60))['ok'])
 def test_zero_area_default_fill_can_be_represented_as_stroke(self):
  dom=self.free();dom['objects'][0]['style']['fill']='rgb(0,0,0)';xml,_=backend.build(dom,(140,60));self.assert_coverage(dom,xml)
 def test_nonzero_area_filled_open_paint_is_not_silently_discarded(self):
  dom=self.free();p=dom['objects'][0];p.update(tag='polyline',attrs={},pointsAttr='40,20 60,30 90,20');p['style']['fill']='rgb(0,0,0)'
  with self.assertRaisesRegex(ValueError,'owner_not_bound'):backend.build(dom,(140,60))
 def test_undeclared_opposite_marker_is_rejected_even_when_other_head_matches(self):
  dom=self.free();xml,_=backend.build(dom,(140,60));changed=xml.replace('startArrow=none','startArrow=block');self.assertFalse(coverage.verify(dom,changed,(140,60))['ok'])
 def test_wrong_marker_fill_and_size_are_independent_source_errors(self):
  dom=self.free();xml,_=backend.build(dom,(140,60))
  for changed in (xml.replace('endFill=1','endFill=0'),xml.replace('endSize=5','endSize=8'),xml.replace('endFillColor=#000000','endFillColor=#ff0000')):
   self.assertNotEqual(changed,xml);self.assertFalse(coverage.verify(dom,changed,(140,60))['ok'])

if __name__=='__main__':unittest.main()
