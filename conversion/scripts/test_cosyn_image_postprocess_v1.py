import copy,io,unittest,xml.etree.ElementTree as E
from PIL import Image,PngImagePlugin
import compiler_cosyn_image_postprocess_v1 as p
SOURCE=dict(source='allenai--CoSyn-400K',format='python',pair_sha256='a'*64,code_sha256='b'*64,image_sha256='c'*64)
SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="864pt" height="411pt" viewBox="0 0 864 410.82"><g id="graph"><path id="edge" d="M0 0 L864 400"/><text id="label" x="10" y="20">hello</text></g></svg>'
def png(size=(256,128),mode='RGB',metadata=False):
 a=Image.new(mode,size,'white' if mode=='RGB' else (255,0,0,0));a.paste('blue' if mode=='RGB' else (0,0,255,255),(size[0]//2,0,*size));b=io.BytesIO();info=PngImagePlugin.PngInfo();info.add_text('Software','fixture metadata');a.save(b,format='PNG',pnginfo=info if metadata else None);return b.getvalue()
class PostprocessTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.large=p.postprocess(png((3600,1712)),SOURCE)
 def test_exact_official_function_identity(self):self.assertEqual(p.sha(p.OFFICIAL_PROCESS_IMAGE_SOURCE.encode()),p.PRODUCER_FUNCTION_SHA256)
 def test_actual_provider_thumbnail_outputs_2560_1217(self):self.assertEqual(self.large['mapping']['output_canvas'],[2560,1217])
 def test_forward_result_matches_original_reference_header(self):self.assertTrue(p.match_reference_canvas(self.large,(2560,1217))['ok'])
 def test_inverse_rounding_2559_canvas_is_rejected(self):self.assertFalse(p.match_reference_canvas(self.large,(2559,1217))['ok'])
 def test_width_over_2560_without_area_threshold_is_not_resized(self):
  m=p.canvas_plan((2687,1196));self.assertFalse(m['conditional_thumbnail']);self.assertEqual(m['output_canvas'],[2687,1196])
 def test_tall_image_below_area_threshold_is_not_forced_to_box(self):self.assertEqual(p.canvas_plan((1141,2400))['output_canvas'],[1141,2400])
 def test_exact_threshold_not_thumbnail(self):self.assertFalse(p.canvas_plan((2560,1440))['conditional_thumbnail'])
 def test_alpha_is_composited_over_white(self):
  a=p.postprocess(png(mode='RGBA'),SOURCE);im=Image.open(io.BytesIO(a['png']));self.assertEqual(im.mode,'RGB');self.assertEqual(im.getpixel((0,0)),(255,255,255));self.assertEqual(im.getpixel((255,0)),(0,0,255))
 def test_provider_frombytes_drops_inherited_metadata(self):self.assertEqual(Image.open(io.BytesIO(p.postprocess(png(metadata=True),SOURCE)['png'])).info,{})
 def test_native_revision_binds_original_source_hashes(self):
  s={**SOURCE,'source_format':'python','source_code_sha256':'d'*64,'source_image_sha256':'e'*64};a=p.postprocess(png(),s);self.assertEqual(a['evidence']['identity']['source_code_sha256'],'d'*64)
 def test_wrong_provider_never_uses_CoSyn_transform(self):
  with self.assertRaisesRegex(ValueError,'requires_CoSyn'):p.postprocess(png(),{**SOURCE,'source':'other'})
 def test_missing_source_identity_rejected(self):
  with self.assertRaisesRegex(ValueError,'missing_source_hash'):p.postprocess(png(),{**SOURCE,'code_sha256':None})
 def test_monochromatic_image_retains_provider_filter(self):
  b=io.BytesIO();Image.new('RGB',(128,128),'white').save(b,format='PNG');self.assertFalse(p.postprocess(b.getvalue(),SOURCE)['ok'])
 def test_small_and_over_aspect_keep_provider_filters(self):
  self.assertFalse(p.postprocess(png((127,256)),SOURCE)['ok']);self.assertFalse(p.postprocess(png((128,1000)),SOURCE)['ok'])
 def test_full_extent_mapping_has_no_crop_or_padding(self):
  m=self.large['mapping'];self.assertFalse(m['crop']);self.assertFalse(m['padding']);self.assertTrue(m['all_source_pixel_extent_preserved']);self.assertEqual(m['scale_x'],2560/3600);self.assertEqual(m['scale_y'],1217/1712)
 def test_registered_SVG_carries_integer_pixel_grid_to_all_source_children(self):
  out,proof=p.register_svg(SVG,self.large['mapping'],p.sha(SVG));root=E.fromstring(out);self.assertEqual(root.get('viewBox'),'0 0 3600 1712');self.assertEqual(root.get('preserveAspectRatio'),'none');self.assertEqual(root.get('width'),'2560');self.assertTrue(proof['source_children_unchanged']);self.assertTrue(p.verify_registered_svg(SVG,out,self.large['mapping'],p.sha(SVG))['ok'])
 def test_registered_SVG_is_embeddable_as_literal_HTML_SVG(self):
  out,_=p.register_svg(SVG,self.large['mapping'],p.sha(SVG));self.assertTrue(out.startswith(b'<svg '));self.assertIn(b'xmlns="http://www.w3.org/2000/svg"',out)
 def test_target_fitted_or_modified_mapping_rejected(self):
  m=copy.deepcopy(self.large['mapping']);m['output_canvas']=[2559,1217]
  with self.assertRaisesRegex(ValueError,'modified_mapping'):p.register_svg(SVG,m,p.sha(SVG))
 def test_changed_original_source_SVG_rejected(self):
  with self.assertRaisesRegex(ValueError,'identity_changed'):p.register_svg(SVG.replace(b'hello',b'bad'),self.large['mapping'],p.sha(SVG))
 def test_edge_deletion_in_registered_SOURCE_rejected(self):
  out,_=p.register_svg(SVG,self.large['mapping'],p.sha(SVG));root=E.fromstring(out);g=root.find('.//{http://www.w3.org/2000/svg}g');g.remove(g.find('{http://www.w3.org/2000/svg}path'))
  with self.assertRaisesRegex(ValueError,'registered_SOURCE_SVG_changed'):p.verify_registered_svg(SVG,E.tostring(root),self.large['mapping'],p.sha(SVG))
 def test_frame_offset_in_registered_SOURCE_rejected(self):
  out,_=p.register_svg(SVG,self.large['mapping'],p.sha(SVG));root=E.fromstring(out);root[0].set('x','1')
  with self.assertRaisesRegex(ValueError,'registered_SOURCE_SVG_changed'):p.verify_registered_svg(SVG,E.tostring(root),self.large['mapping'],p.sha(SVG))
 def test_visible_raster_wrapper_is_not_SOURCE_geometry(self):
  s=SVG.replace(b'<g id="graph">',b'<g id="graph"><image href="data:image/png;base64,YQ=="/>')
  with self.assertRaisesRegex(ValueError,'unsupported_SOURCE_SVG'):p.register_svg(s,self.large['mapping'],p.sha(s))
 def test_actual_pixels_rederived_from_source(self):
  source=png();out=p.postprocess(source,SOURCE);self.assertTrue(p.verify_postprocess(source,out['png'],SOURCE)['ok'])
 def test_rehashed_removed_paint_cannot_pass_source_replay(self):
  source=png();out=p.postprocess(source,SOURCE);bad=Image.open(io.BytesIO(out['png']));bad.paste('white',(0,0,*bad.size));b=io.BytesIO();bad.save(b,format='PNG')
  with self.assertRaisesRegex(ValueError,'pixels_do_not_reproduce'):p.verify_postprocess(source,b.getvalue(),SOURCE)
if __name__=='__main__':unittest.main()
