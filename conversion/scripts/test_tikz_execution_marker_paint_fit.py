"""Source path closure and contrast-normalized AA measurements stay explicit."""
import unittest
from tikz_execution_marker_paint_fit import local_path,aa_diagnostics
from tikz_execution_binding_v2 import _source_geometry,marker_metrics
import test_tikz_execution_binding_v2 as fixtures


class PaintFitTests(unittest.TestCase):
 def test_return_to_start_is_not_silently_closed(self):
  points,xml,dom,proof=fixtures.MarkerV2Tests().inputs();obj=dom['objects'][0];obj['d']='M70 44 L82 50 L70 56 L70 44';obj['attrs']['d']=obj['d'];geo=_source_geometry(obj,dom['objects'][1],'end');path,closed=local_path(obj,geo);self.assertFalse(closed);self.assertNotIn('Z',path)
  obj['d']+=' Z';obj['attrs']['d']=obj['d'];path,closed=local_path(obj,geo);self.assertTrue(closed);self.assertTrue(path.endswith('Z'))
 def test_exact_contrast_measurement(self):
  fixture=fixtures.MarkerV2Tests();points,xml,dom,proof=fixture.inputs();image=fixture.image(points);quality=marker_metrics(image,image,xml,dom,proof);diag=aa_diagnostics(image,image,dom,proof,quality)['markers'][0];self.assertEqual(diag['normalized_alpha_l1'],0);self.assertEqual(diag['total_rgb_absolute_error'],0);self.assertEqual(diag['soft_ink_iou'],1)
  self.assertEqual(len(diag['alpha_levels']),5);self.assertTrue(all(m['symmetric_boundary_max_device_px']==0 for m in diag['alpha_levels']))


if __name__=='__main__':unittest.main()
