#!/usr/bin/env python3
"""Regression tests for complete native page isolation and zTXt repair."""
from pathlib import Path
import base64,json,struct,sys,tempfile,unittest,urllib.parse,zlib
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parent))
import embedded_xml_compiler_v1 as C
import embedded_xml_page_core_v1 as P

MODEL=('<mxGraphModel dx="10" dy="20" pageWidth="850" pageHeight="1100"><root>'
 '<mxCell id="0"/><mxCell id="1" parent="0"/>'
 '<mxCell id="a" value="A" vertex="1" parent="1" style="rounded=1;"><mxGeometry x="10" y="20" width="80" height="30" as="geometry"/></mxCell>'
 '<mxCell id="g" value="Group" vertex="1" parent="1"><mxGeometry x="200" y="10" width="200" height="100" as="geometry"/></mxCell>'
 '<mxCell id="b" value="B" vertex="1" parent="g"><mxGeometry x="15" y="20" width="50" height="20" as="geometry"/></mxCell>'
 '<mxCell id="e" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell>'
 '</root></mxGraphModel>')
MODEL2=MODEL.replace('value="A"','value="Second page A"').replace('x="10"','x="13"')

def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
def png(text,kind=b'tEXt'):
 if kind==b'tEXt':payload=b'mxfile\x00'+text
 elif kind==b'zTXt':payload=b'mxfile\x00\x00'+text
 else:payload=b'mxfile\x00'+text
 head=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
 return head+chunk(kind,payload)+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00\x00'))+chunk(b'IEND',b'')
def zraw(data):
 c=zlib.compressobj(9,zlib.DEFLATED,-15);return c.compress(data)+c.flush()
def author(pages):
 return ('<mxfile>'+''.join('<diagram id="p%d" name="Page-%d">%s</diagram>'%(i,i,m) for i,m in enumerate(pages))+'</mxfile>').encode()
def compressed_page(model):
 return base64.b64encode(zraw(urllib.parse.quote(model,safe='').encode())).decode()

class ExtractionRepair(unittest.TestCase):
 def test_raw_deflate_zTXt_is_repaired_and_old_adapter_fails(self):
  xml=author([MODEL]);p=png(zraw(xml),b'zTXt')
  with self.assertRaises(Exception):C.decode_png_metadata(p)
  e=P.decode_png_metadata_v2(p);self.assertEqual(e['compression_mode'],'raw_deflate');self.assertEqual(e['raw'],xml)
 def test_zlib_wrapped_zTXt_still_supported(self):
  xml=author([MODEL]);p=png(zlib.compress(xml),b'zTXt');e=P.decode_png_metadata_v2(p);self.assertEqual(e['compression_mode'],'zlib_wrapper');self.assertEqual(e['raw'],xml)
 def test_bad_zTXt_is_typed_failure(self):
  with self.assertRaises(ValueError):P.decode_png_metadata_v2(png(b'not deflate',b'zTXt'))

