import unittest
from plantuml_marker_closed_paint_v1 import outline,certificate,area,simple
from plantuml_marker_minimax_v1 import classic
from test_plantuml_marker_minimax_v1 import source

class ClosedPaintTests(unittest.TestCase):
 def test_miter_outline_includes_entire_stroke_and_closing_edge(self):
  square=[(0,0),(10,0),(10,10),(0,10)];self.assertEqual(outline(square,2),[(-1,-1),(11,-1),(11,11),(-1,11)])
 def test_excessive_svg_miter_uses_complete_bevel(self):
  arrow=[(0,0),(-9,4),(-5,0),(-9,-4)];self.assertEqual(len(outline(arrow,1,'miter',4)),6);self.assertEqual(len(outline(arrow,1,'miter',10)),4)
 def test_subpixel_full_paint_translation_has_continuous_upper_certificate(self):
  a=outline([(0,0),(10,0),(10,10),(0,10)],1);b=[(x+.6,y+.2) for x,y in a];v=certificate(a,b);self.assertTrue(v['ok']);self.assertLessEqual(v['upper_bound_px'],1);self.assertTrue(v['both_full_closed_paint_boundaries'])
 def test_actual_greater_than_one_pixel_boundary_is_rejected(self):
  a=outline([(0,0),(10,0),(10,10),(0,10)],1);self.assertFalse(certificate(a,[(x+1.01,y) for x,y in a])['ok'])
 def test_identical_vertex_set_cannot_hide_wrong_interior_segments(self):
  a=[(0,0),(10,0),(10,10),(0,10)];b=[(0,0),(10,10),(10,0),(0,10)];self.assertFalse(simple(b));self.assertFalse(certificate(a,b)['ok'])
 def test_source_only_fit_includes_visible_stroke_outline(self):
  obj,shaft=source();obj['original_computed_paint']={'strokeWidth':1,'linejoin':'miter','miterlimit':4};fit=classic(obj,shaft,'end');self.assertIsNotNone(fit);self.assertTrue(fit['full_source_paint_fit']['predicted_full_paint_certificate']['ok']);self.assertFalse(fit['full_source_paint_fit']['raster_inputs'])

if __name__=='__main__':unittest.main()
