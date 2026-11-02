import unittest
from native_font_order_probe_v3 import derive_order

class FakeProbe:
 def __init__(self,physical):self.physical=physical;self.calls=[]
 def graphemes(self,text):return list(text)
 def fonts(self,family,flags,size,text):
  self.calls.append(text)
  return [{'postScriptName':ps,'glyphCount':1,'isCustomFont':False} for ps in self.physical[text]]

def row(text,faces):
 return {'label':text,'style':{'fontFamily':'Arial','fontStyle':0,'fontSize':24},'actual_fonts':[{'postScriptName':ps,'glyphCount':1,'isCustomFont':False} for ps in faces]}

class FontOrderTests(unittest.TestCase):
 def test_observed_character_fallback_overrides_arbitrary_aggregate_order(self):
  p=FakeProbe({'A':['Arial'],'∈':['Sans']});cmaps={'Arial':{65},'Math':{65,0x2208,0x1d4ab},'Sans':{65,0x2208}}
  order,proof=derive_order(p,row('A∈𝒫',['Arial','Math','Sans']),set(cmaps),['Arial','Math','Sans'],cmaps)
  self.assertEqual(order,['Arial','Sans','Math']);self.assertIn(['Sans','Math'],proof['constraints'])
 def test_unique_original_observed_cmap_preserves_contextual_math_fallback(self):
  p=FakeProbe({'A':['Arial']});cmaps={'Arial':{65},'Math':{65,0x211d}}
  order,proof=derive_order(p,row('Aℝ',['Arial','Math']),set(cmaps),['Arial','Math'],cmaps)
  self.assertEqual(order,['Arial','Math']);self.assertNotIn('ℝ',p.calls)
  self.assertEqual(proof['observations'][1]['basis'],'unique_original_observed_cmap_face')
 def test_cycle_refuses_context_mapping_that_no_single_stack_can_represent(self):
  p=FakeProbe({'a':['One'],'b':['Two']});cmaps={'One':{97,98},'Two':{97,98}}
  with self.assertRaisesRegex(ValueError,'precedence_cycle'):derive_order(p,row('ab',cmaps),set(cmaps),list(cmaps),cmaps)
 def test_ambiguous_actual_grapheme_fonts_refused(self):
  p=FakeProbe({'x':['One','Two']});cmaps={'One':{120},'Two':{120}}
  with self.assertRaisesRegex(ValueError,'ambiguous_grapheme'):derive_order(p,row('x',cmaps),set(cmaps),list(cmaps),cmaps)
 def test_new_unobserved_system_fallback_never_enters_original_stack(self):
  p=FakeProbe({'x':['Other']});cmaps={'One':{120},'Two':{120}}
  with self.assertRaisesRegex(ValueError,'ambiguous_grapheme'):derive_order(p,row('x',cmaps),set(cmaps),list(cmaps),cmaps)
 def test_whitespace_not_used_as_fallback_decision(self):
  p=FakeProbe({});cmaps={'One':{120}}
  order,proof=derive_order(p,row(' x ',cmaps),set(cmaps),list(cmaps),cmaps)
  self.assertEqual(order,['One']);self.assertEqual(p.calls,[]);self.assertEqual(len(proof['observations']),1)
 def test_repeatable_proof_hash_without_target_image_input(self):
  args=(row('x',['One']),{'One'},['One'],{'One':{120}})
  a=derive_order(FakeProbe({}),*args);b=derive_order(FakeProbe({}),*args)
  self.assertEqual(a,b);self.assertTrue(a[1]['no_target_image_score_used'])

if __name__=='__main__':unittest.main()
