import copy,unittest
import tikz_closed_paint_bridge_v1 as m

def sp(points,close=False):
 s=''.join('\\pgfsyssoftpath@'+('moveto' if i==0 else 'lineto')+'token {'+str(x)+'pt}{'+str(y)+'pt}' for i,(x,y) in enumerate(points))
 if close:s+='\\pgfsyssoftpath@closepathtoken {'+str(points[0][0])+'pt}{'+str(points[0][1])+'pt}'
 return s

def event(path,points,close=False,arrow='-'):
 return {'kind':'finish','fields':['1',str(path),arrow,'0','1' if arrow!='-' else '0',sp(points,close)]}

def fixture(axis=True):
 scale=72/72.27;off=[20,60];trans=lambda p:[p[0]*scale+20,-p[1]*scale+60]
 es=[event(1,[[0,0],[10,0],[10,10],[0,10]],True)]
 p=[trans(x) for x in [[0,0],[10,0],[10,10],[0,10],[0,0]]]
 ds=[{'id':0,'parts':[[('moveTo',[p[0]])]+[('lineTo',[x]) for x in p[1:]]],'fill':'#ffcccc','stroke':'none','stroke_width':0}]
 if axis:
  es.append(event(2,[[0,0],[40,0]],arrow='-stealth'));start=trans([0,0]);tip=trans([40,0]);end=[tip[0]-2.5,tip[1]];head=[tip,[tip[0]-4,tip[1]-2],[tip[0]-2.5,tip[1]],[tip[0]-4,tip[1]+2]]
  ds.extend([{'id':1,'parts':[[('moveTo',[start]),('lineTo',[end])]],'fill':'none','stroke':'#000000','stroke_width':.8},{'id':2,'parts':[[('moveTo',[head[0]])]+[('lineTo',[p]) for p in head[1:]]],'fill':'#000000','stroke':'none','stroke_width':0}])
  es.append(event(3,[[0,0],[0,40]],arrow='-stealth'));tip=trans([0,40]);end=[tip[0],tip[1]+2.5];head=[tip,[tip[0]-2,tip[1]+4],[tip[0],tip[1]+2.5],[tip[0]+2,tip[1]+4]]
  ds.extend([{'id':3,'parts':[[('moveTo',[start]),('lineTo',[end])]],'fill':'none','stroke':'#000000','stroke_width':.8},{'id':4,'parts':[[('moveTo',[head[0]])]+[('lineTo',[p]) for p in head[1:]]],'fill':'#000000','stroke':'none','stroke_width':0}])
 return es,ds

