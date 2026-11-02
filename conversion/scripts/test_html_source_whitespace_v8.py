"""Real-browser CSS whitespace/UTF16 observations and strict label grammar."""
import html,json,unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
import html_source_whitespace_capture_v8 as capture
from compiler_html_source_quality_ro_v8 import LabelGrammar
class LiteralGrammarTests(unittest.TestCase):
 def test_exact_pre_only_style_allowed(self):LabelGrammar(convert_charrefs=True).feed('<span data-img2code-source-whitespace="v8" style="white-space:pre;">A   B&nbsp;C</span>')
 def test_word_spacing_patch_disallowed(self):
  with self.assertRaisesRegex(ValueError,'unproved_label_style'):LabelGrammar().feed('<span style="word-spacing:2px;">A B</span>')
 def test_other_whitespace_style_disallowed(self):
  with self.assertRaisesRegex(ValueError,'unproved_literal_whitespace'):LabelGrammar().feed('<span style="white-space:normal;">A B</span>')
 def test_absolute_overlay_disallowed(self):
  with self.assertRaisesRegex(ValueError,'unproved_label_positioning'):LabelGrammar().feed('<span style="position:absolute;">A B</span>')
class BrowserWhitespaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=capture.CHROME,args=['--disable-dev-shm-usage'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def observe(self,text,mode='pre-wrap',width=400,break_words=False):
  page=self.browser.new_page(viewport={'width':640,'height':480});page.set_content('<style>html,body{margin:0;background:white}#x{font:16px Arial;width:'+str(width)+'px;white-space:'+mode+(';overflow-wrap:anywhere'if break_words else'')+'}</style><div id="x">'+html.escape(text)+'</div>');page.evaluate('document.fonts.ready');before=capture.screenshot(page);dom=page.evaluate(capture.source_js());observation=page.evaluate(capture.SOURCE_GLYPHS,dom);after=capture.screenshot(page);page.close();self.assertEqual(before,after);self.assertEqual(observation['errors'],[]);self.assertTrue(all(x['rawUnicodeRoundtrip']for x in dom['qaWhitespaceIR']));return observation['dom']
 def texts(self,dom):return [o['text']for o in dom['objects']if o['type']=='text']
 def test_pre_wrap_preserves_every_space_and_NBSP(self):self.assertEqual(self.texts(self.observe('A   B\u00a0C')),['A   B\u00a0C'])
 def test_normal_collapses_only_CSS_ASCII_whitespace(self):self.assertEqual(self.texts(self.observe('A \t \n B\u00a0C','normal')),['A B\u00a0C'])
 def test_NBSP_does_not_collapse_with_normal(self):self.assertEqual(self.texts(self.observe('A\u00a0\u00a0B','normal')),['A\u00a0\u00a0B'])
 def test_normal_trims_zero_advance_line_edges(self):self.assertEqual(self.texts(self.observe('  A  B   ','normal')),['A B'])
 def test_pre_literal_TAB_is_not_replaced_by_space(self):self.assertEqual(self.texts(self.observe('A\tB','pre')),['A\tB'])
 def test_pre_hard_break_is_explicit_IR_and_line_UTF16_ranges(self):
  d=self.observe('A\n  B','pre');self.assertEqual(self.texts(d),['A','  B']);self.assertEqual(d['qaWhitespaceIR'][0]['hardBreaks'][0]['raw'],'\n');self.assertEqual([(x['qaTextStart'],x['qaTextEnd'])for x in d['objects']if x['type']=='text'],[(0,1),(2,5)])
 def test_pre_line_collapses_spaces_but_preserves_hard_break(self):self.assertEqual(self.texts(self.observe('A   B\n C   D','pre-line')),['A B','C D'])
 def test_surrogate_and_combining_grapheme_keep_UTF16_offsets(self):
  d=self.observe('A😀  e\u0301');o=next(o for o in d['objects']if o['type']=='text');chars=o['actualSourceGlyphs'];self.assertEqual([(g['text'],g['start'],g['end'])for g in chars],[('A',0,1),('😀',1,3),(' ',3,4),(' ',4,5),('e\u0301',5,7)])
 def test_wrapped_word_characters_are_never_dropped(self):
  text='abcdefghijklmnop';d=self.observe(text,'pre-wrap',20,True);self.assertGreater(len(self.texts(d)),1);self.assertEqual(''.join(self.texts(d)),text);self.assertTrue(d['qaWrappedWords'][0]['all_logical_characters_preserved'])
 def test_break_spaces_retains_multiple_spaces(self):self.assertEqual(self.texts(self.observe('A   B','break-spaces')),['A   B'])
if __name__=='__main__':unittest.main()
