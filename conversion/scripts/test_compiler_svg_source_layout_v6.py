"""General anchor grammar and unchanged source corruption controls."""
import copy
import unittest
from unittest.mock import patch
import compiler_svg_source_layout_v6 as module
from test_compiler_svg_source_layout_v1 import SVG,source

class Tests(unittest.TestCase):
    def test_nested_anchors_keep_transform_style_opacity_and_tooltips(self):
        code=SVG.replace(b'<rect x="0" y="0" width="20" height="40"/>',
          b'<a id="anchor1" transform="translate(2,3)" style="fill:#123456;opacity:.5" title="tooltip"><g id="anchor2" transform="scale(1.1)"><rect id="paint1" x="0" y="0" width="20" height="40"/></g></a>')
        self.assertEqual(module.source_admission(source(code),code,(100,50))['source_nodes'],2)
        self.assertIn(b'transform="translate(2,3)"',code);self.assertIn(b'opacity:.5',code)

    def test_edge_paint_inside_anchor_is_counted_once(self):
        code=SVG.replace(b'<path d="M20,20 L70,20"/>',b'<a title="edge tooltip"><path d="M20,20 L70,20"/></a>')
        self.assertEqual(module.source_admission(source(code),code,(100,50))['source_edges'],1)

    def test_href_is_passive_metadata_and_active_schemes_events_rejected(self):
        for href in ('https://example.org/info','http://example.org','#details','relative.html','mailto:user@example.org'):
            code=SVG.replace(b'<text x="4" y="20">A</text>',('<a href="'+href+'"><text x="4" y="20">A</text></a>').encode())
            module.source_admission(source(code),code,(100,50))
        for attribute in ('href="javascript:alert(1)"','href="data:text/html,test"','onclick="run()"','onload="run()"'):
            code=SVG.replace(b'<text x="4" y="20">A</text>',('<a '+attribute+'><text x="4" y="20">A</text></a>').encode())
            with self.assertRaises(ValueError):module.source_admission(source(code),code,(100,50))

    def test_actual_cairo_sfnt_mismatch_is_a_blocker(self):
        capture={'positions':{'t':{'text':'A','actual_fonts':[{'postScriptName':'PS','glyphCount':1}]}},
                 'faces':{'PS':{'face':{'postscript':'PS','table_hashes':{'a':'good'}}}}}
        observation={'faces':{'f':{'file':'unused','sha256':module.sha(b'font'),'collection_index':0,'postscript':'PS'}},
                     'paint':[{'text':'A','face':'f','operation':'show_text'}]}
        with patch('pathlib.Path.read_bytes',return_value=b'font'),patch('native_source_font_profile_v4._sfnt',return_value={'postscript':'PS','table_hashes':{'a':'bad'}}):
            result=module._cairo_font_check(observation,capture)
        self.assertFalse(result['ok']);self.assertEqual(result['failures'][0]['reason'],'source_cairo_browser_actual_physical_font_differs')

    def test_deleted_character_arrow_and_occluding_extra_object_controls(self):
        from test_auto_quality_source_vector_v2 import fixture
        from auto_quality_source_vector_v2 import _graphviz_coverage
        dom,xml,stats=fixture();self.assertTrue(_graphviz_coverage(dom,xml,stats)['ok'])
        changed=[xml.replace('value="B"','value=""'),xml.replace('endArrow=classic','endArrow=none'),
                 xml.replace('</root>','<mxCell id="opaque" vertex="1" parent="1" style="fillColor=#ffffff;"/></root>')]
        for value in changed:self.assertFalse(_graphviz_coverage(dom,value,stats)['ok'])

    def test_cross_renderer_local_diagnostic_requires_complete_source_proof(self):
        with self.assertRaisesRegex(ValueError,'complete_independent_source_proof'):
            module.quality_visual({},'',{},b'',b'',{'ok':False})

    def test_path_build_prepass_is_not_a_second_logical_string(self):
        face={'postscript':'PS','table_hashes':{'a':'same'}}
        capture={'positions':{'t':{'text':'A','actual_fonts':[{'postScriptName':'PS','glyphCount':1}]}},'faces':{'PS':{'face':face}}}
        observation={'faces':{'f':{'file':'unused','sha256':module.sha(b'font'),'collection_index':0,'postscript':'PS'}},
                     'paint':[{'text':'A','face':'f','operation':'text_path'},{'text':'A','face':'f','operation':'show_text'}]}
        with patch('pathlib.Path.read_bytes',return_value=b'font'),patch('native_source_font_profile_v4._sfnt',return_value=face):
            result=module._cairo_font_check(observation,capture)
        self.assertTrue(result['ok']);self.assertEqual(result['nonblank_scalars'],1)

    def test_invalid_nested_a_is_typed_unsupported(self):
        code=SVG.replace(b'<text x="4" y="20">A</text>',b'<a><a><text x="4" y="20">A</text></a></a>')
        with self.assertRaisesRegex(ValueError,'invalid_nested_svg_anchor_rendering_unproven'):
            module.source_admission(source(code),code,(100,50))



