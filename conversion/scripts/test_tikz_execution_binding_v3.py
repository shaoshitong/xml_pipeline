import copy, unittest
from tikz_execution_binding_v3 import graph_from_events, _path_matches_execution

def e(kind,*fields):return {'kind':kind,'fields':list(fields)}
def trace(soft,refs=(),label=False):
 out=[e('header','1','3.1.10'),e('picture','1','begin'),e('path','1','1','begin')]
 if refs and refs[0]=='source':out.append(e('ref','1','1',r'\tikz@@moveto','ghost','center','0pt','0pt','0'))
 out+=[e('operation','1','1','move','1'),e('operation','1','1','line','2')]
 if label:out.append(e('node','1','1','1','label','','rectangle','note','0pt','0pt','2'))
 out+=[e('finish','1','1','->','0','1',soft),e('picture','1','end'),e('complete','1','1','1' if label else '0')]
 return out
SOFT=r'\pgfsyssoftpath@movetotoken{0pt}{0pt}\pgfsyssoftpath@linetotoken{20pt}{30pt}'
class TypedPathTests(unittest.TestCase):
 def test_numeric_path_is_free_and_full_inventory(self):
  g=graph_from_events(trace(SOFT));self.assertTrue(g['ok'],g['failures']);self.assertEqual(len(g['edges']),1);self.assertIsNone(g['edges'][0]['source']);self.assertIsNone(g['edges'][0]['target']);self.assertEqual(g['typed_free_paths'][0]['kind'],'numeric_numeric')
 def test_free_label_preserved_as_free_annotation(self):
  g=graph_from_events(trace(SOFT,label=True));self.assertTrue(g['ok'],g['failures']);self.assertEqual(len(g['decorative_nodes']),1)
 def test_missing_named_reference_never_becomes_free(self):
  g=graph_from_events(trace(SOFT,refs=['source']));self.assertFalse(g['ok']);self.assertEqual(g['typed_free_paths'],[])
 def test_incomplete_counter_rejected(self):
  t=trace(SOFT);t[-1]['fields'][1]='2';self.assertFalse(graph_from_events(t)['ok'])
 def test_curve_not_silently_treated_as_line(self):
  t=trace(SOFT+r'\pgfsyssoftpath@curvetosupportatoken{3pt}{4pt}');self.assertFalse(graph_from_events(t)['ok'])
 def test_closed_paint_not_invented_edge_from_inherited_arrow(self):
  g=graph_from_events(trace(SOFT+r'\pgfsyssoftpath@closepathtoken{0pt}{0pt}'));self.assertTrue(g['ok'],g['failures']);self.assertFalse(g['edges']);self.assertEqual(len(g['closed_source_paint']),1)
 def test_changed_point_detected(self):
  q={'start_arrow':False,'end_arrow':False};self.assertTrue(_path_matches_execution([[0,0],[20,30]],[[0,0],[20,30]],q));self.assertFalse(_path_matches_execution([[0,0],[30,30]],[[0,0],[20,30]],q))
 def test_polyline_internal_geometry_checked(self):
  q={'start_arrow':False,'end_arrow':False};self.assertFalse(_path_matches_execution([[0,0],[10,6],[20,30]],[[0,0],[10,5],[20,30]],q))
if __name__=='__main__':unittest.main()

class FrameTests(unittest.TestCase):
 def obj(self,id,points):
  return {'id':id,'type':'shape','tag':'path','d':'M'+str(points[0][0])+','+str(points[0][1])+' '+' '.join('L'+str(x)+','+str(y) for x,y in points[1:]),'matrix':[1,0,0,1,0,0],'style':{'fill':'none','stroke':'#000000'},'attrs':{}}
 def test_complete_vector_frame_without_inventing_label_node_shapes(self):
  from tikz_execution_binding_v3 import coordinate_mapping,TEX_PT_TO_PDF_BP
  t=trace(SOFT);t[-3]['fields'][4]='0';g=graph_from_events(t);d={'objects':[self.obj('shaft',[[10,20],[10+20*TEX_PT_TO_PDF_BP,20-30*TEX_PT_TO_PDF_BP]])]};m=coordinate_mapping(d,g,[1,0,0,1,0,0]);self.assertEqual(m['node_cell_ids'],{});self.assertAlmostEqual(m['matrix'][4],10);self.assertAlmostEqual(m['matrix'][5],20)
 def test_source_frame_cannot_scale_to_hide_wrong_geometry(self):
  from tikz_execution_binding_v3 import coordinate_mapping,Unsupported
  g=graph_from_events(trace(SOFT));d={'objects':[self.obj('shaft',[[10,20],[50,80]])]}
  with self.assertRaises(Unsupported):coordinate_mapping(d,g,[1,0,0,1,0,0])
 def test_missing_source_vector_rejected(self):
  from tikz_execution_binding_v3 import coordinate_mapping,Unsupported
  g=graph_from_events(trace(SOFT));d={'objects':[]}
  with self.assertRaises(Unsupported):coordinate_mapping(d,g,[1,0,0,1,0,0])

class VerticalFrameTests(unittest.TestCase):
 def fixture(self):
  from tikz_execution_binding_v3 import TEX_PT_TO_PDF_BP
  nodes=[];objects=[]
  for i,name in enumerate(['A','B','C']):
   y=50+30*i*TEX_PT_TO_PDF_BP;nodes.append({'name':name,'expanded_label_tex':name,'shape':'rectangle','center_pt':['0pt',str(-30*i)+'pt']});objects += [{'id':name,'type':'shape','style':{'fill':'white'},'bbox':{'x':40,'y':y-10,'w':20,'h':20}},{'id':name+'t','type':'text','text':name,'bbox':{'x':45,'y':y-5,'w':10,'h':10}}]
  return {'nodes':nodes,'edges':[]},{'objects':objects}
 def test_fixed_units_do_not_need_horizontal_span(self):
  from tikz_execution_binding_v3 import coordinate_mapping
  g,d=self.fixture();m=coordinate_mapping(d,g,[1,0,0,1,0,0]);self.assertAlmostEqual(m['matrix'][4],50);self.assertAlmostEqual(m['matrix'][5],50);self.assertEqual(m['node_centers_checked'],3)
 def test_inconsistent_center_still_rejected(self):
  from tikz_execution_binding_v3 import coordinate_mapping,Unsupported
  g,d=self.fixture();d['objects'][4]['bbox']['x']+=2
  with self.assertRaises(Unsupported):coordinate_mapping(d,g,[1,0,0,1,0,0])
