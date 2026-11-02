import copy,unittest,xml.etree.ElementTree as E
from unittest.mock import patch
import plantuml_textlength_layout_v1 as t
class TextLengthTests(unittest.TestCase):
 def fixture(self):
  chars=[{'text':c,'x':10+i*6.25,'y':20.,'width':6.,'height':10.} for i,c in enumerate('ABC')];fonts=[{'postScriptName':'PhysicalFace','glyphCount':3,'isCustomFont':True}];p={'text':'ABC','graphemes':list('ABC'),'chars':chars,'base_spacing':0.,'spacing':.25,'spacing_delta':.25,'fontSize':10.,'actual_fonts':fonts,'source_declared_textLength':'18.5','source_natural_width':18.};runs=[{'fontKerning':'auto','fontFeatureSettings':'normal','letterSpacing':'.25px','chars':[{**c,'x':c['x']-.5,'y':c['y']+.25,'width':6.25} for c in chars[:-1]]},{'fontKerning':'auto','fontFeatureSettings':'normal','letterSpacing':'0px','chars':[{**chars[-1],'x':chars[-1]['x']-.5,'y':chars[-1]['y']+.25}]}];info={'actual_text_positions':[{'cell':'actual','runs':runs}],'actual_platform_font_usage':[{'cell':'actual','fonts':fonts}]};return p,info
 def test_source_declared_spacing_separates_glyph_size_from_css_trailing_advance(self):
  p,i=self.fixture();r=t.audit({'source':p},i,{'source':'actual'},allow_origin=True);self.assertEqual(r['whole_run_origin']['source'],{'dx':.5,'dy':-.25});self.assertEqual(r['details'][0]['actual_intrinsic_range_size_max_error_px'],0)
 def test_fresh_final_origin_must_match_source(self):
  p,i=self.fixture()
  with self.assertRaisesRegex(ValueError,'grapheme_position_changed'):t.audit({'source':p},i,{'source':'actual'})
 def test_local_per_character_warp_cannot_hide_in_whole_run_origin(self):
  p,i=self.fixture();i['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.1
  with self.assertRaisesRegex(ValueError,'grapheme_position_changed'):t.audit({'source':p},i,{'source':'actual'},allow_origin=True)
 def test_glyph_scaling_rejected_even_if_total_spacing_can_match(self):
  p,i=self.fixture();i['actual_text_positions'][0]['runs'][0]['chars'][0]['width']+=.1
  with self.assertRaisesRegex(ValueError,'grapheme_size_changed'):t.audit({'source':p},i,{'source':'actual'},allow_origin=True)
 def test_actual_css_spacing_must_be_declared_source_value(self):
  p,i=self.fixture();i['actual_text_positions'][0]['runs'][0]['letterSpacing']='.5px'
  with self.assertRaisesRegex(ValueError,'uniform_spacing_changed'):t.audit({'source':p},i,{'source':'actual'},allow_origin=True)
 def test_actual_unicode_and_physical_font_must_be_preserved(self):
  p,i=self.fixture();i['actual_text_positions'][0]['runs'][0]['chars'][0]['text']='Α'
  with self.assertRaisesRegex(ValueError,'graphemes_changed'):t.audit({'source':p},i,{'source':'actual'},allow_origin=True)
  p,i=self.fixture();i['actual_platform_font_usage'][0]['fonts']=[{'postScriptName':'OtherFace','glyphCount':3,'isCustomFont':True}]
  with self.assertRaisesRegex(ValueError,'physical_font_or_glyph_count_changed'):t.audit({'source':p},i,{'source':'actual'},allow_origin=True)
 def test_origin_is_bounded_and_no_extra_css_is_permitted(self):
  p,i=self.fixture()
  with self.assertRaisesRegex(ValueError,'origin_delta'):t.label('source',p,2.1,0)
  value=t.label('source',p,.5,-.25);tree=E.Element('mxfile');model=E.SubElement(tree,'mxGraphModel');root=E.SubElement(model,'root');cell=E.SubElement(root,'mxCell',{'id':'actual','value':value});xml=lambda:E.tostring(tree,encoding='unicode');self.assertTrue(t.verify_labels(xml(),{'source':p},{'source':'actual'}));cell.set('value',value.replace('position:relative','opacity:0;position:relative'))
  with self.assertRaisesRegex(ValueError,'source_declared_span|rich_style_changed'):t.verify_labels(xml(),{'source':p},{'source':'actual'})
 def test_plain_baseline_does_not_require_a_producer_span_flag(self):
  p,i=self.fixture();tree=E.Element('mxfile');model=E.SubElement(tree,'mxGraphModel');root=E.SubElement(model,'root');E.SubElement(root,'mxCell',{'id':'actual','value':'ABC'});self.assertTrue(t.verify_labels(E.tostring(tree,encoding='unicode'),{'source':p},{'source':'actual'}))
  with self.assertRaisesRegex(ValueError,'actual_source_declared_uniform_spacing_changed|grapheme_position_changed'):t.audit({'source':p},{**i,'actual_text_positions':[{'cell':'actual','runs':[{'fontKerning':'auto','fontFeatureSettings':'normal','letterSpacing':'normal','chars':[c for r in i['actual_text_positions'][0]['runs'] for c in r['chars']]}]}]},{'source':'actual'})
 def test_entire_text_inventory_required(self):
  p,i=self.fixture();i['actual_text_positions'].append({'cell':'extra','runs':[]})
  with self.assertRaisesRegex(ValueError,'inventory_changed'):t.audit({'source':p},i,{'source':'actual'},allow_origin=True)
if __name__=='__main__':unittest.main()