class TranslationTests(unittest.TestCase):
    def test_original_leading_trailing_whitespace_survives_html_and_offsets(self):
        import xml.etree.ElementTree as ET
        from auto_quality_source_vector_v2 import _plain
        tree=ET.fromstring('<mxfile><diagram><mxGraphModel><root><mxCell id="t" value=" _output "/></root></mxGraphModel></diagram></mxfile>')
        cell=tree.find('.//mxCell');positions={'t':{'text':' _output '}}
        module._preserve_source_whitespace({'t':cell},positions)
        self.assertEqual(_plain(cell.get('value')),' _output ')
        changed=module._apply_offsets(ET.tostring(tree,encoding='unicode'),positions,{'t':{'applied':True,'dx':.25,'dy':-.5}})
        self.assertEqual(_plain(ET.fromstring(changed).find('.//mxCell').get('value')),' _output ')

    def test_existing_rich_font_runs_cannot_be_silently_flattened(self):
        import xml.etree.ElementTree as ET
        tree=ET.fromstring('<mxfile><diagram><mxGraphModel><root><mxCell id="t" value="&lt;span style=&quot;color:red&quot;&gt;A&lt;/span&gt;"/></root></mxGraphModel></diagram></mxfile>')
        with self.assertRaisesRegex(ValueError,'rich_native_font_runs'):
            module._apply_offsets(ET.tostring(tree,encoding='unicode'),{'t':{'text':'A'}},{'t':{'applied':True,'dx':.2,'dy':0}})

    def test_cairo_logical_paint_mismatch_rejected_before_browser_override(self):
        from unittest.mock import Mock
        page=Mock();page.evaluate.return_value=[{'source_element_index':0,'text':'B'}]
        with self.assertRaisesRegex(ValueError,'logical_paint_inventory_differs'):
            module._bind_actual_cairo_faces(page,{'faces':{},'paint':[{'text':'A','face':'f','operation':'show_text'}]},Mock())

    def test_source_screenshot_fallback_only_for_capture_infrastructure(self):
        from unittest.mock import Mock
        page=Mock();page.screenshot.side_effect=ValueError('source content mismatch')
        with self.assertRaisesRegex(ValueError,'source content mismatch'):module._screenshot(page)
        page.context.new_cdp_session.assert_not_called()



class AlphaTests(unittest.TestCase):
    def test_fully_transparent_svg_stroke_never_becomes_visible_native_outline(self):
        original={'objects':[{'type':'shape','style':{'fill':'rgb(255,255,255)','fillOpacity':1,'stroke':'rgba(0, 0, 0, 0)','strokeOpacity':1,'strokeWidth':1}}]}
        fixed=module._normalize_paint_alpha(original)
        self.assertEqual(fixed['objects'][0]['style']['stroke'],'none')
        self.assertEqual(fixed['objects'][0]['style']['strokeOpacity'],0)
        self.assertEqual(original['objects'][0]['style']['stroke'],'rgba(0, 0, 0, 0)')

    def test_partial_alpha_multiplies_existing_paint_opacity_once(self):
        original={'objects':[{'style':{'fill':'rgba(10, 20, 30, 0.25)','fillOpacity':.4,'stroke':'none','strokeOpacity':1}}]}
        fixed=module._normalize_paint_alpha(original)
        self.assertEqual(fixed['objects'][0]['style']['fill'],'rgb(10,20,30)')
        self.assertAlmostEqual(fixed['objects'][0]['style']['fillOpacity'],.1)
        self.assertEqual(module._normalize_paint_alpha(fixed),fixed)

    def test_transparent_paint_corruption_is_detected_independently_of_emitter(self):
        import xml.etree.ElementTree as ET
        from auto_quality_source_vector_v2 import _paint_coverage
        from svg_convert_v2 import build
        source={'id':'shape','type':'shape','tag':'rect','attrs':{'x':5,'y':7,'width':20,'height':10,'rx':0,'ry':0},'matrix':[1,0,0,1,0,0],'bbox':{'x':5,'y':7,'w':20,'h':10},'style':{'fill':'rgb(255, 255, 255)','stroke':'rgba(0, 0, 0, 0)','strokeWidth':1,'fillOpacity':1,'strokeOpacity':1,'opacity':1,'linecap':'butt','linejoin':'miter','dash':'none'}}
        norm=module._normalize_paint_alpha({'nodes':{},'issues':[],'objects':[source]})
        xml,_=build(norm,100,100)
        self.assertTrue(_paint_coverage(norm,xml)['ok'])
        tree=ET.fromstring(xml);cell=next(c for c in tree.iter('mxCell') if c.get('id')==source['id'])
        style=dict(p.split('=',1) for p in cell.get('style','').split(';') if '=' in p)
        style.update(strokeColor='#000000',strokeOpacity='100');cell.set('style',';'.join(k+'='+v for k,v in style.items())+';')
        check=_paint_coverage(norm,ET.tostring(tree,encoding='unicode'))
        self.assertFalse(check['ok']);self.assertTrue(any(x.get('property')=='strokeColor' for x in check['errors']))

if __name__=='__main__':unittest.main()
