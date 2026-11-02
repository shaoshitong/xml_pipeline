import copy
from html.parser import HTMLParser
import json
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import compiler_python_cosyn_frame_v1 as frame


def source_text():
    sx,sy=2560/3600,1217/1712
    return dict(id='v3t0',type='text',tag='text',text='A < B & C',matrix=[sx,0,0,sy,5,7],fontSize=40*sx,
                color='rgb(0, 0, 0)',opacity=1,bbox=dict(x=10,y=20,w=100,h=30),fontFamily='source-face')


def native_xml(obj=None,carrier=None):
    obj=obj or source_text();carrier=carrier or dict(policy='source-frame',mapping=dict(source_canvas=[3600,1712],output_canvas=[2560,1217]))
    root=ET.Element('mxfile');page=ET.SubElement(root,'diagram');model=ET.SubElement(page,'mxGraphModel',pageWidth='2560',pageHeight='1217');cells=ET.SubElement(model,'root')
    ET.SubElement(cells,'mxCell',id='0',**{frame.CARRIER:frame.raw(carrier).decode().strip()});ET.SubElement(cells,'mxCell',id='1',parent='0')
    cell=ET.SubElement(cells,'mxCell',id=obj['id'],parent='1',vertex='1',style='shape=text;fontSize='+format(obj['fontSize'],'.12g')+';fontColor=#000000;fontFamily=source-face;fontStyle=0;opacity=100;html=1;',value=frame.shape_value(obj['id'],frame.text_shape(obj)))
    ET.SubElement(cell,'mxGeometry',x='10',y='20',width='100',height='30',**{'as':'geometry'})
    return ET.tostring(root,encoding='unicode'),carrier


def checked_paint(dom,xml,carrier):
    positions={obj['id']:dict(actual_fonts=[dict(postScriptName='SourcePS',glyphCount=4,isCustomFont=True)])for obj in dom['objects']if obj['type']=='text'}
    faces=dict(SourcePS=dict(family='source-face',face=dict(bold=False,italic=False)))
    return frame.paint_and_shape(dom,xml,carrier,positions,faces)


class IntrinsicShapeTests(unittest.TestCase):
    def test_actual_bold_face_is_not_synthetically_bolded_again(self):
        obj=source_text();obj['bold']=True
        position=dict(actual_fonts=[dict(postScriptName='SourceBold',glyphCount=4,isCustomFont=True)])
        faces=dict(SourceBold=dict(family='source-bold',face=dict(bold=True,italic=False)))
        self.assertEqual(frame.physical_text_style(obj,position,faces),dict(fontFamily='source-bold',fontStyle='0'))

    def test_unproved_synthetic_face_style_stays_pending(self):
        obj=source_text();obj['bold']=True
        position=dict(actual_fonts=[dict(postScriptName='SourcePS',glyphCount=4,isCustomFont=True)])
        faces=dict(SourcePS=dict(family='source-face',face=dict(bold=False,italic=False)))
        with self.assertRaisesRegex(ValueError,'synthetic_SOURCE_font_style_pending'):frame.physical_text_style(obj,position,faces)
    def test_original_font_shape_is_preserved_before_output_frame(self):
        obj=source_text();shape=frame.text_shape(obj)
        self.assertAlmostEqual(shape['source_intrinsic_font_size'],40)
        self.assertAlmostEqual(shape['fontSize'],obj['fontSize'])
        self.assertAlmostEqual(shape['fontSize']*shape['scale_x'],40*2560/3600)
        self.assertAlmostEqual(shape['fontSize']*shape['scale_y'],40*1217/1712)

    def test_integer_thumbnail_axis_rounding_never_collapses_to_uniform_fit(self):
        shape=frame.text_shape(source_text())
        self.assertNotEqual(shape['source_ctm_x'],shape['source_ctm_y']);self.assertNotEqual(shape['scale_x'],shape['scale_y'])
        value=frame.shape_value('v3t0',shape)
        self.assertIn(format(shape['scale_x'],'.12g'),value);self.assertIn(format(shape['scale_y'],'.12g'),value)

    def test_rotation_or_skew_remains_pending_instead_of_losing_frame(self):
        for matrix in ([.7,.1,0,.7,0,0],[.7,0,.1,.7,0,0],[-.7,0,0,.7,0,0]):
            obj=source_text();obj['matrix']=matrix
            with self.assertRaisesRegex(ValueError,'non_axis_aligned'):frame.text_shape(obj)

    def test_source_text_is_escaped_without_losing_characters_or_extra_objects(self):
        class Text(HTMLParser):
            def __init__(self):super().__init__();self.text='';self.tags=[]
            def handle_data(self,value):self.text+=value
            def handle_starttag(self,tag,attrs):self.tags.append(tag)
        parser=Text();parser.feed(frame.shape_value('v3t0',frame.text_shape(source_text())))
        self.assertEqual(parser.text,source_text()['text']);self.assertEqual(parser.tags,['span','span'])

    def test_anchor_adjustment_preserves_all_geometry_style_and_frame_metadata(self):
        xml,_=native_xml();obj=source_text();out=frame.apply_anchors(xml,{obj['id']:frame.text_shape(obj)},{obj['id']:dict(dx=1.25,dy=-.5)})
        before,after=ET.fromstring(xml),ET.fromstring(out)
        for root in (before,after):
            for cell in root.iter('mxCell'):cell.attrib.pop('value',None)
        self.assertEqual(ET.tostring(before),ET.tostring(after));self.assertIn('left:1.25px;top:-0.5px;',out)

    def test_anchor_scope_cannot_silently_drop_a_source_text_object(self):
        xml,_=native_xml();obj=source_text()
        with self.assertRaisesRegex(ValueError,'scope_incomplete'):frame.apply_anchors(xml,{obj['id']:frame.text_shape(obj)},{})


