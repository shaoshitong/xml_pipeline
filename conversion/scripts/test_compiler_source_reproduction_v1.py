import unittest
from compiler_source_reproduction_v1 import canvas_mapping, _text_positions


class SourceReproductionPolicyTests(unittest.TestCase):
    def test_identity_canvas(self):
        self.assertEqual(canvas_mapping((2534,865),(2534,865))['scale'],1)

    def test_declared_uniform_downscale_rounding(self):
        result=canvas_mapping((3600,1233),(2560,877))
        self.assertEqual(result['rounded_output_canvas'],[2560,877])
        self.assertLessEqual(max(result['rounding_error_px']),1)
        self.assertFalse(result['crop']);self.assertFalse(result['padding'])

    def test_stretch_rejected(self):
        with self.assertRaisesRegex(ValueError,'canvas_mismatch'):canvas_mapping((100,100),(90,80))

    def test_upscale_rejected(self):
        with self.assertRaisesRegex(ValueError,'upscale'):canvas_mapping((100,100),(200,200))

    def test_unregistered_rounding_padding_rejected(self):
        with self.assertRaisesRegex(ValueError,'canvas_mismatch'):canvas_mapping((100,100),(100,101))

    def test_whole_source_text_run_included(self):
        positions=_text_positions({'objects':[{'id':'v1','type':'text','text':'Example','bbox':{'x':3,'y':4,'w':40,'h':12}}, {'id':'v2','type':'text','text':' ','bbox':{'x':0,'y':0,'w':2,'h':12}}]})
        self.assertEqual(len(positions),1)
        self.assertEqual(positions[0]['runs'][0]['chars'][0]['text'],'Example')


if __name__=='__main__':unittest.main()
