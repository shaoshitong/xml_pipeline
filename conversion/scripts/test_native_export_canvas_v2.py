import copy,io,unittest
import native_export_canvas_v2 as q
from PIL import Image

def png(im):
 b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
class NativeExportTests(unittest.TestCase):
 def fixture(self):
  a=Image.new('RGB',(10,10),'white');a.putpixel((3,3),(10,10,10));b=Image.new('RGB',(8,8),'white');b.putpixel((2,2),(10,10,10));return a,b
 def state(self):
  a={'actual_platform_font_usage':[{'cell':'a','fonts':[{'postScriptName':'ArialMT','glyphCount':1,'isCustomFont':True}]}],'actual_text_positions':[{'cell':'a','runs':[{'chars':[{'text':'A','x':3,'y':3,'width':4,'height':5}]}]}],'graphBounds':{'x':3,'y':3,'width':4,'height':5}}
  b=copy.deepcopy(a);b['actual_text_positions'][0]['runs'][0]['chars'][0].update(x=2,y=2);b['graphBounds'].update(x=2,y=2);return a,b
 def test_bounded_roundoff_same_foreground(self):
  a,b=self.fixture();b.putpixel((2,2),(12,11,12));self.assertEqual(q.exact_shift(png(a),png(b),-1,-1)['maximum_channel_roundoff'],2)
 def test_roundoff_over_bound_is_rejected(self):
  a,b=self.fixture();b.putpixel((2,2),(13,10,10))
  with self.assertRaisesRegex(ValueError,'roundoff'):q.exact_shift(png(a),png(b),-1,-1)
 def test_missing_ink_is_rejected(self):
  a,b=self.fixture();b.putpixel((2,2),(255,255,255))
  with self.assertRaisesRegex(ValueError,'foreground_mask'):q.exact_shift(png(a),png(b),-1,-1)
 def test_source_paint_crop_is_rejected(self):
  a,b=self.fixture()
  with self.assertRaisesRegex(ValueError,'crop_source_paint'):q.exact_shift(png(a),png(b),-4,-4)
 def test_actual_glyph_translation(self):
  self.assertTrue(q.verify_render_translation(*self.state(),-1,-1)['actual_graphemes_exactly_translated'])
 def test_wrong_font_is_rejected(self):
  a,b=self.state();b['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='TimesNewRomanPSMT'
  with self.assertRaisesRegex(ValueError,'physical_font'):q.verify_render_translation(a,b,-1,-1)
 def test_missing_text_is_rejected(self):
  a,b=self.state();b['actual_text_positions'][0]['runs'][0]['chars']=[]
  with self.assertRaisesRegex(ValueError,'glyph_count'):q.verify_render_translation(a,b,-1,-1)
 def test_wrong_offset_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'glyph_geometry'):q.verify_render_translation(*self.state(),0,-1)
 def test_changed_shape_extent_is_rejected(self):
  a,b=self.state();b['graphBounds']['width']+=1
  with self.assertRaisesRegex(ValueError,'graph_bounds'):q.verify_render_translation(a,b,-1,-1)
if __name__=='__main__':unittest.main()
