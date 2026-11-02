"""Producer-label compatibility, exact ownership/CAS and rollback tests."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import auto_quality_producer_bridge_v1 as b

XML = '<mxfile><diagram><mxGraphModel pageWidth="200" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" value="A" vertex="1" style="fontSize=12;fillColor=#fff;"><mxGeometry x="10" y="10" width="20" height="20" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
POLICY = b.QA3 + 'isolated-test'


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT,output_record TEXT,input_record TEXT,input_manifest TEXT,worker_pid INT,updated_at TEXT)')
        self.db.execute('CREATE TABLE harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,attempts INT DEFAULT 0,priority INT DEFAULT 0,worker_pid INT,started_at TEXT,heartbeat TEXT,session_dir TEXT,error TEXT)')
        self.db.execute('CREATE TABLE auto_quality_exceptions_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,route TEXT,state TEXT,reason TEXT,updated_at TEXT,PRIMARY KEY(id,code_hash,image_hash,policy))')
        self.db.execute('CREATE TABLE auto_quality_audits_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT,record TEXT,updated_at TEXT,PRIMARY KEY(id,code_hash,image_hash,policy))')
        b.initialize(self.db)
        self.record = self.add('case')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def add(self, identifier, xml=XML):
        folder = self.root / 'clean' / identifier
        folder.mkdir(parents=True)
        (folder / 'diagram.drawio').write_text(xml)
        (folder / 'image.png').write_bytes(b'current-native-png')
        (folder / 'original.png').write_bytes(b'original-source-image')
        (folder / 'source.tex').write_bytes(b'original-tex')
        r = {'id': identifier, 'source_pair_sha256': identifier, 'source_format': 'tikz',
             'source_code_sha256': b.core.sha(b'original-tex'), 'source_image_sha256': b.core.sha(b'original-source-image'),
             'code_file': str((folder / 'diagram.drawio').relative_to(self.root)), 'code_sha256': b.core.sha(xml.encode()),
             'image_file': str((folder / 'image.png').relative_to(self.root)), 'image_sha256': b.core.sha(b'current-native-png'),
             'original_source_code': str((folder / 'source.tex').relative_to(self.root)),
             'original_reference': str((folder / 'original.png').relative_to(self.root)),
             'root_review': {'reviewer': 'human', 'comment': 'Preserve this earlier comment.'}}
        inp = {'code_sha256': r['source_code_sha256'], 'image_sha256': r['source_image_sha256']}
        (folder / 'conversion.json').write_text(json.dumps(r))
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)', (identifier, 'needs_quality_repair', json.dumps(r), json.dumps(inp), 'remote-manifest', None, 'old-job-stamp'))
        self.db.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?,?,?,?)',
                        (identifier, 'held_for_quality_v3', 7, 88, None, 'old-start', 'old-heartbeat', 'conversion/harness_sessions/old-case', 'historic-error'))
        report = {'id': identifier, 'policy': POLICY, 'state': 'repair_required', 'accepted': False,
                  'input_code_sha256': r['code_sha256'], 'input_image_sha256': r['image_sha256'],
                  'source_code_sha256': r['source_code_sha256'], 'source_image_sha256': r['source_image_sha256'],
                  'checks': {'source': {'supported': True, 'ok': False, 'failures': [{'reason': 'executed_source_object_missing'}]}},
                  'failures': ['source_coverage_failure: executed_source_object_missing']}
        self.audit(r, report)
        self.db.commit()
        return r

    def audit(self, r, report, route='source_geometry_or_harness', state='pending'):
        args = (r['id'], r['code_sha256'], r['image_sha256'], report['policy'])
        self.db.execute('INSERT OR REPLACE INTO auto_quality_audits_v1 VALUES(?,?,?,?,?,?,?)', (*args, 'repair_required', json.dumps(report), 'qa-stamp'))
        self.db.execute('INSERT OR REPLACE INTO auto_quality_exceptions_v1 VALUES(?,?,?,?,?,?,?,?)', (*args, route, state, '; '.join(report['failures']), 'qa-stamp'))

    def plan(self):
        return b.prepare(self.db, 'case', policy=POLICY, root=self.root)

    def report(self):
        return json.loads(self.db.execute('SELECT record FROM auto_quality_audits_v1 WHERE id="case"').fetchone()[0])

    def queue(self):
        return self.db.execute('SELECT * FROM harness_queue_v3 WHERE id="case"').fetchone()

    def test_release_changes_only_queue_state_and_machine_feedback(self):
        plan = self.plan()
        self.assertTrue(plan['ok'])
        before = self.queue()
        old_job = self.db.execute('SELECT * FROM jobs').fetchone()
        self.db.execute('BEGIN IMMEDIATE')
        updated, receipt = b.apply(self.db, plan, root=self.root)
        after = self.queue()
        self.assertEqual(after[1], 'held_for_source_v5')
        self.assertEqual(before[:1] + before[2:], after[:1] + after[2:])
        self.assertEqual(old_job, self.db.execute('SELECT * FROM jobs').fetchone())
        self.assertEqual(updated['root_review']['comment'], self.record['root_review']['comment'])
        self.assertEqual(updated['root_review']['automatic_quality']['source'], 'automatic_quality')
        self.assertTrue(receipt['released'])
        self.assertEqual(receipt['model_calls_started_by_bridge'], 0)
        self.db.rollback()

    def test_publish_metadata_and_semantic_dedup_ignore_png_aa(self):
        plan = self.plan()
        receipt = b.publish(self.db, plan, root=self.root)
        self.assertTrue(receipt['released'])
        new = json.loads(self.db.execute('SELECT output_record FROM jobs').fetchone()[0])
        self.assertEqual(new['code_sha256'], self.record['code_sha256'])
        self.assertEqual(new['image_sha256'], self.record['image_sha256'])
        self.assertEqual(json.loads((self.root / 'clean/case/conversion.json').read_text()), new)
        self.db.execute("UPDATE harness_queue_v3 SET state='held_for_quality_v3'")
        alternate = b'new-aa-render'
        (self.root / new['image_file']).write_bytes(alternate)
        new['image_sha256'] = b.core.sha(alternate)
        self.db.execute('UPDATE jobs SET output_record=?', (json.dumps(new),))
        report = self.report()
        report['input_image_sha256'] = new['image_sha256']
        self.audit(new, report)
        self.db.commit()
        self.assertEqual(self.plan()['reason'], 'semantic_revision_already_dispatched')

    def test_atomic_rollback_on_sql_failure_restores_exact_metadata_and_history(self):
        plan = self.plan()
        before = self.queue()
        path = self.root / 'clean/case/conversion.json'
        old = path.read_bytes()
        self.db.execute("CREATE TRIGGER abort_jobs BEFORE UPDATE ON jobs BEGIN SELECT RAISE(ABORT,'injected'); END")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            b.publish(self.db, plan, root=self.root)
        self.assertEqual(path.read_bytes(), old)
        self.assertEqual(self.queue(), before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ' + b.TABLE).fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ' + b.core.TABLE).fetchone()[0], 0)

    def test_caller_rollback_undoes_release_and_both_ledgers(self):
        plan = self.plan()
        self.db.execute('BEGIN IMMEDIATE')
        b.apply(self.db, plan, root=self.root)
        self.db.rollback()
        self.assertEqual(self.queue()[1], 'held_for_quality_v3')
        self.assertEqual(self.db.execute('SELECT count(*) FROM ' + b.TABLE).fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ' + b.core.TABLE).fetchone()[0], 0)

    def test_running_and_owned_states_in_all_generations_are_preserved(self):
        for table in b.MODEL_TABLES:
            with self.subTest(table=table):
                if table != 'harness_queue_v3':
                    self.db.execute('CREATE TABLE ' + table + '(id TEXT PRIMARY KEY,state TEXT,worker_pid INT)')
                    self.db.execute('INSERT INTO ' + table + ' VALUES("case","running",NULL)')
                else:
                    self.db.execute("UPDATE harness_queue_v3 SET state='running'")
                self.db.commit()
                before = self.queue()
                self.assertFalse(self.plan()['ok'])
                self.assertEqual(self.queue(), before)
                if table != 'harness_queue_v3':
                    self.db.execute('DROP TABLE ' + table)
                else:
                    self.db.execute("UPDATE harness_queue_v3 SET state='held_for_quality_v3'")
                self.db.commit()
        self.db.execute('CREATE TABLE harness_queue_v2(id TEXT,state TEXT,worker_pid INT)')
        self.db.execute('INSERT INTO harness_queue_v2 VALUES("case","attempt_finished",123)')
        self.db.commit()
        self.assertFalse(self.plan()['ok'])

    def test_prior_generation_without_worker_pid_running_guard(self):
        self.db.execute('CREATE TABLE harness_queue(id TEXT,state TEXT)')
        self.db.execute('INSERT INTO harness_queue VALUES("case","running")')
        self.db.commit()
        self.assertFalse(self.plan()['ok'])

    def test_full_job_queue_audit_and_input_cas(self):
        for sql in ["UPDATE jobs SET state='accepted'", "UPDATE jobs SET worker_pid=77", "UPDATE jobs SET input_record='{}'", "UPDATE jobs SET output_record=output_record||' '", "UPDATE jobs SET input_manifest='new'", "UPDATE harness_queue_v3 SET heartbeat='new'", "UPDATE auto_quality_audits_v1 SET updated_at='new'", "UPDATE auto_quality_exceptions_v1 SET reason='new'"]:
            with self.subTest(sql=sql):
                plan = self.plan()
                self.assertTrue(plan['ok'])
                self.db.execute('SAVEPOINT mutation')
                self.db.execute(sql)
                updated, receipt = b.apply(self.db, plan, root=self.root)
                self.assertFalse(receipt['released'])
                self.db.execute('ROLLBACK TO mutation')
                self.db.execute('RELEASE mutation')

    def test_new_running_model_between_prepare_and_apply(self):
        plan = self.plan()
        self.db.execute('CREATE TABLE harness_queue(id TEXT,state TEXT)')
        self.db.execute('INSERT INTO harness_queue VALUES("case","running")')
        self.db.commit()
        self.db.execute('BEGIN IMMEDIATE')
        self.assertFalse(b.apply(self.db, plan, root=self.root)[1]['released'])
        self.db.rollback()

    def test_unsupported_source_and_font_canvas_failures_are_not_released(self):
        for reason in ['unsupported_source_feature', 'source_profile_validation_error', 'actual_font_portability_requires_embedding', 'Native content outside page']:
            report = self.report()
            report['checks'] = {'source': {'supported': True, 'ok': False, 'failures': [{'reason': reason}]}} if reason.startswith(('unsupported', 'source_profile')) else {}
            report['failures'] = [reason]
            self.audit(self.record, report)
            self.db.commit()
            self.assertFalse(self.plan()['ok'], reason)

    def test_genuine_native_marker_failure_is_supported(self):
        report = self.report()
        report['checks'] = {'native_marker_paint': {'supported': True, 'ok': False, 'failures': [{'reason': 'arrowhead_contour_mismatch'}]}}
        report['failures'] = ['native_marker_paint_failure: arrowhead_contour_mismatch']
        self.audit(self.record, report)
        self.db.commit()
        self.assertTrue(self.plan()['ok'])

    def test_other_labels_and_accepted_jobs_preserved(self):
        for state in ['held_for_quality_v2', 'held_for_canvas_v6', 'attempt_finished', 'held_for_source_v5', 'running', 'resolved']:
            self.db.execute('UPDATE harness_queue_v3 SET state=?', (state,))
            self.db.commit()
            self.assertFalse(self.plan()['ok'])
        self.db.execute("UPDATE harness_queue_v3 SET state='held_for_quality_v3'")
        self.db.execute("UPDATE jobs SET state='accepted'")
        self.db.commit()
        self.assertFalse(self.plan()['ok'])

    def test_pending_current_hash_and_exact_active_qa3_policy_required(self):
        for table, field, value in [('auto_quality_exceptions_v1', 'state', 'resolved'), ('auto_quality_exceptions_v1', 'route', 'deterministic_canvas_repair'), ('auto_quality_exceptions_v1', 'code_hash', 'wrong'), ('auto_quality_audits_v1', 'image_hash', 'wrong'), ('auto_quality_audits_v1', 'state', 'accepted')]:
            self.db.execute('SAVEPOINT mutation')
            self.db.execute('UPDATE ' + table + ' SET ' + field + '=?', (value,))
            self.assertFalse(self.plan()['ok'])
            self.db.execute('ROLLBACK TO mutation')
            self.db.execute('RELEASE mutation')
        self.assertFalse(b.prepare(self.db, 'case', policy='old-qa2', root=self.root)['ok'])
        self.assertFalse(b.prepare(self.db, 'case', policy=b.QA3+'different-active', root=self.root)['ok'])

    def test_report_and_authoritative_source_identity_checked(self):
        for key in ['id', 'policy', 'input_code_sha256', 'input_image_sha256', 'source_code_sha256', 'source_image_sha256']:
            report = self.report()
            original = copy.deepcopy(report)
            report[key] = 'wrong'
            self.db.execute('UPDATE auto_quality_audits_v1 SET record=?', (json.dumps(report),))
            self.db.commit()
            self.assertFalse(self.plan()['ok'], key)
            self.db.execute('UPDATE auto_quality_audits_v1 SET record=?', (json.dumps(original),))
            self.db.commit()
        self.db.execute('UPDATE jobs SET input_record=?', (json.dumps({'code_sha256':'wrong','image_sha256':self.record['source_image_sha256']}),))
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'authoritative_input'):
            self.plan()

    def test_mutated_xml_png_reference_or_source_refused(self):
        for name in ['diagram.drawio', 'image.png', 'original.png', 'source.tex']:
            path = self.root/'clean/case'/name
            old = path.read_bytes()
            path.write_bytes(old+b' changed')
            with self.assertRaisesRegex(ValueError, 'hash_changed'):
                self.plan()
            path.write_bytes(old)

    def test_same_serialization_revision_already_dispatched_is_not_released(self):
        first = self.plan()
        b.publish(self.db, first, root=self.root)
        xml = XML.replace('fontSize=12;fillColor=#fff;', 'fillColor=#fff;fontSize=12.0;').replace('<mxfile>', '<mxfile host="new">')
        self.db.execute("UPDATE harness_queue_v3 SET state='held_for_quality_v3'")
        r = json.loads(self.db.execute('SELECT output_record FROM jobs').fetchone()[0])
        r['code_sha256'] = b.core.sha(xml.encode())
        (self.root/r['code_file']).write_text(xml)
        self.db.execute('UPDATE jobs SET output_record=?', (json.dumps(r),))
        report = self.report()
        report['input_code_sha256'] = r['code_sha256']
        self.audit(r, report)
        self.db.commit()
        self.assertEqual(self.plan()['reason'], 'semantic_revision_already_dispatched')

    def test_apply_requires_transaction_and_no_filesystem_write(self):
        plan = self.plan()
        with self.assertRaises(RuntimeError):
            b.apply(self.db, plan, root=self.root)
        self.db.execute('BEGIN IMMEDIATE')
        with mock.patch.object(b, '_atomic', side_effect=AssertionError('unexpected filesystem write')):
            b.apply(self.db, plan, root=self.root)
        self.db.rollback()


if __name__ == '__main__':
    unittest.main()
