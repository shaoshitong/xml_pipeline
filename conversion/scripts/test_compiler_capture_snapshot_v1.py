"""Fault injection for immutable capture identity; no dataset files are used."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import compiler_capture_snapshot_v1 as capture


class CaptureSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.patch=patch.object(capture,'R',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.put('clean/input.dot',b'digraph { a -> b }')
        self.put('clean/input.svg',b'<svg/>')
        self.put('clean/data.json',b'{}')
        self.put('conversion/cache/returned_image.png',b'cached-raster-test-bytes')
        self.put('conversion/cache/audit.json',json.dumps(dict(id='id1',source_code_sha256='code1',directory='conversion/cache')).encode())
        self.record=dict(id='id1',source_code_sha256='code1',source_image_sha256='image1',
                         source_render_dot='clean/input.dot',source_render_svg='clean/input.svg',
                         source_render_svg_sha256=capture.sha(b'<svg/>'),execution_audit='conversion/cache/audit.json',
                         original_source_data='clean/data.json',source_data_sha256=capture.sha(b'{}'))

    def put(self,name,blob):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)

    def snapshot(self):return capture.seal_snapshot(self.record)

    def test_unchanged_snapshot_and_selected_bytes_pass(self):
        first=self.snapshot();evidence={key:first[key] for key in ('source_dot_sha256','source_svg_sha256','execution_audit_sha256')}
        second=capture.seal_snapshot(self.record,evidence)
        self.assertEqual(first,second);self.assertTrue(capture.check_snapshot(self.record,second)['ok'])

    def test_dot_comment_drift_is_not_hidden_by_unchanged_svg(self):
        snapshot=self.snapshot();self.put('clean/input.dot',b'digraph { a -> b } // changed')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_payload_changed:source_dot'):
            capture.check_snapshot(self.record,snapshot)

    def test_audit_whitespace_drift_is_rejected(self):
        snapshot=self.snapshot();path=self.root/self.record['execution_audit'];path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_payload_changed:execution_audit'):
            capture.check_snapshot(self.record,snapshot)

    def test_historical_png_is_bound_before_execution(self):
        snapshot=self.snapshot();self.put('conversion/cache/returned_image.png',b'changed')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_returned_image_changed'):
            capture.check_snapshot(self.record,snapshot)

    def test_missing_capture_is_fatal_infrastructure_drift(self):
        snapshot=self.snapshot();(self.root/'clean/input.dot').unlink()
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_payload_unreadable'):
            capture.check_snapshot(self.record,snapshot)

    def test_clean_payload_symlink_cannot_escape_clean(self):
        self.put('conversion/outside.dot',b'digraph { a -> b }')
        path=self.root/'clean/input.dot';path.unlink();path.symlink_to(self.root/'conversion/outside.dot')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_outside_owner'):
            self.snapshot()

    def test_locator_change_is_not_accepted_for_same_bytes(self):
        snapshot=self.snapshot();self.put('clean/other.dot',b'digraph { a -> b }')
        record={**self.record,'source_render_dot':'clean/other.dot'}
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_locator_changed:source_dot'):
            capture.check_snapshot(record,snapshot)

    def test_source_data_drift_is_rejected(self):
        snapshot=self.snapshot();self.put('clean/data.json',b'{"changed":true}')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_data_payload_changed'):
            capture.check_snapshot(self.record,snapshot)

    def test_selection_snapshot_cannot_be_replaced_with_current_bytes(self):
        snapshot=self.snapshot();evidence={key:snapshot[key] for key in ('source_dot_sha256','source_svg_sha256','execution_audit_sha256')}
        self.put('clean/input.dot',b'new current bytes')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_capture_differs_from_selected_snapshot:source_dot'):
            capture.seal_snapshot(self.record,evidence)


if __name__=='__main__':unittest.main()
