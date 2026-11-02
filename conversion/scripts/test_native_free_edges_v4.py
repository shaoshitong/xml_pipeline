import hashlib,unittest
import native_free_edges_v4 as q

class NativeOriginalFreeEndpointTests(unittest.TestCase):
 def fixture(self):
  xml='<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="A"><mxGeometry x="10" y="10" width="20" height="20" as="geometry"/></mxCell><mxCell id="b" parent="1" vertex="1" value="B"><mxGeometry x="70" y="10" width="20" height="20" as="geometry"/></mxCell><mxCell id="e" parent="1" edge="1" target="b"><mxGeometry relative="1" as="geometry"><mxPoint as="sourcePoint" x="0" y="20"/></mxGeometry></mxCell></root></mxGraphModel></diagram></mxfile>'
  return xml
 def check(self,xml=None,profile=None):
  xml=xml or self.fixture();record={'source_format':'drawio','code_sha256':hashlib.sha256(xml.encode()).hexdigest()};profile=profile or {'profile':'original_native_xml','supported':True,'ok':True,'evidence':{'unchanged_source_objects_except_portable_font_styles':True,'source_pages':1}};return q.structure_checks(xml,record=record,source_profile=profile)
 def test_explicit_source_point_is_valid_native_editable_endpoint(self):
  r=self.check();self.assertTrue(r['ok']);self.assertEqual(r['explicit_free_sides'],[{'edge':'e','side':'source','point':{'x':0,'y':20}}])
 def test_missing_named_terminal_cannot_be_reinterpreted_as_free_point(self):
  with self.assertRaisesRegex(ValueError,'dangling_named_terminal'):self.check(self.fixture().replace('edge="1" target="b"','edge="1" source="missing" target="b"'))
 def test_missing_explicit_endpoint_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'missing_or_ambiguous'):self.check(self.fixture().replace('<mxPoint as="sourcePoint" x="0" y="20"/>',''))
 def test_nonfinite_explicit_endpoint_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'nonfinite'):self.check(self.fixture().replace('sourcePoint" x="0"','sourcePoint" x="NaN"'))
 def test_duplicate_explicit_endpoint_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'missing_or_ambiguous'):self.check(self.fixture().replace('<mxPoint as="sourcePoint" x="0" y="20"/>','<mxPoint as="sourcePoint" x="0" y="20"/><mxPoint as="sourcePoint" x="1" y="20"/>'))
 def test_dangling_port_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'dangling_named_port'):self.check(self.fixture().replace('edge="1" target="b"','edge="1" target="b" style="sourcePort=unknown;"'))
 def test_bad_source_proof_cannot_release_free_edges(self):
  with self.assertRaisesRegex(ValueError,'successful_original_source_profile'):self.check(profile={'supported':True,'ok':False})
 def test_non_source_bound_call_is_rejected(self):
  xml=self.fixture()
  with self.assertRaisesRegex(ValueError,'hash_bound'):q.structure_checks(xml,record={'source_format':'svg','code_sha256':hashlib.sha256(xml.encode()).hexdigest()},source_profile={})
if __name__=='__main__':unittest.main()
