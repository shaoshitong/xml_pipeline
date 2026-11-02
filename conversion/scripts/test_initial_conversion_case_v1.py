import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

import initial_conversion_case_v1 as c


def png(width=20,height=10):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\xff\xff'*width)*height))+chunk(b'IEND',b'')


@unittest.skipUnless(importlib.util.find_spec('PIL'),'Pillow input checks run on HKUST')
class CaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.work=self.root/c.OWNER/'case'/'attempt';self.work.mkdir(parents=True);self.patches=[patch.object(c,'R',self.root),patch.object(c,'W',self.root/'conversion')]
        for p in self.patches:p.start()
        source=self.root/'conversion/inputs/case';source.mkdir(parents=True);self.code=b'Original source TeX';self.image=png();(source/'source.txt').write_bytes(self.code);(source/'ref.png').write_bytes(self.image)
        self.request={'id':'case','stage':'compile','stage_input_hash':'input','pins':{},'phase_timeout_seconds':150,'max_side':8192,
            'source':{'pair_sha256':'case','format':'tikz','source':'dataset','category':'scientific_diagram','code_sha256':c.sha(self.code),'image_sha256':c.sha(self.image)},
            'manifest':{'id':'case','source_format':'tikz','source_code':str((source/'source.txt').relative_to(self.root)),'reference_image':str((source/'ref.png').relative_to(self.root)),'code_sha256':c.sha(self.code),'image_sha256':c.sha(self.image),'width':20,'height':10,'panel_assets':[]},
            'execution':{'source_code_sha256':c.sha(self.code),'pages':2},'proposed_clean_directory':'clean/case','artifact_version':'test-version'}
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_registered_source_bytes_are_frozen_in_owned_workspace_and_dimensions_retained(self):
        code,image,size,ext=c.inputs(self.request,self.work);self.assertEqual((code,image,size,ext),(self.code,self.image,(20,10),'png'));self.assertEqual((self.work/'source.tex').read_bytes(),self.code);self.assertEqual((self.work/'reference.bin').read_bytes(),self.image);self.assertFalse((self.root/'clean').exists())
    def test_source_pair_or_manifest_hash_mismatch_fails_before_any_conversion(self):
        self.request['source']['pair_sha256']='other'
        with self.assertRaises(c.Deferred):c.inputs(self.request,self.work)
        self.assertFalse((self.work/'source.tex').exists())
    def test_modified_source_file_is_retained_as_typed_resource_recovery(self):
        (self.root/self.request['manifest']['source_code']).write_bytes(b'changed')
        with self.assertRaises(c.Deferred) as failure:c.inputs(self.request,self.work)
        self.assertEqual(failure.exception.reason,'source_file_hash_mismatch')
    def test_reference_header_dimensions_cannot_be_replaced_or_scaled(self):
        self.request['manifest']['width']=19
        with self.assertRaises(c.Deferred) as failure:c.inputs(self.request,self.work)
        self.assertEqual(failure.exception.reason,'reference_header_dimensions_mismatch')
    def test_panel_assets_go_to_recovery_tier_without_invoking_compiler(self):
        self.request['manifest']['panel_assets']=['asset']
        with patch.object(c.subprocess,'run') as mock,self.assertRaises(c.Deferred) as failure:c.compile_case(self.request,self.work)
        self.assertEqual(failure.exception.reason,'asset_mapping_requires_larger_tier');mock.assert_not_called()
    def test_multipage_native_case_is_deferred_with_original_inputs_intact(self):
        with self.assertRaises(c.Deferred) as failure:c.native_case(self.request,self.work)
        self.assertEqual(failure.exception.reason,'multi_page_source_requires_recovery_tier');self.assertEqual((self.work/'source.tex').read_bytes(),self.code)
    def test_large_reference_requests_a_larger_tier_before_any_rescaling_or_native_render(self):
        self.request['max_side']=16
        with self.assertRaises(c.Deferred) as failure:c.native_case(self.request,self.work)
        self.assertEqual(failure.exception.reason,'larger_canvas_tier_required');self.assertFalse((self.work/'candidate.png').exists())
    def test_native_tight_canvas_and_scaled_dimensions_are_retained_as_distinct_recovery_types(self):
        info={'output_size':[20,10],'selected_image':'declared_first_page','content_outside_declared_canvas':False};c.require_native_canvas(png(),info,20,10)
        with self.assertRaises(c.Deferred) as tight:c.require_native_canvas(png(21,10),{**info,'output_size':[21,10],'selected_image':'complete_tight_graph','content_outside_declared_canvas':True},20,10)
        self.assertEqual(tight.exception.reason,'native_outside_reference_canvas_requires_registered_recovery');self.assertEqual(tight.exception.details['original_reference_page'],[20,10]);self.assertEqual(tight.exception.details['native_png_page'],[21,10])
        with self.assertRaises(c.Deferred) as scaled:c.require_native_canvas(png(10,5),{**info,'output_size':[10,5]},20,10)
        self.assertEqual(scaled.exception.reason,'native_dimensions_require_larger_renderer_tier')

    def test_phase_deadline_is_recovery_not_source_abandonment(self):
        path=self.work/'request.json';path.write_text(json.dumps(self.request))
        with patch.object(c,'compile_case',side_effect=subprocess.TimeoutExpired('compiler',150)):c.main(path)
        result=json.loads((self.work/'result.json').read_text());self.assertFalse(result['ok']);self.assertEqual(result['state'],'deferred_recovery_tier');self.assertEqual(result['reason'],'phase_subprocess_deadline');self.assertEqual(result['model_calls'],0);self.assertFalse(result['accepted'])
    def test_unexpected_runtime_failure_has_typed_receipt_and_frozen_identity(self):
        path=self.work/'request.json';path.write_text(json.dumps(self.request))
        with patch.object(c,'compile_case',side_effect=ValueError('runtime failed')):c.main(path)
        result=json.loads((self.work/'result.json').read_text());self.assertEqual(result['error_type'],'ValueError');self.assertEqual(result['code_sha256'],c.sha(self.code));self.assertTrue((self.work/'traceback.txt').is_file())
    @unittest.skipUnless(Path('/usr/bin/prlimit').is_file(),'Linux cached compiler command runs on HKUST')
    def test_cached_only_sandbox_missing_dependency_never_fetches_or_mutates_shared_receipts(self):
        with patch.object(c.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr="File `missing.sty' not found")) as mock,self.assertRaises(c.Deferred) as failure:
            c.compile_case(self.request,self.work)
        command=mock.call_args.args[0];self.assertIn('--only-cached',command);self.assertIn('--unshare-all',command);self.assertIn('--cpu=90:100',command);self.assertEqual(failure.exception.reason,'missing_cached_dependencies');self.assertFalse((self.root/'conversion/tex_dependencies').exists());self.assertTrue((self.work/'compile.json').exists())


if __name__=='__main__':unittest.main()
