import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import initial_conversion_case_v1b as b


class PageDictionaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.patch=patch.object(b.frozen,'R',self.root);self.patch.start();self.work=self.root/b.frozen.OWNER/'case';self.work.mkdir(parents=True);self.path=self.work/'page0_text.json'
    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def test_lossless_images_masks_and_all_text_geometry(self):
        value={'width':448.,'height':240.,'blocks':[{'type':1,'bbox':[1.,2.5,3.,4.],'image':b'\0\xffimage','mask':b'\x00\x01'},{'type':0,'lines':[{'dir':[1.,0.],'spans':[{'text':'\u03b1\u4e2d','font':'CustomBold','size':12.5,'origin':[2.,3.],'flags':16}]}]}]}
        b.write_json(self.path,value);stored=json.loads(self.path.read_text());self.assertEqual(b.restore_page_dictionary(stored,self.work),value);image=stored['blocks'][0]['image'][b.MARKER];self.assertEqual(image['type'],'bytes');self.assertEqual(image['length'],7);self.assertEqual((self.root/image['file']).read_bytes(),value['blocks'][0]['image']);self.assertEqual(stored['blocks'][1],value['blocks'][1])
    def test_no_bytes_output_is_identical_to_frozen_writer(self):
        value={'blocks':[{'text':'unchanged','bbox':[1.,2.,3.,4.]}]};b.write_json(self.path,value);expected=self.work/'expected.json';b.ORIGINAL_WRITE_JSON(expected,value);self.assertEqual(self.path.read_bytes(),expected.read_bytes());self.assertFalse((self.work/'page_dictionary_binary_v1').exists())
    def test_duplicate_bytes_share_exact_asset_and_empty_bytes_survive(self):
        value={'image':b'hello','nested':[b'hello',b'']};packed=b.externalize_page_dictionary(value,self.path);self.assertEqual(b.restore_page_dictionary(packed,self.work),value);self.assertEqual(len(list((self.work/'page_dictionary_binary_v1').rglob('*.bin'))),2)
    def test_only_exact_page_file_pattern_is_adapted(self):
        for name in ['source_dom.json','page0_text.json.extra','pagex_text.json','xpage0_text.json','page-1_text.json']:
            with self.assertRaises(TypeError):b.write_json(self.work/name,{'image':b'image'})
        b.write_json(self.work/'page12_text.json',{'image':b'image'});self.assertTrue((self.work/'page12_text.json').is_file())
    def test_unknown_types_and_nonstring_keys_fail_closed(self):
        for value in [{'value':object()},{'value':bytearray(b'not-bytes')},{1:'key'},{'value':float('nan')}]:
            with self.assertRaises((TypeError,ValueError)):b.write_json(self.path,value)
    def test_owned_asset_hash_length_and_locator_validation(self):
        packed=b.externalize_page_dictionary({'image':b'image'},self.path);descriptor=packed['image'][b.MARKER];path=self.root/descriptor['file'];path.write_bytes(b'tampered')
        with self.assertRaises(ValueError):b.restore_page_dictionary(packed,self.work)
        descriptor['file']='outside.bin'
        with self.assertRaises(ValueError):b.restore_page_dictionary(packed,self.work)
        descriptor['type']='str'
        with self.assertRaises(ValueError):b.restore_page_dictionary(packed,self.work)
    def test_outside_owned_workspace_is_rejected(self):
        with self.assertRaises(ValueError):b.externalize_page_dictionary({'image':b'image'},self.root/'page0_text.json')
    def test_main_only_replaces_serializer_and_restores_it_even_on_failure(self):
        previous=b.frozen.write_json;compile_fn=b.frozen.compile_case;native_fn=b.frozen.native_case
        def main(path):
            self.assertIs(b.frozen.write_json,b.write_json);self.assertIs(b.frozen.compile_case,compile_fn);self.assertIs(b.frozen.native_case,native_fn);raise RuntimeError('fixture')
        with patch.object(b.frozen,'main',side_effect=main):
            with self.assertRaises(RuntimeError):b.main('request')
        self.assertIs(b.frozen.write_json,previous)


if __name__=='__main__':unittest.main()
