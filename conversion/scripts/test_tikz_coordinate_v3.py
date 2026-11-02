"""Coordinate-semantic unit checks; actual browser controls are separate."""
import copy,unittest,xml.etree.ElementTree as E
import native_svg_screen_offset_v2 as n
import tikz_native_page_v2 as page
XML='''<mxfile><diagram><mxGraphModel pageWidth="100" pageHeight="80"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1"><mxGeometry x="10" y="20" width="40" height="30" as="geometry"/></mxCell><mxCell id="e" parent="1" edge="1" source="a" style="exitX=1;exitY=0.5;exitPerimeter=0;"><mxGeometry relative="1" as="geometry"><mxPoint x="70" y="60" as="targetPoint"/><Array as="points"><mxPoint x="65" y="40"/></Array></mxGeometry></mxCell><mxCell id="g" parent="e" vertex="1"><mxGeometry relative="1" x="0.2" y="0.3" as="geometry"><mxPoint x="3" y="4" as="offset"/></mxGeometry></mxCell><mxCell id="t" parent="g" vertex="1" value="label"><mxGeometry x="2" y="5" width="20" height="10" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'''
def frame(offsets):return {'policy':n.POLICY,'code_sha256':n.sha(XML.encode()),'actual_mxCodec_save_reload_verified':True,'offsets':offsets,'cells':{k:{'bbox':[0,0,40,30]} for k in ('a','e','g','t')}}
def cells(xml):return {c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
def xy(c,path='mxGeometry'):
 p=c.find(path);return float(p.get('x',0)),float(p.get('y',0))
class CoordinateTest(unittest.TestCase):
 def test_relative_group_compensates_parent_once(self):
  c=cells(n.transform(XML,frame({'e':.5})));self.assertEqual(xy(c['g'],"mxGeometry/mxPoint[@as='offset']"),(3.5,4.5));self.assertEqual(xy(c['t']),(2,5))
 def test_relative_fraction_remains_semantic(self):
  c=cells(n.transform(XML,frame({'e':.5})));self.assertEqual(xy(c['g']),(.2,.3))
 def test_relative_painted_child_receives_world_delta_only_once(self):
  c=cells(n.transform(XML,frame({'e':.5,'g':.5})));self.assertEqual(xy(c['g'],"mxGeometry/mxPoint[@as='offset']"),(3,4));self.assertEqual(xy(c['t']),(2.5,5.5))
 def test_free_endpoint_is_physical_not_fractional(self):
  c=cells(n.transform(XML,frame({'e':.5})));self.assertEqual(xy(c['e'],"mxGeometry/mxPoint[@as='targetPoint']"),(69.5,59.5))
 def test_route_control_translates_in_same_frame(self):
  c=cells(n.transform(XML,frame({'e':.5})));self.assertEqual(xy(c['e'],"mxGeometry/Array/mxPoint"),(64.5,39.5))
 def test_named_port_compensates_terminal_relative_delta(self):
  c=cells(n.transform(XML,frame({'e':.5})));s=n.unpack(c['e'].get('style'));self.assertEqual(float(s['exitX']),.9875);self.assertAlmostEqual(float(s['exitY']),.5-.5/30)
 def test_same_native_offset_preserves_fixed_port(self):
  c=cells(n.transform(XML,frame({'a':.5,'e':.5})));s=n.unpack(c['e'].get('style'));self.assertEqual((float(s['exitX']),float(s['exitY'])),(1,.5))
 def test_wrong_original_frame_rejected(self):
  f=frame({});f['code_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'not_bound'):n.transform(XML,f)
 def test_fractional_unsupported_offsets_rejected(self):
  with self.assertRaisesRegex(ValueError,'invalid_actual_offset_inventory'):n.transform(XML,frame({'e':.25}))
 def test_unknown_painter_cell_rejected(self):
  with self.assertRaisesRegex(ValueError,'invalid_actual_offset_inventory'):n.transform(XML,frame({'unknown':.5}))
 def test_view_adds_no_geometry_or_text_change(self):
  new=page.set_view(XML,{'dx':2,'dy':1,'width':103,'height':82});self.assertTrue(page.geometry_identity(XML,new)['all_model_geometry_styles_text_topology_identical'])
 def test_export_size_distinct_from_original_declared_page(self):
  new=page.set_view(XML,{'dx':2,'dy':1,'width':103,'height':82});self.assertEqual(page.dimensions(new),(103,82));self.assertEqual(E.fromstring(new).find('.//mxGraphModel').get('pageWidth'),'100')
 def test_view_does_not_permit_changed_text(self):
  new=page.set_view(XML.replace('label','wrong'),{'dx':2,'dy':1,'width':103,'height':82})
  with self.assertRaisesRegex(ValueError,'export_changed_original'):page.geometry_identity(XML,new)
 def test_view_does_not_permit_missing_edge(self):
  root=E.fromstring(XML);r=root.find('.//root');r.remove(next(x for x in r if x.get('id')=='e'))
  with self.assertRaisesRegex(ValueError,'export_changed_original'):page.geometry_identity(XML,E.tostring(root,encoding='unicode'))
 def test_view_does_not_permit_changed_port(self):
  with self.assertRaisesRegex(ValueError,'export_changed_original'):page.geometry_identity(XML,XML.replace('exitX=1;','exitX=0;'))
if __name__=='__main__':unittest.main()
