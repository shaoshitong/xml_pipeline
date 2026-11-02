import io,unittest
from PIL import Image
import tikz_native_page_v1 as page
import tikz_native_free_v1 as free

XML='''<mxfile><diagram><mxGraphModel page="1" pageWidth="10" pageHeight="10"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="v" vertex="1" parent="1"><mxGeometry x="2" y="2" width="3" height="3" as="geometry"/></mxCell><mxCell id="e" edge="1" parent="1" style="endArrow=classic;"><mxGeometry relative="1" as="geometry"><mxPoint x="1" y="1" as="sourcePoint"/><mxPoint x="8" y="8" as="targetPoint"/></mxGeometry></mxCell></root></mxGraphModel></diagram></mxfile>'''

class FreeEndpointRules(unittest.TestCase):
 def setup_proof(self,xml):
  record={'source_format':'tikz','code_sha256':free.sha(xml.encode()),'source_code_sha256':'originalcode','source_image_sha256':'originalimage'}
  profile={'profile':'compiler_tikz_poppler_source_v2','supported':True,'ok':True,'failures':[],
           'evidence':{'complete_source_coverage':True,'candidate_code_sha256':record['code_sha256'],'source_code_sha256':'originalcode','source_image_sha256':'originalimage','actual_original_PDF_paint_inventory':{'complete_actual_PDF_paint_inventory':True}}}
  return record,profile
 def test_explicit_finite_source_coordinates_are_valid_free_sides(self):
  r,p=self.setup_proof(XML);result=free.structure_checks(XML,record=r,source_profile=p);self.assertEqual(len(result['explicit_free_sides']),2)
 def test_named_dangling_terminal_is_never_reinterpreted_as_free(self):
  xml=XML.replace('id="e" edge="1"','id="e" edge="1" target="missing"');r,p=self.setup_proof(xml)
  with self.assertRaisesRegex(ValueError,'dangling_named_terminal'):free.structure_checks(xml,record=r,source_profile=p)
 def test_nan_free_coordinate_is_not_accepted(self):
  xml=XML.replace('x="8" y="8"','x="NaN" y="8"');r,p=self.setup_proof(xml)
  with self.assertRaisesRegex(ValueError,'nonfinite_explicit_endpoint'):free.structure_checks(xml,record=r,source_profile=p)
 def test_original_native_flag_cannot_replace_full_PGF_PDF_source_proof(self):
  r,p=self.setup_proof(XML);p['evidence'].pop('actual_original_PDF_paint_inventory');r['original_native_xml']=True
  with self.assertRaisesRegex(ValueError,'display_list_proof'):free.structure_checks(XML,record=r,source_profile=p)
 def test_stale_source_proof_cannot_authorize_changed_XML(self):
  r,p=self.setup_proof(XML)
  with self.assertRaisesRegex(ValueError,'not_bound_to_current_XML'):free.structure_checks(XML.replace('endArrow=classic','endArrow=none'),record=r,source_profile=p)

class WholeNativePixelProof(unittest.TestCase):
 def png(self,im):
  data=io.BytesIO();im.save(data,format='PNG');return data.getvalue()
 def proof_images(self):
  # Same 2x2 actual page shifted by a documented integer (1,1), with a full
  # audit canvas that also covers original out-of-page paint.
  original=Image.new('RGB',(2,2),'white');original.putpixel((0,0),(0,0,0))
  expanded=Image.new('RGB',(3,3),'white');expanded.paste(original,(1,1))
  before=Image.new('RGB',(8,8),'white');before.paste(original,(2,2));after=Image.new('RGB',(9,9),'white');after.paste(expanded,(2,2))
  old={'outside_page_pixel_audit':{'offset':[2,2]},'actual_platform_font_usage':[]};new={'outside_page_pixel_audit':{'offset':[2,2]},'actual_platform_font_usage':[]}
  return [self.png(before),self.png(after),self.png(original),self.png(expanded),old,new,{'dx':1,'dy':1}]
 def test_complete_native_paint_and_original_page_are_preserved(self):self.assertTrue(page.exact_pixels(*self.proof_images())['complete_same_view_native_paint_pixel_identical'])
 def test_deleting_outside_paint_cannot_be_called_padding(self):
  args=self.proof_images();after=Image.open(io.BytesIO(args[1])).convert('RGB');after.putpixel((8,8),(0,0,0));args[1]=self.png(after)
  with self.assertRaisesRegex(ValueError,'complete_native_paint_changed'):page.exact_pixels(*args)
 def test_font_substitution_invalidates_padding(self):
  args=self.proof_images();args[5]['actual_platform_font_usage']=[{'cell':'v','font':'substitute'}]
  with self.assertRaisesRegex(ValueError,'physical_fonts_changed'):page.exact_pixels(*args)

if __name__=='__main__':unittest.main()
