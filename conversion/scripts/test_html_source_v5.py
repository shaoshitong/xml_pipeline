import copy,io,unittest,xml.etree.ElementTree as E
from html_source_clip_v5 import plan,initialize,finalize
from compiler_html_source_quality_ro_v5 import LabelGrammar

class SourceMaskTests(unittest.TestCase):
 def fixture(self):
  glyph=[dict(text='i',raw='i',x=12,y=20,width=4,height=12,rectCount=1)]
  o=dict(id=1,type='text',text='i',fontSize=12,underline=False,actualSourceGlyphs=glyph,actualSourceCss={'fontSize':12},actualSourcePhysicalFonts={'basis':'actual_text_node','fonts':[{'postScriptName':'Face','glyphCount':1}]},sourceClip={'partial':True,'unmodeled':[],'chain':[dict(left=0,top=0,right=100,bottom=25,clipX=True,clipY=True,radius=['0px']*4)]})
  dom={'objects':[o]};info={'scale':1,'actual_text_positions':[{'cell':'2','runs':[{'font':'12px Face','chars':[dict(text='i',x=11,y=19,width=4,height=12)]}]}],'actual_platform_font_usage':[{'cell':'2','fonts':[{'postScriptName':'Face','glyphCount':1}]}],'actual_clip_boxes':[]}
  xml='<mxfile><diagram><mxGraphModel pageWidth="100" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" parent="1" vertex="1" value="i" style="html=1;shape=text;rotation=0;"><mxGeometry x="11" y="19" width="4" height="12" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
  return xml,dom,info,[100,100]
 def test_missing_source_mask_is_a_real_new_compiler_primitive(self):
  x,d,n,v=self.fixture();p=plan(x,d,n,v);self.assertEqual(len(p['changes']),1);self.assertEqual(p['changes'][0]['delta'],{'dx':1,'dy':1});self.assertEqual(p['changes'][0]['source_clip_bounds'],[0,0,100,25])
 def test_zero_offset_and_already_aligned_glyph_still_gets_missing_mask(self):
  x,d,n,v=self.fixture();n['actual_text_positions'][0]['runs'][0]['chars'][0].update(x=12,y=20);p=plan(x,d,n,v);self.assertEqual(len(p['changes']),1)
 def test_all_source_text_gets_viewport_mask_even_if_range_not_partial(self):
  x,d,n,v=self.fixture();d['objects'][0]['sourceClip']['partial']=False;self.assertEqual(plan(x,d,n,v)['changes'],[]);self.assertEqual(len(plan(x,d,n,v,all_text=True)['changes']),1)
 def test_wrong_physical_face_cannot_be_positioned_by_bbox(self):
  x,d,n,v=self.fixture();n['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='Wrong';p=plan(x,d,n,v);self.assertFalse(p['changes']);self.assertIn('physical_face',p['unsupported'][0]['reason'])
 def test_actual_glyph_shape_advance_mismatch_is_rejected(self):
  x,d,n,v=self.fixture();n['actual_text_positions'][0]['runs'][0]['chars'][0]['width']=6;self.assertFalse(plan(x,d,n,v)['changes'])
 def test_nonrectangular_source_clip_not_silently_flattened(self):
  x,d,n,v=self.fixture();d['objects'][0]['sourceClip']['chain'][0]['radius']=['2px']*4;self.assertFalse(plan(x,d,n,v)['changes'])
 def test_fractional_source_clip_is_explicit_pending(self):
  x,d,n,v=self.fixture();d['objects'][0]['sourceClip']['chain'][0]['bottom']=25.25;p=plan(x,d,n,v);self.assertFalse(p['changes']);self.assertIn('fractional',p['unsupported'][0]['reason'])
 def test_actual_mask_reference_box_not_nominal_cell_bbox(self):
  x,d,n,v=self.fixture();p=plan(x,d,n,v);init=initialize(x,p);r={'actual_clip_boxes':[{'cell':'2','clips':[{'x':11.5,'y':19.5,'width':4.25,'height':12.5,'fragments':[{}]}]}]};new,p=finalize(init,p,r);self.assertEqual(p['changes'][0]['insets'],[-19.5,-84.25,7.0,-11.5]);self.assertIn('inset(-19.5px -84.25px 7px -11.5px)',new)
 def test_graph_font_geometry_and_logical_text_preserved(self):
  x,d,n,v=self.fixture();p=plan(x,d,n,v);new=E.fromstring(initialize(x,p));old=E.fromstring(x)
  for a,b in zip(old.iter('mxCell'),new.iter('mxCell')):
   if a.get('id')=='2':b.set('value',a.get('value'))
  self.assertEqual(E.canonicalize(E.tostring(old,encoding='unicode')),E.canonicalize(E.tostring(new,encoding='unicode')))

class LabelGrammarTests(unittest.TestCase):
 def test_only_measured_text_spans_allowed(self):
  LabelGrammar().feed('<span data-img2code-source-clip="v5" style="clip-path:inset(1px);"><span data-img2code-source-glyph="v5" style="position:relative;left:.5px;top:0px;">x</span></span>')
 def test_svg_overlay_rejected(self):
  with self.assertRaisesRegex(ValueError,'overlay'):LabelGrammar().feed('<svg><path/></svg>')
 def test_raster_label_overlay_rejected(self):
  with self.assertRaisesRegex(ValueError,'overlay'):LabelGrammar().feed('<img src="x">')
 def test_opacity_hiding_text_rejected(self):
  with self.assertRaisesRegex(ValueError,'style'):LabelGrammar().feed('<span style="opacity:0">x</span>')
 def test_absolute_overlays_rejected(self):
  with self.assertRaisesRegex(ValueError,'position'):LabelGrammar().feed('<span style="position:absolute">x</span>')

if __name__=='__main__':unittest.main()
