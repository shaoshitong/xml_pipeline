import unittest
import compiler_tikz_node_paint_iteration_pool_v2 as pool

def picture(body):return r'\documentclass{standalone}\usepackage{tikz}\begin{document}\begin{tikzpicture}'+body+r'\end{tikzpicture}\end{document}'
CHAIN=picture(r'\node(A) at (0,0){Alpha};\node(B) at (1,0){Beta};\node(C) at (2,0){Gamma};\draw[->](A)--(B);\draw[->](B)--(C);')

class SourceFamilyTests(unittest.TestCase):
 def test_renamed_labels_ids_and_geometry_are_conservatively_same_family(self):
  other=picture(r'\node(X) at (10,2){One};\node(Y) at (30,7){Two};\node(Z) at (50,9){Three};\draw[->](X)--(Y);\draw[->](Y)--(Z);')
  self.assertEqual(pool.family(CHAIN)[0],pool.family(other)[0])
 def test_different_actual_endpoint_graph_changes_family(self):
  fork=CHAIN.replace(r'\draw[->](B)--(C)',r'\draw[->](A)--(C)')
  self.assertNotEqual(pool.family(CHAIN)[0],pool.family(fork)[0])
 def test_arrow_role_changes_family(self):
  self.assertNotEqual(pool.family(CHAIN)[0],pool.family(CHAIN.replace('[->]','[-]'))[0])
 def test_unknown_program_statement_is_not_discarded(self):
  with self.assertRaises(ValueError):pool.family(CHAIN.replace(r'\end{tikzpicture}',r'\unknownmacro{extra};\end{tikzpicture}'))
 def test_numeric_free_path_is_unknown_for_this_complete_static_family_parser(self):
  with self.assertRaises(ValueError):pool.family(picture(r'\draw(0,0)--(1,1);'))
 def test_cross_format_code_or_image_overlap_excludes_new_id(self):
  source={'code_sha256':'code','image_sha256':'image'}
  self.assertTrue(pool.identity_overlap('new',source,set(),{'code'},set()))
  self.assertTrue(pool.identity_overlap('new',source,set(),set(),{'image'}))
  self.assertFalse(pool.identity_overlap('new',source,set(),set(),set()))


class TransitiveComponentTests(unittest.TestCase):
 @staticmethod
 def row(id,keys,known=True,pending=True):return {'audit':{},'request':{'id':id,'source':{'code_sha256':id+'code','image_sha256':id+'image'}},'keys':set(keys),'known':known,'pending':pending}
 def test_unselected_bridge_closes_development_family(self):
  rs=[self.row('bridge',{'dev','shared'},pending=False),self.row('new',{'shared','other'})];eligible,_=pool.independent_components(rs,set(),set(),set(),{'dev'});self.assertEqual(eligible,[])
 def test_unknown_bridge_prevents_independence_but_keeps_input_record(self):
  rs=[self.row('unknown',{'same'},False),self.row('known',{'same','typed'})];eligible,_=pool.independent_components(rs,set(),set(),set(),set());self.assertEqual(eligible,[]);self.assertEqual(len(rs),2)
 def test_exact_image_connects_different_source_families(self):
  rs=[self.row('a',{'image','familyA'}),self.row('b',{'image','familyB'})];eligible,_=pool.independent_components(rs,set(),set(),set(),set());self.assertEqual(len(eligible),1)
 def test_qualified_bridge_does_not_allow_duplicate_development_family(self):
  rs=[self.row('qualified',{'dev','family'},pending=False),self.row('pending',{'family'})];eligible,_=pool.independent_components(rs,set(),set(),set(),{'dev'});self.assertEqual(eligible,[])


class OriginalSourcePathTests(unittest.TestCase):
 def test_canonical_staged_source_inside_remote_root_is_allowed(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);p=root/'conversion/inputs/source.tex';p.parent.mkdir(parents=True);p.write_bytes(b'original TikZ')
   self.assertEqual(pool.checked_original_code('conversion/inputs/source.tex',pool.sha(p.read_bytes()),root),'original TikZ')
 def test_changed_canonical_staged_bytes_rejected(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);p=root/'source.tex';p.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'hash_changed'):pool.checked_original_code('source.tex','0'*64,root)
 def test_staged_symlink_cannot_escape_registered_root(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory()as tmp:
   folder=Path(tmp);root=folder/'registered';root.mkdir();other=folder/'outside.tex';other.write_bytes(b'outside');(root/'source.tex').symlink_to(other)
   with self.assertRaisesRegex(ValueError,'outside_registered_root'):pool.checked_original_code('source.tex',pool.sha(other.read_bytes()),root)
if __name__=='__main__':unittest.main()
