#!/usr/bin/env python3
"""Synthetic regression tests, official decoder control and one real renderer control."""
from pathlib import Path
import base64, json, html, os, struct, sys, tempfile, unittest, urllib.parse, zlib
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedded_xml_compiler_v1 as C

MODEL = ('<mxGraphModel dx="100" dy="100" pageWidth="850" pageHeight="1100"><root>'
         '<mxCell id="0"/><mxCell id="1" parent="0"/>'
         '<mxCell id="a" value="A+B" vertex="1" parent="1" style="fillColor=#ffffff;">'
         '<mxGeometry x="10" y="20" width="80" height="30" as="geometry"/></mxCell>'
         '<mxCell id="b" value="B" vertex="1" parent="1"><mxGeometry x="100" y="20" width="80" height="30" as="geometry"/></mxCell>'
         '<mxCell id="e" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell>'
         '</root></mxGraphModel>')
AUTHOR = ('<mxfile scale="1" border="0"><diagram id="p" name="Page-1">' + MODEL + '</diagram></mxfile>').encode()

def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)

def png(text_chunk, after_idat=False):
    head = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(b'\x00\x00\x00\x00\x00'))
    return head + (idat + text_chunk if after_idat else text_chunk + idat) + chunk(b'IEND', b'')

def text_png(text, kind=b'tEXt', after_idat=False):
    if kind == b'tEXt': data = b'mxfile\x00' + text
    elif kind == b'zTXt': data = b'mxfile\x00\x00' + zlib.compress(text)
    else:
        data = b'mxfile\x00\x00\x00en\x00en\x00' + text
    return png(chunk(kind, data), after_idat=after_idat)

def svg_with_content(content):
    root = ET.Element('svg', {'xmlns':'http://www.w3.org/2000/svg', 'content':content})
    return ET.tostring(root, encoding='utf-8')

def with_doctype(blob):
    return b'<?xml version="1.0"?>\n<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n' + blob

def qtwice(text):
    return urllib.parse.quote(urllib.parse.quote(text, safe=''), safe='')

class Extraction(unittest.TestCase):
    def test_png_text_raw(self):
        e = C.decode_png_metadata(text_png(AUTHOR)); self.assertEqual(e['raw'], AUTHOR)
    def test_png_text_uri_twice(self):
        e = C.decode_png_metadata(text_png(qtwice(AUTHOR.decode()).encode())); self.assertEqual(e['raw'], AUTHOR)
    def test_png_ztxt(self):
        clean = AUTHOR.replace(b'A+B', b'AB')
        e = C.decode_png_metadata(text_png(clean, kind=b'zTXt')); self.assertEqual(e['raw'], clean)
    def test_png_ztxt_plus_is_refused_not_silently_changed(self):
        with self.assertRaisesRegex(ValueError, 'plus_to_space'): C.decode_png_metadata(text_png(b'mxfile\x00<mxfile>+</mxfile>', kind=b'zTXt'))
    def test_png_itext_official_unsupported(self):
        with self.assertRaisesRegex(ValueError, 'iTXt'): C.decode_png_metadata(text_png(AUTHOR, kind=b'iTXt'))
    def test_png_after_idat_refused(self):
        with self.assertRaisesRegex(ValueError, 'IDAT'): C.decode_png_metadata(text_png(AUTHOR, after_idat=True))
    def test_png_crc_and_truncation_refused(self):
        b = bytearray(text_png(AUTHOR)); b[30] ^= 1
        with self.assertRaises(ValueError): C.decode_png_metadata(bytes(b))
        with self.assertRaises(ValueError): C.decode_png_metadata(text_png(AUTHOR)[:-5])
    def test_png_unsafe_entity_refused(self):
        bad = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><mxfile>&e;</mxfile>'
        with self.assertRaises(ValueError): C.decode_svg_metadata(bad)

    def test_svg_raw_content(self):
        e = C.decode_svg_metadata(svg_with_content(AUTHOR.decode())); self.assertEqual(e['raw'], AUTHOR)
    def test_svg_uri_content(self):
        e = C.decode_svg_metadata(svg_with_content(urllib.parse.quote(AUTHOR.decode(), safe=''))); self.assertEqual(e['raw'], AUTHOR)
    def test_svg_legacy_base64(self):
        e = C.decode_svg_metadata(svg_with_content(base64.b64encode(AUTHOR).decode())); self.assertEqual(e['raw'], AUTHOR)
    def test_svg_standard_doctype(self):
        e = C.decode_svg_metadata(with_doctype(svg_with_content(AUTHOR.decode()))); self.assertEqual(e['raw'], AUTHOR)
    def test_svg_internal_subset_refused(self):
        bad = (b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
               b'<svg xmlns="http://www.w3.org/2000/svg" content="x">&x;</svg>')
        with self.assertRaises(ValueError): C.decode_svg_metadata(bad)
    def test_svg_missing_content_refused(self):
        with self.assertRaisesRegex(ValueError, 'content'): C.decode_svg_metadata(b'<svg xmlns="http://www.w3.org/2000/svg"/>')

