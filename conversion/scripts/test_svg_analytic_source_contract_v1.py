import unittest
from compiler_svg_general_guard_v3 import source_features


class AnalyticSourceStrokeContractTests(unittest.TestCase):
    def scene(self,matrix):
        return dict(nodes={},objects=[dict(id='curve',type='shape',tag='path',d='M0 0 C0 50 70 0 100 0',
          matrix=matrix,attrs={},bbox=dict(x=0,y=0,w=200,h=50),sampledPoints=[[0,0],[100,0]],
          markerStart='none',markerEnd='none',sceneAncestry=[],sceneComputedCss={},
          style=dict(fill='none',stroke='rgb(0,0,0)',strokeWidth=1,opacity=1,fillOpacity=1,strokeOpacity=1,
                     linecap='butt',linejoin='miter',dash='none'))],sceneMetadata=dict(markerContexts={}))

    def test_nonuniform_scale_cannot_claim_one_exact_native_stroke_width(self):
        result=source_features(self.scene([1.5,0,0,1,0,0]),[256,256])
        self.assertFalse(result['ok']);self.assertIn('source_stroked_nonconformal_connector_requires_outline_compiler',{r['reason']for r in result['failures']})

    def test_shear_is_also_not_an_isotropic_stroke(self):
        self.assertFalse(source_features(self.scene([1,.5,0,1,0,0]),[256,256])['ok'])

    def test_rotation_and_uniform_scale_remain_supported(self):
        self.assertTrue(source_features(self.scene([0,2,-2,0,10,20]),[256,256])['ok'])

    def test_reflected_similarity_remains_supported(self):
        self.assertTrue(source_features(self.scene([-2,0,0,2,200,0]),[256,256])['ok'])


if __name__=='__main__':unittest.main()
