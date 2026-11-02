import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import auto_quality_publication_v4 as m
from auto_quality_common import sha
from auto_quality_dispatch_v2 import initialize


class Publication(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        m.R = Path(self.temporary.name)
        m.W = m.R / 'conversion'
        m.W.mkdir()
        self.folder = m.R / 'clean/pair'
        self.folder.mkdir(parents=True)
        (self.folder / 'diagram.drawio').write_bytes(b'<mxfile/>')
        (self.folder / 'image.png').write_bytes(b'previous-png')
        self.record = {'id': 'one', 'code_file': 'clean/pair/diagram.drawio', 'image_file': 'clean/pair/image.png', 'code_sha256': sha(b'<mxfile/>'), 'image_sha256': sha(b'previous-png')}
        (self.folder/'original.png').write_bytes(b'original-png')
        (self.folder/'original.html').write_bytes(b'original-source')
        self.record.update(source_pair_sha256='one',source='test',category='poster',source_format='html',original_reference='clean/pair/original.png',original_source_code='clean/pair/original.html',source_code_sha256=sha(b'original-source'),source_image_sha256=sha(b'original-png'))
        self.original={'source':'test','category':'poster','format':'html','code_sha256':self.record['source_code_sha256'],'image_sha256':self.record['source_image_sha256']}
        self.raw = json.dumps(self.record)
        self.metadata = b'old-metadata\n'
        (self.folder / 'conversion.json').write_bytes(self.metadata)
        self.item = ('one', 'accepted', self.raw, json.dumps(self.original), 'native')
        self.report = {'id': 'one', 'state': 'qualified', 'accepted': False, 'failures': []}
        self.out = {**self.record,'automatic_quality_policy':'test-policy', 'image_file': 'clean/pair/image.native.new.png', 'image_sha256': sha(b'new-png')}
        self.work = m.W / 'proof'
        self.work.mkdir()
        (self.work / 'fresh.png').write_bytes(b'new-png')
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('create table jobs(id primary key,state,output_record,input_record,worker_pid,updated_at,error,input_manifest)')
        self.db.execute('insert into jobs values(?,?,?,?,?,?,?,?)', ('one', 'accepted', self.raw, self.item[3], None, 'old', 'old-error', None))
        self.db.execute('create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at,primary key(id,code_hash,image_hash,policy))')
        self.db.execute('create table auto_quality_exceptions_v1(id,code_hash,image_hash,policy,route,state,reason,updated_at,primary key(id,code_hash,image_hash,policy))')
        self.db.execute('create table harness_queue_v3(id primary key,state,attempts,priority,worker_pid,started_at,heartbeat,session_dir,error)')
        self.db.execute('insert into harness_queue_v3 values(?,?,?,?,?,?,?,?,?)', ('one', 'held_for_source_v5', 2, 9, None, 'old', 'old', 'history', 'prior-error'))
        self.db.execute('create table auto_quality_dirty_v2(id primary key,payload_version)')
        self.db.execute("insert into auto_quality_dirty_v2 values('one',1)")
        self.db.execute("create trigger payload after update of output_record on jobs begin update auto_quality_dirty_v2 set payload_version=payload_version+1 where id=NEW.id;end")
        self.db.execute('create table processing_outcomes_v2(id primary key,source_code_hash,source_image_hash,status,reason,record,updated_at)')
        self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?)',('one',self.record['source_code_sha256'],self.record['source_image_sha256'],'pending',None,None,'old'))
        self.out['automatic_quality_audit']='conversion/proof/audit.json'
        initialize(self.db)
        self.db.commit()

    def publish(self, enabled=True):
        self.db.commit()
        m.publish(self.db, self.item, self.report, self.out, self.work, enabled, 'test-policy')
        self.assertEqual((self.folder / 'image.png').read_bytes(), b'previous-png')
        self.assertEqual((self.folder / 'diagram.drawio').read_bytes(), b'<mxfile/>')

    def stale(self):
        self.publish()
        self.assertEqual(self.report['state'], 'stale_revision')
        self.assertFalse(self.report['accepted'])
        self.assertEqual((self.folder / 'conversion.json').read_bytes(), self.metadata)
        self.assertFalse((self.folder / 'image.native.new.png').exists())

    def test_legacy_acceptance_upgrades_without_overwriting_pair(self):
        self.publish()
        self.assertTrue(self.report['accepted'])
        self.assertEqual(self.db.execute('select state from jobs').fetchone()[0], 'accepted')
        self.assertEqual((self.folder / 'image.native.new.png').read_bytes(), b'new-png')
        self.assertEqual(json.loads((self.folder / 'conversion.json').read_text()), self.out)
        self.assertEqual(self.db.execute('select state,attempts,priority,session_dir from harness_queue_v3').fetchone(), ('resolved', 2, 9, 'history'))

    def test_changed_authoritative_input_rejects(self):
        self.db.execute('update jobs set input_record=?', ('{"source":"changed"}',))
        self.stale()

    def test_changed_output_metadata_rejects(self):
        self.db.execute('update jobs set output_record=?', (json.dumps({**self.record, 'other': True}),))
        self.stale()

    def test_job_owner_rejects(self):
        self.db.execute('update jobs set worker_pid=12')
        self.stale()

    def test_changed_job_state_rejects(self):
        self.db.execute("update jobs set state='needs_quality_repair'")
        self.stale()

    def test_running_model_rejects_even_without_job_owner(self):
        self.db.execute("update harness_queue_v3 set state='running'")
        self.stale()
        self.assertEqual(self.db.execute('select state from harness_queue_v3').fetchone()[0], 'running')

    def test_model_owner_rejects_even_if_queue_label_not_running(self):
        self.db.execute('update harness_queue_v3 set worker_pid=19')
        self.stale()

    def test_previous_model_generation_running_rejects(self):
        self.db.execute('create table harness_queue_v2(id primary key,state)')
        self.db.execute("insert into harness_queue_v2 values('one','running')")
        self.stale()

    def test_sql_failure_restores_exact_metadata_and_job(self):
        self.db.execute("create trigger abort_update before update on jobs begin select raise(abort,'injected failure');end")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.publish()
        self.assertEqual((self.folder / 'conversion.json').read_bytes(), self.metadata)
        self.assertEqual((self.folder / 'image.png').read_bytes(), b'previous-png')
        self.assertEqual(self.db.execute('select output_record from jobs').fetchone()[0], self.raw)
        self.assertEqual(self.db.execute('select state from harness_queue_v3').fetchone()[0], 'held_for_source_v5')
        self.assertEqual(self.db.execute('select count(*) from auto_quality_audits_v1').fetchone()[0], 0)

    def test_changed_file_rejects_before_metadata_write(self):
        (self.folder / 'diagram.drawio').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual((self.folder / 'conversion.json').read_bytes(), self.metadata)

    def test_dry_run_preserves_payload_and_queue(self):
        self.publish(False)
        self.assertFalse(self.report['accepted'])
        self.assertFalse((self.folder / 'image.native.new.png').exists())
        self.assertEqual((self.folder / 'conversion.json').read_bytes(), self.metadata)
        self.assertEqual(self.db.execute('select state from harness_queue_v3').fetchone()[0], 'held_for_source_v5')

    def test_failed_legacy_fonts_enter_repair_and_retain_pair(self):
        self.report.update(state='repair_required', failures=['actual_font_portability_requires_embedding'])
        self.out = None
        self.publish()
        self.assertEqual(self.db.execute('select state from jobs').fetchone()[0], 'needs_quality_repair')
        self.assertEqual(self.db.execute('select route,state from auto_quality_exceptions_v1').fetchone(), ('deterministic_font_embedding', 'pending'))
        self.assertEqual((self.folder / 'conversion.json').read_bytes(), self.metadata)

    def test_unsupported_legacy_is_not_left_accepted(self):
        self.report.update(state='repair_required', failures=['source_profile_not_implemented: unsupported source'])
        self.out = None
        self.publish()
        self.assertEqual(self.db.execute('select state from jobs').fetchone()[0], 'needs_quality_repair')
        self.assertEqual(self.db.execute('select route from auto_quality_exceptions_v1').fetchone()[0], 'source_profile_extension')


    def test_geometry_failure_records_local_feedback_without_queue_dispatch(self):
        self.report.update(state='repair_required', failures=['source_coverage_failure: actual difference'])
        self.out=None
        self.db.execute("update jobs set input_manifest='release/manifest.jsonl'")
        self.publish()
        self.assertFalse(self.report['model_dispatch']['dispatched'])
        self.assertEqual(self.db.execute('select state,attempts from harness_queue_v3').fetchone(),('held_for_source_v5',2))
        self.assertEqual(self.db.execute('select count(*) from auto_quality_model_dispatch_v2').fetchone()[0],0)

    def test_publication_commits_cache_at_exact_new_payload_version(self):
        self.publish()
        row=self.db.execute('select payload_version,trusted,manifest_record from qualified_index_cache_v4').fetchone()
        self.assertEqual(row[:2],(2,1))
        self.assertEqual(self.db.execute('select status from processing_outcomes_v2').fetchone()[0],'qualified')
        self.assertEqual(json.loads(row[2])['image_sha256'],self.out['image_sha256'])

    def test_missing_outcome_identity_rolls_back_acceptance_and_cache(self):
        self.db.execute('delete from processing_outcomes_v2');self.db.commit()
        with self.assertRaises(ValueError):self.publish()
        self.assertEqual(self.db.execute('select output_record from jobs').fetchone()[0],self.raw)
        self.assertEqual((self.folder/'conversion.json').read_bytes(),self.metadata)

if __name__ == '__main__':
    unittest.main()
