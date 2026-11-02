import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import html_source_frontend_v5 as q

class StaticSourceTests(unittest.TestCase):
 def support(self,css='',body='hello',size=(100,100)):
  b=io.BytesIO();Image.new('RGB',size,'white').save(b,format='PNG')
  source={'code_sha256':'a'*64,'image_sha256':'b'*64,'asset_root':'clean/assets'};code=('<html><head><style>'+css+'</style></head><body>'+body+'</body></html>').encode()
  with tempfile.TemporaryDirectory() as t:
   (Path(t)/'clean/assets').mkdir(parents=True)
   with patch.object(q,'R',Path(t)),patch.object(q,'source_inputs',return_value=(source,{'asset_root':'clean/assets'},code,b.getvalue())):
    return q.static_support({'id':'c'*64})
 def test_source_static_only_without_existing_native(self):self.assertTrue(self.support()['supported'])
 def test_background_image_none_is_not_unimplemented_paint(self):self.assertTrue(self.support('body { background-image: none; }')['supported'])
 def test_none_transform_not_false_positive_due_regex_whitespace(self):self.assertTrue(self.support('body { transform: none;filter: none;text-shadow: none; }')['supported'])
 def test_gradient_source_is_explicit_next_primitive(self):self.assertIn('background_paint',self.support('body{background:linear-gradient(red,blue)}')['reasons'][0])
 def test_actual_background_image_is_deferred(self):self.assertFalse(self.support('body{background-image:url(x.png)}')['supported'])
 def test_css_transform_not_guessed_from_bbox(self):self.assertFalse(self.support('body{transform:rotate(3deg)}')['supported'])
 def test_rounded_background_not_blanket_rejected_as_rounded_text_clip(self):self.assertTrue(self.support('body{overflow:hidden}.card{border-radius:12px}')['supported'])
 def test_font_face_source_provenance_needs_new_adapter(self):self.assertFalse(self.support('@font-face{font-family:x;src:url(a.ttf)}')['supported'])
 def test_dynamic_source_script_not_accepted_by_static_HTML_grammar(self):self.assertFalse(self.support(body='<script>bad()</script>hello')['supported'])
 def test_canvas_does_not_silently_become_raster(self):self.assertFalse(self.support(body='<canvas>hello</canvas>')['supported'])
 def test_original_viewport_plus_fixed_frame_must_fit_renderer(self):self.assertFalse(self.support(size=(8130,1))['supported'])

if __name__=='__main__':unittest.main()
