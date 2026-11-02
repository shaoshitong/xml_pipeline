import copy,unittest,xml.etree.ElementTree as ET
import compiler_svg_scene_backend_v1 as b
import compiler_svg_scene_frontend_v1 as frontend

def fixture():
 base={'type':'shape','matrix':[1,0,0,1,0,0],'edge':None,'node':None,'style':{'fill':'rgb(255,255,255)','stroke':'rgb(0,0,0)','strokeWidth':1,'fillOpacity':1,'strokeOpacity':1,'opacity':1,'linecap':'butt','linejoin':'miter','dash':'none'}}
 def rect(key,x):return {**copy.deepcopy(base),'id':key,'tag':'rect','attrs':{'x':x,'y':10,'width':30,'height':20,'rx':0,'ry':0},'bbox':{'x':x,'y':10,'w':30,'h':20},'sceneGeometry':{'topology':{'all_subpaths_explicitly_closed':True,'subpaths':[{'closed':True,'operations':[]}]}}}
 path={**copy.deepcopy(base),'id':'shaft','tag':'line','attrs':{'x1':40,'y1':20,'x2':90,'y2':20},'bbox':{'x':40,'y':20,'w':50,'h':0},'sampledPoints':[[40,20],[65,20],[90,20]]};path['style']['fill']='none'
 head={**copy.deepcopy(base),'id':'head','tag':'polygon','attrs':{},'pointsAttr':'90,20 84,17 84,23','bbox':{'x':84,'y':17,'w':6,'h':6},'markerOwner':'shaft','sceneMarkerContexts':['m1']};head['style'].update(fill='rgb(0,0,0)',stroke='none')
 return {'nodes':{},'issues':[{'reason':'scene_marker_viewport_clip_unproven'}],'objects':[rect('a',10),rect('z',90),path,head],'sceneMetadata':{'root':{'width':140,'height':60},'markerContexts':{'m1':{'owner':'shaft','side':'end','ownerBBoxIsOriginalDocumentInstance':True,'risks':['synthetic_clone_does_not_apply_marker_viewport_clip'],'refCoordinateInterpretationProven':True,'viewportScreenPolygon':[[83,16],[91,16],[91,24],[83,24]]}}}}

class Tests(unittest.TestCase):
 def test_source_nodes_and_explicit_marker_become_bound_native_editable_edge(self):
  dom=fixture();xml,stats=b.build(dom,(140,60));cells={c.get('id'):c for c in ET.fromstring(xml).iter('mxCell')};edge=cells['shaft'];self.assertEqual(edge.get('source'),'node_source_a');self.assertEqual(edge.get('target'),'node_source_z');self.assertNotIn('head',cells);self.assertIn('endArrow=block;',edge.get('style'));self.assertTrue(frontend._semantics(dom,xml)['ok'])
 def test_wrong_terminal_rejected_by_fresh_source_relationship_checker(self):
  dom=fixture();xml,_=b.build(dom,(140,60));tree=ET.fromstring(xml);edge=next(c for c in tree.iter('mxCell') if c.get('id')=='shaft');edge.set('target',edge.get('source'));self.assertFalse(frontend._semantics(dom,ET.tostring(tree,encoding='unicode'))['ok'])
 def test_hollow_or_removed_arrow_cannot_reuse_source_filled_arrow_proof(self):
  dom=fixture();xml,_=b.build(dom,(140,60))
  for change in (xml.replace('endFill=1','endFill=0'),xml.replace('endArrow=block','endArrow=none')):self.assertFalse(frontend._semantics(dom,change)['ok'])
 def test_ambiguous_node_binding_is_pending_not_a_guessed_relationship(self):
  dom=fixture();node=copy.deepcopy(dom['objects'][1]);node['id']='competing';dom['objects'].insert(2,node)
  with self.assertRaisesRegex(ValueError,'ambiguous_native_node_outline'):b.derive(dom,(140,60))
 def test_marker_clip_requires_full_source_geometry_containment(self):
  dom=fixture();dom['sceneMetadata']['markerContexts']['m1']['viewportScreenPolygon']=[[84,19],[85,19],[85,20],[84,20]]
  with self.assertRaisesRegex(ValueError,'paint_clipped_by_viewport'):b.derive(dom,(140,60))
 def test_standalone_source_arrow_cannot_survive_as_unbound_paint(self):
  dom=fixture();xml,_=b.build(dom,(140,60));tree=ET.fromstring(xml);ET.SubElement(tree.find('.//mxGraphModel/root'),'mxCell',id='head',vertex='1',parent='1');self.assertFalse(frontend._semantics(dom,ET.tostring(tree,encoding='unicode'))['ok'])
 def test_frame_translation_preserves_edge_label_relative_coordinates(self):
  xml='<mxfile><mxGraphModel><root><mxCell id="a" vertex="1" parent="1"><mxGeometry x="10" y="20" width="30" height="20"/></mxCell><mxCell id="e" edge="1" parent="1"><mxGeometry relative="1"><Array as="points"><mxPoint x="60" y="30"/></Array></mxGeometry></mxCell><mxCell id="label" vertex="1" parent="e"><mxGeometry relative="1" x=".8" y="0"><mxPoint as="offset" x="4" y="3"/></mxGeometry></mxCell></root></mxGraphModel></mxfile>'
  shifted=b.translate_frame(xml,-.5,-.5);tree=ET.fromstring(shifted);label=next(c for c in tree.iter('mxCell') if c.get('id')=='label');self.assertEqual(label.find('mxGeometry').get('x'),'.8');self.assertEqual(label.find('.//mxPoint').get('x'),'4')

if __name__=='__main__':unittest.main()
