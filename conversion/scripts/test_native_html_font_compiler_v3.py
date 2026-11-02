"""Pure proposal tests: no Fontconfig, browser, font files or sample I/O."""
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E

import native_html_font_compiler_v3 as compiler


def face(ps, count=1, custom=False):
    return {'postScriptName':ps,'familyName':ps,'glyphCount':count,'isCustomFont':custom}


def row(cell, fonts, family='Arial', flags=0, label='<div>A∈𝒥</div>'):
    return {'cell':cell,'style':{'fontFamily':family,'fontStyle':flags},'actual_fonts':fonts,'label':label}


def source_xml(rows, wrappers=False):
    root=E.Element('mxfile');cells=E.SubElement(E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel'),'root')
    for r in rows:
        parent=E.SubElement(cells,'object',id=r['cell']) if wrappers else cells
        attrs={'value':r['label'],'vertex':'1','style':'namedText;fontFamily='+r['style']['fontFamily']+';fontStyle='+str(r['style']['fontStyle'])+';fontSize=20;'}
        if not wrappers:attrs['id']=r['cell']
        E.SubElement(parent,'mxCell',**attrs)
    return E.tostring(root,encoding='unicode')


def output_cell(xml, identifier):
    root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p}
    return next(c for c in root.iter('mxCell') if (c.get('id') or parents[c].get('id'))==identifier)


def style(cell):
    return dict(item.split('=',1) for item in cell.get('style','').split(';') if '=' in item)


class FontconfigOrderTests(unittest.TestCase):
    def setUp(self):compiler.fallback_order.cache_clear()
    def tearDown(self):compiler.fallback_order.cache_clear()

    def test_css_family_quotes_flags_and_argument_vector(self):
        with patch.object(compiler.subprocess,'check_output',return_value='Arial-BoldItalicMT\nDejaVuSans\n') as call:
            self.assertEqual(compiler.fallback_order('"Arial", sans-serif',3),('Arial-BoldItalicMT','DejaVuSans'))
        self.assertEqual(call.call_args.args[0],['fc-match','-s','--format=%{postscriptname}\n','Arial,sans-serif:weight=200:slant=100'])
        self.assertTrue(call.call_args.kwargs['text'])

    def test_postscript_aliases_are_split_deduplicated_and_stable(self):
        with patch.object(compiler.subprocess,'check_output',return_value='ArialMT,ArialAlias\n\nArialMT\nMathPS\n'):
            self.assertEqual(compiler.fallback_order('Arial',0),('ArialMT','ArialAlias','MathPS'))

    def test_non_bold_italic_flags_do_not_change_fontconfig_weight(self):
        with patch.object(compiler.subprocess,'check_output',return_value='ArialMT\n') as call:
            compiler.fallback_order('Arial',4)
        self.assertEqual(call.call_args.args[0][-1],'Arial:weight=80:slant=0')

    def test_unsupported_family_pattern_is_rejected_before_process(self):
        with patch.object(compiler.subprocess,'check_output') as call:
            for family in ['Arial:style=Bold','Arial;rm -rf /','Arial\nOther','$(font)']:
                with self.subTest(family=family), self.assertRaisesRegex(ValueError,'family_grammar'):
                    compiler.fallback_order(family,0)
        call.assert_not_called()

    def test_no_fontconfig_faces_returns_empty_proposal_rank(self):
        with patch.object(compiler.subprocess,'check_output',return_value=''):
            self.assertEqual(compiler.fallback_order('',0),())


class FontEmbeddingProposalTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.font_style={'ArialMT':(False,False),'Arial-BoldMT':(True,False),'MathPS':(False,False),'SansPS':(False,False)}

    def fake_original_embed(self,xml,observations,directory):
        self.calls.append(copy.deepcopy(observations));fonts={};changes=[];issues=[]
        for r in observations:
            observed=r['actual_fonts'][0];ps=observed['postScriptName']
            if observed.get('isCustomFont'):
                issues.append({'cell':r['cell'],'reason':'existing_custom_font_requires_original_asset_lookup'});continue
            family='Native_'+ps;bold,italic=self.font_style[ps];flags=int(r['style']['fontStyle'])
            fonts[family]={'family':family,'physical_bold':bold,'physical_italic':italic,'physical_postscript_name':ps,'original_file':'/unused/'+ps+'.ttf','collection_index':0}
            changes.append({'cell':r['cell'],'family':family,'after_flags':flags & ~(1 if bold else 0) & ~(2 if italic else 0)})
        return xml,fonts,{'changes':changes,'issues':issues}

    def embed(self,rows,order=('ArialMT','SansPS','MathPS'),wrappers=False):
        xml=source_xml(rows,wrappers)
        portable=types.ModuleType('portable_native_fonts');portable.embed=self.fake_original_embed
        pdf=types.ModuleType('pdf_to_native');pdf.attach_fonts=lambda xml,fonts:xml
        class MockFont:
            def __init__(self,*args,**kwargs):pass
            def getBestCmap(self):return {ord(c):c for c in 'A∈𝒥'}
            def close(self):pass
        ttlib=types.ModuleType('fontTools.ttLib');ttlib.TTFont=MockFont
        with patch.dict(sys.modules,{'portable_native_fonts':portable,'pdf_to_native':pdf,'fontTools.ttLib':ttlib}), patch.object(compiler,'fallback_order',return_value=order):
            return xml,compiler.embed(xml,rows,Path('/unused/pure-test-fonts'))

    def test_fallback_stack_uses_fontconfig_order_without_changing_markup(self):
        rows=[row('a',[face('MathPS'),face('ArialMT'),face('SansPS')])]
        before,(after,_,details)=self.embed(rows)
        self.assertEqual(style(output_cell(after,'a'))['fontFamily'],'Native_ArialMT,Native_SansPS,Native_MathPS')
        self.assertEqual(output_cell(before,'a').get('value'),output_cell(after,'a').get('value'))
        self.assertEqual(details['issues'],[])

    def test_same_graph_observed_primary_supplies_fallback_only_strut(self):
        rows=[row('base',[face('ArialMT')]),row('symbol',[face('MathPS')],label='<div>𝒥</div>')]
        _,(after,fonts,details)=self.embed(rows)
        change=next(c for c in details['changes'] if c['cell']=='symbol')
        self.assertEqual(style(output_cell(after,'symbol'))['fontFamily'],'Native_ArialMT,Native_MathPS')
        self.assertEqual(change['primary_strut'],{'postscript':'ArialMT','family':'Native_ArialMT','basis':'same_original_graph_observed_requested_primary_face'})
        self.assertEqual(change['actual_fonts'],rows[1]['actual_fonts'])
        self.assertEqual(set(fonts),{'Native_ArialMT','Native_MathPS'})

    def test_unobserved_primary_is_never_embedded_or_inserted(self):
        _,(after,fonts,details)=self.embed([row('symbol',[face('MathPS')])])
        self.assertEqual(style(output_cell(after,'symbol'))['fontFamily'],'Native_MathPS')
        self.assertNotIn('Native_ArialMT',fonts)
        self.assertIsNone(details['changes'][0]['primary_strut'])

    def test_observed_primary_with_different_original_style_flags_is_not_reused(self):
        rows=[row('bold',[face('Arial-BoldMT')],flags=1),row('symbol',[face('MathPS')],flags=0)]
        _,(after,_,details)=self.embed(rows)
        self.assertEqual(style(output_cell(after,'symbol'))['fontFamily'],'Native_MathPS')
        self.assertIsNone(next(c for c in details['changes'] if c['cell']=='symbol')['primary_strut'])

    def test_primary_physical_style_mismatch_cannot_change_fallback_cell_style(self):
        self.font_style['ArialMT']=(True,False)
        rows=[row('base',[face('ArialMT')]),row('symbol',[face('MathPS')])]
        _,(after,_,details)=self.embed(rows)
        self.assertEqual(style(output_cell(after,'symbol'))['fontFamily'],'Native_MathPS')
        self.assertIsNone(next(c for c in details['changes'] if c['cell']=='symbol')['primary_strut'])

    def test_mixed_physical_bold_regular_is_a_typed_issue(self):
        rows=[row('mixed',[face('Arial-BoldMT'),face('MathPS')])]
        before,(after,_,details)=self.embed(rows,order=('Arial-BoldMT','MathPS'))
        self.assertEqual(output_cell(before,'mixed').get('style'),output_cell(after,'mixed').get('style'))
        self.assertEqual(details['issues'],[{'cell':'mixed','reason':'inline_mixed_physical_styles_require_per_run_embedding'}])

    def test_zero_glyph_faces_are_ignored_and_cannot_supply_primary(self):
        rows=[row('symbol',[face('ArialMT',count=0),face('MathPS')])]
        _,(after,fonts,details)=self.embed(rows)
        self.assertEqual(style(output_cell(after,'symbol'))['fontFamily'],'Native_MathPS')
        self.assertEqual(set(fonts),{'Native_MathPS'})
        self.assertIsNone(details['changes'][0]['primary_strut'])

    def test_same_physical_face_and_flags_is_probed_once_across_graph(self):
        self.embed([row('a',[face('ArialMT')]),row('b',[face('ArialMT')])])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(len(self.calls[0]),1)
        self.assertEqual(self.calls[0][0]['label'],'physical-face-probe')

    def test_wrapper_owned_cell_id_is_supported(self):
        _,(after,_,details)=self.embed([row('wrapped',[face('ArialMT')])],wrappers=True)
        self.assertEqual(style(output_cell(after,'wrapped'))['fontFamily'],'Native_ArialMT')
        self.assertEqual(details['changes'][0]['cell'],'wrapped')

    def test_missing_fontconfig_rank_keeps_actual_observation_order(self):
        _,(after,_,details)=self.embed([row('a',[face('MathPS'),face('SansPS')])],order=())
        self.assertEqual(style(output_cell(after,'a'))['fontFamily'],'Native_MathPS,Native_SansPS')
        self.assertIsNone(details['changes'][0]['primary_strut'])

    def test_existing_custom_face_refusal_is_not_silently_accepted(self):
        rows=[row('custom',[face('ArialMT',custom=True)])]
        before,(after,_,details)=self.embed(rows)
        self.assertEqual(output_cell(before,'custom').get('style'),output_cell(after,'custom').get('style'))
        self.assertEqual(details['changes'],[])
        self.assertEqual(details['issues'][0]['reason'],'existing_custom_font_requires_original_asset_lookup')


if __name__=='__main__':unittest.main()
