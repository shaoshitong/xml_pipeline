import copy,math,unittest
from plantuml_marker_closed_paint_v1 import certificate
from plantuml_marker_grid_rule_v1 import decision

class GridRuleTests(unittest.TestCase):
 def proof(self,dx=.7):
  p=[(0,0),(10,0),(10,10),(0,10)];return certificate(p,[(x+dx,y) for x,y in p])
 def test_sqrt2_only_under_complete_physical_one_pixel_proof(self):
  result=decision(math.sqrt(2),1.,self.proof(),opaque_paint_style_equivalent=True);self.assertTrue(result['ok']);self.assertTrue(result['grid_alias_used']);self.assertFalse(result['old_one_pixel_raster_rule_passed'])
 def test_greater_than_one_physical_pixel_rejected_even_when_raster_old_rule_passes(self):self.assertFalse(decision(1.,1.,self.proof(1.25),opaque_paint_style_equivalent=True)['ok'])
 def test_whole_both_perimeters_are_required(self):
  proof=self.proof();proof['both_full_closed_paint_boundaries']=False;self.assertFalse(decision(1.,1.,proof,opaque_paint_style_equivalent=True)['ok'])
 def test_style_mismatch_never_uses_alias(self):self.assertFalse(decision(1.,1.,self.proof(),opaque_paint_style_equivalent=False)['ok'])
 def test_raster_and_area_caps_remain_finite_and_unchanged(self):
  for distance,ratio in [(2.,1.),(1.,.79),(1.,1.26),(float('nan'),1.)]:self.assertFalse(decision(distance,ratio,self.proof(),opaque_paint_style_equivalent=True)['ok'])

if __name__=='__main__':unittest.main()
