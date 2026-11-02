"""Known geometric displacements and outside-ROI corruption are fixed negatives."""
import io,unittest
from PIL import Image,ImageDraw
from tikz_execution_marker_quality import check_marker_quality

class MarkerQualityTests(unittest.TestCase):
 def fixture(self,dx=0,remove=False,outside=False):
  image=Image.new('RGB',(100,100),'white')
  if not remove:ImageDraw.Draw(image).polygon([(40+dx,40),(50+dx,45),(40+dx,50)],fill='blue')
  if outside:image.putpixel((1,1),(0,0,0))
  stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()
 def arguments(self):
  xml='<mxfile><diagram><mxGraphModel><root><mxCell id="e" edge="1" source="a" target="b" style="endArrow=block;endFill=1;endFillColor=#0000ff;endStrokeColor=transparent;"/></root></mxGraphModel></diagram></mxfile>'
  dom={'objects':[{'id':'arrow','bbox':{'x':40,'y':40,'w':10,'h':10},'matrix':[1,0,0,1,0,0],'style':{'fill':'rgb(0, 0, 255)','strokeWidth':0}}]}
  binding={'native_arrowheads':[{'source_object':'arrow','edge':'e','side':'end','marker':'block','native_marker_stroke':'transparent'}]}
  return xml,dom,binding
 def test_exact_and_one_pixel_change_are_bounded(self):
  xml,dom,binding=self.arguments()
  exact=check_marker_quality(self.fixture(),self.fixture(),xml,dom,binding);self.assertTrue(exact['ok'],exact)
  shifted=check_marker_quality(self.fixture(),self.fixture(dx=1),xml,dom,binding);self.assertTrue(shifted['ok'],shifted);self.assertEqual(shifted['markers'][0]['symmetric_boundary_distance_device_px'],1)
 def test_material_geometry_and_missing_marker_fail(self):
  xml,dom,binding=self.arguments()
  self.assertFalse(check_marker_quality(self.fixture(),self.fixture(dx=2),xml,dom,binding)['ok'])
  self.assertFalse(check_marker_quality(self.fixture(),self.fixture(remove=True),xml,dom,binding)['ok'])
 def test_outside_roi_and_native_style_cannot_change(self):
  xml,dom,binding=self.arguments()
  bad=check_marker_quality(self.fixture(),self.fixture(outside=True),xml,dom,binding);self.assertFalse(bad['ok']);self.assertEqual(bad['changed_pixels_outside_marker_rois'],1)
  self.assertFalse(check_marker_quality(self.fixture(),self.fixture(),xml.replace('endFillColor=#0000ff','endFillColor=#ff0000'),dom,binding)['ok'])
  self.assertFalse(check_marker_quality(self.fixture(),self.fixture(),xml.replace('endArrow=block','endArrow=classic'),dom,binding)['ok'])

if __name__=='__main__':unittest.main()