class Graphs(unittest.TestCase):
    def graphs(self, raw): return C.document_graphs(raw)
    def test_viewport_excluded_from_dedup_hash(self):
        _,_,h1,_ = self.graphs(AUTHOR)
        _,_,h2,_ = self.graphs(AUTHOR.replace(b'dx="100"', b'dx="999"'))
        self.assertEqual(h1, h2)
    def test_text_change_changes_dedup_hash(self):
        _,_,h1,_ = self.graphs(AUTHOR)
        _,_,h2,_ = self.graphs(AUTHOR.replace(b'value="B"', b'value="Changed"'))
        self.assertNotEqual(h1, h2)
    def test_paint_order_change_changes_dedup_hash(self):
        root = ET.fromstring(MODEL); cells = root.find('root'); first = cells[2]; cells.remove(first); cells.insert(3, first)
        changed = ET.tostring(root)
        _,_,h1,_ = self.graphs(AUTHOR); _,_,h2,_ = self.graphs(changed)
        self.assertNotEqual(h1, h2)
    def test_wrapper_static_failure(self):
        f = C.import_native_modules()[2](MODEL)
        ms = C.import_native_modules()[0](MODEL.encode())[1]
        q = C.static_diagnostics(MODEL.encode(), f, ms)
        self.assertTrue(q['ok'])
        wrapper = ('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
                   '<mxCell id="i" value="" vertex="1" parent="1" style="shape=image;image=data:image/png;base64,AAAA;"/></root></mxGraphModel>')
        fw = C.import_native_modules()[2](wrapper); mw = C.import_native_modules()[0](wrapper.encode())[1]
        qw = C.static_diagnostics(wrapper.encode(), fw, mw); self.assertFalse(qw['ok'])

class OfficialControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng
        cls.r = OfficialXmlPng()
    @classmethod
    def tearDownClass(cls):
        cls.r.close()
    def test_official_png_decoder_agreement(self):
        raw = text_png(AUTHOR)
        e = C.decode_png_metadata(raw)
        proof = C.official_decode_agreement(self.r, raw, 'PNG_native_XML_marker', e['raw'])
        self.assertTrue(proof['exact_bytes_equal'] or proof['canonical_XML_equal'])
    def test_official_png_uri_twice_agreement(self):
        raw = text_png(qtwice(AUTHOR.decode()).encode())
        e = C.decode_png_metadata(raw)
        proof = C.official_decode_agreement(self.r, raw, 'PNG_native_XML_marker', e['raw'])
        self.assertTrue(proof['exact_bytes_equal'] or proof['canonical_XML_equal'])
    def test_official_svg_raw_uri_base64_agreement(self):
        for blob in (svg_with_content(AUTHOR.decode()), svg_with_content(urllib.parse.quote(AUTHOR.decode(), safe='')), svg_with_content(base64.b64encode(AUTHOR).decode())):
            e = C.decode_svg_metadata(blob)
            proof = C.official_decode_agreement(self.r, blob, 'SVG_native_XML_marker', e['raw'])
            self.assertTrue(proof['exact_bytes_equal'] or proof['canonical_XML_equal'])
    def test_official_marker_unsupported_cases(self):
        got_i = self.r.page.evaluate(C.PNG_DECODE_JS, base64.b64encode(text_png(AUTHOR, kind=b'iTXt')).decode())
        got_a = self.r.page.evaluate(C.PNG_DECODE_JS, base64.b64encode(text_png(AUTHOR, after_idat=True)).decode())
        self.assertIsNone(got_i); self.assertIsNone(got_a)

class RenderControl(unittest.TestCase):
    def test_real_official_edit_render_restore(self):
        from arxiv_math_stable_export_renderer_v1 import MathSynced
        parent = Path(tempfile.mkdtemp(prefix='render_control_', dir=str(C.D)))
        root = parent/'case'
        r = MathSynced()
        try: proof = r.replay(AUTHOR, root)
        finally: r.close()
        self.assertTrue(proof['ok'], json.dumps({k:proof[k] for k in ('normalized_model_exact_restore','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact')}))
        self.assertTrue(proof['restored_actual_RGBA_exact'])
        self.assertTrue(proof['restored_PNG_bytes_exact'])

if __name__ == '__main__':
    C.D.mkdir(parents=True, exist_ok=True)
    result = unittest.main(verbosity=2, exit=False)
    (C.D/'tests').mkdir(parents=True, exist_ok=True)
    summary = {'tests': result.result.testsRun, 'failures': len(result.result.failures), 'errors': len(result.result.errors), 'skipped': len(result.result.skipped), 'ok': result.result.wasSuccessful(), 'at_utc': C.datetime.datetime.now(C.datetime.timezone.utc).isoformat() if hasattr(C,'datetime') else None}
    import datetime
    summary['at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (C.D/'tests'/'results.json').write_text(json.dumps(summary, indent=2)+'\n')
    sys.exit(0 if summary['ok'] else 1)
