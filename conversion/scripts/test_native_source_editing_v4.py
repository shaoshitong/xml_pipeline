import copy,hashlib,unittest
import native_source_editing_v4 as m


def fixture(style='',node_style='',port=False,actual_port_terminal=False,labels=False,source=True):
    extra=''
    if port:extra+='<mxCell id="p" vertex="1" parent="a" style="ellipse;perimeter=ellipsePerimeter;"><mxGeometry x="1" y="0.5" width="10" height="10" relative="1" as="geometry"/></mxCell>'
    if labels:extra+='<mxCell id="al" vertex="1" parent="a" value="child"><mxGeometry x="10" y="5" width="20" height="10" as="geometry"/></mxCell>'
    terminal='p' if actual_port_terminal else 'a'
    terminal_attr='source="'+terminal+'"' if source else ''
    edge_style=style+(';sourcePort=p;' if port and not actual_port_terminal else '')
    edge_extra=''
    if labels:edge_extra='<mxCell id="label" vertex="1" parent="e" style="group;"><mxGeometry x="0" y="0" width="30" height="10" relative="1" as="geometry"/></mxCell><mxCell id="background" vertex="1" parent="label" style="fillColor=#ffffff;"><mxGeometry x="0" y="0" width="30" height="10" as="geometry"/></mxCell><mxCell id="text" vertex="1" parent="label" value="edge"><mxGeometry x="0" y="0" width="30" height="10" as="geometry"/></mxCell>'
    return '<mxfile><diagram><mxGraphModel pageWidth="600" pageHeight="400"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" vertex="1" parent="1" style="'+node_style+'"><mxGeometry x="100" y="100" width="80" height="40" as="geometry"/></mxCell><mxCell id="b" vertex="1" parent="1"><mxGeometry x="300" y="200" width="80" height="40" as="geometry"/></mxCell>'+extra+'<mxCell id="e" edge="1" parent="1" '+terminal_attr+' target="b" style="'+edge_style+'"><mxGeometry relative="1" as="geometry"><mxPoint x="1000" y="1000" as="sourcePoint"/></mxGeometry></mxCell>'+edge_extra+'</root></mxGraphModel></diagram></mxfile>'


def run(xml):
    record={'source_format':'drawio','code_sha256':hashlib.sha256(xml.encode()).hexdigest()}
    proof={'supported':True,'ok':True,'profile':'original_native_xml','evidence':{'unchanged_source_objects_except_portable_font_styles':True,'source_pages':1}}
    return m.audit(xml,record=record,source_profile=proof)


class Boundary(unittest.TestCase):
 def test_wrong_format_rejected(self):
  with self.assertRaises(ValueError):m.require_source_proof({'source_format':'svg'}, {}, 'xml')
 def test_failed_source_rejected(self):
  record={'source_format':'drawio','code_sha256':hashlib.sha256(b'xml').hexdigest()}
  with self.assertRaises(ValueError):m.require_source_proof(record,{'supported':True,'ok':False},'xml')
 def test_geometry_reconstruction_not_native_original(self):
  record={'source_format':'drawio','code_sha256':hashlib.sha256(b'xml').hexdigest()}
  with self.assertRaises(ValueError):m.require_source_proof(record,{'supported':True,'ok':True,'profile':'svg_complete'},'xml')
 def test_font_source_needs_full_verified_contract(self):
  record={'source_format':'drawio','code_sha256':hashlib.sha256(b'xml').hexdigest()}
  with self.assertRaises(ValueError):m.require_source_proof(record,{'supported':True,'ok':True,'profile':'original_native_exact_graph_physical_font_only_v4','evidence':{'current_code_sha256':record['code_sha256']}},'xml')
 def test_canvas_needs_verified_contract(self):
  record={'source_format':'drawio','code_sha256':hashlib.sha256(b'xml').hexdigest(),'auto_quality_canvas_repair':{'proof':'p'}}
  proof={'supported':True,'ok':True,'profile':'original_native_xml','evidence':{'unchanged_source_objects_except_portable_font_styles':True,'source_pages':1}}
  with self.assertRaises(ValueError):m.require_source_proof(record,proof,'xml')


class LiveNative(unittest.TestCase):
 def test_default_floating_perimeter(self):
  proof=run(fixture());self.assertEqual(proof['edge_count'],1);self.assertTrue(all(x['mode']=='floating_native_perimeter' for x in proof['moves']))
  self.assertTrue(any(abs(x['delta']['x']-x['offset']['x'])>.1 or abs(x['delta']['y']-x['offset']['y'])>.1 for move in proof['moves'] for x in move['interventions']))
  damaged=copy.deepcopy(proof);damaged['moves'][0]['interventions'][0]['after']['actual']['x']+=5
  with self.assertRaises(ValueError):m.validate_report(damaged)
  damaged=copy.deepcopy(proof);damaged['moves'][0]['interventions'][0]['after']['painted']['x']+=5
  with self.assertRaises(ValueError):m.validate_report(damaged)
  damaged=copy.deepcopy(proof);damaged['moves'].pop()
  with self.assertRaises(ValueError):m.validate_report(damaged)
  damaged=copy.deepcopy(proof);damaged['model_and_all_live_states_restored']=False
  with self.assertRaises(ValueError):m.validate_report(damaged)
 def test_fixed_constraints(self):
  proof=run(fixture('exitX=1;exitY=0.5;entryX=0;entryY=0.5;exitPerimeter=0;entryPerimeter=0;'))
  for move in proof['moves']:
   self.assertEqual(move['mode'],'fixed_constraint')
   for step in move['interventions']:
    for axis in ('x','y'):self.assertAlmostEqual(step['delta'][axis],step['offset'][axis])
 def test_orthogonal_router(self):self.assertTrue(run(fixture('edgeStyle=orthogonalEdgeStyle;rounded=0;'))['ok'])
 def test_short_orthogonal_route_replays_model_waypoints_before_clipping(self):
  xml=fixture('edgeStyle=orthogonalEdgeStyle;rounded=0;jettySize=auto;',node_style='ellipse;perimeter=ellipsePerimeter;')
  xml=xml.replace('x="100" y="100" width="80" height="40"','x="240" y="150" width="30" height="30"').replace('<mxCell id="b" vertex="1" parent="1">','<mxCell id="b" vertex="1" parent="1" style="shape=label;perimeter=rectanglePerimeter;rounded=1;">').replace('x="300" y="200" width="80" height="40"','x="300" y="146.5" width="70" height="37"')
  self.assertTrue(run(xml)['ok'])
 def test_rotated_ellipse(self):self.assertTrue(run(fixture(node_style='ellipse;perimeter=ellipsePerimeter;rotation=37;'))['ok'])
 def test_native_owned_port(self):self.assertTrue(run(fixture(port=True))['ok'])
 def test_relative_terminal_moves_owning_vertex(self):
  proof=run(fixture(port=True,actual_port_terminal=True));self.assertEqual(proof['moves'][0]['moved_vertex'],'a')
 def test_native_node_child_and_compound_edge_label(self):self.assertTrue(run(fixture('edgeStyle=orthogonalEdgeStyle;',labels=True))['ok'])
 def test_unbound_detached_endpoint_rejected(self):
  with self.assertRaises(Exception):run(fixture(source=False))
 def test_port_owned_by_wrong_terminal_rejected(self):
  with self.assertRaises(Exception):run(fixture('sourcePort=b;'))

if __name__=='__main__':unittest.main()
