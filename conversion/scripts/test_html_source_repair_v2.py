import hashlib
import html
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
from PIL import Image
import auto_quality_source_vector_v2 as q
import html_source_repair_v2 as repair
from html_range_extractor_v2 import source_js
sha=lambda b:hashlib.sha256(b).hexdigest()

class RepairTests(unittest.TestCase):
    def _fixture(self,directory):
        root=Path(directory);(root/'clean').mkdir();code=b'<html>synthetic wrapped word fixture</html>';(root/'clean/source.html').write_bytes(code);out=io.BytesIO();Image.new('RGB',(100,100),'white').save(out,format='PNG');reference=out.getvalue();(root/'clean/ref.png').write_bytes(reference)
        xml='<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" parent="1" vertex="1" value="Title" style="shape=text;fontSize=18;fontColor=#000000;opacity=100;fontFamily=EmbeddedArial;html=1;"><mxGeometry x="0" y="0" width="30" height="15"/></mxCell></root></mxGraphModel></diagram></mxfile>'
        common={'type':'text','fontFamilyRaw':'Arial','bold':False,'italic':False,'underline':False,'fontSize':18,'color':{'color':'#000000','opacity':1},'opacity':1,'qaOwner':0,'qaOwnerTag':'DIV'}
        objects=[{**common,'id':1,'text':'Title','x':0,'y':0,'w':30,'h':15,'qaPaintEvent':1},
                 {**common,'id':2,'text':'Test','x':0,'y':20,'w':30,'h':15,'qaPaintEvent':2,'qaTextStart':0,'qaWrappedFragment':True,'qaWordText':'Testlong','qaWordStart':0,'qaFragmentIndex':0},
                 {**common,'id':3,'text':'long','x':0,'y':40,'w':30,'h':15,'qaPaintEvent':2,'qaTextStart':4,'qaWrappedFragment':True,'qaWordText':'Testlong','qaWordStart':0,'qaFragmentIndex':1}]
        dom={'objects':objects,'unsupported':[],'_source_paint_order':{'1':0,'2':0,'3':0},'qaWrappedWords':[{'source_word':'Testlong','all_logical_characters_preserved':True}]}
        record={'id':'fixture','source_format':'html','category':'poster','code_sha256':sha(xml.encode()),'original_source_code':'clean/source.html','source_code_sha256':sha(code),'original_reference':'clean/ref.png','source_image_sha256':sha(reference)}
        return root,record,xml,dom
    def test_adds_only_verified_wrapped_fragments(self):
        with tempfile.TemporaryDirectory() as directory:
            root,record,xml,dom=self._fixture(directory)
            with patch.object(q,'R',root),patch.object(q,'_capture',return_value=(dom,{})):
                proposed,proof=repair.propose(record,xml,root/'scratch')
            self.assertEqual(len(proof['new_editable_text_fragments']),2)
            self.assertTrue(proof['source_coverage']['ok'])
            self.assertTrue(proof['all_existing_object_payloads_unchanged'])
            cells={c.get('id'):c for c in E.fromstring(proposed).iter('mxCell')}
            self.assertEqual(cells['3'].get('value'),'Test');self.assertEqual(cells['4'].get('value'),'long')
    def test_missing_nonwrapped_objects_cannot_be_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            root,record,xml,dom=self._fixture(directory);dom['objects'][1]['qaWrappedFragment']=False
            with patch.object(q,'R',root),patch.object(q,'_capture',return_value=(dom,{})):
                with self.assertRaises(AssertionError):repair.propose(record,xml,root/'scratch')
    def test_new_words_need_style_matched_embedded_font(self):
        with tempfile.TemporaryDirectory() as directory:
            root,record,xml,dom=self._fixture(directory);dom['objects'][1]['fontFamilyRaw']='Different source face'
            with patch.object(q,'R',root),patch.object(q,'_capture',return_value=(dom,{})):
                with self.assertRaises(AssertionError):repair.propose(record,xml,root/'scratch')
    def test_unsupported_source_clip_stays_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root,record,xml,dom=self._fixture(directory);dom['objects'][1]['sourceClip']={'unmodeled':[{'transform':'matrix(...)'}]}
            with patch.object(q,'R',root),patch.object(q,'_capture',return_value=(dom,{})):
                with self.assertRaises(AssertionError):repair.propose(record,xml,root/'scratch')

@unittest.skipUnless(os.environ.get('IMG2CODE_BROWSER_TESTS')=='1','Enable only on the remote browser runtime')
class BrowserTests(unittest.TestCase):
    def test_real_grapheme_line_extraction_and_clipping(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=q.CHROME,args=['--disable-dev-shm-usage']);page=browser.new_page(viewport={'width':300,'height':200});page.route('**/*',lambda r:r.abort())
            page.set_content('<style>body{margin:0}.word{width:45px;height:30px;overflow:hidden;word-break:break-all;font:20px Arial}</style><div class="word">ABCDEFGHI</div>')
            dom=page.evaluate(source_js(q.W/'scripts/html_dom_clip.js'))
            self.assertEqual(len(dom['qaWrappedWords']),1)
            proof=dom['qaWrappedWords'][0]
            self.assertTrue(proof['all_logical_characters_preserved']);self.assertFalse(proof['no_visible_source_glyphs'])
            fragments=[o for o in dom['objects'] if o.get('qaWrappedFragment')]
            self.assertTrue(fragments);self.assertTrue(any(o['sourceClip']['partial'] for o in fragments))
            self.assertLess(len(''.join(o['text'] for o in fragments)),len('ABCDEFGHI'))
            self.assertFalse(any(i.get('reason')=='word_spans_multiple_lines' for i in dom['unsupported']))
            page.set_content('<style>.word{width:45px;height:0;overflow:hidden;word-break:break-all;font:20px Arial}</style><div class="word">ABCDEFGHI</div>')
            dom=page.evaluate(source_js(q.W/'scripts/html_dom_clip.js'))
            self.assertFalse([o for o in dom['objects'] if o['type']=='text'])
            browser.close()

if __name__=='__main__':unittest.main()
