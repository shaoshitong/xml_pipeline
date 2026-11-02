import json
import sqlite3
import unittest
from processing_outcomes_v2 import sync


class OutcomeAccounting(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.execute('create table jobs(id primary key,category,format,input_record,state,output_record)')
        self.expected={'scientific_diagram':1,'poster':1}
        self.original={'code_sha256':'a'*64,'image_sha256':'b'*64}
        self.record={'id':'one','source_pair_sha256':'one','source_code_sha256':'a'*64,'source_image_sha256':'b'*64,
          'code_file':'clean/one/diagram.drawio','code_sha256':'c'*64,'image_file':'clean/one/image.native.png','image_sha256':'d'*64,
          'original_reference':'clean/one/original.png','original_source_code':'clean/one/original.drawio',
          'automatic_quality_policy':'verified-fixed-program','automatic_quality_audit':'conversion/audit.json'}
        self.db.execute('insert into jobs values(?,?,?,?,?,?)',('one','scientific_diagram','drawio',json.dumps(self.original),'accepted',json.dumps(self.record)))
        self.db.execute('insert into jobs values(?,?,?,?,?,?)',('two','poster','html',json.dumps(self.original),'accepted',json.dumps({'quality_state':'legacy'})))
        self.db.commit()
    def run_sync(self):return sync(self.db,self.expected)
    def test_every_original_is_recorded_but_legacy_is_pending(self):
        r=self.run_sync();self.assertEqual(r['outcomes'],{'pending':1,'qualified':1});self.assertFalse(r['completion_proven'])
    def test_idempotent_sync_does_not_rewrite_existing_qualification(self):
        self.run_sync();r=self.run_sync();self.assertEqual(r['qualified_revisions_updated'],0)
    def test_scope_loss_is_rejected(self):
        self.db.execute("delete from jobs where id='two'");self.db.commit()
        with self.assertRaises(AssertionError):self.run_sync()
    def test_changed_original_identity_is_not_overwritten(self):
        self.run_sync();self.db.execute('update jobs set input_record=? where id=?',(json.dumps({**self.original,'code_sha256':'f'*64}),'two'));self.db.commit()
        with self.assertRaises(AssertionError):self.run_sync()
        self.assertEqual(self.db.execute("select source_code_hash from processing_outcomes_v2 where id='two'").fetchone()[0],'a'*64)
    def test_abandonment_requires_explicit_reason(self):
        self.run_sync()
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("update processing_outcomes_v2 set status='abandoned' where id='two'")
    def test_changed_quality_revision_returns_to_pending(self):
        self.run_sync();self.db.execute("update jobs set state='needs_quality_repair' where id='one'");self.db.commit()
        self.assertEqual(self.run_sync()['outcomes'],{'pending':2})
    def test_abandoned_is_distinct_from_success(self):
        self.run_sync();self.db.execute("update processing_outcomes_v2 set status='abandoned',reason='source_reference_conflict_no_reliable_local_repair' where id='two'");self.db.commit()
        r=self.run_sync();self.assertEqual(r['outcomes'],{'abandoned':1,'qualified':1});self.assertFalse(r['completion_proven'])
    def test_untrusted_payload_path_is_rejected(self):
        self.db.execute('update jobs set output_record=? where id=?',(json.dumps({**self.record,'image_file':'raw/old.png'}),'one'));self.db.commit()
        with self.assertRaises(AssertionError):self.run_sync()
    def test_new_deterministic_candidate_invalidates_old_abandonment(self):
        self.run_sync()
        self.db.execute("update processing_outcomes_v2 set status='abandoned',reason='budget_exhausted',record=? where id='one'",(json.dumps(self.record),))
        self.db.execute("update jobs set state='needs_quality_repair',output_record=? where id='one'",(json.dumps({**self.record,'image_sha256':'e'*64}),));self.db.commit()
        self.assertEqual(self.run_sync()['outcomes'],{'pending':2})
        self.assertEqual(self.db.execute("select reason from processing_outcomes_v2 where id='one'").fetchone()[0],'abandoned_revision_changed_waiting_program_qa')


if __name__=='__main__':unittest.main()