class SourceRoleTests(unittest.TestCase):
 def test_closed_and_numeric_axis_complete_unique_source_ownership(self):
  e,d=fixture();r=m.source_roles(e,d);self.assertEqual([x['role'] for x in r['objects']],['source_explicit_closed_basic_paint','explicit_numeric_coordinate_axis_free_edge','explicit_numeric_coordinate_axis_free_edge']);self.assertFalse(r['axis_graph_terminal_claim']);self.assertTrue(r['all_source_and_PDF_paint_accounted'])
 def test_pure_closed_source_geometry_supported(self):
  e,d=fixture(False);r=m.source_roles(e,d);self.assertEqual(len(r['objects']),1)
 def test_named_source_nodes_not_routed_through_paint_profile(self):
  e,d=fixture();e.append({'kind':'node','fields':['1','3','1','node','named','rectangle','text','0pt','0pt','0']})
  with self.assertRaisesRegex(ValueError,'named nodes'):m.source_roles(e,d)
 def test_named_reference_not_replaced_by_free_axis(self):
  e,d=fixture();e.append({'kind':'ref','fields':[]})
  with self.assertRaisesRegex(ValueError,'graph/reference'):m.source_roles(e,d)
 def test_actual_source_unowned_PGF_paint_rejected(self):
  e,d=fixture();e.append({'kind':'unsupportedpaint','fields':[]})
  with self.assertRaisesRegex(ValueError,'unowned'):m.source_roles(e,d)
 def test_ambiguous_duplicate_closed_PDF_owner_rejected(self):
  e,d=fixture();x=copy.deepcopy(d[0]);x['id']=9;d.append(x)
  with self.assertRaisesRegex(ValueError,'ambiguous'):m.source_roles(e,d)
 def test_extra_unmapped_PDF_paint_rejected(self):
  e,d=fixture();d.append({'id':19,'parts':[[('moveTo',[[100,100]]),('lineTo',[[110,110]])]],'fill':'none','stroke':'#aabbcc','stroke_width':1})
  with self.assertRaisesRegex(ValueError,'unmapped'):m.source_roles(e,d)
 def test_wrong_source_PDF_scale_cannot_be_fitted_by_translation(self):
  e,d=fixture(False);d[0]['parts'][0][1][1][0][0]+=1
  with self.assertRaisesRegex(ValueError,'does not match'):m.source_roles(e,d)
 def test_unhandled_softpath_operator_is_not_discarded(self):
  with self.assertRaisesRegex(ValueError,'unsupported'):m.softpath(r'\pgfsyssoftpath@rectcornertoken {0pt}{0pt}')
 def test_unknown_softpath_or_truncated_control_rejected(self):
  for s in (r'\unknown',r'\pgfsyssoftpath@curvetosupportatoken {0pt}{0pt}'):
   with self.assertRaises(ValueError):m.softpath(s)
 def test_arrowhead_detached_from_actual_source_tip_rejected(self):
  e,d=fixture();d[2]['parts'][0][0][1][0][0]+=1
  with self.assertRaisesRegex(ValueError,'arrow head'):m.source_roles(e,d)
 def test_no_arrow_head_never_accepts_plain_shaft(self):
  e,d=fixture();d.pop()
  with self.assertRaisesRegex(ValueError,'arrow head'):m.source_roles(e,d)
 def test_source_arrow_direction_or_colour_change_rejected(self):
  e,d=fixture();d[2]['fill']='#ff0000'
  with self.assertRaisesRegex(ValueError,'arrow head'):m.source_roles(e,d)
 def test_open_source_without_closed_anchor_not_silently_closed(self):
  e,d=fixture();e=e[1:];d=d[1:]
  with self.assertRaisesRegex(ValueError,'no closed source'):m.source_roles(e,d)
 def test_source_marker_kind_not_guessed_from_polygon(self):
  e,d=fixture();e[1]['fields'][2]='->'
  with self.assertRaisesRegex(ValueError,'unhandled source'):m.source_roles(e,d)
 def test_multiple_source_subpaths_fail_closed(self):
  e,d=fixture();e[0]['fields'][5]+=sp([[100,100],[110,100],[110,110]],True)
  with self.assertRaisesRegex(ValueError,'multiple source subpaths'):m.source_roles(e,d)
 def test_builtin_classic_is_not_exact_PGF_stealth(self):
  # Equal tip/base/width do not establish equality: classic notch .75L vs .625L.
  stealth=[[4,0],[0,-2],[1.5,0],[0,2]];classic=[[4,0],[0,-2],[1,0],[0,2]]
  self.assertGreater(m.polygon_distance(stealth,classic),.03)
 def test_polygon_order_cannot_hide_shape_change(self):
  self.assertEqual(m.polygon_distance([[0,0],[2,0],[0,2]],[[2,0],[0,2],[0,0]]),0)
 def test_close_normalization_never_adds_an_extra_closed_segment(self):
  v=[('moveTo',[[0,0]]),('lineTo',[[1,0]]),('lineTo',[[0,0]]),('closePath',[])];r=m.normalized_ops(v);self.assertEqual(len(r[0]),3)
 def test_single_numeric_arrow_is_not_automatically_a_coordinate_axis(self):
  e,d=fixture();e=e[:2];d=d[:3]
  with self.assertRaisesRegex(ValueError,'coordinate-axis pair'):m.source_roles(e,d)
 def test_control_point_change_not_only_endpoint_bounds(self):
  a=[[('moveTo',[[0,0]]),('curveTo',[[0,1],[1,1],[1,0]])]];b=copy.deepcopy(a);b[0][1][1][0][1]=2;self.assertEqual(m.op_distance(a,b),1)

if __name__=='__main__':unittest.main()
