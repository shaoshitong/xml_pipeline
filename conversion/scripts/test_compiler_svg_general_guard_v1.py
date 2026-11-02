import copy,unittest
from test_compiler_svg_scene_backend_v4 import fixture
from compiler_svg_general_guard_v1 import source_features
class SourceFeatureTests(unittest.TestCase):
 def test_known_supported_explicit_marker_source_passes_guard(self):self.assertTrue(source_features(fixture(),(140,60))['ok'])
 def test_group_opacity_compositing_is_pending(self):
  dom=fixture();dom['objects'][0]['style']['opacity']=.5;self.assertIn('source_element_or_ancestor_opacity_requires_compositing_frontend',[f['reason'] for f in source_features(dom,(140,60))['failures']])
 def test_unmapped_connector_dash_offset_rejected(self):
  dom=fixture();dom['objects'][2]['sceneComputedCss']={'strokeDashoffset':'1px'};self.assertFalse(source_features(dom,(140,60))['ok'])
 def test_internal_stroke_before_fill_not_claimed_complete(self):
  dom=fixture();dom['objects'][0]['sceneComputedCss']={'paintOrder':'stroke fill markers'};self.assertFalse(source_features(dom,(140,60))['ok'])
 def test_ancestor_blend_not_claimed_flat(self):
  dom=fixture();dom['objects'][0]['sceneAncestry']=['g'];dom['sceneMetadata']['ancestors']={'g':{'mixBlendMode':'multiply','isolation':'auto'}};self.assertFalse(source_features(dom,(140,60))['ok'])
if __name__=='__main__':unittest.main()
