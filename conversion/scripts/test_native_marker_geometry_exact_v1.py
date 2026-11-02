import copy,math,unittest
from native_marker_geometry_exact_v1 import compare_paint,contour_decision,EXACT_EPSILON_PX

class Tests(unittest.TestCase):
 def setUp(self):
  self.source=[(0,0),(-9,3),(-9,-3)];self.paint=[{'d':'M 0 0 L -9 3 L -9 -3 Z','fill':'#000000','stroke':'transparent','transform':None}]
 def decision(self,g,d=math.sqrt(2),ratio=1,viewport=True,editing=True):return contour_decision(d,ratio,g,source_viewport_containment=viewport,actual_editing=editing)
 def test_only_actual_exact_polygon_gets_the_grid_alias(self):
  g=compare_paint(self.paint,0,self.source,'#000000');self.assertEqual(g['maximum_vertex_error_px'],0);self.assertTrue(self.decision(g)['alias_used']);self.assertEqual(EXACT_EPSILON_PX,1e-6)
 def test_offsets_below_old_point_zero_three_tolerance_cannot_use_alias(self):
  for offset in (.001,.01,.02):
   g=compare_paint(self.paint,offset,self.source,'#000000');self.assertFalse(g['exact_geometry']);self.assertFalse(self.decision(g)['ok']);self.assertFalse(self.decision(g)['exact_geometry_alias_eligible'])
 def test_nonexact_geometry_still_uses_the_old_one_pixel_rule(self):
  g=compare_paint(self.paint,.01,self.source,'#000000');self.assertTrue(self.decision(g,1)['old_rule_passed']);self.assertFalse(self.decision(g,1)['alias_used'])
 def test_viewport_editing_and_exact_actual_paint_all_mandatory(self):
  g=compare_paint(self.paint,0,self.source,'#000000');self.assertFalse(self.decision(g,viewport=False)['ok']);self.assertFalse(self.decision(g,editing=False)['ok']);wrong=copy.deepcopy(self.paint);wrong[0]['fill']='#ff0000';g=compare_paint(wrong,0,self.source,'#000000');self.assertFalse(self.decision(g)['ok'])
 def test_unchanged_area_and_grid_bounds_reject_bad_rasters(self):
  g=compare_paint(self.paint,0,self.source,'#000000')
  for d,area in [(2,1),(math.sqrt(2),1.251),(math.sqrt(2),.799)]:self.assertFalse(self.decision(g,d,area)['ok'])
 def test_compound_curved_or_unproved_transformed_paint_is_not_exact_triangle(self):
  for change in [{'d':'M0 0 Q1 2 3 4 Z'},{'transform':'translate(1,0)'},{'d':'M0 0 L1 2 L3 4 L5 6 Z'}]:
   p=copy.deepcopy(self.paint);p[0].update(change)
   with self.assertRaises(ValueError):compare_paint(p,0,self.source,'#000000')

if __name__=='__main__':unittest.main()
