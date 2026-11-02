"""Audit-only tests: no writer, model, production DB or renderer is invoked."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest

import svg_program_terminal_canonical_audit_v1 as audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.identifier = 'a' * 64
        self.blobs = {'source.svg': b'original_svg', 'reference.png': b'original_png',
                      'candidate.drawio': b'candidate_xml', 'candidate.png': b'candidate_png'}
        for name, raw in self.blobs.items():
            path = self.root / 'clean' / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
        self.original = {'pair_sha256': self.identifier, 'category': 'scientific_diagram', 'format': 'svg',
                         'source': 'fixture', 'code_sha256': audit.sha(self.blobs['source.svg']),
                         'image_sha256': audit.sha(self.blobs['reference.png'])}
        self.record = {'id': self.identifier, 'source_pair_sha256': self.identifier, 'category': 'scientific_diagram',
                       'source': 'fixture', 'source_format': 'svg', 'format': 'drawio',
                       'source_code_sha256': self.original['code_sha256'], 'source_image_sha256': self.original['image_sha256'],
                       'code_sha256': audit.sha(self.blobs['candidate.drawio']), 'image_sha256': audit.sha(self.blobs['candidate.png']),
                       'original_source_code': 'clean/source.svg', 'original_reference': 'clean/reference.png',
                       'code_file': 'clean/candidate.drawio', 'image_file': 'clean/candidate.png'}
        self.manifest = {'id': self.identifier, 'source_format': 'svg', 'code_sha256': self.original['code_sha256'],
                         'image_sha256': self.original['image_sha256'], 'source_code': 'clean/source.svg',
                         'reference_image': 'clean/reference.png'}
        self.job = dict(zip(audit.JOB_COLUMNS, (self.identifier, 'scientific_diagram', 'svg', 'fixture',
                         json.dumps(self.original), 'needs_quality_repair', 'vector', 1, 'initial',
                         json.dumps(self.record), None, json.dumps(self.manifest), None)))
        folder = self.root / 'conversion/prototype/source_certificate'
        folder.mkdir(parents=True)
        (folder / 'current.drawio').write_bytes(self.blobs['candidate.drawio'])
        (folder / 'original_source.svg').write_bytes(self.blobs['source.svg'])
        self.plan = {**{key: self.record[key] for key in ('source_code_sha256', 'source_image_sha256', 'code_sha256', 'image_sha256')},
                     'evidence_directory': str(folder), 'certificate_sha256': 'b' * 64}
        self.receipt = {'created_at': 'committed', 'commit_nonce': 'c' * 32}
        self.document = {'commit_nonce': self.receipt['commit_nonce'], 'plan': self.plan,
                         'complete_database_cas_snapshot': {'tables': {'jobs': {'columns': list(audit.JOB_COLUMNS),
                         'rows': [[self.job[key] for key in audit.JOB_COLUMNS]]}}}}
        self.reader = types.SimpleNamespace(validate_outcome=lambda *a: {'receipt_verified': True},
                                            _read=lambda *a: self.document)
        raw = json.dumps({audit.MARKER: {'decision': self.receipt, 'commit_nonce': self.receipt['commit_nonce']}})
        self.row = (self.identifier, 'scientific_diagram', 'svg', self.original['code_sha256'],
                    self.original['image_sha256'], 'current program failure', raw, 'committed')

    def check(self, job=None, row=None):
        return audit.audit_one(row or self.row, job or self.job, self.reader, self.root, {})

    def test_exact_current_source_candidate_and_frozen_evidence_verify(self):
        result = self.check()
        self.assertEqual(result['state'], 'verified', result)
        self.assertEqual(result['revision_state'], 'exact_committed_job_and_revision_preserved')
        self.assertEqual(len(result['artifact_checks']), 8)

    def test_later_same_source_candidate_is_superseded_and_not_writer_corruption(self):
        raw = b'later_valid_candidate_xml'
        (self.root / 'clean/new.drawio').write_bytes(raw)
        record = {**self.record, 'code_file': 'clean/new.drawio', 'code_sha256': audit.sha(raw)}
        current = {**self.job, 'output_record': json.dumps(record), 'updated_at': 'later'}
        result = self.check(current)
        self.assertEqual(result['state'], 'verified', result)
        self.assertEqual(result['revision_state'], 'superseded_candidate_same_original_source')
        self.assertTrue(result['later_job_changes_not_attributed_to_terminal_writer'])

    def test_later_metadata_same_candidate_is_separate(self):
        result = self.check({**self.job, 'updated_at': 'later', 'state': 'rendered'})
        self.assertEqual(result['state'], 'verified', result)
        self.assertEqual(result['revision_state'], 'superseded_job_metadata_same_candidate')

    def test_original_source_identity_change_is_refused(self):
        record = {**self.record, 'source_code_sha256': 'f' * 64}
        result = self.check({**self.job, 'output_record': json.dumps(record)})
        self.assertEqual(result['state'], 'audit_failed', result)
        self.assertIn('original_source_hash_mismatch', result['errors'][0])

    def test_nonce_or_registry_timestamp_mismatch_is_refused(self):
        for field in ('nonce', 'timestamp'):
            row = list(self.row)
            if field == 'nonce':
                raw = json.loads(row[6]); raw[audit.MARKER]['commit_nonce'] = 'f' * 32; row[6] = json.dumps(raw)
            else:
                row[7] = 'wrong'
            self.assertEqual(self.check(row=tuple(row))['state'], 'audit_failed')

    def test_current_artifact_tamper_is_not_hidden_by_matching_metadata(self):
        (self.root / 'clean/candidate.drawio').write_bytes(b'tampered')
        result = self.check()
        self.assertEqual(result['state'], 'audit_failed')
        self.assertIn('payload_digest_mismatch', result['errors'][0])

    def test_hash_cache_does_not_hide_new_inode_or_changed_content(self):
        cache = {}
        audit.file_digest(self.root, 'clean/source.svg', self.original['code_sha256'], cache)
        (self.root / 'clean/source.svg').write_bytes(b'changed_source')
        with self.assertRaises(ValueError):
            audit.file_digest(self.root, 'clean/source.svg', self.original['code_sha256'], cache)

    def test_source_escape_symlink_is_refused(self):
        outside = self.root / 'outside.svg'; outside.write_bytes(self.blobs['source.svg'])
        (self.root / 'clean/source-link.svg').symlink_to(outside)
        with self.assertRaises(ValueError):
            audit.file_digest(self.root, 'clean/source-link.svg', self.original['code_sha256'])

    def test_database_snapshot_does_not_write_or_leave_read_transaction(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('create table jobs(' + ','.join(name + ' text' for name in audit.JOB_COLUMNS) + ')')
        db.execute('create table processing_outcomes_v2(id text,category text,format text,source_code_hash text,source_image_hash text,status text,reason text,record text,updated_at text)')
        db.execute('insert into jobs values(' + ','.join('?' for _ in audit.JOB_COLUMNS) + ')', [self.job[key] for key in audit.JOB_COLUMNS])
        db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)', (*self.row[:5], 'abandoned', *self.row[5:]))
        db.commit()
        before = list(db.iterdump())
        db.execute('pragma query_only=on')
        rows, jobs, protections = audit.snapshot(db, {self.identifier})
        self.assertEqual(len(rows), 1)
        self.assertEqual(jobs[self.identifier]['id'], self.identifier)
        self.assertEqual(protections[self.identifier][4], 'abandoned')
        self.assertFalse(db.in_transaction)
        self.assertEqual(list(db.iterdump()), before)
        db.execute('pragma query_only=off')
        db.execute('update processing_outcomes_v2 set format="html"')
        db.commit()
        db.execute('pragma query_only=on')
        self.assertEqual(len(audit.snapshot(db, {self.identifier})[0]), 1, 'Marker with wrong format must be audited, not silently skipped')
        with self.assertRaises(sqlite3.OperationalError):
            db.execute('update jobs set state="wrong"')


if __name__ == '__main__':
    unittest.main()
