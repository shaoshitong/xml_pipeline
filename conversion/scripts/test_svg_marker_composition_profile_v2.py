"""Fail-closed root ownership + real partial-source controls; no API/DB writes."""
from pathlib import Path
import copy,hashlib,json,sys,tempfile,unittest
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'conversion/prototype/svg_marker_composition_v2';sys.path.insert(0,str(P));import svg_marker_composition_profile_v2 as profile
sha=lambda raw:hashlib.sha256(raw).hexdigest()
class Ownership(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'clean').mkdir();self.raw=b'not-media-test';(self.root/'clean/a').write_bytes(self.raw)
    def tearDown(self):self.tmp.cleanup()
    def test_own_regular_bytes(self):self.assertEqual(profile.read_owned(self.root,'clean/a',sha(self.raw)),self.raw)
    def test_sha_tamper(self):
        with self.assertRaisesRegex(ValueError,'sha256_mismatch'):profile.read_owned(self.root,'clean/a','0'*64)
    def test_traversal(self):
        with self.assertRaisesRegex(ValueError,'relative_owned'):profile.read_owned(self.root,'clean/../clean/a',sha(self.raw))
    def test_absolute(self):
        with self.assertRaisesRegex(ValueError,'relative_owned'):profile.read_owned(self.root,str(self.root/'clean/a'),sha(self.raw))
    def test_same_root_symlink_rejected(self):
        (self.root/'clean/link').symlink_to(self.root/'clean/a')
        with self.assertRaisesRegex(ValueError,'symlink_forbidden'):profile.read_owned(self.root,'clean/link',sha(self.raw))
    def test_external_same_bytes_symlink_rejected(self):
        (self.root/'outside').write_bytes(self.raw);(self.root/'clean/link').symlink_to(self.root/'outside')
        with self.assertRaisesRegex(ValueError,'symlink_forbidden'):profile.read_owned(self.root,'clean/link',sha(self.raw))
    def test_directory_symlink_rejected(self):
        (self.root/'clean/sub').mkdir();(self.root/'clean/sub/a').write_bytes(self.raw);(self.root/'clean/link').symlink_to(self.root/'clean/sub')
        with self.assertRaisesRegex(ValueError,'symlink_forbidden'):profile.read_owned(self.root,'clean/link/a',sha(self.raw))
class PhysicalFontMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(executable_path=profile.prior.CHROME,args=['--disable-dev-shm-usage'])
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.p.stop()
    def capture(self,html,objects):
        context=self.browser.new_context();page=context.new_page();page.set_content(html);page.evaluate('document.fonts.ready')
        try:return profile.source_platform_fonts(page,context,{'objects':page.evaluate(objects)})
        finally:context.close()
    def test_exact_actual_node(self):
        rows=self.capture('<svg><text x="10" y="30">abc</text></svg>',"() => {const n=document.querySelector('text').firstChild,r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();return [{id:'v1',type:'text',text:'abc',originalBoundingBox:{x:b.x,y:b.y,w:b.width,h:b.height}}]}")
        self.assertTrue(rows['complete']);self.assertTrue(rows['actual_platform_font_usage'][0]['fonts'])
    def test_ambiguous_same_text_geometry_rejected(self):
        rows=self.capture('<svg><text x="10" y="30">abc</text><text x="10" y="30">abc</text></svg>',"() => {const n=document.querySelector('text').firstChild,r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();return [{id:'v1',type:'text',text:'abc',originalBoundingBox:{x:b.x,y:b.y,w:b.width,h:b.height}}]}")
        self.assertFalse(rows['complete']);self.assertEqual(rows['failures'][0]['reason'],'source_text_physical_font_instance_not_unique')
    def test_multiple_text_runs_parent_rejected(self):
        rows=self.capture('<svg><text x="10" y="30"></text></svg>',"() => {const t=document.querySelector('text');t.append(document.createTextNode('abc'),document.createTextNode('def'));const n=t.firstChild,r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();return [{id:'v1',type:'text',text:'abc',originalBoundingBox:{x:b.x,y:b.y,w:b.width,h:b.height}}]}")
        self.assertFalse(rows['complete']);self.assertEqual(rows['failures'][0]['reason'],'source_text_parent_font_usage_not_individually_attributable')
    def test_wrong_text_rejected(self):
        rows=self.capture('<svg><text x="10" y="30">abc</text></svg>',"() => [{id:'v1',type:'text',text:'WRONG',originalBoundingBox:{x:10,y:0,w:0,h:0}}]")
        self.assertFalse(rows['complete'])
class RealPartialSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=P/'private_roots/c54f570f8a924fa788d54322728f1a1a';cls.record=json.loads((cls.root/'candidate_record.json').read_text());cls.xml=profile.read_owned(cls.root,cls.record['code_file'],cls.record['code_sha256']).decode();cls.source=profile.read_owned(cls.root,cls.record['original_source_code'],cls.record['source_code_sha256']).decode();cls.result=profile.check_source(cls.record,cls.xml,cls.source,cls.root)
    def test_five_unknown_source_paths_remain_pending(self):
        self.assertFalse(self.result['supported']);self.assertFalse(self.result['ok']);self.assertFalse(self.result['evidence']['complete_source_coverage']);self.assertEqual({r['id'] for r in self.result['evidence']['unknown_source_features']},{'v8','v9','v10','v11','v12'})
    def test_required_text_ids_complete_unique(self):
        ids=self.result['evidence']['required_text_cell_ids'];self.assertEqual(len(ids),11);self.assertEqual(len(set(ids)),11)
    def test_source_actual_fonts_complete(self):
        info=self.result['evidence']['source_physical_fonts'];self.assertTrue(info['complete']);self.assertEqual(len(info['actual_platform_font_usage']),11);proof=profile._proof(self.record,self.root);base=profile.asset(self.root,proof,'baseline_xml').decode();native=profile._render(base,450,550)['native_render'];self.assertEqual(profile.font_signature(info),profile.font_signature(native))
    def test_official_editing_refuses_partial(self):
        with self.assertRaisesRegex(ValueError,'whole_source_not_marker_subset'):profile.audit_editing(self.record,self.xml,self.result,self.root)
    def test_forged_full_source_flag_fails_fresh_revalidation(self):
        forged={'supported':True,'ok':True,'evidence':{'complete_source_coverage':True}}
        with self.assertRaisesRegex(ValueError,'source_unknown_features_remain'):profile.audit_editing(self.record,self.xml,forged,self.root)
    def test_wrong_source_payload_rejected(self):
        result=profile.check_source(self.record,self.xml,self.source+'\n',self.root);self.assertFalse(result['ok']);self.assertIn('supplied_source_differs',result['failures'][0]['error'])
    def test_wrong_candidate_payload_rejected(self):
        result=profile.check_source(self.record,self.xml+'\n',self.source,self.root);self.assertFalse(result['ok']);self.assertIn('candidate_or_source_format',result['failures'][0]['error'])
    def test_explicit_closed_root_does_not_fall_back_to_canonical(self):
        with tempfile.TemporaryDirectory() as root:result=profile.check_source(self.record,self.xml,self.source,root)
        self.assertFalse(result['ok']);self.assertFalse(result['supported'])
if __name__=='__main__':unittest.main(verbosity=2)
