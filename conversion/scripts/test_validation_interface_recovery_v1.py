import json, sqlite3, tempfile, unittest
from pathlib import Path
from unittest import mock
import validation_interface_recovery_v1 as recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'clean').mkdir()
        (self.root / 'conversion').mkdir()
        self.identifier = 'a' * 64
        self.db = sqlite3.connect(self.root / 'conversion/jobs.sqlite', isolation_level=None)
        self.addCleanup(self.db.close)
        self.failure = 'source_coverage_failure: ' + json.dumps([{'reason': 'source_profile_validation_error', 'error': "KeyError('source_render_svg')"}])
        self.candidate = {'id': self.identifier, 'source_pair_sha256': self.identifier, 'category': 'scientific_diagram', 'source_format': 'svg'}
        self.source = {'pair_sha256': self.identifier, 'category': 'scientific_diagram', 'format': 'svg'}
        for field, digest, content in [('code_file', 'code_sha256', b'candidate'), ('image_file', 'image_sha256', b'png'), ('original_reference', 'source_image_sha256', b'original'), ('original_source_code', 'source_code_sha256', b'<svg/>')]:
            path = 'clean/' + field
            (self.root / path).write_bytes(content)
            self.candidate.update({field: path, digest: recovery.sha(content)})
        for stem in ('code', 'image'):
            self.source[stem + '_sha256'] = self.candidate['source_' + stem + '_sha256']
        self.prior = {key: self.candidate[key] for key in ('id', 'code_sha256', 'image_sha256', 'source_code_sha256', 'source_image_sha256')}
        self.prior.update(confirmed_model_calls=2, history_snapshot_id='known-history', failed_qa_policy='qa-current', failed_qa_reasons=[self.failure])
        audit = {'id': self.identifier, 'accepted': False, 'failures': [self.failure], 'input_code_sha256': self.candidate['code_sha256'], 'input_image_sha256': self.candidate['image_sha256'], 'source_code_sha256': self.candidate['source_code_sha256'], 'source_image_sha256': self.candidate['source_image_sha256']}
        (self.root / 'conversion/auto_quality_owner.json').write_text(json.dumps({'policy': 'qa-current'}))
        self.db.executescript('create table jobs(id primary key,state,worker_pid,input_record,output_record,category,format,updated_at);create table processing_outcomes_v2(id primary key,category,format,source_code_hash,source_image_hash,status,reason,record,updated_at);create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at);')
        self.db.execute('insert into jobs values(?,?,?,?,?,?,?,?)', (self.identifier, 'needs_quality_repair', None, json.dumps(self.source), json.dumps(self.candidate), 'scientific_diagram', 'svg', 'original'))
        self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)', (self.identifier, 'scientific_diagram', 'svg', self.source['code_sha256'], self.source['image_sha256'], 'abandoned', 'lifetime_model_budget_exhausted_quality_failed', json.dumps(self.prior), 'original'))
        self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)', (self.identifier, self.candidate['code_sha256'], self.candidate['image_sha256'], 'qa-current', 'repair_required', json.dumps(audit), 'original'))

    def prepare(self):
        return recovery.prepare(self.db, self.identifier, self.root)

    def test_only_exact_interface_errors(self):
        self.assertTrue(recovery.only_interface_errors([self.failure]))
        for failures in ([], ['raster_anomaly: local_fail'], [self.failure, 'visual_failure'], ['source_coverage_failure: []'], ['source_coverage_failure: bad-json'], ['source_coverage_failure: {}'], ['source_coverage_failure: [{"reason":"source_profile_validation_error","error":"ValueError(unknown)"}]']):
            self.assertFalse(recovery.only_interface_errors(failures))

    def test_dry_run_is_read_only(self):
        before = self.db.total_changes
        result = recovery.apply(self.db, self.prepare(), self.root)
        self.assertEqual(result['state'], 'dry_run_current')
        self.assertEqual(self.db.total_changes, before)
        self.assertFalse((self.root / 'conversion/validation_interface_recovery_v1').exists())

    def test_publish_only_changes_outcome_and_preserves_budget_evidence(self):
        job = recovery.row(self.db, 'jobs', self.identifier)
        old_qa = self.db.execute('select * from auto_quality_audits_v1').fetchall()
        changes = self.db.total_changes
        result = recovery.apply(self.db, self.prepare(), self.root, True)
        self.assertEqual(result['state'], 'recovery_pending')
        self.assertEqual(self.db.total_changes - changes, 1)
        self.assertEqual(recovery.row(self.db, 'jobs', self.identifier), job)
        self.assertEqual(self.db.execute('select * from auto_quality_audits_v1').fetchall(), old_qa)
        self.assertEqual(recovery.row(self.db, 'processing_outcomes_v2', self.identifier)['status'], 'pending')
        blob = (self.root / result['receipt']).read_bytes()
        self.assertEqual(recovery.sha(blob), result['sha256'])
        self.assertEqual(json.loads(json.loads(blob)['plan']['outcome']['record'])['confirmed_model_calls'], 2)

    def test_candidate_revision_is_not_reopened(self):
        plan = self.prepare()
        self.db.execute('update jobs set updated_at="newer"')
        with self.assertRaisesRegex(ValueError, 'fresh_plan_changed'):
            recovery.apply(self.db, plan, self.root, True)
        self.assertEqual(recovery.row(self.db, 'processing_outcomes_v2', self.identifier)['status'], 'abandoned')

    def test_competing_writer_between_prepare_and_commit_is_preserved(self):
        plan = self.prepare()
        other = sqlite3.connect(self.root / 'conversion/jobs.sqlite', isolation_level=None)
        self.addCleanup(other.close)
        actual = recovery.os.fsync
        def competing_write(fd):
            other.execute('update jobs set updated_at="foreign-update"')
            return actual(fd)
        with mock.patch.object(recovery.os, 'fsync', side_effect=competing_write):
            with self.assertRaisesRegex(ValueError, 'full_cas_changed'):
                recovery.apply(self.db, plan, self.root, True)
        self.assertEqual(recovery.row(self.db, 'jobs', self.identifier)['updated_at'], 'foreign-update')
        self.assertEqual(recovery.row(self.db, 'processing_outcomes_v2', self.identifier)['status'], 'abandoned')

    def test_missing_or_changed_payload_is_rejected(self):
        (self.root / self.candidate['original_source_code']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'payload_hash_changed'):
            self.prepare()

    def test_active_job_is_preserved(self):
        self.db.execute('update jobs set worker_pid=123')
        with self.assertRaisesRegex(ValueError, 'job_not_idle'):
            self.prepare()

    def test_current_visual_failure_cannot_be_reopened_as_interface_error(self):
        audit = json.loads(self.db.execute('select record from auto_quality_audits_v1').fetchone()[0])
        audit['failures'].append('raster_anomaly: foreground_below_threshold')
        self.db.execute('update auto_quality_audits_v1 set record=?', (json.dumps(audit),))
        with self.assertRaisesRegex(ValueError, 'current_failure_not_only_known_interface_errors'):
            self.prepare()

    def test_owner_policy_revision_is_preserved(self):
        plan = self.prepare()
        (self.root / 'conversion/auto_quality_owner.json').write_text(json.dumps({'policy': 'new-policy'}))
        with self.assertRaisesRegex(ValueError, 'fresh_plan_changed'):
            recovery.apply(self.db, plan, self.root, True)

    def test_exact_historical_error_can_be_reopened_without_claiming_current_failure(self):
        (self.root / 'conversion/auto_quality_owner.json').write_text(json.dumps({'policy': 'new-policy'}))
        plan = self.prepare()
        self.assertIn('historical_exact_revision', plan['qa_scope'])
        self.assertEqual(plan['qa_policy'], 'qa-current')
        self.assertEqual(recovery.apply(self.db, plan, self.root, True)['state'], 'recovery_pending')

    def test_current_real_failure_supersedes_historical_interface_error(self):
        (self.root / 'conversion/auto_quality_owner.json').write_text(json.dumps({'policy': 'new-policy'}))
        audit = json.loads(self.db.execute('select record from auto_quality_audits_v1').fetchone()[0])
        audit['failures'] = ['raster_anomaly: actual_visual_failure']
        self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)', (self.identifier, self.candidate['code_sha256'], self.candidate['image_sha256'], 'new-policy', 'repair_required', json.dumps(audit), 'new'))
        with self.assertRaisesRegex(ValueError, 'current_failure_not_only_known_interface_errors'):
            self.prepare()

    def test_non_budget_abandonment_is_preserved(self):
        self.db.execute('update processing_outcomes_v2 set reason="proved_semantics_unsupported"')
        with self.assertRaisesRegex(ValueError, 'not_budget_abandonment'):
            self.prepare()

    def test_original_source_identity_is_checked(self):
        self.db.execute('update processing_outcomes_v2 set source_code_hash="wrong"')
        with self.assertRaisesRegex(ValueError, 'source_hash_changed'):
            self.prepare()

    def test_double_application_refuses_pending_outcome(self):
        recovery.apply(self.db, self.prepare(), self.root, True)
        with self.assertRaisesRegex(ValueError, 'not_budget_abandonment'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
