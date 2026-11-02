import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('cluster',Path(__file__).with_name('compiler_validation_dot_cluster_v2.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class AuditControlTests(unittest.TestCase):
 def test_wrapper_near_needs_actual_DOT_or_is_insufficient(self):
  self.assertEqual(m.evidence_disposition(False,False,False,True,False),'audit_insufficient_near_development_DOT_unknown')
 def test_only_wrapper_near_with_distinct_known_DOT_does_not_block(self):
  self.assertEqual(m.evidence_disposition(False,False,False,False,False),'eligible_unconsumed_audited_cluster')
 def test_exact_family_remains_hard(self):
  r={'id':'I','code_sha256':'C','image_sha256':'P','cluster_keys':['skeleton:X','old_family:Y','near:Q'],'provenance_keys':['document:D']};k=m.hard_keys(r)
  self.assertIn('skeleton:X',k);self.assertIn('old_family:Y',k);self.assertIn('document:D',k);self.assertNotIn('near:Q',k)
 def test_unknown_candidate_never_eligible(self):
  self.assertEqual(m.evidence_disposition(False,True,False,False,False),'DOT_parse_or_identity_unknown')
 def test_unknown_component_never_eligible(self):
  self.assertEqual(m.evidence_disposition(False,False,True,False,False),'component_DOT_audit_unknown')
 def test_same_typed_input_counts_once(self):
  self.assertEqual(m.evidence_disposition(False,False,False,False,True),'duplicate_global_DOT_or_hard_cluster')
 def test_development_transitive_closure_still_blocks(self):
  d=m.DSU(3);d.union(0,1);d.union(1,2);self.assertEqual(d.find(0),d.find(2));self.assertEqual(m.evidence_disposition(True,False,False,False,False),'development_cluster_overlap')
if __name__=='__main__':unittest.main()
