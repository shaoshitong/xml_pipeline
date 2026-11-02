import copy,importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('dotir',Path(__file__).with_name('compiler_validation_dot_ir_v2.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def doc(ids=(0,1),labels=('A','B')):
 return {'name':'G','directed':True,'strict':False,'_subgraph_cnt':0,'objects':[{'_gvid':ids[0],'name':'arbitraryA','label':labels[0],'shape':'box'},{'_gvid':ids[1],'name':'arbitraryB','label':labels[1],'shape':'box'}],'edges':[{'_gvid':0,'tail':ids[0],'head':ids[1]}]}
class IRTests(unittest.TestCase):
 def eq(self,a,b):return m.equivalent(m.typed_graph(a),m.typed_graph(b))
 def test_text_ID_order_renaming_same_input_family(self):
  a=doc();b=doc((9,4),('A wholly different long label','Chinese label changed'));b['objects'].reverse();b['name']='renamed';b['objects'][0]['name']='Y';b['objects'][1]['name']='X'
  self.assertTrue(self.eq(a,b))
 def test_topology_not_erased(self):
  a=doc();b=doc();b['edges'].append({'_gvid':1,'tail':1,'head':0});self.assertFalse(self.eq(a,b))
 def test_direction_not_erased(self):
  a=doc();a['objects'][0]['shape']='diamond';b=copy.deepcopy(a);b['edges'][0].update(tail=1,head=0);self.assertFalse(self.eq(a,b))
 def test_parallel_edge_multiplicity_preserved(self):
  a=doc();b=doc();b['edges'].append({'_gvid':1,'tail':0,'head':1});self.assertFalse(self.eq(a,b))
 def test_shape_preserved_and_alias_canonical(self):
  a=doc();b=doc();b['objects'][0]['shape']='rectangle';self.assertTrue(self.eq(a,b));b['objects'][0]['shape']='ellipse';self.assertFalse(self.eq(a,b))
 def test_font_style_and_dimensions_preserved(self):
  for key,value in [('fontname','Arial'),('fontsize','18'),('style','filled'),('width','2')]:
   a=doc();b=doc();b['objects'][0][key]=value;self.assertFalse(self.eq(a,b))
 def test_defaults_and_style_order(self):
  a=doc();b=doc();a['objects'][0]['style']='filled,rounded';b['objects'][0]['style']='rounded,filled';b['objects'][0]['fontsize']='14.0';self.assertTrue(self.eq(a,b))
 def test_compass_port_preserved(self):
  a=doc();b=doc();a['edges'][0]['tailport']='n';b['edges'][0]['tailport']='s';self.assertFalse(self.eq(a,b))
 def test_record_port_rename_preserved_but_port_target_distinct(self):
  a=doc();b=doc()
  for d,label,port in [(a,'<one>Alpha|<two>Beta','one'),(b,'<xx>Different|<yy>Longer text','xx')]:d['objects'][0].update(shape='record',label=label);d['edges'][0]['tailport']=port
  self.assertTrue(self.eq(a,b));b['edges'][0]['tailport']='yy';self.assertFalse(self.eq(a,b))
 def test_cluster_membership_and_name_normalization(self):
  a=doc((1,2));a['_subgraph_cnt']=1;a['objects'].insert(0,{'_gvid':0,'name':'cluster_A','nodes':[1]});b=copy.deepcopy(a);b['objects'][0]['name']='cluster_renamed';self.assertTrue(self.eq(a,b));b['objects'][0]['nodes']=[2];self.assertFalse(self.eq(a,b))
 def test_graph_layout_setting(self):
  a=doc();b=doc();a['rankdir']='LR';b['rankdir']='TB';self.assertFalse(self.eq(a,b))
 def test_implicit_node_label_text_not_new_family(self):
  a=doc();b=doc();b['objects'][0].pop('label');self.assertTrue(self.eq(a,b))
 def test_unknown_port_excluded(self):
  a=doc();a['edges'][0]['tailport']='madeup';self.assertRaises(ValueError,m.typed_graph,a)
 def test_wl_only_candidate_filter_not_equivalence(self):
  self.assertIn('nx.is_isomorphic',__import__('inspect').getsource(m.equivalent))
if __name__=='__main__':unittest.main()
