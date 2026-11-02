import importlib.util,unittest
from pathlib import Path
D=Path(__file__).parent
s=importlib.util.spec_from_file_location('audit',D/'compiler_validation_cluster_audit_v1.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
s=importlib.util.spec_from_file_location('oldsampler',D/'round2_heldout_select_v1.py');old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
class AuditTests(unittest.TestCase):
 def test_program_array_length_and_values_not_independence(self):
  a='import matplotlib.pyplot as p\nx=[1,2,3]\np.plot(x,label="A")'
  b='import matplotlib.pyplot as q\ny=[9,8,7,6,5]\nq.plot(y,label="Long different text")'
  self.assertEqual(m.tree_skeleton(a,'python',old),m.tree_skeleton(b,'python',old))
 def test_program_control_structure_preserved(self):
  a='import graphviz\ng=graphviz.Digraph()\ng.node("a")'
  b='import graphviz\ng=graphviz.Digraph()\nfor x in range(3):\n g.node(x)'
  self.assertNotEqual(m.tree_skeleton(a,'python',old),m.tree_skeleton(b,'python',old))
 def test_unquoted_mermaid_label_length_not_independence(self):
  a='flowchart LR\n A[Alpha] --> B[Beta]'
  b='flowchart LR\n X[A much longer phrase] --> Y[Another many word label]'
  self.assertEqual(m.tree_skeleton(a,'mermaid',old),m.tree_skeleton(b,'mermaid',old))
 def test_xml_repeat_multiplicity_not_independence(self):
  a='<svg><rect x="1" y="2"/><rect x="3" y="4"/></svg>'
  b='<svg><rect x="5" y="6"/></svg>'
  self.assertEqual(m.tree_skeleton(a,'svg',old),m.tree_skeleton(b,'svg',old))
 def test_xml_primitive_preserved(self):
  self.assertNotEqual(m.tree_skeleton('<svg><path d="M 1 2"/></svg>','svg',old),m.tree_skeleton('<svg><rect/></svg>','svg',old))
 def test_archive_shard_not_template(self):
  self.assertEqual(m.provenance({'annotation':{'template_archive':'shard_012.tar','template_dir':'PAPER_1/'}},'P'),[])
 def test_document_provenance_paper_shared(self):
  self.assertEqual(m.provenance({'annotation':{'paper_id':'X'}},'P'),m.provenance({'annotation':{'paper_id':'X'}},'Q'))
 def test_transitive_leakage(self):
  d=m.DSU(3);d.union(0,1);d.union(1,2);self.assertEqual(d.find(0),d.find(2))
 def test_language_type_before_repair_action(self):
  self.assertEqual(m.feature_group('flowchart LR\n A-->B','mermaid')[0],'mermaid_flowchart')
  self.assertEqual(m.feature_group('@startuml\n component "A" as A\n@enduml','plantuml')[0],'plantuml_component')
 def test_source_feature_imports(self):
  self.assertEqual(m.feature_group('from graphviz import Digraph\ng=Digraph()','python')[0],'python_graphviz')
 def test_audit_not_conversion(self):
  import inspect
  x=inspect.getsource(m)
  self.assertNotIn('subprocess',x);self.assertNotIn('eval(',x);self.assertNotIn('exec(',x)
if __name__=='__main__':unittest.main()
