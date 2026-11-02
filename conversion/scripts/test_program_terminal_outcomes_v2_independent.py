"""Independent private-DB adversarial tests of the v2 publication boundary."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch

import bounded_program_terminal_planner_v1 as planner
import test_bounded_program_terminal_planner_v1 as fixtures
import program_terminal_outcomes_v2 as writer


class IndependentBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixtures.Guards.setUp(self)
        self.original_prepare=planner.prepare
        self.preparation_patch=patch.object(planner,'prepare',side_effect=lambda db,identifier,config:self.original_prepare(db,identifier,config,terminal_verifier=self.stub))
        self.preparation_patch.start();self.addCleanup(self.preparation_patch.stop)

    def plan(self):
        return self.original_prepare(self.db,self.identifier,self.config,terminal_verifier=self.stub)

    def snapshot(self):
        tables=[row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {table:self.db.execute('SELECT * FROM '+table).fetchall() for table in tables}

    def registry(self):
        return self.db.execute('SELECT * FROM processing_outcomes_v2 WHERE id=?',(self.identifier,)).fetchone()

    def disk_connection(self):
        path=self.root/'conversion/private_writer.sqlite';disk=sqlite3.connect(path,timeout=0)
        self.db.backup(disk);self.db=disk;self.addCleanup(disk.close);return path

    def mutation_before_writer_begin(self,mutation):
        real_begin=writer.begin;mutated=[]
        def begin(db,*args,**kwargs):
            if not mutated:
                self.assertFalse(db.in_transaction)
                mutation(db);mutated.append(True)
            return real_begin(db,*args,**kwargs)
        return patch.object(writer,'begin',side_effect=begin),mutated

    def assert_refused_without_outcome_change(self,plan,mutation):
        prior=self.registry();hook,mutated=self.mutation_before_writer_begin(mutation)
        with hook:result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertTrue(mutated,'The mutation must occur at the actual writer-admission hook')
        self.assertFalse(result['applied'],result);self.assertEqual(self.registry(),prior);self.assertFalse(self.db.in_transaction)
        return result

    def test_dryrun_changes_no_rows_or_files(self):
        plan=self.plan();before=self.snapshot();files=sorted(str(path) for path in self.root.rglob('*'));changes=self.db.total_changes
        result=writer.apply(self.db,plan,self.config)
        self.assertEqual(result['state'],'dry_run_current',result);self.assertTrue(result['would_apply']);self.assertFalse(result['applied']);self.assertEqual(self.db.total_changes,changes);self.assertEqual(self.snapshot(),before);self.assertEqual(sorted(str(path) for path in self.root.rglob('*')),files)

    def test_crypto_and_receipt_fsync_are_strictly_outside_writer_transaction(self):
        plan=self.plan();real_witness=writer.file_witness;real_write=writer._write_receipt;real_fsync=writer.os.fsync;calls=[]
        def witnessing(*args,**kwargs):
            self.assertFalse(self.db.in_transaction,'crypto read ran inside a SQL transaction');calls.append('crypto');time.sleep(.002);return real_witness(*args,**kwargs)
        def writing(*args,**kwargs):
            self.assertFalse(self.db.in_transaction,'immutable decision was written inside writer transaction');calls.append('receipt');return real_write(*args,**kwargs)
        def syncing(fd):
            self.assertFalse(self.db.in_transaction,'fsync ran inside writer transaction');calls.append('fsync');return real_fsync(fd)
        with patch.object(writer,'file_witness',side_effect=witnessing),patch.object(writer,'_write_receipt',side_effect=writing),patch.object(writer.os,'fsync',side_effect=syncing):result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertTrue(result['applied'],result);self.assertIn('crypto',calls);self.assertIn('receipt',calls);self.assertIn('fsync',calls)

    def test_other_connection_can_hold_writer_lock_during_crypto_preparation(self):
        path=self.disk_connection();plan=self.plan();other=sqlite3.connect(path,timeout=0);self.addCleanup(other.close);real_witness=writer.file_witness;probed=[]
        def witnessing(*args,**kwargs):
            self.assertFalse(self.db.in_transaction)
            other.execute('BEGIN IMMEDIATE');probed.append(True);time.sleep(.002);other.rollback()
            return real_witness(*args,**kwargs)
        with patch.object(writer,'file_witness',side_effect=witnessing):result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertTrue(result['applied'],result);self.assertTrue(probed)

    def test_identical_bytes_replaced_inode_is_not_treated_as_verified_file(self):
        plan=self.plan();path=self.root/self.record['original_source_code'];prior=path.stat();raw=path.read_bytes()
        def mutate(db):
            temporary=path.with_suffix('.replacement');temporary.write_bytes(raw);temporary.replace(path);os.utime(path,ns=(prior.st_atime_ns,prior.st_mtime_ns));self.assertEqual(path.read_bytes(),raw);self.assertNotEqual(path.stat().st_ino,prior.st_ino)
        self.assert_refused_without_outcome_change(plan,mutate)

    def test_same_size_and_restored_mtime_still_detects_inplace_rewrite(self):
        plan=self.plan();path=self.root/self.record['original_source_code'];prior=path.stat();self.assertEqual(path.read_bytes(),b'original')
        def mutate(db):
            time.sleep(.002);path.write_bytes(b'ORIGINAL');os.utime(path,ns=(prior.st_atime_ns,prior.st_mtime_ns));current=path.stat();self.assertEqual(current.st_size,prior.st_size);self.assertEqual(current.st_mtime_ns,prior.st_mtime_ns);self.assertNotEqual(current.st_ctime_ns,prior.st_ctime_ns)
        self.assert_refused_without_outcome_change(plan,mutate)

    def test_current_quality_pass_added_after_historical_failure_preparation_refuses(self):
        self.db.execute("UPDATE auto_quality_audits_v1 SET policy='historical'");self.db.commit();historical=self.db.execute('SELECT state,record,updated_at FROM auto_quality_audits_v1').fetchone();self.config['equivalences']={'historical':{'fixture':True}}
        def historical_failure(*args):return {'kind':'failure_only_verified_TikZ_equivalence','policy':'current','historical_policy':'historical','snapshot':list(historical),'source_failure':self.audit['checks']['source'],'acceptance_certified':False}
        with patch.object(planner,'failure_proof',side_effect=historical_failure):
            plan=self.plan()
            def mutate(db):
                passed={**self.audit,'state':'accepted','accepted':True,'failures':[],'checks':{'source':{'supported':True,'ok':True,'failures':[]}}}
                db.execute('INSERT INTO auto_quality_audits_v1 VALUES(?,?,?,?,?,?,?)',(self.identifier,self.record['code_sha256'],self.record['image_sha256'],'current','accepted',json.dumps(passed),'new-pass'));db.commit()
                self.assertEqual(planner.revalidate(db,plan,self.config,check_files=False),'current','Fixture should expose the historical-only revalidation gap')
            self.assert_refused_without_outcome_change(plan,mutate)

    def test_unknown_idle_owner_appearing_after_preparation_refuses(self):
        self.db.execute('CREATE TABLE independent_stage(id,state,owner_pid)');self.db.execute('INSERT INTO independent_stage VALUES(?,?,?)',(self.identifier,'idle',None));self.db.commit();plan=self.plan()
        def mutate(db):db.execute('UPDATE independent_stage SET owner_pid=99');db.commit()
        self.assert_refused_without_outcome_change(plan,mutate)

    def test_new_unknown_stage_schema_and_owner_refuse(self):
        plan=self.plan()
        def mutate(db):db.execute('CREATE TABLE new_unknown_stage(id,state,owner_pid)');db.execute('INSERT INTO new_unknown_stage VALUES(?,?,?)',(self.identifier,'idle',99));db.commit()
        self.assert_refused_without_outcome_change(plan,mutate)

    def test_full_job_columns_include_manifest_omitted_by_old_planner_hash(self):
        self.db.execute('ALTER TABLE jobs ADD COLUMN input_manifest TEXT');self.db.execute('UPDATE jobs SET input_manifest=?',('{"baseline":true}',));self.db.commit();plan=self.plan()
        def mutate(db):
            db.execute('UPDATE jobs SET input_manifest=?',('{"changed":true}',));db.commit();self.assertEqual(planner.revalidate(db,plan,self.config,check_files=False),'current')
        self.assert_refused_without_outcome_change(plan,mutate);self.assertEqual(self.db.execute('SELECT input_manifest FROM jobs').fetchone()[0],'{"changed":true}')

    def test_job_schema_change_after_preparation_refuses(self):
        plan=self.plan()
        def mutate(db):db.execute('ALTER TABLE jobs ADD COLUMN future_owner TEXT');db.commit()
        self.assert_refused_without_outcome_change(plan,mutate)

    def test_trigger_side_effect_rolls_back_jobs_queue_and_history(self):
        self.db.execute('CREATE TABLE independent_history(id,record)');self.db.execute("CREATE TRIGGER unrelated_side_effect AFTER UPDATE ON processing_outcomes_v2 BEGIN UPDATE jobs SET error='bad'; INSERT INTO harness_queue_v3 VALUES('side-effect','held',NULL); INSERT INTO independent_history VALUES('side-effect','bad'); END");self.db.commit();plan=self.plan();before=self.snapshot();result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertFalse(result['applied'],result);self.assertEqual(self.snapshot(),before);self.assertFalse(self.db.in_transaction)

    def test_filesystem_only_trigger_is_caught_by_precommit_identity_recheck(self):
        source=self.root/self.record['original_source_code'];calls=[]
        def touch_source():
            time.sleep(.002);source.write_bytes(b'ORIGINAL');calls.append(True);return 0
        self.db.create_function('independent_touch_source',0,touch_source);self.db.execute('CREATE TRIGGER filesystem_only AFTER UPDATE ON processing_outcomes_v2 BEGIN SELECT independent_touch_source(); END');self.db.commit();plan=self.plan();prior=self.registry();result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertEqual(calls,[True]);self.assertFalse(result['applied'],result);self.assertEqual(self.registry(),prior);self.assertIn('file_identity_changed',result['error']);self.assertFalse(self.db.in_transaction)

    def test_unknown_owner_without_state_column_is_also_refused(self):
        self.db.execute('CREATE TABLE no_state_owner(id,owner_pid)');self.db.execute('INSERT INTO no_state_owner VALUES(?,?)',(self.identifier,333));self.db.commit();plan=self.plan();before=self.snapshot();result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertFalse(result['applied'],result);self.assertEqual(self.snapshot(),before);self.assertIn('unverified_stage_owner:no_state_owner',result['error'])

    def test_commit_ack_loss_recovers_exact_nonce_without_second_update(self):
        plan=self.plan();real_commit=writer.commit;calls=[]
        def ack_lost(db,*args,**kwargs):
            calls.append(True);real_commit(db,*args,**kwargs);raise sqlite3.OperationalError('lost completion acknowledgement')
        with patch.object(writer,'commit',side_effect=ack_lost):result=writer.apply(self.db,plan,self.config,publish=True)
        self.assertEqual(len(calls),1);self.assertEqual(self.registry()[5],'abandoned');self.assertNotIn(result['state'],['failed_rolled_back','commit_outcome_unknown'],result)
        evidence=json.loads(self.registry()[7]);marker=evidence['program_terminal_outcome_v2'];nonce=marker.get('commit_nonce') or marker['decision'].get('commit_nonce');self.assertIsInstance(nonce,str);self.assertEqual(len(nonce),32)
        changes=self.db.total_changes;second=writer.apply(self.db,plan,self.config,publish=True);self.assertFalse(second['applied'],second);self.assertTrue(second.get('idempotent'),second);self.assertEqual(self.db.total_changes,changes)


if __name__=='__main__':unittest.main()
