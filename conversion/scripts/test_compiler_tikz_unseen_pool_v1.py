import unittest
import compiler_tikz_unseen_pool_v1 as pool

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

if __name__=='__main__':unittest.main()
