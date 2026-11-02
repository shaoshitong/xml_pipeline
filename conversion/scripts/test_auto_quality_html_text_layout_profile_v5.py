import copy
import tempfile
from pathlib import Path
from importlib.util import find_spec
import unittest
from unittest.mock import patch
import html_text_layout_registration_v5 as registration
import auto_quality_html_text_layout_profile_v5 as profile
import auto_quality_source_vector_v2 as source
import html_actual_text_alignment as glyph
import test_html_text_layout_registration_v5 as fixtures

@unittest.skipUnless(find_spec('skimage') is not None,'Remote source/metric verification runtime')
class FreshProfileTests(unittest.TestCase):
    def test_fresh_source_replay_reuses_supplied_native_clip_boxes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);record,reference,xml,proof,path,dom,info=fixtures.synthetic(root)
            with patch.object(registration,'_base_registration',side_effect=lambda record,reference,xml,root:(record,None)):verified,_=registration.registration_record(record,reference,xml,root)
            capture={'viewport':[32,32]}
            with patch.object(profile,'R',root),patch.object(profile,'W',root/'conversion'),patch.object(source,'R',root),patch.object(glyph,'capture_source',return_value=(dom,{},b'',capture)):
                result=profile.check_html_profile(verified,xml,native_render=info)
            self.assertTrue(result['ok'],result['failures']);self.assertTrue(result['evidence']['fresh_native_render_reused']);self.assertEqual(result['evidence']['whitespace_cells'],['2']);self.assertEqual(result['evidence']['fixed_clip_cells'],['3'])
    def test_fresh_source_space_clip_feature_or_actual_glyph_font_damage_rejected(self):
        for mode in ('source_space','source_clip','source_feature','glyph','font','missing_clip_probe'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);record,reference,xml,proof,path,dom,info=fixtures.synthetic(root)
                with patch.object(registration,'_base_registration',side_effect=lambda record,reference,xml,root:(record,None)):verified,_=registration.registration_record(record,reference,xml,root)
                if mode=='source_space':dom['objects'][0]['actualSourceGlyphs'][1]['width']+=1
                elif mode=='source_clip':dom['objects'][1]['sourceClip']['chain'][0]['bottom']+=1
                elif mode=='source_feature':dom['unsupported']=[{'reason':'pseudo_content'}]
                elif mode=='glyph':info['actual_text_positions'][0]['runs'][0]['chars'][0]['x']+=.2
                elif mode=='font':info['actual_platform_font_usage'][0]['fonts'][0]['isCustomFont']=False
                else:info.pop('actual_clip_boxes')
                with patch.object(profile,'R',root),patch.object(profile,'W',root/'conversion'),patch.object(source,'R',root),patch.object(glyph,'capture_source',return_value=(dom,{},b'',{'viewport':[32,32]})):
                    result=profile.check_html_profile(verified,xml,native_render=info)
                self.assertFalse(result['ok'],mode)

if __name__=='__main__':unittest.main()
