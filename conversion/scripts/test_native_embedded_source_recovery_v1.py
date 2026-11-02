import base64,copy,json,struct,unittest,urllib.parse,zlib
import xml.etree.ElementTree as E
import compiler_native_embedded_source_recovery_v1 as c
MODEL='<mxGraphModel dx="100" dy="100" pageWidth="850" pageHeight="1100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" value="A+B" vertex="1" parent="1" style="fillColor=#ffffff;"><mxGeometry x="10" y="20" width="80" height="30" as="geometry"/></mxCell><mxCell id="b" value="B" vertex="1" parent="1"><mxGeometry x="100" y="20" width="80" height="30" as="geometry"/></mxCell><mxCell id="e" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell></root></mxGraphModel>'
def author(model=MODEL):return ('<mxfile scale="1" border="0"><diagram id="p">'+model+'</diagram></mxfile>').encode()
def classification(gold,auth=None):
 a=auth or author();return c.compare(c.document(gold),c.document(a),gold,a)
class Recovery(unittest.TestCase):
 def test_percent_decode_preserves_plus(self):
  b,steps=c.decode_author(urllib.parse.quote(author().decode(),safe=''));self.assertEqual(b,author());self.assertIn(b'A+B',b)
 def test_literal_XML_plus_not_form_decoded(self):self.assertEqual(c.decode_author(author().decode())[0],author())
 def test_raw_identity(self):self.assertEqual(classification(author())['classification'],'completely_identical')
 def test_wrapper_only(self):self.assertEqual(classification(MODEL.encode())['classification'],'wrapper_or_editor_export_metadata_difference')
 def test_dx_dy_are_explicit_source_metadata(self):
  result=classification(MODEL.replace('dy="100"','dy="200"').encode());self.assertEqual(result['classification'],'wrapper_or_editor_export_metadata_difference');self.assertIn('dy',result['page_matrix'][0]['model_attribute_differences'])
 def test_text_conflict_rejected(self):
  r=classification(MODEL.replace('value="B"','value="Changed"').encode());self.assertEqual(r['classification'],'valid_native_models_semantic_or_paint_conflict');self.assertEqual(r['page_matrix'][0]['counts']['text'],1)
 def test_geometry_conflict_rejected(self):
  r=classification(MODEL.replace('x="10"','x="11"').encode());self.assertEqual(r['classification'],'valid_native_models_semantic_or_paint_conflict');self.assertEqual(r['page_matrix'][0]['counts']['geometry'],1)
 def test_bound_terminal_conflict_rejected(self):
  r=classification(MODEL.replace('target="b"','target="a"').encode());self.assertEqual(r['classification'],'valid_native_models_semantic_or_paint_conflict');self.assertEqual(r['page_matrix'][0]['counts']['edge_endpoints'],1)
 def test_source_style_conflict_rejected(self):
  r=classification(MODEL.replace('#ffffff','#ff0000').encode());self.assertEqual(r['classification'],'valid_native_models_semantic_or_paint_conflict');self.assertEqual(r['page_matrix'][0]['counts']['style'],1)
 def test_broken_XML_is_corruption(self):self.assertEqual(classification(MODEL[:-12].encode())['classification'],'provided_source_corrupt_author_original_recoverable')
 def test_dangling_terminal_is_corruption(self):self.assertEqual(classification(MODEL.replace('target="b"','target="missing"').encode())['classification'],'provided_source_corrupt_author_original_recoverable')
 def test_native_coordinate_edges_not_falsely_corrupt(self):
  m=MODEL.replace(' source="a" target="b"','').replace('<mxGeometry relative="1" as="geometry"/>','<mxGeometry relative="1" as="geometry"><mxPoint x="0" y="0" as="sourcePoint"/><mxPoint x="5" y="5" as="targetPoint"/></mxGeometry>');self.assertTrue(c.document(m.encode())['structurally_valid'])
 def test_compressed_page_preserves_complete_model(self):
  compressor=zlib.compressobj(wbits=-15);packed=compressor.compress(urllib.parse.quote(MODEL,safe='').encode())+compressor.flush();b=('<mxfile><diagram>'+base64.b64encode(packed).decode()+'</diagram></mxfile>').encode();self.assertEqual(classification(b)['classification'],'wrapper_or_editor_export_metadata_difference')
 def test_alternate_page_selected_only_by_source(self):
  other=MODEL.replace('value="B"','value="Other"');a=('<mxfile><diagram id="other">'+other+'</diagram><diagram id="exact">'+MODEL+'</diagram></mxfile>').encode();r=classification(MODEL.encode(),a);self.assertEqual(r['paired_author_page_indices'],[1]);self.assertEqual(r['page_pairing_basis'],'source_native_content_only_no_target_pixels')
 def test_duplicate_author_pages_not_guessed(self):
  a=('<mxfile><diagram>'+MODEL+'</diagram><diagram>'+MODEL+'</diagram></mxfile>').encode();self.assertEqual(classification(MODEL.encode(),a)['classification'],'valid_native_models_semantic_or_paint_conflict')
 def test_ID_alpha_renaming_requires_exact_order_and_relations(self):
  tree=E.fromstring(MODEL);mapping={'0':'root','1':'layer','a':'first','b':'second','e':'edge'}
  for n in tree.iter():
   for k in ('id','parent','source','target'):
    if n.get(k)in mapping:n.set(k,mapping[n.get(k)])
  r=classification(E.tostring(tree));self.assertEqual(r['classification'],'wrapper_or_editor_export_metadata_difference');self.assertTrue(r['page_matrix'][0]['ordered_alpha_content_exact_except_editor_export'])
 def test_paint_order_not_silently_normalized(self):
  tree=E.fromstring(MODEL);root=tree.find('root');a,b=root[2],root[3];root.remove(a);root.insert(3,a);r=classification(E.tostring(tree));self.assertEqual(r['classification'],'valid_native_models_semantic_or_paint_conflict')
 def test_text_decoder_does_not_execute_entities(self):
  with self.assertRaisesRegex(ValueError,'entity_declaration'):c.decode_author('<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><mxfile>&x;</mxfile>')
 def test_PNG_metadata_without_image_decoding(self):
  def chunk(kind,b):return struct.pack('>I',len(b))+kind+b+struct.pack('>I',zlib.crc32(kind+b)&0xffffffff)
  payload=urllib.parse.quote(author().decode(),safe='').encode();png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'tEXt',b'mxfile\x00'+payload)+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00\x00'))+chunk(b'IEND',b'');m=c.png_metadata(png);self.assertFalse(m['pixels_decoded']);self.assertEqual(c.decode_author(m['texts'][0]['text'])[0],author())
if __name__=='__main__':unittest.main(verbosity=2)
