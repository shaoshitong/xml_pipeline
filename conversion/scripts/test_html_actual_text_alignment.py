import copy
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from importlib.util import find_spec
import unittest
import xml.etree.ElementTree as E
import html_actual_text_alignment as align


def fixture(native_y=16):
    source=[{'text':'A','raw':'A','x':10,'y':12,'width':5,'height':10,'rectCount':1},{'text':'B','raw':'B','x':15,'y':12,'width':5,'height':10,'rectCount':1}]
    obj={'id':1,'type':'text','text':'AB','x':10,'y':10,'w':20,'h':12,'fontSize':10,'color':{'color':'#000000','opacity':1},'opacity':1,'actualSourceGlyphs':source,'actualSourceCss':{'fontSize':10},'actualSourcePhysicalFonts':{'fonts':[{'postScriptName':'FixtureFace','glyphCount':2}],'basis':'actual_text_node'}}
    dom={'objects':[obj],'_source_paint_order':{'1':0}}
    native={'actual_text_positions':[{'cell':'2','runs':[{'font':'10px Embedded','chars':[{'text':'A','x':10,'y':native_y,'width':5,'height':10},{'text':'B','x':15,'y':native_y,'width':5,'height':10}]}]}],'actual_platform_font_usage':[{'cell':'2','fonts':[{'postScriptName':'FixtureFace','glyphCount':2,'isCustomFont':True}]}]}
    xml='<mxfile><mxCell id="2" parent="1" vertex="1" value="AB" style="shape=text;fontSize=10;fontColor=#000000;opacity=100;"><mxGeometry x="10" y="10" width="20" height="12"/></mxCell></mxfile>'
    return dom,native,xml


