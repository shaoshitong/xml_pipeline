import importlib.util,json,unittest,xml.etree.ElementTree as E
from pathlib import Path
spec=importlib.util.spec_from_file_location('round2_source_repair_v1',Path(__file__).with_name('round2_source_repair_v1.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def doc(value='abc',size='12',family='Arial',x='10',style=''):
 return f'<mxfile><diagram><mxGraphModel extFonts="f^data:font/ttf;base64,AAA"><root><mxCell id="t" vertex="1" value="{value}" style="fontSize={size};fontFamily={family};{style}"><mxGeometry x="{x}" y="0" width="30" height="20"/></mxCell></root></mxGraphModel></diagram></mxfile>'
class Tests(unittest.TestCase):
 def test_trigger(self):self.assertTrue(m.eligible({'source_format':'python'},['source_arrow_missing_attached_native_marker']))
 def test_unsupported_format(self):self.assertFalse(m.eligible({'source_format':'html'},['source_connector_missing_native_edge']))
 def test_non_semantic_failure_not_selected(self):self.assertFalse(m.eligible({'source_format':'svg'},['actual_font_portability_requires_embedding']))
 def test_font_transfer_preserves_new_geometry(self):
  xml,cells=m.preserve_fonts(doc(family='NativeFace_a',style='fontSource=datauri;fontStyle=1;'),doc(x='25'))
  c=E.fromstring(xml).find('.//mxCell');self.assertEqual(c.find('mxGeometry').get('x'),'25');self.assertIn('fontFamily=NativeFace_a;',c.get('style'));self.assertEqual(cells,['t'])
 def test_different_text_does_not_transfer(self):self.assertEqual(m.preserve_fonts(doc(family='Native_a'),doc(value='other'))[1],[])
 def test_different_font_size_does_not_transfer(self):self.assertEqual(m.preserve_fonts(doc(family='Native_a'),doc(size='15'))[1],[])
 def test_system_font_does_not_transfer(self):self.assertEqual(m.preserve_fonts(doc(),doc())[1],[])
 def test_missing_model_rejected(self):
  with self.assertRaises(ValueError):m.preserve_fonts('<mxfile/>',doc())
 def test_clean_source_path_required(self):
  with self.assertRaises(ValueError):m._read('/tmp/test','wrong')
 def test_no_mutation(self):
  before=doc(family='Native_a');after=doc(x='20');m.preserve_fonts(before,after);self.assertEqual(before,doc(family='Native_a'));self.assertEqual(after,doc(x='20'))
if __name__=='__main__':unittest.main()