class IndependentShapeContractTests(unittest.TestCase):
    def test_scalar_font_substitution_is_rejected_even_with_same_declared_box(self):
        xml,carrier=native_xml();xml=xml.replace('fontSize='+format(source_text()['fontSize'],'.12g')+';','fontSize=40;')
        with self.assertRaisesRegex(ValueError,'intrinsic_SOURCE_font_size_changed'):checked_paint(dict(objects=[source_text()]),xml,carrier)

    def test_modified_axis_frame_is_rejected_after_XML_has_been_rehashed(self):
        xml,carrier=native_xml();shape=frame.text_shape(source_text());xml=xml.replace('scale(1,'+format(shape['scale_y'],'.12g')+')','scale(1,1)')
        self.assertNotEqual(frame.sha(xml.encode()),frame.sha(native_xml()[0].encode()))
        with self.assertRaisesRegex(ValueError,'glyph_shape_matrix_changed'):checked_paint(dict(objects=[source_text()]),xml,carrier)

    def test_unbounded_anchor_or_extra_CSS_has_no_source_proof(self):
        xml,carrier=native_xml()
        for changed in (xml.replace('left:0px','left:13px'),xml.replace('position:relative;','position:relative;opacity:0;')):
            with self.assertRaisesRegex(ValueError,'anchor_style'):checked_paint(dict(objects=[source_text()]),changed,carrier)

    def test_complete_frame_carrier_cannot_be_replaced_by_a_rehashed_one(self):
        xml,carrier=native_xml();other=copy.deepcopy(carrier);other['mapping']['output_canvas'][0]-=1
        with self.assertRaisesRegex(ValueError,'complete_official_SOURCE_frame_changed'):checked_paint(dict(objects=[source_text()]),xml,other)

    def test_synthetic_font_style_change_is_rejected_even_when_glyph_widths_match(self):
        xml,carrier=native_xml();xml=xml.replace('fontStyle=0;','fontStyle=1;')
        with self.assertRaisesRegex(ValueError,'physical_font_style_changed'):checked_paint(dict(objects=[source_text()]),xml,carrier)

    def test_paint_gate_retains_source_geometry_and_requires_separate_glyph_pixels(self):
        obj=source_text();dom=dict(objects=[obj]);original=copy.deepcopy(dom);xml,carrier=native_xml(obj)
        with patch('auto_quality_source_vector_v2._paint_coverage',return_value=dict(ok=True,errors=[]))as paint:
            result,proof=checked_paint(dom,xml,carrier)
        adjusted=paint.call_args.args[0]
        self.assertEqual(dom,original);self.assertEqual(adjusted['objects'][0]['bbox'],obj['bbox']);self.assertEqual(adjusted['objects'][0]['matrix'],obj['matrix'])
        self.assertEqual(adjusted['objects'][0]['fontSize'],obj['fontSize']);self.assertFalse(proof['glyph_geometry_or_pixel_checks_waived']);self.assertTrue(result['ok'])


