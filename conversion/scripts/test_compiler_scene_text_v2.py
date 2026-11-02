import copy
import unittest
import xml.etree.ElementTree as ET
import json
from unittest.mock import patch
import compiler_scene_text_v2 as module
from compiler_scene_text_v2 import offsets, apply_offsets, _plain, _fingerprint, sha, raw


class FractionalAnchorTests(unittest.TestCase):
    def source(self):
        return {'t':{'text':'AB','actual_fonts':[{'postScriptName':'FontPS','glyphCount':2}],
                     'chars':[{'text':'A','x':1.25,'y':2.375,'width':5,'height':10}, {'text':'B','x':6.25,'y':2.375,'width':6,'height':10}]}}

    def info(self):
        return {'actual_platform_font_usage':[{'cell':'t','fonts':[{'postScriptName':'FontPS','glyphCount':2,'isCustomFont':True}]}],
                'actual_text_positions':[{'cell':'t','runs':[{'chars':[{'text':'A','x':1,'y':2,'width':5,'height':10}, {'text':'B','x':6,'y':2,'width':6,'height':10}]}]}]}

    def xml(self):
        return '<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="t" parent="1" vertex="1" value="AB" style="shape=text;fontSize=10;fontFamily=Face;"><mxGeometry x="1" y="2" width="11" height="10" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'

    def test_exact_fractional_translation(self):
        correction=offsets(self.source(),self.info())['t']
        self.assertEqual((correction['dx'],correction['dy']),(.25,.375))
        self.assertTrue(correction['applied'])

    def test_width_or_shaping_loss_rejected(self):
        native=self.info();native['actual_text_positions'][0]['runs'][0]['chars'][1]['width']+=.1
        with self.assertRaisesRegex(ValueError,'shaping'):offsets(self.source(),native)

    def test_nonuniform_advance_not_translated_away(self):
        native=self.info();native['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.2
        with self.assertRaisesRegex(ValueError,'spacing'):offsets(self.source(),native)

    def test_physical_font_difference_rejected(self):
        native=self.info();native['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='Other'
        with self.assertRaisesRegex(ValueError,'font_mismatch'):offsets(self.source(),native)

    def test_unembedded_font_rejected(self):
        native=self.info();native['actual_platform_font_usage'][0]['fonts'][0]['isCustomFont']=False
        with self.assertRaisesRegex(ValueError,'embedded'):offsets(self.source(),native)

    def test_large_shift_rejected(self):
        native=self.info()
        for char in native['actual_text_positions'][0]['runs'][0]['chars']:char['x']-=4
        with self.assertRaisesRegex(ValueError,'supported_rounding'):offsets(self.source(),native)

    def test_text_geometry_topology_styles_preserved(self):
        before=self.xml();correction=offsets(self.source(),self.info());after=apply_offsets(before,self.source(),correction)
        a=ET.fromstring(before);b=ET.fromstring(after)
        cells_a={c.get('id'):c for c in a.iter('mxCell')};cells_b={c.get('id'):c for c in b.iter('mxCell')}
        self.assertEqual(set(cells_a),set(cells_b))
        for identifier in cells_a:
            old,new=cells_a[identifier],cells_b[identifier]
            self.assertEqual(old.get('style'),new.get('style'));self.assertEqual(old.get('parent'),new.get('parent'))
            self.assertEqual(ET.tostring(old.find('mxGeometry')) if old.find('mxGeometry') is not None else None,ET.tostring(new.find('mxGeometry')) if new.find('mxGeometry') is not None else None)
            self.assertEqual(_plain(old.get('value')),_plain(new.get('value')))

    def test_no_source_or_observation_mutation(self):
        source,native=self.source(),self.info();expected=(copy.deepcopy(source),copy.deepcopy(native))
        offsets(source,native)
        self.assertEqual((source,native),expected)

    def test_foreign_rich_font_semantics_not_removed(self):
        xml=self.xml().replace('value="AB"','value="&lt;span style=&quot;font-family:Other&quot;&gt;AB&lt;/span&gt;"')
        with self.assertRaisesRegex(ValueError,'rich_native_font'):apply_offsets(xml,self.source(),offsets(self.source(),self.info()))

    def test_missing_fresh_native_observer_is_infrastructure(self):
        import sys,types
        fake=types.SimpleNamespace(native=types.SimpleNamespace(native_job=lambda *a,**k:{'ok':True,'png':b'png','native_render':{}}))
        with patch.dict(sys.modules,{'native_worker':fake}):
            with self.assertRaisesRegex(RuntimeError,'infrastructure_native_text_observer_missing'):
                module._render_observed(self.xml(),100,100)

    def setup_fixture(self):
        source=self.source();before=self.xml();corrections=offsets(source,self.info());after=apply_offsets(before,source,corrections)
        baseline={'id':'unit','source_pair_sha256':'unit','source_code_sha256':'sourcecode','source_image_sha256':'sourceimage','source_render_svg_sha256':'svg','code_file':'before.drawio','code_sha256':sha(before.encode()),'image_file':'before.png','image_sha256':sha(b'png')}
        blobs={'source.json':raw(source),'before.drawio':before.encode(),'before.png':b'png','before_record.json':raw(baseline)}
        def asset(name):return {'file':name,'sha256':sha(blobs[name])}
        proof={key:baseline[key] for key in ('id','source_code_sha256','source_image_sha256','source_render_svg_sha256')}
        proof.update(baseline_record=asset('before_record.json'),baseline_xml=asset('before.drawio'),source_positions=asset('source.json'),offsets=corrections,output_code_sha256=sha(after.encode()))
        blobs['proof.json']=raw(proof);record={**baseline,'code_file':'after.drawio','code_sha256':sha(after.encode()),'compiler_scene_text_v2':{'policy':module.POLICY,'proof_file':'proof.json','proof_sha256':sha(blobs['proof.json'])}}
        def read(name,digest=None,*a,**k):
            result=blobs[name]
            if digest is not None and digest!=sha(result):raise ValueError('fixture_digest_mismatch')
            return result
        return source,before,after,record,blobs,read

    def test_before_text_record_bound_for_registration_composition(self):
        source,before,after,record,blobs,read=self.setup_fixture()
        with patch.object(module,'_read',side_effect=read):result=module.validate_registration_setup(record,after)
        self.assertTrue(result['ok']);self.assertEqual(result['baseline_xml'],before)
        self.assertFalse(result['evidence']['same_native_pixels_claimed'])

    def test_current_geometry_change_requires_verified_registration(self):
        source,before,after,record,blobs,read=self.setup_fixture()
        changed=after.replace('x="1"','x="2"');record['code_sha256']=sha(changed.encode())
        with patch.object(module,'_read',side_effect=read):result=module.validate_registration_setup(record,changed)
        self.assertFalse(result['ok'])

    def test_fresh_render_wrong_glyph_position_rejected(self):
        source,before,after,record,blobs,read=self.setup_fixture();info=self.info()
        for observed,wanted in zip(info['actual_text_positions'][0]['runs'][0]['chars'],source['t']['chars']):observed.update(wanted)
        info['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.1
        paint={'ok':True,'errors':[],'source_layout_translation':{'dx':0,'dy':0}}
        with patch.object(module,'_read',side_effect=read),patch.object(module,'source_positions',return_value=(source,{})),patch('auto_quality_source_vector_v2._paint_coverage',return_value=paint):
            result=module.validate_text_render(record,after,info)
        self.assertFalse(result['ok']);self.assertTrue(any(row['reason']=='fresh_native_source_grapheme_position_changed' for row in result['failures']))


if __name__=='__main__':unittest.main()
