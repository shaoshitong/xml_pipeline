import copy,json,sqlite3,stat,unittest
from pathlib import Path
from unittest.mock import patch
import program_terminal_outcomes_v2 as writer
import bounded_program_terminal_planner_v1 as planner
import test_bounded_program_terminal_planner_v1 as fixtures


class OutcomeV2Tests(unittest.TestCase):
    def setUp(self):
        fixtures.Guards.setUp(self);self.original_prepare=planner.prepare;self.patching=patch.object(planner,'prepare',side_effect=lambda db,id,config:self.original_prepare(db,id,config,terminal_verifier=self.stub));self.patching.start();self.addCleanup(self.patching.stop)
    def plan(self):return self.original_prepare(self.db,self.identifier,self.config,terminal_verifier=self.stub)
    def snapshot(self):return {row[0]:self.db.execute('SELECT * FROM '+row[0]).fetchall() for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    def test_default_dryrun_has_no_rows_files_or_writer_lock(self):
        plan=self.plan();before=self.snapshot();files=sorted(str(path) for path in self.root.rglob('*'));changes=self.db.total_changes;result=writer.apply(self.db,plan,self.config);self.assertEqual(result['state'],'dry_run_current',result);self.assertEqual(result['writer_lock_held_seconds'],0);self.assertEqual(result['transaction_kind'],'readonly_deferred');self.assertEqual(before,self.snapshot());self.assertEqual(changes,self.db.total_changes);self.assertEqual(files,sorted(str(path) for path in self.root.rglob('*')))
    def test_only_registry_changes_complete_version2_author_and_immutable_decision(self):
        plan=self.plan();before=self.snapshot();original=copy.deepcopy(plan);result=writer.apply(self.db,plan,self.config,True);self.assertEqual(result['state'],'abandoned',result);self.assertTrue(result['applied']);self.assertEqual(plan,original);after=self.snapshot()
        for table in before:
            if table!=writer.TABLE:self.assertEqual(before[table],after[table])
        receipt=result['decision'];path=self.root/receipt['file'];document=json.loads(path.read_bytes());self.assertEqual(document['version'],2);self.assertEqual(document['writer_policy'],writer.POLICY);self.assertEqual(document['writer_sha256'],writer.sha(Path(writer.__file__).read_bytes()));self.assertEqual(document['planner_sha256'],writer.sha(Path(planner.__file__).read_bytes()));self.assertEqual(document['plan'],plan);self.assertEqual(document['prior_outcome']['status'],'pending');self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o444);self.assertEqual(document['commit_nonce'],receipt['commit_nonce']);self.assertIn('jobs',document['preparation']['db_cas_snapshots']['tables']);self.assertTrue(document['preparation']['file_witnesses']);self.assertEqual(writer.canonical(document),path.read_bytes());self.assertLess(result['lock_body_seconds'],1)
    def test_exact_repeat_is_zero_write_and_preserves_receipt(self):
        plan=self.plan();first=writer.apply(self.db,plan,self.config,True);before=self.snapshot();changes=self.db.total_changes;path=self.root/first['decision']['file'];inode=path.stat().st_ino;second=writer.apply(self.db,plan,self.config,True);self.assertEqual(second['state'],'already_applied',second);self.assertEqual(self.db.total_changes,changes);self.assertEqual(self.snapshot(),before);self.assertEqual(path.stat().st_ino,inode)
    def test_changed_reason_does_not_reuse_valid_cas_for_different_semantics(self):
        plan=self.plan();plan['evidence']['reason_code']='intrinsically_impossible';before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertEqual(result['state'],'preparation_refused');self.assertIn('fresh',result['error']);self.assertEqual(self.snapshot(),before);self.assertFalse((self.root/writer.DIRECTORY).exists())
    def test_other_outcomes_are_preserved_without_decision_file(self):
        plan=self.plan()
        for status in ['qualified','abandoned']:
            self.db.execute('UPDATE processing_outcomes_v2 SET status=?,record=?',(status,'{}'));self.db.commit();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertEqual(result['state'],'preserved_'+status);self.assertEqual(self.snapshot(),before);self.assertFalse((self.root/writer.DIRECTORY).exists())
    def test_exact_historical_pgf_owner_is_preserved_and_other_terminal_owner_refused(self):
        self.db.execute('CREATE TABLE '+planner.STAGE+'('+planner.STAGE_COLUMNS+')');stage=(self.identifier,self.record['code_sha256'],self.record['image_sha256'],self.record['source_code_sha256'],self.record['source_image_sha256'],'exec','unsupported_source',55,'a'*32,'run',1,'{}','old');self.db.execute('INSERT INTO '+planner.STAGE+' VALUES('+','.join('?' for _ in stage)+')',stage);self.db.commit();self.config['execution_policy']='exec';self.stub=lambda *args:{'reason_code':'verified_semantic_fixture','source_construct_classes':['numeric_or_unbound_path_terminal'],'stage_table':planner.STAGE,'stage_snapshot_sha256':planner.json_sha(stage)};plan=self.plan();result=writer.apply(self.db,plan,self.config,True);self.assertTrue(result['applied'],result);document=json.loads((self.root/result['decision']['file']).read_bytes());self.assertTrue(document['historical_terminal_receipt_owners'][0]['historical_receipt_not_live_lease'])
    def test_receipt_fsync_failure_never_opens_writer_transaction(self):
        plan=self.plan();before=self.snapshot()
        with patch.object(writer.os,'fsync',side_effect=OSError('fixture fsync')),patch.object(writer,'begin',side_effect=AssertionError('must not begin')):result=writer.apply(self.db,plan,self.config,True)
        self.assertEqual(result['state'],'preparation_refused');self.assertEqual(self.snapshot(),before);self.assertFalse(self.db.in_transaction)
    def test_writer_rejects_parent_transaction_and_nonbool_publish(self):
        plan=self.plan();self.db.execute('BEGIN')
        with self.assertRaises(writer.Refused):writer.apply(self.db,plan,self.config,True)
        self.assertTrue(self.db.in_transaction);self.db.rollback()
        with self.assertRaises(writer.Refused):writer.apply(self.db,plan,self.config,'yes')
    def test_receipt_cannot_become_symlink_or_mutable_file_for_idempotence(self):
        plan=self.plan();result=writer.apply(self.db,plan,self.config,True);path=self.root/result['decision']['file'];payload=path.read_bytes();path.chmod(0o600);self.assertEqual(writer.apply(self.db,plan,self.config,True)['state'],'preserved_abandoned');path.chmod(0o444);self.assertEqual(writer.apply(self.db,plan,self.config,True)['state'],'already_applied');target=path.with_name('elsewhere.json');path.rename(target);path.symlink_to(target);self.assertEqual(writer.apply(self.db,plan,self.config,True)['state'],'preserved_abandoned');self.assertEqual(target.read_bytes(),payload)
    def test_real_readonly_database_dryrun_does_not_attempt_writer_begin(self):
        path=self.root/'private.sqlite';target=sqlite3.connect(path);self.db.backup(target);target.close();db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=0)
        try:
            plan=self.original_prepare(db,self.identifier,self.config,terminal_verifier=self.stub)
            with patch.object(writer,'begin',side_effect=AssertionError('RO dryrun must not begin writer')):result=writer.apply(db,plan,self.config)
            self.assertEqual(result['state'],'dry_run_current',result)
        finally:db.close()
    def test_planner_json_sha_never_runs_during_writer_phase_including_pgf_owner(self):
        self.db.execute('CREATE TABLE '+planner.STAGE+'('+planner.STAGE_COLUMNS+')');stage=(self.identifier,self.record['code_sha256'],self.record['image_sha256'],self.record['source_code_sha256'],self.record['source_image_sha256'],'exec','unsupported_source',55,'a'*32,'run',1,'{}','old');self.db.execute('INSERT INTO '+planner.STAGE+' VALUES('+','.join('?' for _ in stage)+')',stage);self.db.commit();self.config['execution_policy']='exec';self.stub=lambda *args:{'reason_code':'verified_semantic_fixture','stage_table':planner.STAGE,'stage_snapshot_sha256':planner.json_sha(stage)};plan=self.plan();active=[False];calls=[];real_begin=writer.begin;real_commit=writer.commit;real_hash=planner.json_sha;real_sha=writer.sha
        def hashing(value):self.assertFalse(active[0],'planner.json_sha under writer lock');calls.append(1);return real_hash(value)
        def hashing_v2(value):self.assertFalse(active[0],'writer.sha under writer lock');return real_sha(value)
        def beginning(*a,**kw):result=real_begin(*a,**kw);active[0]=True;return result
        def committing(*a,**kw):result=real_commit(*a,**kw);active[0]=False;return result
        with patch.object(planner,'json_sha',side_effect=hashing),patch.object(writer,'sha',side_effect=hashing_v2),patch.object(writer,'begin',side_effect=beginning),patch.object(writer,'commit',side_effect=committing):result=writer.apply(self.db,plan,self.config,True)
        self.assertTrue(result['applied'],result);self.assertGreater(len(calls),1);self.assertFalse(active[0])


if __name__=='__main__':unittest.main()
