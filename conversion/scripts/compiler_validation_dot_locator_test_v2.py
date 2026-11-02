import ast,importlib.util,unittest
from pathlib import Path
D=Path(__file__).parent
s=importlib.util.spec_from_file_location('fix',D/'compiler_validation_dot_cluster_v2_locator_fixed.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class LocatorTests(unittest.TestCase):
 def test_locator_from_already_frozen_audited_metadata_not_raw_reservoir(self):
  r=[{'id':'ID','source':{'code_sha256':'C','image_sha256':'I'}}];a={'ID':{'id':'ID','format':'python','code_sha256':'C','image_sha256':'I','cluster_keys':[],'source_locator':'clean/source.py'}}
  v=m.bind_candidate_metadata(r,a);self.assertEqual(v[0]['source_locator'],'clean/source.py');self.assertEqual([x['id'] for x in v],['ID'])
 def test_metadata_mismatch_aborts_before_audit(self):
  self.assertRaises(ValueError,m.bind_candidate_metadata,[{'id':'ID','source':{'code_sha256':'C','image_sha256':'I'}}],{'ID':{'id':'ID','code_sha256':'bad','image_sha256':'I'}})
 def test_semantic_cluster_functions_identical_to_precommitted_v2(self):
  def funcs(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
  a=funcs(D/'compiler_validation_dot_cluster_v2.py');b=funcs(D/'compiler_validation_dot_cluster_v2_locator_fixed.py')
  for k in ('hard_keys','evidence_disposition','DSU','graph_identity','parse_dot'):self.assertEqual(a[k],b[k])
if __name__=='__main__':unittest.main()
