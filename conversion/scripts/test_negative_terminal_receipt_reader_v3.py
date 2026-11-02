import copy
import json
from pathlib import Path
import unittest

import negative_terminal_receipt_reader_v3 as reader
import svg_program_terminal_outcomes_v1 as writer
import test_svg_program_terminal_outcomes_v1 as fixtures


class SVGReaderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.WriterTests('test_valid_collector_proof_is_current')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        result = writer.apply(self.fixture.db, self.fixture.plan, self.fixture.config, publish=True)
        self.assertEqual(result['state'], 'abandoned', result)
        self.row = dict(zip(reader.prior.OUTCOME_COLUMNS, self.fixture.db.execute(
            'select id,category,format,source_code_hash,source_image_hash,reason,record from processing_outcomes_v2').fetchone()))
        self.root = self.fixture.root
        self.pins = {'svg': {'writer_sha256': writer.sha(Path(writer.__file__).read_bytes()),
                             'collector_sha256': writer.sha(Path(writer.collector.__file__).read_bytes())}}

    def validate(self, row=None, pins=None):
        return reader.validate_outcome(row or self.row, self.root, pins if pins is not None else self.pins)

    def changed_evidence(self, transform):
        row = copy.deepcopy(self.row)
        evidence = json.loads(row['record'])
        transform(evidence)
        row['record'] = json.dumps(evidence)
        return row

    def resealed_document(self, transform):
        row = copy.deepcopy(self.row)
        evidence = json.loads(row['record'])
        receipt = evidence[reader.MARKER]['decision']
        doc = json.loads((self.root / receipt['file']).read_bytes())
        transform(doc)
        payload = reader.canonical(doc)
        digest = reader.sha(payload)
        receipt['sha256'] = digest
        receipt['file'] = str(reader.DIRECTORY / row['id'] / ('decision.' + digest + '.json'))
        path = self.root / receipt['file']
        path.write_bytes(payload)
        path.chmod(0o444)
        row['record'] = json.dumps(evidence)
        return row

    def test_real_writer_receipt_is_strictly_verified(self):
        result = self.validate()
        self.assertEqual(result['kind'], 'svg_program_terminal_v1')
        self.assertTrue(result['receipt_verified'])
        self.assertFalse(result['accepted'])
        self.assertEqual(reader.manifest_row(self.row, self.root, self.pins)['status'], 'abandoned')

    def test_unknown_svg_marker_cannot_fall_through_to_legacy(self):
        row = self.changed_evidence(lambda value: value.update(svg_program_terminal_outcome_v99=value.pop(reader.MARKER)))
        with self.assertRaises(ValueError):
            self.validate(row)

    def test_mixed_svg_and_old_program_markers_are_rejected(self):
        for old in ('program_terminal_outcome_v1', 'program_terminal_outcome_v2'):
            row = self.changed_evidence(lambda value: value.update({old: {}}))
            with self.assertRaises(ValueError):
                self.validate(row)

    def test_wrong_writer_or_collector_author_pins_fail(self):
        for name in self.pins['svg']:
            pins = copy.deepcopy(self.pins)
            pins['svg'][name] = 'f' * 64
            with self.assertRaises(ValueError):
                self.validate(pins=pins)

    def test_nonce_cannot_be_changed_only_in_outcome(self):
        row = self.changed_evidence(lambda value: value[reader.MARKER].update(commit_nonce='f' * 32))
        with self.assertRaises(ValueError):
            self.validate(row)

    def test_resealed_decision_with_changed_author_or_prior_source_is_rejected(self):
        transforms = [lambda doc: doc.update(writer_sha256='f' * 64),
                      lambda doc: doc['prior_outcome'].update(source_image_hash='f' * 64),
                      lambda doc: doc.update(commit_nonce='f' * 32),
                      lambda doc: doc['plan'].update(certificate_sha256='f' * 64)]
        for transform in transforms:
            row = self.resealed_document(transform)
            with self.assertRaises(ValueError):
                self.validate(row)

    def test_original_and_candidate_digest_or_category_tampering_fail(self):
        for key in ('source_code_hash', 'source_image_hash', 'category'):
            row = {**self.row, key: 'wrong'}
            with self.assertRaises(ValueError):
                self.validate(row)
        row = self.changed_evidence(lambda value: value.update(code_sha256='wrong'))
        with self.assertRaises(ValueError):
            self.validate(row)

    def test_decision_ancestor_symlink_is_not_followed(self):
        directory = self.root / reader.DIRECTORY / self.row['id']
        actual = directory.with_name('actual_directory')
        directory.rename(actual)
        directory.symlink_to(actual, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)):
            self.validate()

    def test_legacy_explicit_record_keeps_source_identity_checks(self):
        row = self.changed_evidence(lambda value: value.pop(reader.MARKER))
        self.assertEqual(self.validate(row)['kind'], 'legacy_explicit')
        row['source_image_hash'] = 'f' * 64
        with self.assertRaises(ValueError):
            self.validate(row)


if __name__ == '__main__':
    unittest.main()
