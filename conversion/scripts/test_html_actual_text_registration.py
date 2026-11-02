"""Isolated immutable lineage, graph damage and origin-chain tests; no jobs DB."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from importlib.util import find_spec
from unittest.mock import patch
import xml.etree.ElementTree as E
import html_actual_text_alignment as glyph
import html_actual_text_registration as registration
from test_html_actual_text_alignment import fixture

@unittest.skipUnless(find_spec('skimage') is not None,'Run with the remote verification runtime')
class LineageTests(unittest.TestCase):
    def setup_case(self,root,contract=None):
        from PIL import Image
        dom,before,xml=fixture();root=Path(root);work=root/registration.OWNER/'fixture';work.mkdir(parents=True)
        xml=xml.replace('<mxfile>','<mxfile><diagram><mxGraphModel pageWidth="32" pageHeight="32"><root><mxCell id="0"/><mxCell id="1" parent="0"/>').replace('</mxfile>','</root></mxGraphModel></diagram></mxfile>')
        image=io.BytesIO();Image.new('RGB',(32,32),'white').save(image,format='PNG');png=image.getvalue();code=b'<html>AB</html>'
        clean=root/'clean';clean.mkdir();(clean/'source.html').write_bytes(code);(clean/'reference.png').write_bytes(png)
        old={'id':'fixture','source_format':'html','category':'poster','source_code_sha256':glyph.sha(code),'source_image_sha256':glyph.sha(png),'original_source_code':'clean/source.html','original_reference':'clean/reference.png','code_sha256':glyph.sha(xml.encode()),'image_sha256':glyph.sha(png)}
        analysis=glyph.analyze(dom,before,xml);new,_=glyph.translate(xml,analysis);after=copy.deepcopy(before)
        for char in after['actual_text_positions'][0]['runs'][0]['chars']:char['y']=12
        blobs={'previous_record':json.dumps(old).encode(),'before_xml':xml.encode(),'before_png':png,'baseline_fresh_png':png,'current_xml':new.encode(),'current_png':png,'source_dom':json.dumps(dom).encode(),'baseline_render':json.dumps(before).encode(),'first_xml':new.encode(),'first_render':json.dumps(after).encode(),'current_render':json.dumps(after).encode()}
        files={}
        for name,blob in blobs.items():
            p=work/name;p.write_bytes(blob);files[name]={'file':str(p.relative_to(root)),'sha256':glyph.sha(blob)}
        windows=glyph.reference_windows(before,after,{'2'},[32,32]);local=glyph.same_crop_metrics(png,png,png,old,(0,0),windows)
        proof={'version':3,'policy':'fixture-policy','id':'fixture','accepted':False,'input_code_sha256':old['code_sha256'],'input_image_sha256':old['image_sha256'],'output_code_sha256':glyph.sha(new.encode()),'output_image_sha256':glyph.sha(png),'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'files':files,'source_dom_offset':[0,0],'reference_offset':[0,0],'source_viewport':[32,32],'changed_cells':['2'],'reference_windows':windows,'local_reference_validation':local}
        p=work/'proof.json';p.write_text(json.dumps(proof));link={key:proof[key] for key in ('version','policy','input_code_sha256','input_image_sha256','output_code_sha256','output_image_sha256','source_code_sha256','source_image_sha256','changed_cells')};link.update(proof=str(p.relative_to(root)),proof_sha256=glyph.sha(p.read_bytes()),previous_record=files['previous_record']['file'],previous_record_sha256=files['previous_record']['sha256'])
        current={**old,'code_sha256':glyph.sha(new.encode()),'image_sha256':glyph.sha(png),registration.FIELD:link}
        return current,png,new,proof,p,blobs
    def resolver(self,record,reference,xml,root):return record,None
    def write_proof(self,record,proof,path):path.write_text(json.dumps(proof));record[registration.FIELD]['proof_sha256']=glyph.sha(path.read_bytes())
    def test_identity_registration_accepts_only_reconstructed_text_delta(self):
        with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
            record,ref,xml,*_=self.setup_case(root);verified,contract=registration.registration_record(record,ref,xml,root)
            self.assertIsNone(contract);self.assertTrue(verified['_verified_glyph_alignment']['allowed_range_delta_verified']);self.assertTrue(verified['_verified_glyph_alignment']['original_reference_crop_nonworsening_recomputed'])
    def test_valid_canvas_and_optional_font_origin_is_delegated_and_retained(self):
        with tempfile.TemporaryDirectory() as root:
            record,ref,xml,*_=self.setup_case(root);calls=[]
            def resolver(old,reference,before,where):calls.append(old);return old,{'reference_page':[32,32],'output_page':[32,32],'original_page_offset':[0,0],'font_only_delta_verified':True}
            with patch.object(registration,'_base_registration',side_effect=resolver):verified,contract=registration.registration_record(record,ref,xml,root)
            self.assertEqual(len(calls),1);self.assertTrue(contract['font_only_delta_verified']);self.assertTrue(contract['glyph_alignment_delta_verified']);self.assertEqual(contract['current_code_sha256'],record['code_sha256'])
    def test_all_graph_mutations_are_rejected_even_with_updated_payload_hashes(self):
        for mutation in [lambda x:x.replace('width="20"','width="21"'),lambda x:x.replace('fontSize=10','fontSize=11'),lambda x:x.replace('value="AB"','value="AC"'),lambda x:x.replace('parent="1" vertex','parent="0" vertex'),lambda x:x.replace('pageWidth="32"','pageWidth="33"'),lambda x:x.replace('opacity=100','opacity=50'),lambda x:x.replace('shape=text','shape=image')]:
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,ref,xml,proof,path,_=self.setup_case(root);bad=mutation(xml);self.assertNotEqual(bad,xml)
                outpath=Path(root)/proof['files']['current_xml']['file'];outpath.write_text(bad);digest=glyph.sha(bad.encode());proof['files']['current_xml']['sha256']=digest;proof['output_code_sha256']=digest;record['code_sha256']=digest;record[registration.FIELD]['output_code_sha256']=digest;self.write_proof(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,ref,bad,root)
    def test_changed_actual_font_face_or_glyph_count_is_rejected(self):
        for field,value in [('postScriptName','OtherFace'),('glyphCount',1),('isCustomFont',False)]:
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,ref,xml,proof,path,_=self.setup_case(root);entry=proof['files']['current_render'];target=Path(root)/entry['file'];info=json.loads(target.read_text());info['actual_platform_font_usage'][0]['fonts'][0][field]=value;target.write_text(json.dumps(info));entry['sha256']=glyph.sha(target.read_bytes());self.write_proof(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,ref,xml,root)
    def test_actual_glyph_damage_is_rejected(self):
        with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
            record,ref,xml,proof,path,_=self.setup_case(root);entry=proof['files']['current_render'];target=Path(root)/entry['file'];info=json.loads(target.read_text());info['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.2;target.write_text(json.dumps(info));entry['sha256']=glyph.sha(target.read_bytes());self.write_proof(record,proof,path)
            with self.assertRaises(AssertionError):registration.registration_record(record,ref,xml,root)
    def test_proof_source_or_artifact_hash_damage_is_rejected(self):
        for item in ('source','artifact','proof'):
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,ref,xml,proof,path,_=self.setup_case(root)
                target=Path(root)/'clean/source.html' if item=='source' else Path(root)/proof['files']['baseline_render']['file'] if item=='artifact' else path;target.write_bytes(target.read_bytes()+b' ')
                with self.assertRaises(AssertionError):registration.registration_record(record,ref,xml,root)
    def test_fake_verified_fields_and_guess_offsets_do_not_bypass_lineage(self):
        with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
            record,ref,xml,proof,path,_=self.setup_case(root);record['_verified_glyph_alignment']={'allowed_range_delta_verified':True};proof['reference_offset']=[1,0];self.write_proof(record,proof,path)
            with self.assertRaises(AssertionError):registration.registration_record(record,ref,xml,root)
    def test_missing_changed_crop_or_outside_owned_evidence_is_rejected(self):
        for mode in ('missing_crop','outside'):
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,ref,xml,proof,path,_=self.setup_case(root)
                if mode=='missing_crop':proof['local_reference_validation']={}
                else:proof['files']['before_xml']['file']='clean/source.html'
                self.write_proof(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,ref,xml,root)

if __name__=='__main__':unittest.main()
