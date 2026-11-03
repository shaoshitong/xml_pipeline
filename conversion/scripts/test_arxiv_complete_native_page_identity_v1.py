import base64,unittest,urllib.parse,zlib
from arxiv_complete_native_page_identity_v1 import verify
A=b'<mxGraphModel pageWidth="850"><root><mxCell id="0"/><mxCell id="a" value="A  B" vertex="1" style="fillColor=red"><mxGeometry x="3" y="4"/></mxCell><mxCell id="b" value="B" vertex="1"/></root></mxGraphModel>'
B=A.replace(b'A  B',b'Other page')
def document(compressed=False):
 def diag(index,xml):
  if compressed:
   c=zlib.compressobj(wbits=-15);xml=base64.b64encode(c.compress(urllib.parse.quote(xml.decode(),safe='').encode())+c.flush())
  return b'<diagram id="p'+str(index).encode()+b'" name="Page'+str(index).encode()+b'">'+xml+b'</diagram>'
 return b'<mxfile>'+diag(0,A)+diag(1,B)+b'</mxfile>'
class CompletePageIdentityTest(unittest.TestCase):
 def test_inline_and_compressed_complete_page(self):
  for compressed in (False,True):self.assertTrue(verify(document(compressed),B,1,'p1','Page1')['all_original_cells_edges_groups_styles_geometry_labels_and_order_preserved'])
 def test_wrong_page_not_accepted(self):
  with self.assertRaises(ValueError):verify(document(),A,1,'p1','Page1')
 def test_geometry_label_style_and_cell_drop_fail(self):
  for changed in [A.replace(b'x="3"',b'x="4"'),A.replace(b'A  B',b'A B'),A.replace(b'fillColor=red',b'fillColor=blue'),A.replace(b'<mxCell id="0"/>',b'')]:
   with self.assertRaises(ValueError):verify(document(),changed,0,'p0','Page0')
 def test_paint_order_change_fails(self):
  changed=A.replace(b'<mxCell id="0"/>',b'').replace(b'</root>',b'<mxCell id="0"/></root>')
  with self.assertRaises(ValueError):verify(document(),changed,0,'p0','Page0')
 def test_wrong_identity_or_index_fails(self):
  for index,pid,name in [(2,'p2','Page2'),(0,'wrong','Page0'),(0,'p0','wrong')]:
   with self.assertRaises(ValueError):verify(document(),A,index,pid,name)
 def test_original_bytes_unchanged(self):
  full=document(True);before=bytes(full);verify(full,A,0,'p0','Page0');self.assertEqual(full,before)
if __name__=='__main__':unittest.main()
