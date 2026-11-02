import copy,unittest
import html_compiler_v3 as q
from html_actual_text_alignment import analyze

class MixedPhysicalGlyphTests(unittest.TestCase):
 def fixture(self):
  fonts=[{'postScriptName':'ArialMT','glyphCount':1},{'postScriptName':'DejaVuMathTeXGyre-Regular','glyphCount':1}]
  glyphs=[{'text':'A','raw':'A','x':10,'y':10,'width':8,'height':14},{'text':'∑','raw':'∑','x':18,'y':10,'width':10,'height':14}]
  dom={'objects':[{'id':1,'type':'text','text':'A∑','fontSize':12,'actualSourceGlyphs':glyphs,'actualSourceCss':{'fontSize':12},'actualSourcePhysicalFonts':{'basis':'actual_text_node','fonts':fonts}}]}
  native=copy.deepcopy(glyphs)
  for c in native:c['x']-=1;c['y']-=2
  info={'scale':1,'actual_text_positions':[{'cell':'2','runs':[{'font':'12px Alias','chars':native}]}],'actual_platform_font_usage':[{'cell':'2','fonts':copy.deepcopy(fonts)}]}
  xml='<mxfile><diagram><mxGraphModel><root><mxCell id="2" value="A∑" vertex="1" parent="1" style="html=1;"/></root></mxGraphModel></diagram></mxfile>'
  return dom,info,xml
 def result(self,fixture=None):return q.mixed_analyze(analyze,*(fixture or self.fixture()))['objects'][0]
 def test_same_physical_faces_and_uniform_actual_glyphs(self):
  r=self.result();self.assertEqual(r['category'],'uniform_baseline_translation');self.assertEqual(r['translation'],{'dx':1,'dy':2});self.assertTrue(r['safe_translation'])
 def test_wrong_font_set_is_rejected(self):
  a=list(self.fixture());a[1]['actual_platform_font_usage'][0]['fonts'][1]['postScriptName']='DejaVuSans';self.assertFalse(self.result(a)['safe_translation'])
 def test_nonuniform_actual_glyphs_are_rejected(self):
  a=list(self.fixture());a[1]['actual_text_positions'][0]['runs'][0]['chars'][1]['x']-=1;self.assertFalse(self.result(a)['safe_translation'])
 def test_changed_glyph_size_is_rejected(self):
  a=list(self.fixture());a[1]['actual_text_positions'][0]['runs'][0]['chars'][1]['width']+=1;self.assertFalse(self.result(a)['safe_translation'])
 def test_inexact_source_node_font_scope_is_rejected(self):
  a=list(self.fixture());a[0]['objects'][0]['actualSourcePhysicalFonts']['basis']='actual_owner_subtree';self.assertFalse(self.result(a)['safe_translation'])
 def test_partial_clip_requires_separate_proof(self):
  a=list(self.fixture());a[0]['objects'][0]['sourceClip']={'partial':True};self.assertFalse(self.result(a)['safe_translation'])
 def test_context_always_restores_old_analyzer(self):
  import html_actual_text_alignment as glyph
  original=glyph.analyze
  with self.assertRaises(RuntimeError):
   with q.source_scope():
    self.assertIsNot(glyph.analyze,original);raise RuntimeError()
  self.assertIs(glyph.analyze,original)
if __name__=='__main__':unittest.main()
