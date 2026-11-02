"""Safe coordinator replacement: lineage isolation, old terminals and drain."""
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import auto_quality_glyph_alignment_batch_v3c as c

POLICY='glyph-v3c-test'


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.work=self.root/'conversion';self.work.mkdir()
        self.patches=[patch.object(c,'R',self.root),patch.object(c,'W',self.work),patch.object(c,'DRAIN',False)]
        for item in self.patches:item.start()
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,format TEXT,state TEXT,output_record TEXT,worker_pid INT,error TEXT,updated_at TEXT,input_record TEXT,input_manifest TEXT)')
        self.db.execute('CREATE TABLE auto_quality_exceptions_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,route TEXT,state TEXT,reason TEXT,updated_at TEXT)')
        self.db.execute('CREATE TABLE processing_outcomes_v2(id TEXT PRIMARY KEY,category TEXT,format TEXT,source_code_hash TEXT,source_image_hash TEXT,status TEXT,reason TEXT,record TEXT,updated_at TEXT)')
        self.db.execute('CREATE TABLE harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,attempts INT DEFAULT 0,priority INT DEFAULT 0,worker_pid INT,started_at TEXT,heartbeat TEXT,session_dir TEXT,error TEXT)')
        self.db.commit();c.init(self.db)
        self.old={'id':'case','source_pair_sha256':'case','category':'poster','source_format':'html','code_sha256':'c'*64,'image_sha256':'d'*64,
                  'source_code_sha256':'a'*64,'source_image_sha256':'b'*64,'code_file':'clean/case/old.drawio','image_file':'clean/case/old.png'}
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',('case','html','needs_quality_repair',json.dumps(self.old),None,'old-error','old-time','{}','old-manifest'))
        self.db.execute('INSERT INTO auto_quality_exceptions_v1 VALUES(?,?,?,?,?,?,?,?)',('case',self.old['code_sha256'],self.old['image_sha256'],'qa','source_geometry_or_harness','pending','local_text_line_ssim_below_0.55','old-qa-time'))
        self.db.execute('INSERT INTO processing_outcomes_v2 VALUES(?,?,?,?,?,?,?,?,?)',('case','poster','html','a'*64,'b'*64,'pending',None,None,'old-outcome-time'))
        self.db.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?,?,?,?)',('case','held_by_user_policy',7,42,None,'old-start','old-heart','old-session','old-model-error'))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for item in reversed(self.patches):item.stop()
        self.tmp.cleanup()

    def selection(self):return c.select_candidate(self.db,POLICY)
    def claim(self):return c.claim(self.db,self.selection(),POLICY,pid=111)

    def prior_table(self):
        self.db.execute('CREATE TABLE '+c.PRIOR_TABLE+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT)');self.db.commit()

    def test_layout_metadata_is_excluded_by_both_selector_and_claim_including_null_or_malformed(self):
        for field in [{'version':5},{},None]:
            old={**self.old,'html_text_layout_v5':field};raw=json.dumps(old);self.db.execute('UPDATE jobs SET output_record=?',(raw,));self.db.commit()
            self.assertIsNone(self.selection())
            forced=('case',tuple(c.snapshot(self.db,'case')))
            self.assertIsNone(c.claim(self.db,forced,POLICY,pid=111))

    def test_prior_glyph_metadata_is_also_immutable(self):
        old={**self.old,'html_actual_text_alignment':{'version':3}}
        self.db.execute('UPDATE jobs SET output_record=?',(json.dumps(old),));self.db.commit();self.assertIsNone(self.selection())

    def test_outcome_qualified_abandoned_missing_or_changed_source_blocks_claim(self):
        for status in ['qualified','abandoned']:
            self.db.execute('UPDATE processing_outcomes_v2 SET status=?',(status,));self.db.commit()
            self.assertIsNone(self.selection());self.assertIsNone(c.claim(self.db,('case',tuple(c.snapshot(self.db,'case'))),POLICY,pid=111))
        self.db.execute("UPDATE processing_outcomes_v2 SET status='pending',source_code_hash='changed'");self.db.commit();self.assertIsNone(self.selection())
        self.db.execute('DROP TABLE processing_outcomes_v2');self.db.commit();self.assertIsNone(self.selection())

    def test_v3b_terminal_revisions_are_reused_across_every_old_policy_hash(self):
        self.prior_table()
        for state in ['published_candidate','retained_prior_candidate','no_change_required','validated_dry_run','stale_revision_or_ownership','running']:
            self.db.execute('DELETE FROM '+c.PRIOR_TABLE)
            self.db.execute('INSERT INTO '+c.PRIOR_TABLE+' VALUES(?,?,?,?,?)',('case',self.old['code_sha256'],self.old['image_sha256'],'old-v3b-policy:'+state,state));self.db.commit()
            self.assertIsNone(self.selection(),state)
            self.assertIsNone(c.claim(self.db,('case',tuple(c.snapshot(self.db,'case'))),POLICY,pid=111),state)

    def test_old_other_revision_does_not_hide_a_new_current_revision(self):
        self.prior_table();self.db.execute('INSERT INTO '+c.PRIOR_TABLE+' VALUES(?,?,?,?,?)',('case','other-code',self.old['image_sha256'],'old','retained_prior_candidate'));self.db.commit()
        self.assertIsNotNone(self.selection())

    def test_old_deferred_paid_case_can_be_reconsidered_once_after_owner_is_gone(self):
        self.prior_table();self.db.execute('INSERT INTO '+c.PRIOR_TABLE+' VALUES(?,?,?,?,?)',('case',self.old['code_sha256'],self.old['image_sha256'],'old','deferred_model_running'));self.db.commit()
        self.assertIsNotNone(self.selection())

    def test_three_paid_queue_generations_and_idle_owned_rows_are_never_taken(self):
        for table in ['harness_queue','harness_queue_v2']:
            self.db.execute('CREATE TABLE '+table+'(id TEXT,state TEXT)');self.db.execute('INSERT INTO '+table+' VALUES("case","running")');self.db.commit()
            self.assertIsNone(self.selection());self.assertIsNone(c.claim(self.db,('case',tuple(c.snapshot(self.db,'case'))),POLICY,pid=111))
            self.db.execute('DROP TABLE '+table);self.db.commit()
        self.db.execute('UPDATE harness_queue_v3 SET worker_pid=77');self.db.commit();self.assertIsNone(self.selection())

    def test_new_terminal_outcome_after_build_does_not_publish_or_change_policy_hold(self):
        current=self.claim();queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone()
        self.db.execute("UPDATE processing_outcomes_v2 SET status='abandoned',reason='explicit root decision'");self.db.commit();calls=[]
        state=c.finish(self.db,current,{'accepted':False},{'fake':'candidate'},publish=True,artifact_writer=lambda *args:calls.append(1))
        self.assertEqual(state,'retained_prior_candidate');self.assertEqual(calls,[])
        self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue)
        self.assertEqual(json.loads(c.snapshot(self.db,'case')[1]),self.old)

    def test_sigusr1_shared_control_stops_new_claim_at_boundary(self):
        selected=self.selection();c.request_drain()
        control=json.loads((self.work/'auto_quality_glyph_alignment_v3c_control.json').read_text())
        self.assertTrue(control['drain']);self.assertIsNone(self.selection());self.assertIsNone(c.claim(self.db,selected,POLICY,pid=111))
        with patch.object(c,'DRAIN',False):self.assertTrue(c.draining(),'A different child must observe the shared control file')
        self.assertEqual(self.db.execute('SELECT count(*) FROM '+c.TABLE).fetchone()[0],0)

    def test_drain_does_not_interrupt_already_claimed_case_finish(self):
        current=self.claim();c.request_drain()
        self.assertEqual(c.finish(self.db,current,{'accepted':False}),'retained_prior_candidate')
        self.assertEqual(c.snapshot(self.db,'case')[0],'needs_quality_repair')
        self.assertIsNone(self.selection())

    def test_malformed_control_fails_closed_and_idle_worker_exits_without_generate(self):
        (self.work/'auto_quality_glyph_alignment_v3c_control.json').write_text('{invalid')
        self.assertTrue(c.draining());previous=signal.getsignal(signal.SIGUSR1)
        try:
            with patch.object(c,'generate',side_effect=AssertionError('must not generate during drain')):
                self.assertEqual(c.worker(0,0,False,[],POLICY,{})['processed'],0)
        finally:signal.signal(signal.SIGUSR1,previous)

    def test_old_beforeclaim_abort_rolls_back_ledger_and_new_state_uses_separate_name(self):
        self.db.execute("CREATE TRIGGER stop_old BEFORE UPDATE OF state ON jobs WHEN NEW.state='auto_quality_html_glyph_v3b_repairing' BEGIN SELECT RAISE(ABORT,'old coordinator drained'); END");self.db.commit()
        prior=c.snapshot(self.db,'case');self.prior_table()
        self.db.execute('BEGIN IMMEDIATE')
        self.db.execute('INSERT INTO '+c.PRIOR_TABLE+' VALUES(?,?,?,?,?)',('case',self.old['code_sha256'],self.old['image_sha256'],'old','running'))
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("UPDATE jobs SET state='auto_quality_html_glyph_v3b_repairing'")
        self.db.rollback();self.assertEqual(c.snapshot(self.db,'case'),prior);self.assertEqual(self.db.execute('SELECT count(*) FROM '+c.PRIOR_TABLE).fetchone()[0],0)
        current=self.claim();self.assertEqual(current['owned_snapshot'][0],'auto_quality_html_glyph_v3c_repairing')

    def test_frozen_generator_is_exactly_v3b_and_existing_files_are_not_modified(self):
        path=Path(c.__file__).with_name('auto_quality_glyph_candidate_generate_v3b.py')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),c.FROZEN_GENERATOR_SHA256)
        self.assertNotIn('auto_quality_glyph_candidate_generate_v3c.py',c.DEPENDENCIES)


if __name__=='__main__':unittest.main()
