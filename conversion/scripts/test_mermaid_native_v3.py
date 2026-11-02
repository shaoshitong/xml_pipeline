import unittest
from mermaid_native_v3 import marker
class MarkerTests(unittest.TestCase):
 def obj(self):return {'mermaidMarker':True,'pointsAttr':'0,0,8,4,0,8','matrix':[1,0,0,1,0,0],'sourceMarkerFill':'#333333','sourceMarkerStroke':'#333333'}
 def test_midpoint_reference_supported(self):self.assertIsNotNone(marker(self.obj(),[[0,4],[4,4]],'end'))
 def test_tip_reference_supported(self):self.assertIsNotNone(marker(self.obj(),[[0,4],[8,4]],'end'))
 def test_base_reference_supported(self):self.assertIsNotNone(marker(self.obj(),[[-2,4],[0,4]],'end'))
 def test_off_axis_marker_rejected(self):self.assertIsNone(marker(self.obj(),[[0,2],[4,2]],'end'))
 def test_floating_reference_beyond_triangle_rejected(self):self.assertIsNone(marker(self.obj(),[[-6,4],[-3,4]],'end'))
 def test_marker_side_reversed_rejected(self):self.assertIsNone(marker(self.obj(),[[8,4],[4,4]],'end'))
if __name__=='__main__':unittest.main()
