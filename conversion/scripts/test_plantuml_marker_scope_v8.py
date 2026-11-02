import copy,math,unittest
from unittest.mock import patch
import compiler_plantuml_natural_candidate_v8 as frontend
from plantuml_marker_closed_paint_v1 import certificate

class ScopeTests(unittest.TestCase):
 def fixtures(self,vertices=4):
  polygon=[(0,0),(10,0),(10,10),(0,10)][:vertices];closed=certificate([(0,0),(10,0),(10,10),(0,10)],[(.7,0),(10.7,0),(10.7,10),(.7,10)]);actual={'ok':True,'markers':[{'ok':True,'source_arrow':'head','native_edge':'edge','side':'end','source_polygon':polygon,'actual_native_polygon':polygon,'actual_bound_move_and_shaft_rotation':True,'continuous_full_paint_certificate':closed}]};raster={'ok':False,'markers':[{'source_arrow':'head','native_edge':'edge','side':'end','boundary_distance_px':math.sqrt(2),'ink_area_ratio':1.,'ok':False}],'failures':[{'reason':'old_fixed_pixel_limit'}]};return actual,raster
 def test_calibrated_four_point_factory_may_use_alias(self):
  actual,raster=self.fixtures()
  with patch.object(frontend,'_marker_raster_gate',return_value=raster),patch('compiler_plantuml_native_paint_quality_v1.verify',return_value=actual):result=frontend._marker_gate({},'xml',{},b'',(10,10))
  self.assertTrue(result['ok']);self.assertTrue(result['markers'][0]['grid_alias_used'])
 def test_uncalibrated_triangles_keep_strict_one_pixel_raster_rule(self):
  actual,raster=self.fixtures(3)
  with patch.object(frontend,'_marker_raster_gate',return_value=raster),patch('compiler_plantuml_native_paint_quality_v1.verify',return_value=actual):result=frontend._marker_gate({},'xml',{},b'',(10,10))
  self.assertFalse(result['ok']);self.assertFalse(result['markers'][0]['grid_alias_used']);self.assertEqual(result['markers'][0]['raster_grid_cap_px'],1.)
 def test_source_native_marker_polygon_topology_cannot_change(self):
  actual,raster=self.fixtures();actual['markers'][0]['actual_native_polygon']=actual['markers'][0]['actual_native_polygon'][:3]
  with patch.object(frontend,'_marker_raster_gate',return_value=raster),patch('compiler_plantuml_native_paint_quality_v1.verify',return_value=actual):
   with self.assertRaisesRegex(ValueError,'topology_changed'):frontend._marker_gate({},'xml',{},b'',(10,10))

if __name__=='__main__':unittest.main()
