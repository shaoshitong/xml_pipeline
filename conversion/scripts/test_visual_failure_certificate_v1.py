"""Failure-certificate boundaries, without any model, renderer or canonical DB."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import visual_failure_certificate_v1 as c


class CertificateTests(unittest.TestCase):
    def setUp(self):
        r = {'id': 'a'*64, 'source_code_sha256': 'b'*64, 'source_image_sha256': 'c'*64,
             'code_sha256': 'd'*64, 'image_sha256': 'e'*64}
        self.request = {'record': r, 'qa_policy': 'frozen_qa', 'no_reachable_current_repair': True, 'route_snapshot_sha256': '2'*64}
        self.observation = {'kind': 'primary_clip_render', 'ok': True, 'code_sha256': r['code_sha256'],
                            'png': {'sha256': 'f'*64}, 'canvas': [100, 100], 'renderer_sha256': '1'*64}
        self.report = {'id': r['id'], 'policy': 'frozen_qa', 'input_code_sha256': r['code_sha256'],
                       'input_image_sha256': r['image_sha256'], 'source_code_sha256': r['source_code_sha256'],
                       'source_image_sha256': r['source_image_sha256'], 'state': 'repair_required', 'accepted': False,
                       'failures': ['raster_anomaly: global_fidelity_below_0.90'],
                       'checks': {'structure': {'ok': True}, 'resources': {'verified_files': []},
                                  'source': {'supported': True, 'ok': True, 'failures': []},
                                  'render': {'code_sha256': r['code_sha256'], 'image_sha256': 'f'*64,
                                             'strict_outside_page_pixels': 0, 'canvas': [100,100], 'renderer_sha256': '1'*64},
                                  'text_paint': {'all_source_text_objects_rendered': True, 'expected_text_objects': 1,
                                                 'actually_positioned_text_objects': 1},
                                  'fonts': {'all_rendered_fonts_embedded': True, 'actual_custom_font_glyphs': 3},
                                  'visual': {'ok': False, 'failures': ['global_fidelity_below_0.90'],
                                             'thresholds': {'ssim': .90, 'tile_p10': .72, 'foreground_precision_recall': .90, 'each_text_line_ssim': .55}}}}

    def classify(self, report=None, observation=None):
        return c.classify(report or self.report, observation or self.observation, self.request)

    def test_fresh_sole_raster_failure_is_only_a_nonpublishing_proposal(self):
        value = self.classify()
        self.assertTrue(value['proposal'])
        self.assertFalse(value['accepted'])
        self.assertFalse(value['terminal_publication_authorized'])
        self.assertEqual(value['native_editing'], {'state': 'not_reached', 'ok': None,
                                                 'reason': 'Frozen QA4b stops at the preceding raster gate.'})

    def test_missing_current_no_repair_proof_refuses_even_if_all_visual_prerequisites_pass(self):
        self.request.pop('route_snapshot_sha256')
        with self.assertRaises(ValueError):self.classify()

    def test_low_ssim_alone_or_unreached_prerequisite_never_proposes(self):
        for name in ('structure','resources','source','render','text_paint','fonts'):
            report = copy.deepcopy(self.report); report['checks'].pop(name)
            with self.assertRaises(ValueError):self.classify(report)

    def test_unsupported_source_or_nonembedded_fonts_or_missing_text_never_proposes(self):
        changes = [('source','supported',False),('source','ok',False),('fonts','all_rendered_fonts_embedded',False),
                   ('fonts','actual_custom_font_glyphs',0),('text_paint','all_source_text_objects_rendered',False),
                   ('text_paint','actually_positioned_text_objects',0)]
        for group,key,value in changes:
            report = copy.deepcopy(self.report);report['checks'][group][key] = value
            with self.assertRaises(ValueError):self.classify(report)

    def test_runtime_mixed_failure_blank_or_unknown_visual_remains_pending(self):
        for reason in ('blank_reference_or_native_render','unknown_new_metric'):
            report = copy.deepcopy(self.report); report['checks']['visual']['failures'] = [reason]
            report['failures'] = ['raster_anomaly: '+reason]
            with self.assertRaises(ValueError):self.classify(report)
        report = copy.deepcopy(self.report);report['failures'].append('fresh_native_render_failed')
        with self.assertRaises(ValueError):self.classify(report)

    def test_render_png_code_canvas_and_renderer_must_be_bound(self):
        for key,value in [('code_sha256','0'*64),('image_sha256','0'*64),('canvas',[101,100]),
                          ('strict_outside_page_pixels',1),('renderer_sha256','0'*64)]:
            report = copy.deepcopy(self.report);report['checks']['render'][key] = value
            with self.assertRaises(ValueError):self.classify(report)

    def test_changed_source_revision_policy_or_visual_thresholds_refused(self):
        for key in ('source_code_sha256','source_image_sha256','input_code_sha256','input_image_sha256','policy'):
            report = copy.deepcopy(self.report);report[key] = 'wrong'
            with self.assertRaises(ValueError):self.classify(report)
        report = copy.deepcopy(self.report);report['checks']['visual']['thresholds']['ssim'] = .1
        with self.assertRaises(ValueError):self.classify(report)

    def test_editing_not_reached_cannot_be_relabelled_as_pass(self):
        report = copy.deepcopy(self.report);report['checks']['native_editing'] = {'ok':True}
        with self.assertRaises(ValueError):self.classify(report)

    def test_now_qualified_or_changed_failure_detail_is_not_a_visual_negative(self):
        report = copy.deepcopy(self.report);report['state'] = 'qualified'
        with self.assertRaises(ValueError):self.classify(report)
        report = copy.deepcopy(self.report);report['failures'] = ['raster_anomaly: foreground_tile_p10_below_0.72']
        with self.assertRaises(ValueError):self.classify(report)

    def test_resource_file_content_or_alias_change_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve();a=root/'a';b=root/'b';link=root/'link'
            a.write_bytes(b'one');b.write_bytes(b'two');link.symlink_to(a)
            before=c.fingerprint(root,'link',c.sha(b'one'))
            link.unlink();link.symlink_to(b)
            with self.assertRaises(ValueError):c.fingerprint(root,'link',c.sha(b'one'))
            self.assertNotEqual(before,c.fingerprint(root,'link',c.sha(b'two')))

    def test_write_guard_allows_owned_evidence_and_blocks_canonical_and_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();owned=root/'owned';owned.mkdir();source=root/'source';source.write_text('original')
            code = '''import json,pathlib,sys
sys.path.insert(0,sys.argv[1]);import visual_failure_certificate_v1 as c
root=pathlib.Path(sys.argv[2]);owned=root/'owned';blocked=[];c.install_write_guard(root,owned,blocked)
(owned/'evidence').write_text('saved')
try:(root/'source').write_text('corrupted')
except PermissionError:pass
try:sys.audit('socket.connect',None,('8.8.8.8',443))
except ValueError:network='blocked'
else:network='unexpected'
print(json.dumps({'original':(root/'source').read_text(),'owned':(owned/'evidence').read_text(),'blocked':len(blocked),'network':network}))
'''
            done=subprocess.run([sys.executable,'-B','-c',code,str(Path(c.__file__).parent),str(root)],capture_output=True,text=True)
            self.assertEqual(done.returncode,0,done.stderr)
            self.assertEqual(json.loads(done.stdout),{'original':'original','owned':'saved','blocked':1,'network':'blocked'})


if __name__=='__main__':unittest.main()
