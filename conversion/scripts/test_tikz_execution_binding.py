"""Unit/negative fixtures for physical units and execution-path matching."""
import copy,unittest
from tikz_execution_binding import coordinate_mapping,_mapped,_path_matches_execution,_softpath_points,_marker_stroke,Unsupported,TEX_PT_TO_PDF_BP,executed_plain_text

class ExecutionBindingUnitsTests(unittest.TestCase):
 def fixture(self):
  graph={'nodes':[]};dom={'objects':[]};sx=2*TEX_PT_TO_PDF_BP;sy=-sx
  for i,(x,y) in enumerate(((0,0),(100,40),(200,0))):
   name='n'+str(i);label='Node '+str(i);cx=sx*x+30;cy=sy*y+200
   graph['nodes'].append({'name':name,'shape':'rectangle','expanded_label_tex':label,'center_pt':[str(x)+'pt',str(y)+'pt']})
   dom['objects'] += [{'id':name,'type':'shape','bbox':{'x':cx-20,'y':cy-10,'w':40,'h':20},'style':{'fill':'white'}},{'id':'t'+name,'sourceId':'t'+name,'type':'text','text':label,'bbox':{'x':cx-15,'y':cy-5,'w':30,'h':10}}]
  return dom,graph
 def test_known_physical_units_not_fitted_scale(self):
  dom,graph=self.fixture();mapping=coordinate_mapping(dom,graph,[2,0,0,2,0,0]);self.assertLess(mapping['maximum_node_center_error_px'],1e-9)
  self.assertEqual(mapping['node_centers_checked'],3);self.assertAlmostEqual(mapping['matrix'][0],2*72/72.27)
  self.assertAlmostEqual(_mapped(['100pt','40pt'],mapping)[0],30+200*72/72.27)
  with self.assertRaises(Unsupported):coordinate_mapping(dom,graph,[3,0,0,3,0,0])
  bad=copy.deepcopy(dom);bad['objects'][2]['bbox']['x']+=1
  with self.assertRaises(Unsupported):coordinate_mapping(bad,graph,[2,0,0,2,0,0])
 def test_marker_shortening_does_not_allow_crossing_or_wrong_path(self):
  expected=[[0,0],[100,0]];edge={'start_arrow':False,'end_arrow':True}
  self.assertTrue(_path_matches_execution([[0,0],[96,0]],expected,edge))
  for points in ([[100,0],[0,0]],[[0,0],[96,1]],[[0,0],[70,0]],[[0,0],[110,0]]):
   self.assertFalse(_path_matches_execution(points,expected,edge))
  self.assertFalse(_path_matches_execution([[0,0],[96,0]],expected,{'start_arrow':False,'end_arrow':False}))
 def test_softpath_preserves_exact_straight_scope_and_rejects_curves(self):
  self.assertEqual(_softpath_points(r'\pgfsyssoftpath@movetotoken {-1.2pt}{0pt}\pgfsyssoftpath@linetotoken {20pt}{3pt}'),[['-1.2pt','0pt'],['20pt','3pt']])
  for text in (r'\pgfsyssoftpath@curvetotoken{0pt}{0pt}',r'\pgfsyssoftpath@movetotoken{0pt}{0pt}\pgfsyssoftpath@movetotoken{1pt}{1pt}',r'\arbitrarycommand{0pt}{0pt}'):
   with self.assertRaises(Unsupported):_softpath_points(text)
 def test_only_executed_text_formatting_is_decoded(self):
  value=r'2010.0s\\[0.2cm]{\protect \footnotesize \protect \color{blue!60!black}Formation of clubs}'
  self.assertEqual(executed_plain_text(value),'2010.0s Formation of clubs')
  self.assertEqual(executed_plain_text(r'\textbf{Text} and 20\%'),'Text and 20%')
  for value in (r'\unknownmacro{hidden}',r'$x^2$',r'\color[RGB]{1,2,3}Text'):
   with self.assertRaises(Unsupported):executed_plain_text(value)
 def test_stroked_marker_must_match_actual_shaft_properties(self):
  style={'stroke':'blue','strokeWidth':1,'opacity':1,'strokeOpacity':1,'linejoin':'miter'}
  marker={'style':style,'matrix':[2,0,0,2,0,0]};shaft={'style':dict(style)}
  self.assertEqual(_marker_stroke(marker,shaft,{'strokeWidth':'2'}),'blue')
  for change in ({'stroke':'red'},{'strokeWidth':2},{'strokeOpacity':.5},{'linejoin':'round'}):
   bad={**marker,'style':{**style,**change}}
   with self.assertRaises(Unsupported):_marker_stroke(bad,shaft,{'strokeWidth':'2'})

if __name__=='__main__':unittest.main()
