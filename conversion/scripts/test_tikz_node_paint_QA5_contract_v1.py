import copy,math,struct,unittest
from tikz_node_paint_render_domain_v1 import retained_visual
from tikz_node_paint_editing_v4 import validate_report

class VisualDomainPolicyTests(unittest.TestCase):
 def test_only_diagnosed_cross_renderer_line_score_is_replaced_by_required_source_gate(self):
  original=dict(ok=False,failures=['local_text_line_ssim_below_0.55'],thresholds=dict(each_text_line_ssim=.55));before=copy.deepcopy(original)
  result=retained_visual(original,dict(ok=True,visual=dict(ok=True)))
  self.assertTrue(result['ok']);self.assertEqual(result['thresholds']['each_text_line_ssim'],.55);self.assertEqual(original,before)
 def test_every_other_reference_failure_remains_mandatory(self):
  for failure in ('global_fidelity_below_0.90','foreground_tile_p10_below_0.72','foreground_coverage_below_0.90','blank_reference_or_native_render'):
   result=retained_visual(dict(ok=False,failures=['local_text_line_ssim_below_0.55',failure]),dict(ok=True))
   self.assertFalse(result['ok']);self.assertIn(failure,result['failures'])
 def test_source_domain_failure_cannot_be_bypassed_by_original_reference_success(self):
  result=retained_visual(dict(ok=True,failures=[]),dict(ok=False));self.assertFalse(result['ok']);self.assertIn('independent_actual_PDF_source_render_domain_failed',result['failures'])

class IndependentPaintPrecisionReportTests(unittest.TestCase):
 def f(self,x):return struct.unpack('f',struct.pack('f',x))[0]
 def box(self,x,y,w,h):return dict(x=self.f(x),y=self.f(y),width=self.f(x+w)-self.f(x),height=self.f(y+h)-self.f(y))
 def report(self):
  b=self.box(2062.86,91.78,137.79,39.37);items=[]
  for offset in (dict(x=17,y=11),dict(x=-13,y=19)):
   a=self.box(2062.86+offset['x'],91.78+offset['y'],137.79,39.37)
   items.append(dict(offset=offset,actual_native_vertex_delta=offset,actual_native_paint_followed=True,model_and_all_live_states_restored=True,painted_members=1,painted_member_precision_proofs=[dict(before=b,after=a,proof=dict(ok=True,policy='SVG_DOMRect_binary32_corner_intervals_v1'))]))
  return dict(ok=True,model_and_all_live_states_restored=True,edge_count=0,moves=[],vertex_count=1,vertex_moves=[dict(cell='one',ok=True,interventions=items)])
 def test_known_large_coordinate_float32_rounding_is_independently_verified(self):self.assertTrue(validate_report(self.report())['ok'])
 def test_real_extent_and_physical_shift_drift_are_rejected(self):
  for field,delta in (('width',.002),('x',.25*100/72)):
   report=self.report();report['vertex_moves'][0]['interventions'][1]['painted_member_precision_proofs'][0]['after'][field]+=delta
   with self.assertRaisesRegex(ValueError,'painted_corner_did_not_follow'):validate_report(report)
 def test_missing_member_observation_is_not_proved_by_boolean(self):
  report=self.report();report['vertex_moves'][0]['interventions'][1]['painted_member_precision_proofs']=[]
  with self.assertRaisesRegex(ValueError,'precision_proof_missing'):validate_report(report)

if __name__=='__main__':unittest.main()