class SVGTextAndViewportTests(unittest.TestCase):
    def run_shape(self):
        obj=source_text();position=dict(actual_fonts=[dict(postScriptName='SourcePS',glyphCount=4,isCustomFont=True)],source_element_index=0)
        faces=dict(SourcePS=dict(family='source-face',face=dict(bold=False,italic=False)))
        svg=b'<svg xmlns="http://www.w3.org/2000/svg"><text x="30" y="40" text-anchor="middle" font-size="40">A &lt; B &amp; C</text></svg>'
        return obj,position,faces,svg,frame.vector_text_shape(obj,position,faces,svg)

    def test_each_source_run_keeps_SVG_baseline_anchor_and_physical_font(self):
        obj,pos,faces,svg,shape=self.run_shape();value=frame.shape_value(obj['id'],shape)
        self.assertIn('<svg ',value);self.assertIn('text-anchor="middle"',value);self.assertIn('font-family="source-face"',value)
        self.assertIn('font-size="40"',value);self.assertIn('x="30" y="40"',value)
        self.assertEqual(shape['vector_matrix'][-2:],[5-10,7-20]);self.assertEqual(shape['source_text'],obj['text'])

    def test_child_runs_stay_pending_instead_of_flattening_ligature_context(self):
        obj,pos,faces,svg,shape=self.run_shape()
        with self.assertRaisesRegex(ValueError,'complex_SOURCE'):
            frame.vector_text_shape(obj,pos,faces,svg.replace(b'A &lt; B &amp; C',b'A <tspan>B</tspan>'))

    def test_svg_shape_mutation_is_rejected_independently(self):
        obj,pos,faces,svg,shape=self.run_shape();xml,carrier=native_xml();root=ET.fromstring(xml);cell=list(root.iter('mxCell'))[-1]
        cell.set('value',frame.shape_value(obj['id'],shape).replace('text-anchor="middle"','text-anchor="start"'))
        with self.assertRaisesRegex(ValueError,'glyph_shape_matrix_changed'):
            frame.paint_and_shape(dict(objects=[obj]),ET.tostring(root,encoding='unicode'),carrier,{obj['id']:pos},faces,svg)

    def background(self):
        return dict(id='v1',type='shape',tag='polygon',node=None,edge=None,sourceId='',matrix=[1,0,0,1,0,0],
                    pointsAttr='-1,-1 -1,51 101,51 101,-1 -1,-1',style=dict(stroke='none'),bbox=dict(x=-1,y=-1,w=102,h=52))

    def test_background_clipping_is_exact_source_viewport_intersection(self):
        obj=self.background();dom=dict(objects=[obj]);out,proof=frame.viewport_lowering(dom,(100,50))
        self.assertEqual(out['objects'][0]['bbox'],dict(x=0,y=0,w=100,h=50));self.assertEqual(len(proof),1)
        self.assertEqual(proof[0]['source_bounds'],[-1,-1,101,51]);self.assertEqual(proof[0]['visible_bounds'],[0,0,100,50])
        self.assertEqual(out['objects'][0]['style']['stroke'],'none');self.assertEqual(out['objects'][0]['style']['strokeWidth'],2)
        self.assertEqual(proof[0]['native_upstream_svg_screen_offset'],0)
        self.assertEqual(dom,dict(objects=[self.background()]));self.assertTrue(proof[0]['source_semantic_id_preserved'])

    def test_named_or_stroked_objects_cannot_be_silently_clipped(self):
        for key,value in [('node','n1'),('edge',dict(id='e1')),('sourceId','source-n1')]:
            obj=self.background();obj[key]=value;out,proof=frame.viewport_lowering(dict(objects=[obj]),(100,50));self.assertEqual(out['objects'][0],obj);self.assertEqual(proof,[])
        obj=self.background();obj['style']['stroke']='rgb(0,0,0)';out,proof=frame.viewport_lowering(dict(objects=[obj]),(100,50));self.assertEqual(out['objects'][0],obj);self.assertEqual(proof,[])


if __name__=='__main__':unittest.main()
