import json
import sqlite3
import unittest

import auto_quality_legacy_batch_v3 as m


class LegacySelection(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('create table jobs(id primary key,state,worker_pid,output_record,input_record)')
        self.db.execute('create table harness_queue_v3(id primary key,state,worker_pid)')
        m.initialize_ledger(self.db)
        self.record = {'code_sha256': 'a'*64, 'image_sha256': 'b'*64}
        for identifier, state, owner, record in (
            ('automatic', 'accepted', None, {**self.record, 'automatic_quality_policy': 'verified'}),
            ('busy', 'accepted', 123, self.record),
            ('model', 'accepted', None, self.record),
            ('pending', 'rendered', None, self.record),
            ('unverified', 'accepted', None, self.record)):
            self.db.execute('insert into jobs values(?,?,?,?,?)', (identifier, state, owner, json.dumps(record), '{}'))
        self.db.execute("insert into harness_queue_v3 values('model','running',NULL)")
        self.db.commit()

    def test_only_unowned_unverified_legacy_is_selected(self):
        self.assertEqual(m.select(self.db, 'publish')[0], 'unverified')

    def test_diagnostic_receipt_does_not_suppress_real_publication(self):
        self.db.execute('insert into ' + m.TABLE + ' values(?,?,?,?,?,?,?,?,?)', ('unverified', 'a'*64, 'b'*64, m.quality.POLICY, 'diagnostic', 'qualified', 1, '{}', 'old'))
        self.assertIsNone(m.select(self.db, 'diagnostic'))
        self.assertEqual(m.select(self.db, 'publish')[0], 'unverified')

    def test_completed_revision_not_repeated_but_new_revision_is_selected(self):
        self.db.execute('insert into ' + m.TABLE + ' values(?,?,?,?,?,?,?,?,?)', ('unverified', 'a'*64, 'b'*64, m.quality.POLICY, 'publish', 'repair_required', 1, '{}', 'old'))
        self.assertIsNone(m.select(self.db, 'publish'))
        self.db.execute('update jobs set output_record=? where id=?', (json.dumps({**self.record, 'code_sha256': 'c'*64}), 'unverified'))
        self.assertEqual(m.select(self.db, 'publish')[0], 'unverified')

    def test_previous_model_generation_claim_is_excluded(self):
        self.db.execute('create table harness_queue_v2(id primary key,state)')
        self.db.execute("insert into harness_queue_v2 values('unverified','running')")
        self.assertIsNone(m.select(self.db, 'publish'))


if __name__ == '__main__':
    unittest.main()
