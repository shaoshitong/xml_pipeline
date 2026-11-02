"""Independent boundary/restart regressions for publication and legacy review.

Only synthetic files and isolated SQLite databases are mutated. No production
jobs, queue rows or dataset payloads are read/modified by these tests.
"""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auto_quality_publication_v3 as publication
import auto_quality_legacy_batch_v3 as legacy
from auto_quality_dispatch_v2 import initialize as initialize_dispatch

sha=lambda blob:hashlib.sha256(blob).hexdigest()
XML=b'<mxfile><diagram><mxGraphModel pageWidth="100" pageHeight="80"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="A" style="shape=text;"><mxGeometry x="10" y="10" width="20" height="20" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'


class PublicationBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.work=self.root/'conversion/proof';self.work.mkdir(parents=True)
        self.pair=self.root/'clean/pair';self.pair.mkdir(parents=True)
        self.addCleanup(patch.stopall)
        patch.object(publication,'R',self.root).start();patch.object(publication,'W',self.root/'conversion').start()
        (self.pair/'diagram.drawio').write_bytes(XML);(self.pair/'image.png').write_bytes(b'old native png')
        self.record={'id':'one','source_pair_sha256':'one','source_format':'svg',
                     'code_file':'clean/pair/diagram.drawio','code_sha256':sha(XML),
                     'image_file':'clean/pair/image.png','image_sha256':sha(b'old native png'),
                     'source_code_sha256':'a'*64,'source_image_sha256':'b'*64}
        self.raw=json.dumps(self.record);self.metadata=b'original exact metadata bytes\n';(self.pair/'conversion.json').write_bytes(self.metadata)
        self.item=('one','accepted',self.raw,'original-input-record','native')
        self.fresh=b'fresh verified native png';(self.work/'fresh.png').write_bytes(self.fresh)
        self.out={**self.record,'image_file':'clean/pair/image.native.new.png','image_sha256':sha(self.fresh),'automatic_quality_policy':'review-test'}
        self.report={'id':'one','state':'qualified','accepted':False,'failures':[]}
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE jobs(id PRIMARY KEY,state,output_record,input_record,worker_pid,updated_at,error,input_manifest);
        CREATE TABLE auto_quality_exceptions_v1(id,code_hash,image_hash,policy,route,state,reason,updated_at,PRIMARY KEY(id,code_hash,image_hash,policy));
        CREATE TABLE auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at,PRIMARY KEY(id,code_hash,image_hash,policy));
        CREATE TABLE harness_queue_v3(id PRIMARY KEY,state,attempts,priority,worker_pid,started_at,heartbeat,session_dir,error);''')
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',('one','accepted',self.raw,self.item[3],None,'before','prior-error','prepared'))
        self.db.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?,?,?,?)',('one','held_for_quality_v2',7,9,None,'start','beat','historic-session','old-model-error'))
        initialize_dispatch(self.db);self.db.commit()
    def run_publish(self):
        publication.publish(self.db,self.item,self.report,self.out,self.work,True,'review-policy')
    def assert_original(self):
        self.assertEqual((self.pair/'diagram.drawio').read_bytes(),XML)
        self.assertEqual((self.pair/'image.png').read_bytes(),b'old native png')
        self.assertEqual((self.pair/'conversion.json').read_bytes(),self.metadata)
        self.assertEqual(self.db.execute('SELECT state,output_record FROM jobs').fetchone(),('accepted',self.raw))
    def test_modified_fresh_png_is_rejected_before_acceptance(self):
        (self.work/'fresh.png').write_bytes(b'changed after verifier completed')
        with self.assertRaises((ValueError,AssertionError)):
            self.run_publish()
        self.assert_original()
        self.assertEqual(self.db.execute('SELECT count(*) FROM auto_quality_audits_v1').fetchone()[0],0)
    def test_output_source_identity_cannot_change_during_publication(self):
        self.out={**self.out,'source_code_sha256':'f'*64}
        with self.assertRaises((ValueError,AssertionError)):
            self.run_publish()
        self.assert_original()
    def test_qualified_output_xml_hash_is_rechecked(self):
        self.out={**self.out,'code_sha256':'f'*64}
        with self.assertRaises((ValueError,AssertionError)):
            self.run_publish()
        self.assert_original()
    def test_legacy_model_queue_without_owner_column_blocks_publication(self):
        self.db.execute('CREATE TABLE harness_queue(id PRIMARY KEY,state)')
        self.db.execute('INSERT INTO harness_queue VALUES("one","running")');self.db.commit()
        self.run_publish()
        self.assertEqual(self.report['state'],'stale_revision');self.assert_original()
    def test_legacy_model_owner_blocks_even_finished_queue_label(self):
        self.db.execute('CREATE TABLE harness_queue_v2(id PRIMARY KEY,state,worker_pid)')
        self.db.execute('INSERT INTO harness_queue_v2 VALUES("one","attempt_finished",77)');self.db.commit()
        self.run_publish()
        self.assertEqual(self.report['state'],'stale_revision');self.assert_original()
    def test_failed_visual_dispatch_and_metadata_all_roll_back_on_sql_error(self):
        self.out=None;self.report.update(state='repair_required',failures=['raster_anomaly: local_text_line_ssim_below_0.55'],checks={'visual':{'ok':False,'failures':['local_text_line_ssim_below_0.55'],'worst_text_regions':[]}})
        before_queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchall()
        self.db.execute("CREATE TRIGGER fail_jobs BEFORE UPDATE ON jobs BEGIN SELECT RAISE(ABORT,'injected jobs failure'); END");self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_publish()
        self.assert_original()
        self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchall(),before_queue)
        self.assertEqual(self.db.execute('SELECT count(*) FROM auto_quality_model_dispatch_v2').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM auto_quality_exceptions_v1').fetchone()[0],0)
    def test_foreign_metadata_write_is_not_rolled_back_over_our_replacement(self):
        atomic=publication.atomic
        def write_then_foreign(path,data):
            atomic(path,data)
            if Path(path)==self.pair/'conversion.json':
                (self.pair/'conversion.json').write_bytes(b'foreign metadata after ours')
                raise OSError('simulated concurrent metadata writer')
        with patch.object(publication,'atomic',side_effect=write_then_foreign):
            with self.assertRaises(OSError):self.run_publish()
        self.assertEqual((self.pair/'conversion.json').read_bytes(),b'foreign metadata after ours')
        self.assertEqual(self.db.execute('SELECT output_record FROM jobs').fetchone()[0],self.raw)


class LegacyRestartBoundaries(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE jobs(id PRIMARY KEY,state,worker_pid,output_record,input_record)')
        self.db.execute('CREATE TABLE harness_queue_v3(id PRIMARY KEY,state,worker_pid)')
        legacy.initialize_ledger(self.db)
        self.record={'code_sha256':'a'*64,'image_sha256':'b'*64}
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',('one','accepted',None,json.dumps(self.record),'original-input'))
        self.db.commit()
    def receipt(self,state,owner,attempt=1):
        self.db.execute('INSERT INTO '+legacy.TABLE+' VALUES(?,?,?,?,?,?,?,?,?)',('one','a'*64,'b'*64,legacy.quality.POLICY,'publish',state,owner,json.dumps({'ledger_attempt':attempt}),'previous-run'));self.db.commit()
    def test_dead_owner_running_receipt_does_not_permanently_hide_legacy_pair(self):
        dead_pid=999999999
        self.assertFalse((Path('/proc')/str(dead_pid)).exists())
        self.receipt('running',dead_pid)
        recovered=legacy.recover_dead(self.db)
        self.assertEqual(recovered,[{'id':'one','state':'recovered_abandoned','old_owner_pid':dead_pid}])
        self.assertIsNotNone(legacy.select(self.db,'publish'))
    def test_retryable_worker_error_does_not_permanently_hide_legacy_pair(self):
        self.receipt('worker_error',999999999)
        self.assertIsNotNone(legacy.select(self.db,'publish'))
    def test_second_worker_error_is_bounded_and_not_retried(self):
        self.receipt('worker_error',999999999,attempt=2)
        self.assertIsNone(legacy.select(self.db,'publish'))
    def test_recovered_second_attempt_is_not_retried(self):
        self.receipt('running',999999999,attempt=2)
        self.assertEqual(legacy.recover_dead(self.db)[0]['state'],'recovered_abandoned')
        self.assertIsNone(legacy.select(self.db,'publish'))
    def test_live_legacy_coordinator_receipt_is_not_recovered(self):
        self.receipt('running',99)
        real_path=Path
        with tempfile.TemporaryDirectory() as directory:
            fake_proc=real_path(directory);p=fake_proc/'99/cmdline';p.parent.mkdir();p.write_bytes(b'python\0/owned/auto_quality_legacy_batch_v3.py\0--publish')
            with patch.object(legacy,'Path',side_effect=lambda path:fake_proc if str(path)=='/proc' else real_path(path)):
                self.assertEqual(legacy.recover_dead(self.db),[])
        self.assertEqual(self.db.execute('SELECT state FROM '+legacy.TABLE).fetchone()[0],'running')
        self.assertIsNone(legacy.select(self.db,'publish'))
    def test_committed_shared_receipt_is_recovered_without_repeating_verifier(self):
        self.receipt('running',999999999)
        self.db.execute('INSERT INTO auto_quality_audits_v1 VALUES(?,?,?,?,?,?,?)',('one','a'*64,'b'*64,legacy.quality.POLICY,'repair_required',json.dumps({'id':'one','state':'repair_required','accepted':False}),'committed'));self.db.commit()
        self.assertEqual(legacy.recover_dead(self.db)[0]['state'],'repair_required')
        self.assertIsNone(legacy.select(self.db,'publish'))
        self.assertEqual(json.loads(self.db.execute('SELECT record FROM '+legacy.TABLE).fetchone()[0])['ledger_attempt'],1)
    def test_previous_generation_running_and_owned_models_are_not_selected(self):
        for table,owner in [('harness_queue',False),('harness_queue_v2',True)]:
            self.db.execute('CREATE TABLE '+table+'(id PRIMARY KEY,state'+(',worker_pid' if owner else '')+')')
            self.db.execute('INSERT INTO '+table+' VALUES('+','.join('?' for _ in range(3 if owner else 2))+')',('one','attempt_finished',77) if owner else ('one','running'));self.db.commit()
            self.assertIsNone(legacy.select(self.db,'publish'))
            self.db.execute('DROP TABLE '+table);self.db.commit()
    def test_completed_diagnostic_does_not_block_publish_mode(self):
        self.db.execute('INSERT INTO '+legacy.TABLE+' VALUES(?,?,?,?,?,?,?,?,?)',('one','a'*64,'b'*64,legacy.quality.POLICY,'diagnostic','repair_required',999999999,'{}','previous-run'));self.db.commit()
        self.assertIsNotNone(legacy.select(self.db,'publish'))


if __name__=='__main__':
    unittest.main()
