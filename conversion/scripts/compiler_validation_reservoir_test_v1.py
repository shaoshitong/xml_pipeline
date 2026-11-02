import importlib.util,unittest,collections
from pathlib import Path
s=importlib.util.spec_from_file_location('reserve',Path(__file__).with_name('compiler_validation_reservoir_v1.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ReservoirTests(unittest.TestCase):
 def test_order_independent_and_bounded(self):
  original=[{'id':str(i).zfill(64)} for i in range(1000)]
  a=collections.defaultdict(list);b=collections.defaultdict(list)
  for r in original:m.keep(a,'unit',r)
  for r in reversed(original):m.keep(b,'unit',r)
  expected={r['id'] for r in sorted(original,key=lambda r:m.sha(m.blob([m.SEED,'population_reservoir','unit',r['id']])))[:500]}
  self.assertEqual({x[1] for x in a['unit']},expected);self.assertEqual({x[1] for x in b['unit']},expected)
 def test_units_do_not_share_reservoir_budget(self):
  a=collections.defaultdict(list)
  for i in range(600):
   m.keep(a,'A',{'id':str(i)});m.keep(a,'B',{'id':str(i)})
  self.assertEqual(len(a['A']),500);self.assertEqual(len(a['B']),500)
 def test_threshold_and_finite_audit_budget_fixed(self):
  self.assertEqual(m.MIN_SIM,.85);self.assertEqual(m.MAX_NEAR_COMPARISONS,2000000)
if __name__=='__main__':unittest.main()
