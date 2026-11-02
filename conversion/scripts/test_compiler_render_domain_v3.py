import copy
import unittest
from unittest.mock import patch
import compiler_render_domain_v3 as module

class RenderDomainTests(unittest.TestCase):
    def source(self):
        return {'t': {'text':'12', 'actual_fonts':[{'postScriptName':'PS','glyphCount':2,'isCustomFont':True}],
                      'chars':[{'text':'1','x':1.25,'y':2.375,'width':5.,'height':10.},
                               {'text':'2','x':6.25,'y':2.375,'width':5.,'height':10.}]}}
    def info(self):
        return {'actual_text_positions':[{'cell':'t','runs':[{'chars':copy.deepcopy(self.source()['t']['chars'])}]}],
                'actual_platform_font_usage':[{'cell':'t','fonts':copy.deepcopy(self.source()['t']['actual_fonts'])}]}
    def test_exact_complete_source_glyphs(self):
        result=module.glyph_check(self.source(),self.info());self.assertTrue(result['ok']);self.assertEqual(result['source_graphemes'],2)
    def test_equal_width_different_character_rejected(self):
        info=self.info();info['actual_text_positions'][0]['runs'][0]['chars'][1]['text']='3'
        result=module.glyph_check(self.source(),info);self.assertFalse(result['ok']);self.assertEqual(result['failures'][0]['reason'],'fresh_native_graphemes_changed')
    def test_deleted_digit_rejected(self):
        info=self.info();info['actual_text_positions'][0]['runs'][0]['chars'].pop()
        self.assertFalse(module.glyph_check(self.source(),info)['ok'])
    def test_duplicate_observation_rejected(self):
        info=self.info();info['actual_text_positions']*=2
        with self.assertRaisesRegex(ValueError,'duplicate_native_text'):module.glyph_check(self.source(),info)
    def test_duplicate_cell_id_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate_or_missing_native_cell_id'):
            module._xml_cells('<mxGraphModel><root><mxCell id="t"/><mxCell id="t"/></root></mxGraphModel>')
    def test_missing_and_extra_native_text_rejected(self):
        info=self.info();info['actual_text_positions'][0]['cell']='other'
        self.assertFalse(module.glyph_check(self.source(),info)['ok'])
    def test_no_source_text_never_passes(self):
        with self.assertRaisesRegex(ValueError,'empty_fresh_source'):module.glyph_check({},self.info())
    def test_missing_observer_is_infrastructure(self):
        with self.assertRaisesRegex(RuntimeError,'infrastructure_'):module.glyph_check(self.source(),{})
    def test_noncustom_font_rejected(self):
        info=self.info();info['actual_platform_font_usage'][0]['fonts'][0]['isCustomFont']=False
        self.assertFalse(module.glyph_check(self.source(),info)['ok'])
    def test_wrong_actual_font_rejected(self):
        info=self.info();info['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='Other'
        self.assertFalse(module.glyph_check(self.source(),info)['ok'])
    def test_subpixel_position_threshold_preserved(self):
        info=self.info();info['actual_text_positions'][0]['runs'][0]['chars'][0]['x']+=.031
        self.assertFalse(module.glyph_check(self.source(),info)['ok'])
    def test_only_verified_registration_offset_can_explain_translation(self):
        info=self.info()
        for c in info['actual_text_positions'][0]['runs'][0]['chars']:c['x']+=8;c['y']+=8
        self.assertFalse(module.glyph_check(self.source(),info)['ok'])
        self.assertTrue(module.glyph_check(self.source(),info,(8,8))['ok'])
    def test_injected_registration_flag_is_stripped(self):
        xml='<mxGraphModel pageWidth="10" pageHeight="20"><root><mxCell id="0"/></root></mxGraphModel>'
        record={'_verified_reference_registration':{'original_page_offset':[8,8]}}
        def no_contract(current,reference,xml):
            self.assertFalse(any(key.startswith('_verified_') for key in current));return current,None
        with patch('compiler_quality_v2.registration_record',side_effect=no_contract):
            _,contract,offset=module._registration(record,xml,b'ref',(10,20),(10,20))
        self.assertIsNone(contract);self.assertEqual(offset,[0,0])
    def test_duplicate_style_keys_rejected(self):
        import xml.etree.ElementTree as ET
        with self.assertRaisesRegex(ValueError,'duplicate_native_style'):
            module._style(ET.fromstring('<mxCell style="opacity=100;opacity=0;"/>'))
    def marker_fixture(self, size='9', arrow='blockThin'):
        style={'fill':'none','stroke':'#000000','strokeWidth':1,'fillOpacity':1,'strokeOpacity':1,'opacity':1,'dash':'none'}
        dom={'objects':[{'id':'p','type':'shape','tag':'path','edge':{'id':'edge'},'matrix':[1,0,0,1,0,0],'sampledPoints':[[0,0],[10,0]],'style':style},
                        {'id':'a','type':'shape','tag':'polygon','edge':{'id':'edge'},'matrix':[1,0,0,1,0,0],'pointsAttr':'20,0 10,-3.333333 10,3.333333','style':{**style,'fill':'#000000'}}]}
        xml='<mxGraphModel><root><mxCell id="p" edge="1" style="endArrow='+arrow+';endSize='+size+';endFill=1;"/></root></mxGraphModel>'
        return dom,xml
    def test_independent_marker_mapping_without_candidate_stats(self):
        dom,xml=self.marker_fixture();result=module.marker_check(dom,xml)
        self.assertTrue(result['ok']);self.assertEqual(result['native_graphviz_arrowheads'][0]['source_arrow_object'],'a')
    def test_non_none_zero_size_marker_rejected(self):
        dom,xml=self.marker_fixture('0');result=module.marker_check(dom,xml)
        self.assertFalse(result['ok']);self.assertIn('size',result['failures'][0]['reason'])
    def test_wrong_native_marker_shape_rejected(self):
        dom,xml=self.marker_fixture(arrow='open');self.assertFalse(module.marker_check(dom,xml)['ok'])
    def test_source_primitive_scope_includes_thin_shapes(self):
        dom={'objects':[{'id':'line','type':'shape','bbox':{'x':1,'y':2,'w':10,'h':0},'style':{'strokeWidth':1}}]}
        rows=module._primitive_positions(dom,(8,9));self.assertEqual(len(rows),1)
        char=rows[0]['runs'][0]['chars'][0];self.assertGreater(char['height'],0);self.assertEqual(char['x'],8.5)
    def test_reference_alias_only_comes_from_independent_contract(self):
        raw={'native_canvas_contract':{'offset':[99,99]},'native_page_padding':{'offset':[88,88]},'_verified_reference_registration':{'original_page_offset':[77,77]}}
        self.assertEqual(module._reference_visual_record(raw,None),{})
        proven={'original_page_offset':[2,3],'output_page':[100,200]}
        self.assertEqual(module._reference_visual_record(raw,proven)['native_canvas_contract']['offset'],[2,3])
    def test_mismatched_native_fontsource_rejected(self):
        import base64
        uri='data:font/ttf;base64,'+base64.b64encode(b'good').decode()
        bad='data:font/ttf;base64,'+base64.b64encode(b'bad').decode()
        xml='<mxGraphModel extFonts="Face^'+uri+'"><root><mxCell id="t" style="fontFamily=Face;fontSource='+bad.replace(';','%3B')+';"/></root></mxGraphModel>'
        record={'native_embedded_fonts':[{'family':'Face','file':'font','sha256':'hash','original_file':'font','original_sha256':'hash'}]}
        with patch.object(module,'_read',return_value=b'good'),patch('native_source_font_profile_v4._sfnt',return_value={'postscript':'PS'}):
            result=module.physical_font_check(record,xml,self.source(),{'PS':{'face':{'postscript':'PS'},'original_sha256':'hash'}},self.info())
        self.assertFalse(result['ok']);self.assertEqual(result['failures'][0]['reason'],'native_font_source_bytes_disagree_with_ext_font')
    def test_cross_domain_failure_is_only_local_text(self):
        self.assertEqual(module.CROSS_DOMAIN_DIAGNOSTIC_ONLY,'local_text_line_ssim_below_0.55')
        self.assertEqual(module.POSITION_TOLERANCE_PX,.03)

if __name__=='__main__':unittest.main()