class Tests(unittest.TestCase):
    def test_uniform_same_face_and_size_translation(self):
        dom,native,xml=fixture();report=align.analyze(dom,native,xml)
        row=report['objects'][0];self.assertTrue(row['safe_translation']);self.assertEqual(row['translation'],{'dx':0,'dy':-4})
        new,proof=align.translate(xml,report);cell=E.fromstring(new).find('mxCell');self.assertEqual(float(cell.find('mxGeometry').get('y')),6)
        self.assertEqual(cell.get('value'),'AB');self.assertTrue(proof['all_other_shapes_assets_text_styles_clips_preserved'])
    def test_analytic_integer_and_fractional_delta_needs_no_render_search(self):
        dom,native,xml=fixture(native_y=16.25);report=align.analyze(dom,native,xml)
        new,proof=align.translate(xml,report);change=proof['changes'][0]
        self.assertEqual(change['geometry_delta'],{'dx':0,'dy':-4})
        self.assertEqual(change['analytic_fractional_glyph_offset'],{'dx':0,'dy':-.25})
        cell=E.fromstring(new).find('mxCell');self.assertEqual(float(cell.find('mxGeometry').get('y')),6)
        self.assertEqual(align._plain(cell.get('value')),'AB')
        self.assertIn('top:-0.25px',cell.get('value'))
    def test_different_face_or_css_size_is_not_translated(self):
        dom,native,xml=fixture();native['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='Wrong'
        self.assertEqual(align.analyze(dom,native,xml)['objects'][0]['category'],'physical_face_mismatch')
        dom,native,xml=fixture();native['actual_text_positions'][0]['runs'][0]['font']='11px Embedded'
        self.assertEqual(align.analyze(dom,native,xml)['objects'][0]['category'],'font_size_mismatch')
    def test_nonuniform_character_residual_is_not_a_baseline_shift(self):
        dom,native,xml=fixture();native['actual_text_positions'][0]['runs'][0]['chars'][1]['x']=17
        row=align.analyze(dom,native,xml)['objects'][0];self.assertFalse(row['safe_translation']);self.assertEqual(row['category'],'nonuniform_spacing_or_position_residual')
    def test_primary_font_metrics_difference_is_not_hidden_by_geometry_shift(self):
        dom,native,xml=fixture();native['actual_text_positions'][0]['runs'][0]['chars'][1]['height']=12
        row=align.analyze(dom,native,xml)['objects'][0];self.assertFalse(row['safe_translation']);self.assertEqual(row['category'],'same_face_font_size_but_range_metrics_differ')
    def test_clipped_text_is_not_moved_with_a_stale_global_clip(self):
        dom,native,xml=fixture();dom['objects'][0]['sourceClip']={'partial':True}
        row=align.analyze(dom,native,xml)['objects'][0];self.assertFalse(row['safe_translation']);self.assertEqual(row['category'],'uniform_translation_requires_fixed_clip')
    def test_range_eligibility_has_no_source_reference_score_precondition(self):
        dom,native,xml=fixture();report=align.analyze(dom,native,xml)
        self.assertTrue(report['objects'][0]['safe_translation'])
        proposed,proof=align.translate(xml,report)
        self.assertEqual(len(proof['changes']),1)
        restored=align.revert_cells(xml,proposed,{'2'})
        self.assertEqual(E.canonicalize(restored),E.canonicalize(xml))
    def test_v3_requires_actual_glyphs_instead_of_relaxing_nominal_boxes(self):
        dom,native,xml=fixture();report=align.analyze(dom,native,xml);new,proof=align.translate(xml,report)
        self.assertFalse(align.check_source_profile_v3({'source_code_sha256':'source'},new,native,dom,{},changed_cells={'2'})['ok'])
        native['actual_text_positions'][0]['runs'][0]['chars'][0]['y']=12;native['actual_text_positions'][0]['runs'][0]['chars'][1]['y']=12
        result=align.check_source_profile_v3({'source_code_sha256':'source'},new,native,dom,{},changed_cells={'2'})
        self.assertTrue(result['ok']);self.assertTrue(result['evidence']['source_coverage']['nominal_text_box_differences_proven_by_actual_glyphs'])
        native['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.2
        self.assertFalse(align.check_source_profile_v3({'source_code_sha256':'source'},new,native,dom,{},changed_cells={'2'})['ok'])
    def test_unmodified_text_keeps_existing_v2_geometry_gate(self):
        dom,native,xml=fixture();native['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='DifferentExistingFace'
        result=align.check_source_profile_v3({'source_code_sha256':'source'},xml,native,dom,{},changed_cells=set())
        self.assertTrue(result['ok'])
        self.assertTrue(result['evidence']['unchanged_text_uses_v2_source_geometry_gate'])
        self.assertEqual(result['evidence']['actual_glyphs_verified_cells'],[])
        shifted=xml.replace('y="10"','y="20"')
        self.assertFalse(align.check_source_profile_v3({'source_code_sha256':'source'},shifted,native,dom,{},changed_cells=set())['ok'])
    def test_wrong_logical_text_never_maps_by_similarity(self):
        dom,native,xml=fixture();native['actual_text_positions'][0]['runs'][0]['chars'][1]['text']='C'
        row=align.analyze(dom,native,xml)['objects'][0];self.assertFalse(row['safe_translation']);self.assertEqual(row['category'],'source_native_grapheme_sequence_mismatch')
    def test_renderer_rounding_bridge_uses_only_bounded_uniform_range_remainder(self):
        dom,native,xml=fixture(native_y=12.25);report=align.analyze(dom,native,xml)
        new,proof=align.bridge_renderer_rounding(xml,report,{'2'})
        self.assertEqual(len(proof['changes']),1);self.assertEqual(proof['changes'][0]['dy'],-.25)
        cell=E.fromstring(new).find('mxCell');self.assertEqual(align._plain(cell.get('value')),'AB')
        self.assertEqual(cell.find('mxGeometry').get('y'),'10')
        dom,native,xml=fixture(native_y=14);report=align.analyze(dom,native,xml)
        with self.assertRaises(AssertionError):align.bridge_renderer_rounding(xml,report,{'2'})
    def test_v3_still_rejects_unsupported_source_content(self):
        dom,native,xml=fixture(native_y=12);dom['unsupported']=[{'reason':'pseudo_content'}]
        self.assertFalse(align.check_source_profile_v3({'source_code_sha256':'source'},xml,native,dom,{})['ok'])
    def test_explicit_page_registration_is_separate_from_text_translation(self):
        self.assertEqual(align.registration({'native_canvas_contract':{'offset':[3,4]}},[100,100],[106,108]),(3,4))
        with self.assertRaises(ValueError):align.registration({},[100,100],[106,108])


@unittest.skipUnless(find_spec('skimage') is not None,'Available in the remote analysis runtime')
class SameCropTests(unittest.TestCase):
    def png(self,shift=0,blank=False):
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(32,24),'white')
        if not blank:ImageDraw.Draw(image).rectangle((10+shift,5,14+shift,17),fill='black')
        output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()
    def test_same_crop_accepts_improvement_and_rejects_worsening(self):
        reference=self.png();windows={'2':[8,3,20,20]}
        good=align.same_crop_metrics(reference,self.png(shift=2),reference,{},(0,0),windows)['2']
        self.assertTrue(good['nonworsening']);self.assertGreater(good['delta'],0);self.assertFalse(good['position_parameters_selected_by_metric'])
        bad=align.same_crop_metrics(reference,reference,self.png(blank=True),{},(0,0),windows)['2']
        self.assertFalse(bad['nonworsening']);self.assertEqual(bad['box'],windows['2'])
    def test_fixed_window_covers_both_actual_glyph_locations(self):
        _,before,_=fixture(native_y=16);_,after,_=fixture(native_y=12)
        windows=align.reference_windows(before,after,{'2'},[32,32])
        self.assertEqual(windows['2'],[8,10,22,28])


@unittest.skipUnless(os.environ.get('IMG2CODE_ALIGNMENT_BROWSER_TESTS')=='1','Only run source browser probes on HKUST3')
class SourceBrowserTests(unittest.TestCase):
    def test_actual_unicode_ranges_and_physical_source_fonts(self):
        from PIL import Image
        import auto_quality_source_vector_v2 as source_profile
        output=io.BytesIO();Image.new('RGB',(300,100),'white').save(output,format='PNG');reference=output.getvalue()
        code='<html><meta charset="utf-8"><body style="font:20px Arial;margin:0">AB😀CD</body></html>'.encode()
        record={'original_source_code':'clean/synthetic.html','source_code_sha256':align.sha(code),'original_reference':'clean/synthetic.png','source_image_sha256':align.sha(reference)}
        blobs={'clean/synthetic.html':code,'clean/synthetic.png':reference}
        def synthetic(relative,digest):
            self.assertEqual(align.sha(blobs[relative]),digest);return blobs[relative]
        (align.W/'prototype').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='glyph-unittest-',dir=align.W/'prototype') as directory,patch.object(source_profile,'_read_clean',side_effect=synthetic):
            dom,served,png,metadata=align.capture_source(record,Path(directory))
        text=next(obj for obj in dom['objects'] if obj['type']=='text')
        self.assertEqual([char['text'] for char in text['actualSourceGlyphs']],['A','B','😀','C','D'])
        self.assertEqual([(char['start'],char['end']) for char in text['actualSourceGlyphs']],[(0,1),(1,2),(2,4),(4,5),(5,6)])
        self.assertTrue(any(font['glyphCount'] for font in text['actualSourcePhysicalFonts']['fonts']))
        self.assertFalse(metadata['source_range_errors'])

if __name__=='__main__':unittest.main()
