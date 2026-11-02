import unittest,xml.etree.ElementTree as ET
from native_svg_screen_offset_v1 import transform
from auto_quality_source_vector_v2 import _world_box,_edge_points
from compiler_svg_scene_backend_v2 import build
from test_compiler_svg_scene_backend_v2 import fixture

class Tests(unittest.TestCase):
 def test_painted_shapes_and_ports_compensate_different_actual_offsets(self):
  xml,_=build(fixture(),(140,60));old={c.get('id'):c for c in ET.fromstring(xml).iter('mxCell')};offsets={'a':.5,'z':0,'shaft':.5};newxml=transform(xml,offsets,-1);new={c.get('id'):c for c in ET.fromstring(newxml).iter('mxCell')}
  for key in ('a','z'):
   before,after=_world_box(old[key],old),_world_box(new[key],new);self.assertAlmostEqual(after[0]+offsets[key],before[0],places=5);self.assertAlmostEqual(after[1]+offsets[key],before[1],places=5)
  for a,b in zip(_edge_points(old['shaft'],old),_edge_points(new['shaft'],new)):
   self.assertAlmostEqual(b[0]+.5,a[0],delta=.0001);self.assertAlmostEqual(b[1]+.5,a[1],delta=.0001)
 def test_inverse_restores_source_geometry_and_bound_ports(self):
  xml,_=build(fixture(),(140,60));offsets={'a':.5,'z':0,'shaft':.5};restored=transform(transform(xml,offsets,-1),offsets,1);a={c.get('id'):c for c in ET.fromstring(xml).iter('mxCell')};b={c.get('id'):c for c in ET.fromstring(restored).iter('mxCell')}
  for p,q in zip(_edge_points(a['shaft'],a),_edge_points(b['shaft'],b)):self.assertAlmostEqual(p[0],q[0],delta=.0001);self.assertAlmostEqual(p[1],q[1],delta=.0001)
 def test_nonfinite_or_unobserved_offset_inventory_is_rejected(self):
  xml,_=build(fixture(),(140,60))
  for wrong in [{'missing':.5},{'a':float('nan')},{'a':.2}]:
   with self.assertRaises(ValueError):transform(xml,wrong)

if __name__=='__main__':unittest.main()
