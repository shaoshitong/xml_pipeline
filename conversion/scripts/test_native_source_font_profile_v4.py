"""Isolated font bytes, frozen audit chain and actual-render proof negative cases.

FontBuilder creates tiny true SFNT faces; native PNG/usage are controlled here.
The separate real smoke exercises the actual native browser renderer.
"""
import base64
import copy
import io
import json
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as E
from pathlib import Path
from unittest import mock

from PIL import Image
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

import native_source_font_profile_v4 as v


def font_bytes(bold=True):
    fb=FontBuilder(1000,isTTF=True)
    fb.setupGlyphOrder(['.notdef','A'])
    fb.setupCharacterMap({65:'A'})
    glyphs={name:TTGlyphPen(None).glyph() for name in ['.notdef','A']}
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({name:(600,0) for name in glyphs})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    name='Proof-Bold' if bold else 'Proof-Regular'
    fb.setupNameTable({'familyName':'Proof Font','styleName':'Bold' if bold else 'Regular',
                      'uniqueFontIdentifier':name,'fullName':name,'psName':name,'version':'Version 1.0'})
    fb.font['head'].macStyle=1 if bold else 0
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200,
                usWeightClass=700 if bold else 400,fsSelection=0x20 if bold else 0x40)
    fb.setupPost()
    fb.setupMaxp()
    buffer=io.BytesIO()
    fb.save(buffer)
    return buffer.getvalue()


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='native_font_v4_test_')
        self.root=Path(self.tmp.name).resolve()
        self.build()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self,flags=1,wrapped=False,leading=False):
        self.identifier='a'*64
        style=(';' if leading else '')+'rounded;text;fontSize=12;fontStyle='+str(flags)+';'
        cell='<mxCell id="a" parent="1" vertex="1" value="AAA" style="'+style+'"><mxGeometry x="1" y="1" width="8" height="8" as="geometry"/></mxCell>'
        if wrapped:cell='<UserObject id="a" label="AAA">'+cell.replace('id="a" ','').replace('value="AAA" ','')+'</UserObject>'
        self.source='<mxGraphModel pageWidth="16" pageHeight="16"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'+cell+'</root></mxGraphModel>'
        self.before=v._normalize(self.source)[0]
        input_hash=v.sha(self.before.encode())
        self.clean=self.root/'clean/case';self.clean.mkdir(parents=True,exist_ok=True)
        self.folder=self.root/'conversion/auto_quality_font_repair_v1'/self.identifier/input_hash
        self.folder.mkdir(parents=True,exist_ok=True)
        self.archive=self.root/'conversion/harness_sessions'/('auto_font_'+self.identifier+'_'+input_hash)/'baseline'
        self.archive.mkdir(parents=True,exist_ok=True)
        self.png=io.BytesIO();image=Image.new('RGBA',(16,16),'white');image.putpixel((1,1),(0,0,0,255));image.save(self.png,format='PNG');self.png=self.png.getvalue()
        self.font=font_bytes()
        digest=v.sha(self.font)
        family='NativeFace_'+digest[:20]
        self.font_file=self.root/'clean/font_assets'/(digest+'.ttf');self.font_file.parent.mkdir(parents=True,exist_ok=True);self.font_file.write_bytes(self.font)
        self.uri='data:font/ttf;base64,'+base64.b64encode(self.font).decode()
        outer,model=v._models(self.before)
        c=v._cells(outer)['a']
        c.set('style',(';' if leading else '')+'rounded;text;fontSize=12;fontFamily='+family+';fontStyle='+str(flags&~1)+';fontSource='+urllib.parse.quote(self.uri,safe='')+';')
        model.set('extFonts',family+'^'+self.uri)
        self.xml=E.tostring(outer,encoding='unicode')
        self.actual={'familyName':'Proof Font','postScriptName':'Proof-Bold','isCustomFont':False,'glyphCount':3}
        self.observations=[{'cell':'a','label':'AAA','style':{'fontFamily':'Proof Font','fontStyle':flags},'actual_fonts':[self.actual]}]
        self.details={'changes':[{'cell':'a','before_family':'Proof Font','before_flags':flags,'after_flags':flags&~1,
                                  'family':family,'actual_font':self.actual}], 'issues':[],'text_cells_observed':1,'font_files':1}
        identity={'id':self.identifier,'source_pair_sha256':self.identifier,'source_code_sha256':v.sha(self.source.encode()),'source_image_sha256':v.sha(self.png)}
        self.previous={**identity,'code_sha256':input_hash,'image_sha256':v.sha(self.png)}
        self.proof={'ok':True,'accepted':False,'input_code_sha256':input_hash,'output_code_sha256':v.sha(self.xml.encode()),
                    'input_image_sha256':v.sha(self.png),'output_image_sha256':v.sha(self.png),
                    'native_pixels_unchanged':True,'physical_faces_and_glyph_counts_preserved':True,'all_actual_fonts_custom':True,
                    'text_cells':1,'audit':str((self.folder/'report.json').relative_to(self.root))}
        self.record={**identity,'source_format':'drawio','source_record':{'code_sha256':identity['source_code_sha256'],'image_sha256':identity['source_image_sha256']},
                     'code_file':'clean/case/current.drawio','image_file':'clean/case/current.png','code_sha256':v.sha(self.xml.encode()),'image_sha256':v.sha(self.png),
                     'original_reference':'clean/case/reference.png','original_source_code':'clean/case/source.drawio',
                     'native_font_validation':self.proof,'previous_candidate_archive':str(self.archive.relative_to(self.root)),
                     'native_embedded_fonts':[{'family':family,'sha256':digest,'original_sha256':digest,'file':str(self.font_file.relative_to(self.root)),
                       'original_file':str(self.font_file.relative_to(self.root)),'collection_index':0,'physical_postscript_name':'Proof-Bold','physical_bold':True,'physical_italic':False}]}
        for folder in [self.folder,self.archive]:
            (folder/('before.drawio' if folder==self.folder else 'diagram.drawio')).write_text(self.before)
            (folder/('before_record.json' if folder==self.folder else 'conversion.json')).write_text(json.dumps(self.previous))
        (self.archive/'image.png').write_bytes(self.png)
        (self.clean/'source.drawio').write_text(self.source)
        (self.clean/'reference.png').write_bytes(self.png)
        self.write_candidate()
        self.baseline_info={'actual_platform_font_usage':[{'cell':'a','fonts':[self.actual]}]}
        self.current_info={'actual_platform_font_usage':[{'cell':'a','fonts':[{**self.actual,'isCustomFont':True}]}]}
        for relative in ['conversion/rendering_paintbounds_strict/remote_render.py','evaluation/assets/drawio-runtime-v32.6.1/manifest.json']:
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture pin')

    def write_candidate(self):
        self.record['code_sha256']=v.sha(self.xml.encode())
        self.proof['output_code_sha256']=self.record['code_sha256']
        (self.clean/'current.drawio').write_text(self.xml)
        (self.clean/'current.png').write_bytes(self.png)
        (self.folder/'candidate.drawio').write_text(self.xml)
        (self.folder/'candidate.png').write_bytes(self.png)
        (self.folder/'candidate_record.json').write_text(json.dumps(self.record))
        (self.folder/'font_details.json').write_text(json.dumps(self.details))
        (self.folder/'observations.json').write_text(json.dumps(self.observations))
        (self.folder/'report.json').write_text(json.dumps(self.proof))

    def check(self,baseline=None,current=None,native_info=None):
        renders=[baseline or {'ok':True,'png':self.png,'native_render':self.baseline_info},
                 current or {'ok':True,'png':self.png,'native_render':self.current_info}]
        with mock.patch.object(v,'_render',side_effect=renders) as render:
            result=v.check_native_profile(self.record,self.xml,self.source,native_info,root=self.root)
            self.render_count=render.call_count
        return result

    def assert_bad(self,word=None,**kwargs):
        result=self.check(**kwargs)
        self.assertFalse(result['ok'],result)
        if word:self.assertIn(word,result['failures'][0]['error'])
        return result

    def mutate_xml(self,fn):
        root,model=v._models(self.xml)
        fn(root,model,v._cells(root))
        self.xml=E.tostring(root,encoding='unicode')
        self.write_candidate()

    def test_valid_bold_absorption_requires_independent_live_pair_and_remains_unaccepted(self):
        result=self.check()
        self.assertTrue(result['ok'],result)
        self.assertFalse(result['accepted'])
        self.assertEqual(self.render_count,2)
        evidence=result['evidence']
        self.assertTrue(evidence['fresh_before_after_and_all_frozen_png_pixels_identical'])
        self.assertTrue((self.root/evidence['audit']).exists())

    def test_userobject_cell_identity_supported(self):
        self.build(wrapped=True)
        self.assertTrue(self.check()['ok'])

    def test_underline_nonbold_flags_must_survive(self):
        self.build(flags=5)
        self.assertTrue(self.check()['ok'])
        self.details['changes'][0]['after_flags']=0
        self.mutate_xml(lambda r,m,c:c['a'].set('style',c['a'].get('style').replace('fontStyle=4','fontStyle=0')))
        self.assert_bad('flags_not_absorbed')

    def test_source_bytes_changed_refused(self):
        self.source=self.source.replace('AAA','AAB')
        self.assert_bad('source_or_current_xml_hash')

    def test_normalized_original_must_equal_owned_before_xml_exactly(self):
        (self.folder/'before.drawio').write_text(self.before.replace('x="1"','x="2"'))
        self.assert_bad('exact_normalized_original')

    def test_geometry_text_parent_and_terminal_changes_not_hidden_by_matching_new_hash(self):
        original=self.xml
        for mutate in [lambda c:c.find('mxGeometry').set('x','2'),lambda c:c.set('value','AAB'),lambda c:c.set('parent','0'),lambda c:c.set('source','unknown')]:
            self.xml=original
            self.mutate_xml(lambda r,m,c:mutate(c['a']))
            self.assert_bad('nonfont_graph_text_geometry')

    def test_bare_named_style_order_and_leading_reset_not_sorted_away(self):
        self.mutate_xml(lambda r,m,c:c['a'].set('style',c['a'].get('style').replace('rounded;text','text;rounded')))
        self.assert_bad('nonfont_graph_text_geometry')
        self.build(leading=True)
        self.assertTrue(self.check()['ok'])
        self.mutate_xml(lambda r,m,c:c['a'].set('style',c['a'].get('style').lstrip(';')))
        self.assert_bad('nonfont_graph_text_geometry')

    def test_bare_named_token_resembling_font_property_is_not_ignored(self):
        before=self.before.replace('rounded;text','rounded;fontFamily;text')
        self.assertNotEqual(v.canonical_font_only(before,{'a'}),v.canonical_font_only(self.xml,{'a'}))

    def test_wrong_actual_face_and_glyph_counts_or_custom_status_refused(self):
        for change in [{'postScriptName':'Proof-Regular'},{'glyphCount':2},{'isCustomFont':False}]:
            info=copy.deepcopy(self.current_info)
            info['actual_platform_font_usage'][0]['fonts'][0].update(change)
            self.assert_bad(current={'ok':True,'png':self.png,'native_render':info})

    def test_old_bool_true_cannot_hide_changed_native_pixel(self):
        buffer=io.BytesIO();image=Image.open(io.BytesIO(self.png)).convert('RGBA');image.putpixel((2,2),(0,0,0,255));image.save(buffer,format='PNG')
        self.assert_bad('native_pixels_changed',current={'ok':True,'png':buffer.getvalue(),'native_render':self.current_info})

    def test_wrong_bold_physical_font_bytes_cannot_be_relabelled_by_metadata(self):
        regular=font_bytes(False)
        self.font_file.write_bytes(regular)
        self.assert_bad('resource_hash_changed')

    def test_wrong_regular_face_with_all_new_hashes_consistent_still_cannot_absorb_bold(self):
        regular=font_bytes(False);digest=v.sha(regular);family='NativeFace_'+digest[:20]
        path=self.root/'clean/font_assets'/(digest+'.ttf');path.write_bytes(regular)
        old_family=self.record['native_embedded_fonts'][0]['family']
        uri='data:font/ttf;base64,'+base64.b64encode(regular).decode()
        self.record['native_embedded_fonts']=[{'family':family,'sha256':digest,'original_sha256':digest,
          'file':str(path.relative_to(self.root)),'original_file':str(path.relative_to(self.root)),
          'collection_index':0,'physical_postscript_name':'Proof-Regular','physical_bold':False,'physical_italic':False}]
        self.details['changes'][0]['family']=family
        outer,model=v._models(self.xml);cell=v._cells(outer)['a']
        cell.set('style',cell.get('style').replace(old_family,family).replace(urllib.parse.quote(self.uri,safe=''),urllib.parse.quote(uri,safe='')))
        model.set('extFonts',family+'^'+uri);self.xml=E.tostring(outer,encoding='unicode');self.write_candidate()
        self.assert_bad('flags_not_absorbed_by_verified_physical_face')

    def test_asset_flags_are_recomputed_from_sfnt_not_trusted(self):
        self.record['native_embedded_fonts'][0]['physical_bold']=False
        self.write_candidate()
        self.assert_bad('physical_flags_or_ps_name_forged')

    def test_after_flag_cannot_change_unjustified_italic_or_other_bit(self):
        for flags in [2,4,8]:
            self.details['changes'][0]['after_flags']=flags
            self.mutate_xml(lambda r,m,c:c['a'].set('style',c['a'].get('style').replace('fontStyle='+str(v.style_values(c['a']).get('fontStyle')),'fontStyle='+str(flags))))
            self.assert_bad('flags_not_absorbed')

    def test_owned_report_details_observations_and_archive_identity_checked(self):
        for filename,mutate in [('report.json',lambda x:x.update(accepted=True)),('font_details.json',lambda x:x['changes'][0].update(before_flags=0)),('observations.json',lambda x:x[0]['actual_fonts'][0].update(glyphCount=2))]:
            path=self.folder/filename
            old=path.read_bytes();data=json.loads(old);mutate(data);path.write_text(json.dumps(data));self.assert_bad();path.write_bytes(old)
        raw=(self.archive/'conversion.json').read_bytes();bad=json.loads(raw);bad['id']='b'*64;(self.archive/'conversion.json').write_text(json.dumps(bad));self.assert_bad('baseline_archive_changed');(self.archive/'conversion.json').write_bytes(raw)

    def test_outside_audit_and_clean_paths_refused(self):
        self.proof['audit']='conversion/unowned/report.json'
        self.assert_bad('unowned_audit')
        self.build()
        self.record['native_embedded_fonts'][0]['file']='conversion/unowned.ttf'
        self.write_candidate()
        self.assert_bad('resource_outside_clean')

    def test_fontsource_data_must_match_verified_ext_face(self):
        wrong='data:font/ttf;base64,'+base64.b64encode(font_bytes(False)).decode()
        self.mutate_xml(lambda r,m,c:c['a'].set('style',c['a'].get('style').replace(urllib.parse.quote(self.uri,safe=''),urllib.parse.quote(wrong,safe=''))))
        self.assert_bad('cell_font_bytes_differ')

    def test_extra_unverified_font_payload_refused(self):
        self.mutate_xml(lambda r,m,c:m.set('extFonts',m.get('extFonts')+'|Unverified^'+self.uri))
        self.assert_bad('added_face_has_no_clean_asset')

    def test_caller_native_info_is_cross_checked_not_trusted(self):
        wrong=copy.deepcopy(self.current_info)
        wrong['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='Wrong-PS'
        self.assert_bad('caller_fresh_physical',native_info=wrong)
        self.assertEqual(self.render_count,2)

    def test_renderer_or_evidence_change_during_native_render_invalidates_proof(self):
        def render(*args):
            (self.folder/'observations.json').write_text('[]')
            return {'ok':True,'png':self.png,'native_render':self.baseline_info if args[0]==self.before else self.current_info}
        with mock.patch.object(v,'_render',side_effect=render):
            result=v.check_native_profile(self.record,self.xml,self.source,root=self.root)
        self.assertFalse(result['ok'])
        self.assertIn('evidence_changed_during',result['failures'][0]['error'])


if __name__=='__main__':
    unittest.main()