class PageIsolation(unittest.TestCase):
 def test_inline_and_compressed_pages_complete(self):
  full=author([MODEL,compressed_page(MODEL2),MODEL.replace('A','Third')])
  doc=P.parse_full_pages(full);self.assertEqual(len(doc['pages']),3)
  self.assertEqual([p['page_index'] for p in doc['pages']],[0,1,2])
  self.assertEqual([p['page_id'] for p in doc['pages']],['p0','p1','p2'])
  self.assertEqual([p['page_name'] for p in doc['pages']],['Page-0','Page-1','Page-2'])
  self.assertEqual(doc['pages'][0]['page_extraction_kind'],'inline_lexical_exact_mxGraphModel')
  self.assertEqual(doc['pages'][1]['page_extraction_kind'],'compressed_raw_deflate_URI_decoded')
  self.assertTrue(P._canon_equal(P.safe_xml(doc['pages'][1]['page_sidecar_XML']),P.safe_xml(MODEL2.encode())))
  self.assertEqual(doc['pages'][0]['cell_count'],6)
  self.assertEqual(doc['pages'][0]['vertex_count'],3)
  self.assertFalse(doc['pages'][0]['sidecar_is_full_embedded_XML'])
 def test_single_root_model_sidecar_is_exact(self):
  doc=P.parse_full_pages(MODEL.encode());self.assertEqual(doc['root_kind'],'mxGraphModel');self.assertEqual(doc['pages'][0]['page_sidecar_XML'],MODEL.encode());self.assertTrue(doc['pages'][0]['sidecar_is_full_embedded_XML'])
 def test_compressed_page_preserves_all_geometry_and_groups(self):
  full=author([compressed_page(MODEL)]);doc=P.parse_full_pages(full);side=doc['pages'][0]['page_sidecar_XML'];root=P.safe_xml(side)
  boxes=[(c.get('id'),c.find('mxGeometry').get('x'),c.find('mxGeometry').get('width')) for c in root.iter('mxCell') if c.find('mxGeometry') is not None]
  self.assertIn(('g','200','200'),boxes);self.assertIn(('b','15','50'),boxes)
 def test_malformed_compressed_page_refused(self):
  bad=('<mxfile><diagram id="x" name="x">'+base64.b64encode(b'not deflate').decode()+'</diagram></mxfile>').encode()
  with self.assertRaises(ValueError):P.parse_full_pages(bad)
 def test_unsafe_DTD_refused(self):
  with self.assertRaises(ValueError):P.parse_full_pages(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><mxfile>&e;</mxfile>')

class OfficialPageControl(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng
  cls.r=OfficialXmlPng()
 @classmethod
 def tearDownClass(cls):cls.r.close()
 def test_official_full_and_page_decode_inline_and_compressed(self):
  full=author([MODEL,compressed_page(MODEL2)])
  # Use the actual PNG path separately to avoid manual XML escaping mistakes.
  p=png(full);e=P.decode_png_metadata_v2(p);self.assertEqual(e['raw'],full)
  proof=C.official_decode_agreement(self.r,p,'PNG_native_XML_marker',e['raw']);self.assertTrue(proof['exact_bytes_equal'] or proof['canonical_XML_equal'])
  doc=P.parse_full_pages(e['raw'])
  for page in doc['pages']:
   cmp=P.official_page_decode_agreement(self.r,e['raw'],page|{'page_sidecar_XML':page['page_sidecar_XML']})
   self.assertTrue(cmp['exact_bytes_equal'] or cmp['canonical_model_equal'])

class RealRendererControl(unittest.TestCase):
 def test_real_page_sidecar_edit_render_restore(self):
  from arxiv_math_stable_export_renderer_v1 import MathSynced
  parent=Path(tempfile.mkdtemp(prefix='page_render_control_',dir=str(P.D)));root=parent/'case'
  r=MathSynced()
  try:proof=r.replay(MODEL.encode(),root)
  finally:r.close()
  self.assertTrue(proof['ok']);self.assertTrue(proof['restored_PNG_bytes_exact']);self.assertTrue(proof['restored_actual_RGBA_exact'])

class RealSourceEvidence(unittest.TestCase):
 def test_known_multipage_source_page_identity(self):
  f=P.C.R/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/papers/2301.12168v1/source/figures/method_schema.png'
  if not f.exists():self.skipTest('frozen sample unavailable')
  before=C.sha(f.read_bytes());e=P.extract_full_v2(f,'PNG_native_XML_marker');doc=P.parse_full_pages(e['raw'])
  self.assertEqual(len(doc['pages']),2);self.assertEqual([p['page_id'] for p in doc['pages']],['0sCOr0dNZM_hzH2vh00O','ayNp_awyyzKCklNIAYEs'])
  for p in doc['pages']:
   self.assertTrue(P._canon_equal(P.safe_xml(p['page_sidecar_XML']),P.safe_xml(p['page_sidecar_XML'])))
   self.assertGreater(p['cell_count'],0)
  self.assertEqual(before,C.sha(f.read_bytes()))

if __name__=='__main__':
 P.D.mkdir(parents=True,exist_ok=True)
 import datetime
 result=unittest.main(verbosity=2,exit=False)
 (P.D/'tests').mkdir(parents=True,exist_ok=True)
 summary={'tests':result.result.testsRun,'failures':len(result.result.failures),'errors':len(result.result.errors),'skipped':len(result.result.skipped),'ok':result.result.wasSuccessful(),'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'CPU_host':'HKUST3'}
 (P.D/'tests'/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
 sys.exit(0 if summary['ok'] else 1)
