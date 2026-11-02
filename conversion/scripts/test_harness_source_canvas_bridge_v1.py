"""No graph-proof inheritance; frozen source and dimensions remain mandatory."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import harness_source_canvas_bridge_v1 as b

XML = '<mxfile><diagram><mxGraphModel pageWidth="202" pageHeight="102"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="current graph"><mxGeometry x="8" y="8" width="20" height="20" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.clean = self.root / 'clean/case'
        self.clean.mkdir(parents=True)
        self.ref = b'actual-original-reference'
        self.source = b'actual-original-source'
        (self.clean / 'ref.png').write_bytes(self.ref)
        (self.clean / 'source.txt').write_bytes(self.source)
        self.identity = {'id': 'case', 'source_code_sha256': b.sha(self.source), 'source_image_sha256': b.sha(self.ref)}
        self.prior_xml = XML.replace('current graph', 'old baseline')
        self.before = {**self.identity, 'code_sha256': b.sha(self.prior_xml.encode()),
                       'original_reference': 'clean/case/ref.png', 'original_source_code': 'clean/case/source.txt',
                       'auto_quality_canvas_repair': {'proof': 'conversion/strict/proof.json'},
                       'html_actual_text_alignment': {'old': 'must not inherit'},
                       'tikz_execution_source_v3': {'old': 'must not inherit'}}
        self.base = self.root / 'conversion/harness_sessions/v5_case/baseline'
        self.frozen = self.base.parent / 'source_provenance'
        for folder in [self.base, self.frozen]:
            folder.mkdir(parents=True)
            (folder / 'diagram.drawio').write_text(self.prior_xml)
            (folder / 'conversion.json').write_text(json.dumps(self.before))
        # Load the real provenance verifier with only its filesystem root mocked.
        spec = importlib.util.spec_from_file_location('fixture_provenance', Path(__file__).with_name('harness_source_provenance.py'))
        self.provenance = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {'native_worker': types.SimpleNamespace(R=self.root)}):
            spec.loader.exec_module(self.provenance)
        checks = self.provenance.validate_source_record(self.before)
        self.proof = {'version': 1, 'archive': str(self.frozen.relative_to(self.root)),
                      'record_sha256': b.sha((self.frozen/'conversion.json').read_bytes()),
                      'archived_code_sha256': b.sha(self.prior_xml.encode()), 'identity': self.identity,
                      'source_hash_checks': checks}
        self.current = {**self.identity, 'code_sha256': b.sha(XML.encode()),
                        'source_provenance': self.proof, 'previous_candidate_archive': str(self.base.relative_to(self.root))}
        self.modules = mock.patch.dict(sys.modules, {'harness_source_provenance': self.provenance})
        self.modules.start()
        self.contract = {'reference_page': [200, 100], 'output_page': [202, 102], 'original_page_offset': [1, 1]}
        self.registration = mock.patch.object(b, '_registration', return_value=self.contract)
        self.registration_mock = self.registration.start()

    def tearDown(self):
        self.registration.stop()
        self.modules.stop()
        self.tmp.cleanup()

    def attached(self):
        return b.attach(self.current, self.ref, XML, root=self.root)

    def test_only_page_lineage_carried_and_current_graph_explicitly_unverified(self):
        out = self.attached()
        self.assertEqual(set(out) - set(self.current), {b.FIELD})
        for key in ['auto_quality_canvas_repair', 'html_actual_text_alignment', 'tikz_execution_source_v3', 'native_font_validation', 'native_canvas_contract']:
            self.assertNotIn(key, out)
        contract = b.validate(out, self.ref, XML, root=self.root)
        self.assertFalse(contract['current_revision_verified'])
        self.assertFalse(contract['current_graph_source_geometry_verified'])
        self.assertTrue(contract['source_page_registration_verified'])
        self.assertFalse(contract['accepted'])
        self.assertEqual(contract['original_page_offset'], [1, 1])
        self.registration_mock.assert_called_with(self.before, self.ref, self.prior_xml)

    def test_font_or_graph_revision_can_reuse_page_but_never_coverage(self):
        out = self.attached()
        changed = XML.replace('current graph', 'different text requiring fresh QA')
        out['code_sha256'] = b.sha(changed.encode())
        contract = b.validate(out, self.ref, changed, root=self.root)
        self.assertFalse(contract['current_revision_verified'])

    def test_unverified_page_changes_refused_without_mutating_xml(self):
        bad = XML.replace('pageWidth="202"', 'pageWidth="200"')
        r = {**self.current, 'code_sha256': b.sha(bad.encode())}
        with self.assertRaisesRegex(ValueError, 'changed_verified_page'):
            b.attach(r, self.ref, bad, root=self.root)
        self.assertEqual(r['code_sha256'], b.sha(bad.encode()))

    def test_frozen_source_archive_record_xml_and_assets_rechecked(self):
        paths = [self.frozen/'conversion.json', self.frozen/'diagram.drawio', self.clean/'ref.png', self.clean/'source.txt', self.base/'diagram.drawio']
        for path in paths:
            with self.subTest(path=path.name):
                old = path.read_bytes()
                path.write_bytes(old+b' changed')
                with self.assertRaises((AssertionError, ValueError, json.JSONDecodeError)):
                    self.attached()
                path.write_bytes(old)

    def test_unowned_or_cross_source_baseline_rejected(self):
        r = {**self.current, 'previous_candidate_archive': 'conversion/unowned'}
        with self.assertRaisesRegex(ValueError, 'outside_harness'):
            b.attach(r, self.ref, XML, root=self.root)
        bad = {**self.before, 'id': 'different-case'}
        (self.base/'conversion.json').write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, 'source_identity'):
            self.attached()

    def test_frozen_provenance_identity_and_source_hash_are_required(self):
        for key in b.IDENTITY:
            r = {**self.current, key: 'wrong'}
            with self.assertRaises((AssertionError, ValueError)):
                b.attach(r, self.ref, XML, root=self.root)
        r = {k:v for k,v in self.current.items() if k!='source_provenance'}
        with self.assertRaisesRegex(ValueError, 'frozen_source'):
            b.attach(r, self.ref, XML, root=self.root)

    def test_inherited_offset_and_frozen_baseline_hash_cannot_be_edited(self):
        for key, value in [('original_page_offset', [0, 0]), ('baseline_record_sha256', 'wrong'), ('source_provenance_record_sha256', 'wrong'), ('output_page', [200, 100])]:
            out = self.attached()
            out[b.FIELD][key] = value
            with self.assertRaisesRegex(ValueError, 'inherited_registration_changed'):
                b.validate(out, self.ref, XML, root=self.root)

    def test_current_hash_reference_and_multiple_pages_refused(self):
        with self.assertRaisesRegex(ValueError, 'original_reference'):
            b.attach(self.current, self.ref+b' changed', XML, root=self.root)
        with self.assertRaisesRegex(ValueError, 'current_xml_hash'):
            b.attach(self.current, self.ref, XML+' ', root=self.root)
        xml = XML.replace('</mxfile>', '<diagram/></mxfile>')
        r = {**self.current, 'code_sha256': b.sha(xml.encode())}
        with self.assertRaisesRegex(ValueError, 'single_uncompressed'):
            b.attach(r, self.ref, xml, root=self.root)

    def test_origin_pixel_proof_validator_must_succeed(self):
        self.registration_mock.side_effect = AssertionError('frozen pixel proof mismatch')
        with self.assertRaisesRegex(AssertionError, 'pixel proof'):
            self.attached()

    def test_reference_must_fit_inside_full_verified_canvas(self):
        for output in [{'reference_page':[200,100], 'output_page':[202,102], 'original_page_offset':[-1,1]}, {'reference_page':[200,100], 'output_page':[202,102], 'original_page_offset':[3,1]}, {'reference_page':[200,100], 'output_page':[202,102], 'original_page_offset':[1.0,1]}]:
            self.registration_mock.return_value = output
            with self.assertRaisesRegex(ValueError, 'invalid_verified_registration'):
                self.attached()


if __name__ == '__main__':
    unittest.main()
