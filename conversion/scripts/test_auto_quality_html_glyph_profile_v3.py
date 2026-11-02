"""Fresh-render reuse and mixed unchanged-source scope regressions."""
import copy
import json
from pathlib import Path
import tempfile
from importlib.util import find_spec
from unittest.mock import patch
import unittest
import auto_quality_html_glyph_profile_v3 as profile
import auto_quality_source_vector_v2 as source
import html_actual_text_alignment as glyph
import html_actual_text_registration as registration
import test_html_actual_text_registration as lineage

@unittest.skipUnless(find_spec('skimage') is not None,'Remote runtime has full image metrics')
class FreshProfileTests(unittest.TestCase):
    def fixture(self,root):
        record,reference,xml,proof,_,blobs=lineage.LineageTests().setup_case(root)
        with patch.object(registration,'_base_registration',side_effect=lambda record,reference,xml,root:(record,None)):
            verified,_=registration.registration_record(record,reference,xml,root)
        return verified,xml,json.loads(blobs['source_dom']),json.loads(blobs['current_render'])
    def test_supplied_fresh_native_is_reused_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);record,xml,dom,info=self.fixture(root)
            with patch.object(profile,'R',root),patch.object(profile,'W',root/'conversion'),patch.object(source,'R',root),patch.object(glyph,'capture_source',return_value=(dom,{},b'',{'viewport':[32,32]})):
                result=profile.check_html_profile(record,xml,native_render=info)
            self.assertTrue(result['ok'],result['failures']);self.assertTrue(result['evidence']['fresh_actual_native_evidence_reused']);self.assertEqual(result['evidence']['changed_text_cells'],['2'])
    def test_fresh_glyph_source_or_font_damage_is_rejected(self):
        for damage in ('glyph','font','source_text','source_style'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);record,xml,dom,info=self.fixture(root)
                if damage=='glyph':info['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.2
                elif damage=='font':info['actual_platform_font_usage'][0]['fonts'][0]['isCustomFont']=False
                elif damage=='source_text':dom['objects'][0]['text']='Changed'
                else:dom['objects'][0]['color']['color']='#ff0000'
                with patch.object(profile,'R',root),patch.object(profile,'W',root/'conversion'),patch.object(source,'R',root),patch.object(glyph,'capture_source',return_value=(dom,{},b'',{'viewport':[32,32]})):
                    result=profile.check_html_profile(record,xml,native_render=info)
                self.assertFalse(result['ok'],damage)
    def test_no_glyph_metadata_keeps_existing_v2_format_dispatch(self):
        sentinel={'supported':True,'ok':False,'profile':'original-v2'}
        with patch.object(source,'check_vector_profile',return_value=sentinel) as fallback:
            self.assertEqual(profile.check_html_profile({'source_format':'svg'},'<mxfile/>'),sentinel)
        fallback.assert_called_once()

if __name__=='__main__':unittest.main()
