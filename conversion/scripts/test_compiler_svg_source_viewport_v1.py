"""Finite source-contact/geometry contract and real native frame controls."""
import io,json,unittest,uuid,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
import compiler_svg_source_viewport_export_v1 as ex
from compiler_svg_source_viewport_graphviz_v1 import source_surface_contact
R=ex.R;W=ex.W

def png(color='white',point=None):
 im=Image.new('RGBA',(16,12),color)
 if point:im.putpixel(point,(0,0,0,255))
 b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
def fixture(x=-3):
 return '<mxfile><diagram><mxGraphModel page="1" pageWidth="100" pageHeight="80"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="n" parent="1" vertex="1" style="shape=rectangle;fillColor=#0000ff;strokeColor=#000000;"><mxGeometry x="'+str(x)+'" y="10" width="20" height="20" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
PLAN={'x':-44,'y':-44,'width':188,'height':168}
class SourceContactTests(unittest.TestCase):
 def test_white_not_contact(self):self.assertFalse(source_surface_contact(png())['source_surface_contact'])
 def test_interior_not_contact(self):self.assertFalse(source_surface_contact(png(point=(8,6)))['source_surface_contact'])
 def test_left_contact(self):self.assertTrue(source_surface_contact(png(point=(0,6)))['source_surface_contact'])
 def test_top_contact(self):self.assertTrue(source_surface_contact(png(point=(8,0)))['source_surface_contact'])
 def test_transparent_black_not_visible_contact(self):self.assertFalse(source_surface_contact(png(color=(0,0,0,0)))['source_surface_contact'])
 def test_contact_reads_no_reference(self):self.assertFalse(source_surface_contact(png(point=(0,0)))['original_reference_pixels_or_scores_used'])
class GeometryContractTests(unittest.TestCase):
 def test_declare_preserves_every_geometry_style_text(self):self.assertTrue(ex.geometry_identity(fixture(),ex.declare(fixture(),PLAN))['all_native_geometry_style_topology_text_identical'])
 def test_declaration_fresh_source_matches(self):self.assertTrue(ex.verify_declaration(ex.declare(fixture(),PLAN),PLAN))
 def test_changed_fresh_source_plan_rejected(self):
  with self.assertRaisesRegex(ValueError,'fresh_SOURCE_plan'):ex.verify_declaration(ex.declare(fixture(),PLAN),{**PLAN,'x':-45})
 def test_noninteger_plan_rejected(self):
  with self.assertRaisesRegex(ValueError,'plan_invalid'):ex.declare(fixture(),{**PLAN,'x':-44.0})
 def test_bool_plan_rejected(self):
  with self.assertRaisesRegex(ValueError,'plan_invalid'):ex.declare(fixture(),{**PLAN,'x':True})
 def test_shape_change_cannot_be_called_geometry_preserving(self):
  with self.assertRaisesRegex(ValueError,'changed_native_geometry'):ex.geometry_identity(fixture(),ex.declare(fixture(1),PLAN))
class ActualNativeFrameTests(unittest.TestCase):
 def test_real_unclipped_native_paint_and_exact_source_export(self):
  r=ex.render(ex.declare(fixture(),PLAN),(100,80));i=r['native_render'];self.assertGreater(i['unclipped_native_outside_source_viewport_pixels'],0);self.assertTrue(i['complete_native_model_paint_inspected']);self.assertTrue(i['native_inspection_to_export_pixels_exact']);self.assertEqual(i['strict_outside_inspection_pixels'],0);self.assertEqual(i['native_outer_svg_inspection_clip_policy']['inspection_computed_overflow'],'visible');self.assertEqual(Image.open(io.BytesIO(r['png'])).size,(100,80))
 def test_wholly_offscreen_paint_is_not_silently_omitted(self):
  with self.assertRaisesRegex(ValueError,'source_viewport_native_render_failed'):ex.render(ex.declare(fixture(-200),PLAN),(100,80))
 def test_inspection_cannot_omit_original_source_surface(self):
  with self.assertRaisesRegex(ValueError,'source_viewport_native_render_failed'):ex.render(ex.declare(fixture(),{**PLAN,'width':120}),(100,80))
if __name__=='__main__':unittest.main()
