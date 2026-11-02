import copy,unittest
from initial_native_tree_translation_analysis_v2 import path_translation_exact,Unsupported,analyze,SVG

class PathEquations(unittest.TestCase):
    def test_all_absolute_command_coordinate_equations(self):
        a='M1 2 L3 4 H5 V6 C1 2 3 4 5 6 Q1 2 3 4 S2 3 4 5 T6 7 A8 9 15 0 1 10 11 Z';b='M2 4 L4 6 H6 V8 C2 4 4 6 6 8 Q2 4 4 6 S3 5 5 7 T7 9 A8 9 15 0 1 11 13 Z';self.assertTrue(path_translation_exact(a,b,1,2))
    def test_subpixel_control_point_change_rejected(self):
        with self.assertRaises(Unsupported):path_translation_exact('M0 0 C1 2 3 4 5 6','M1 1 C2 3 4.000001 5 6 7',1,1)
    def test_arc_radius_and_winding_changes_rejected(self):
        for value in ['M1 1 A3 2 0 0 1 5 5','M1 1 A2 2 0 1 1 5 5']:
            with self.assertRaises(Unsupported):path_translation_exact('M0 0 A2 2 0 0 1 4 4',value,1,1)
    def test_unknown_relative_transform_grammar_not_assumed_equivalent(self):
        with self.assertRaises(Unsupported):path_translation_exact('M0 0 l1 1','M1 1 l1 1',1,1)
    def test_css_path_form(self):self.assertTrue(path_translation_exact('path("M0 0L2 2")','path("M1 1L3 3")',1,1))
    def test_unknown_units_nonfinite_and_missing_points(self):
        for value in ['M 1px 2','MNaN 1','M1','M0 0 R1 2 3 4']:
            with self.assertRaises(Unsupported):path_translation_exact(value,value,0,0)
    def test_scene_analysis_never_claims_full_equivalence_from_geometry(self):
        node={'path':'0','nodeType':1,'namespace':SVG,'tag':'path','attributes':[{'name':'d','value':'M0 0L1 1'}],'computed':{'d':'path("M0 0L1 1")'},'pseudo':{},'children':[]};a={'tree':node,'fontFaceRules':[],'fontFaces':[],'resources':[],'errors':[]};b=copy.deepcopy(a);b['tree']['attributes'][0]['value']='M1 1L2 2';b['tree']['computed']['d']='path("M1 1L2 2")';out=analyze(a,b,[1,1]);self.assertTrue(out['all_implemented_primitive_equations_exact']);self.assertFalse(out['complete_render_tree_equivalence_certified']);self.assertFalse(out['acceptance_allowed'])
    def test_unknown_inherited_style_change_refuses_primitive_claim(self):
        node={'path':'0/0','nodeType':1,'namespace':SVG,'tag':'path','attributes':[{'name':'d','value':'M0 0'}],'computed':{'d':'path("M0 0")','unknown-style':'inherit'},'pseudo':{},'children':[]};a={'tree':node,'fontFaceRules':[],'fontFaces':[],'resources':[],'errors':[]};b=copy.deepcopy(a);b['tree']['computed']['unknown-style']='new-effect';out=analyze(a,b,[0,0]);self.assertFalse(out['all_implemented_primitive_equations_exact']);self.assertEqual(out['unhandled_nonroot_style_changes'][0]['property'],'unknown-style')

if __name__=='__main__':unittest.main()
