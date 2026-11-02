"""Pure admission and independent corruption checks; synthetic SVG only."""
import copy
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
import compiler_svg_source_layout_v1 as module

SVG=b'''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><g class="graph" id="graph1"><g class="edge" id="edge1"><title>A-&gt;B</title><path d="M20,20 L70,20"/><polygon points="70,20 60,17 60,23"/></g><g class="node" id="node1"><title>A</title><rect x="0" y="0" width="20" height="40"/><text x="4" y="20">A</text></g><g class="node" id="node2"><title>B</title><rect x="70" y="0" width="20" height="40"/><text x="74" y="20">B</text></g></g></svg>'''

def source(code=SVG):
    return {'format':'svg','category':'scientific_diagram','render_backend':'cairosvg',
            'image_provenance':'rendered_from_source_svg','pairing':'derived_from_source_svg',
            'source_svg_sha256':module.sha(code),'width':100,'height':50}

class Tests(unittest.TestCase):
    def test_source_only_admission(self):
        result=module.source_admission(source(),SVG,(100,50))
        self.assertEqual(result['source_nodes'],2);self.assertEqual(result['source_edges'],1)
        self.assertFalse(result['relayout'])

    def test_unknown_renderer_or_source_identity_rejected(self):
        for key,value in [('render_backend',None),('render_backend','chromium'),
                          ('image_provenance','dataset_provided_reference_figure'),
                          ('source_svg_sha256','0'*64),('width',101)]:
            with self.subTest(key=key,value=value):
                record=source();record[key]=value
                with self.assertRaises(ValueError):module.source_admission(record,SVG,(100,50))

    def test_unsupported_source_effects_hierarchy_and_ambiguous_terminals(self):
        for change in [b'<filter/>',b'<foreignObject/>',b'<linearGradient/>',b'<use/>',b'<image/>',b'<g class="cluster"/>']:
            code=SVG.replace(b'</svg>',change+b'</svg>')
            with self.subTest(change=change):
                with self.assertRaises(ValueError):module.source_admission(source(code),code,(100,50))
        for code in [SVG.replace(b'A-&gt;B',b'A-&gt;UNKNOWN'),SVG.replace(b'id="node2"',b'id="node1"'),
                     SVG.replace(b'<path d=',b'<path filter="url(#f)" d=')]:
            with self.assertRaises(ValueError):module.source_admission(source(code),code,(100,50))

    def test_source_declared_ports_resolve_uniquely(self):
        code=SVG.replace(b'A-&gt;B',b'A:port:e-&gt;B:w')
        self.assertEqual(module.source_admission(source(code),code,(100,50))['source_edges'],1)

    def test_deleted_character_arrow_and_occluding_extra_object_are_rejected(self):
        from test_auto_quality_source_vector_v2 import fixture
        from auto_quality_source_vector_v2 import _graphviz_coverage
        dom,xml,stats=fixture()
        self.assertTrue(_graphviz_coverage(dom,xml,stats)['ok'])
        variants={'deleted_grapheme':xml.replace('value="B"','value=""'),
                  'removed_arrow':xml.replace('endArrow=classic','endArrow=none'),
                  'opaque_text_cover':xml.replace('</root>','<mxCell id="cover" parent="1" vertex="1" style="fillColor=#ffffff;strokeColor=none;"><mxGeometry x="0" y="0" width="100" height="40" as="geometry"/></mxCell></root>')}
        for name,value in variants.items():
            with self.subTest(name=name):self.assertFalse(_graphviz_coverage(dom,value,stats)['ok'])

    def test_existing_candidate_cannot_authorize_its_own_source_proof(self):
        with patch.object(module,'prepare_source',side_effect=ValueError('authoritative_source_rejected')):
            xml='<mxGraphModel/>';record={'code_sha256':module.sha(xml.encode()),'compiler_svg_source_layout_v1':{'trusted':True}}
            result=module.validate_source(record,xml,native_render={})
            self.assertFalse(result['ok']);self.assertEqual(result['failures'][0]['reason'],'authoritative_source_rejected')

if __name__=='__main__':unittest.main()
