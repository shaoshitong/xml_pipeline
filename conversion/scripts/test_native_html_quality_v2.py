import copy,unittest
import native_html_quality_v2 as q

class NativeRichFontProofTests(unittest.TestCase):
 def fixture(self,mixed=False):
  before='<mxfile><diagram><mxGraphModel><root><mxCell id="c" vertex="1" value="&lt;div&gt;A&lt;/div&gt;" style="namedStyle;fontFamily=Arial;fontStyle=1;fontSize=12;"/></root></mxGraphModel></diagram></mxfile>'
  after=before.replace('fontFamily=Arial;fontStyle=1','fontFamily=FaceBold;fontStyle=0')
  actual=[{'postScriptName':'Arial-BoldMT','isCustomFont':False,'glyphCount':1}]
  row={'cell':'c','style':{'fontFamily':'Arial','fontStyle':1},'actual_fonts':actual}
  change={'cell':'c','families':['FaceBold'],'before_family':'Arial','before_flags':1,'after_flags':0}
  faces={'FaceBold':{'postscript':'Arial-BoldMT','bold':True,'italic':False}}
  if mixed:
   before=before.replace('fontStyle=1','fontStyle=0');after=after.replace('fontFamily=FaceBold','fontFamily=FaceRegular,FaceFallback')
   actual[0]['postScriptName']='ArialMT';actual.append({'postScriptName':'DejaVuSans','isCustomFont':False,'glyphCount':1});row['style']['fontStyle']=0;change.update(families=['FaceRegular','FaceFallback'],before_flags=0)
   faces={'FaceRegular':{'postscript':'ArialMT','bold':False,'italic':False},'FaceFallback':{'postscript':'DejaVuSans','bold':False,'italic':False}}
  return before,after,{'changes':[change],'issues':[]},[row],faces
 def test_rich_label_with_exact_one_face(self):self.assertEqual(q.verify_font_changes(*self.fixture()),{'c'})
 def test_mixed_same_style_stack_preserves_original_markup(self):self.assertEqual(q.verify_font_changes(*self.fixture(True)),{'c'})
 def test_wrong_physical_font_is_rejected(self):
  args=list(self.fixture());args[-1]['FaceBold']['postscript']='TimesNewRomanPS-BoldMT'
  with self.assertRaisesRegex(ValueError,'actual_faces'):q.verify_font_changes(*args)
 def test_changed_label_is_rejected(self):
  args=list(self.fixture());args[1]=args[1].replace('&gt;A&lt;','&gt;B&lt;')
  with self.assertRaisesRegex(ValueError,'markup_changed'):q.verify_font_changes(*args)
 def test_changed_geometry_is_rejected(self):
  args=list(self.fixture());args[1]=args[1].replace('vertex="1"','vertex="1" visible="0"')
  with self.assertRaisesRegex(ValueError,'markup_changed'):q.verify_font_changes(*args)
 def test_named_style_is_not_discarded(self):
  args=list(self.fixture());args[1]=args[1].replace('namedStyle;','')
  with self.assertRaisesRegex(ValueError,'markup_changed'):q.verify_font_changes(*args)
 def test_wrong_style_is_rejected(self):
  args=list(self.fixture());args[-1]['FaceBold']['bold']=False
  with self.assertRaisesRegex(ValueError,'synthetic_style'):q.verify_font_changes(*args)
 def test_unverified_stack_face_is_rejected(self):
  args=list(self.fixture(True));del args[-1]['FaceFallback']
  with self.assertRaisesRegex(ValueError,'unverified_family'):q.verify_font_changes(*args)
 def test_mixed_bold_plain_cannot_be_flattened(self):
  args=list(self.fixture(True));args[-1]['FaceFallback']['bold']=True
  with self.assertRaisesRegex(ValueError,'independent_runs'):q.verify_font_changes(*args)
if __name__=='__main__':unittest.main()
