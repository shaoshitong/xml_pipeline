import math,unittest
from plantuml_marker_minimax_v1 import classic,polygon,correspondence_upper

def source(angle=0,translation=(0,0),notch=5):
 c,s=math.cos(angle),math.sin(angle);x,y=translation
 return {'pointsAttr':f'0,0 -9,4 -{notch},0 -9,-4','matrix':[c,s,-s,c,x,y]},[[x-20*c,y-20*s],[x,y]]

class MinimaxTests(unittest.TestCase):
 def test_actual_four_vertex_joint_fit_improves_ideal_notch_fixed_tip(self):
  obj,shaft=source();fit=classic(obj,shaft,'end');self.assertIsNotNone(fit);self.assertLess(fit['geometric_fit_certificate']['upper_bound_px'],.99);self.assertNotEqual(fit['tip_shift']['along'],0);self.assertTrue(fit['geometric_fit_certificate']['whole_closed_segments_proven'])
 def test_translation_and_rotation_do_not_change_intrinsic_fit(self):
  obj,shaft=source();base=classic(obj,shaft,'end')
  for angle in (.17,1.2,2.6):
   obj,shaft=source(angle,(123.4,59.7));fit=classic(obj,shaft,'end');self.assertEqual(base['arrow'],fit['arrow']);self.assertAlmostEqual(base['length'],fit['length'],places=5);self.assertAlmostEqual(base['maximum_source_vertex_displacement_px'],fit['maximum_source_vertex_displacement_px'],places=5)
 def test_actual_notch_is_measured_instead_of_replaced_by_ideal_template(self):
  obj,shaft=source(notch=5.03);fit=classic(obj,shaft,'end');self.assertAlmostEqual(fit['source_notch_depth'],5.03);self.assertNotAlmostEqual(fit['source_notch_depth'],5*fit['source_length']/9)
 def test_invalid_or_missing_concave_notch_is_not_called_classic(self):
  obj,shaft=source(notch=0);self.assertIsNone(classic(obj,shaft,'end'))
 def test_full_closed_correspondence_bound_is_not_vertex_to_other_set_lower_bound(self):
  a=[(0,0),(1,0),(1,1),(0,1)];b=[(.25,0),(1.25,0),(1.25,1),(.25,1)];proof=correspondence_upper(a,b);self.assertAlmostEqual(proof['upper_bound_px'],.25);self.assertTrue(proof['whole_closed_segments_proven']);self.assertTrue(proof['is_upper_bound_not_discrete_hausdorff'])

if __name__=='__main__':unittest.main()
