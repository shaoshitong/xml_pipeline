import copy,io,json,os,sqlite3,stat,unittest
from pathlib import Path
from unittest.mock import patch
import bounded_program_terminal_planner_v1 as planner
import program_terminal_outcomes_v1 as writer
import test_bounded_program_terminal_planner_v1 as fixtures

class WriterTests(unittest.TestCase):
    def setUp(self):
        fixtures.Guards.setUp(self);self.original_prepare=planner.prepare
        self.clock_patch=patch.object(writer.planner,'now',return_value='2026-10-31T00:00:00Z');self.clock_patch.start();self.addCleanup(self.clock_patch.stop)
        self.prepare_patch=patch.object(writer.planner,'prepare',side_effect=lambda db,id,config:self.original_prepare(db,id,config,terminal_verifier=self.stub));self.prepare_patch.start();self.addCleanup(self.prepare_patch.stop)
    def plan(self):return self.original_prepare(self.db,self.identifier,self.config,terminal_verifier=self.stub)
    def snapshot(self):
        tables=[r[0] for r in self.db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")];return {table:self.db.execute('select * from '+table).fetchall() for table in tables}
    def decisions(self):return list((self.root/writer.DIRECTORY).rglob('decision.*.json'))
    def test_dryrun_checks_current_but_changes_no_database_or_files(self):
        plan=self.plan();before=self.snapshot();changes=self.db.total_changes;files=sorted(str(p) for p in self.root.rglob('*'));result=writer.apply(self.db,plan,self.config)
        self.assertEqual(result['state'],'dry_run_current');self.assertTrue(result['would_apply']);self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.db.total_changes,changes);self.assertEqual(sorted(str(p) for p in self.root.rglob('*')),files);self.assertFalse(self.db.in_transaction)
    def test_publish_only_changes_outcome_with_complete_immutable_replay_evidence(self):
        plan=self.plan();before=self.snapshot();original=copy.deepcopy(plan);result=writer.apply(self.db,plan,self.config,publish=True);self.assertEqual(result['state'],'abandoned',result);self.assertTrue(result['applied']);self.assertEqual(plan,original);after=self.snapshot()
        for table in before:
            if table!=writer.TABLE:self.assertEqual(after[table],before[table],table)
        row=self.db.execute('select status,reason,record from processing_outcomes_v2').fetchone();self.assertEqual(row[0],'abandoned');self.assertIn('current_frozen_program:',row[1]);evidence=json.loads(row[2]);self.assertTrue(evidence['deterministic_recovery_permitted']);self.assertTrue(evidence['abandonment_is_not_conversion_success']);self.assertEqual(evidence['new_model_calls'],0)
        for key in ('id','code_sha256','image_sha256','source_code_sha256','source_image_sha256'):self.assertEqual(evidence[key],plan['evidence'][key])
        receipt=result['decision'];path=self.root/receipt['file'];payload=path.read_bytes();self.assertEqual(writer.sha(payload),receipt['sha256']);document=json.loads(payload);self.assertEqual(document['plan'],plan);self.assertEqual(document['prior_outcome']['status'],'pending');self.assertEqual(document['plan_sha256'],writer.sha(writer.canonical(plan)));self.assertEqual(document['writer_sha256'],writer.sha(Path(writer.__file__).read_bytes()));self.assertEqual(writer.canonical(document),payload);self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o444);self.assertEqual(evidence['program_terminal_outcome_v1']['decision'],receipt)
    def test_repeated_identical_plan_is_zero_write_verified_idempotence(self):
        plan=self.plan();first=writer.apply(self.db,plan,self.config,True);self.assertTrue(first['applied']);before=self.snapshot();changes=self.db.total_changes;files=[(str(p),p.stat().st_ino,p.read_bytes()) for p in self.decisions()];second=writer.apply(self.db,plan,self.config,True);self.assertEqual(second['state'],'already_applied');self.assertTrue(second['idempotent']);self.assertFalse(second['applied']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.db.total_changes,changes);self.assertEqual([(str(p),p.stat().st_ino,p.read_bytes()) for p in self.decisions()],files)
    def test_qualified_or_other_abandonment_is_preserved(self):
        for status in ('qualified','abandoned'):
            plan=self.plan();self.db.execute('update processing_outcomes_v2 set status=?,reason=?,record=?',(status,'other reason','{}'));self.db.commit();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertEqual(result['state'],'preserved_'+status);self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.decisions(),[]);self.db.execute("update processing_outcomes_v2 set status='pending',reason=NULL,record=NULL");self.db.commit()
    def test_busy_job_and_paid_model_owner_are_never_touched(self):
        plan=self.plan()
        for mode in ('job','model'):
            if mode=='job':self.db.execute('update jobs set worker_pid=42')
            else:self.db.execute('insert into harness_queue_v3 values(?,?,?)',(self.identifier,'running',None))
            self.db.commit();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.decisions(),[])
            if mode=='job':self.db.execute('update jobs set worker_pid=NULL')
            else:self.db.execute('delete from harness_queue_v3')
            self.db.commit()
    def test_idle_unknown_stage_owner_is_refused_beyond_frozen_planner_guard(self):
        plan=self.plan();self.db.execute('create table another_stage(id,state,owner_pid)');self.db.execute('insert into another_stage values(?,?,?)',(self.identifier,'idle',99));self.db.commit();self.assertEqual(planner.revalidate(self.db,plan,self.config),'current');before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertIn('unverified_stage_owner',result['error']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.decisions(),[])
    def test_cas_stolen_after_fresh_prepare_before_transaction_is_refused(self):
        plan=self.plan();real_begin=writer.begin
        def steal(db,**kwargs):db.execute("update jobs set updated_at='stolen'");db.commit();return real_begin(db,**kwargs)
        with patch.object(writer,'begin',side_effect=steal):result=writer.apply(self.db,plan,self.config,True)
        self.assertFalse(result['applied']);self.assertEqual(self.db.execute('select status from processing_outcomes_v2').fetchone()[0],'pending');self.assertEqual(self.db.execute('select updated_at from jobs').fetchone()[0],'stolen');self.assertEqual(self.decisions(),[])
    def test_current_source_payload_mutation_blocks_existing_plan(self):
        plan=self.plan();(self.root/self.record['original_source_code']).write_bytes(b'new source');before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.decisions(),[])
    def test_active_owner_and_policy_mutations_are_refused(self):
        plan=self.plan();before=self.snapshot();(self.root/'conversion/auto_quality_owner.json').write_text('{"policy":"new"}');result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.decisions(),[])
        (self.root/'conversion/auto_quality_owner.json').write_text('{}');changed={**self.config,'policy':'new'};self.assertFalse(writer.apply(self.db,plan,changed,True)['applied'])
    def test_report_reason_or_identity_tampering_does_not_pass_valid_cas(self):
        plan=self.plan();damaged=copy.deepcopy(plan);damaged['evidence']['reason_code']='intrinsic_drawio_impossibility';self.assertEqual(planner.revalidate(self.db,damaged,self.config),'current');before=self.snapshot();result=writer.apply(self.db,damaged,self.config,True);self.assertFalse(result['applied']);self.assertIn('differs_from_fresh',result['error']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.decisions(),[])
    def test_changed_proof_during_receipt_write_rolls_back_and_retains_unreferenced_receipt(self):
        proof=self.root/'conversion/proof.json';proof.write_text('{}');self.config['pinned_files']={'conversion/proof.json':planner.sha(proof.read_bytes())};plan=self.plan();before=self.snapshot();real_write=writer._write_receipt
        def mutate(root,receipt,payload):real_write(root,receipt,payload);proof.write_text('{"changed":true}')
        with patch.object(writer,'_write_receipt',side_effect=mutate):result=writer.apply(self.db,plan,self.config,True)
        self.assertFalse(result['applied']);self.assertEqual(result['state'],'failed_rolled_back');self.assertEqual(self.snapshot(),before);self.assertEqual(len(self.decisions()),1);receipt_path=self.decisions()[0];inode=receipt_path.stat().st_ino;proof.write_text('{}');retry=writer.apply(self.db,plan,self.config,True);self.assertTrue(retry['applied'],retry);self.assertEqual(receipt_path.stat().st_ino,inode)
    def test_sql_abort_rolls_back_without_reporting_success(self):
        plan=self.plan();self.db.execute("create trigger reject_outcome before update on processing_outcomes_v2 begin select raise(ABORT,'test abort');end;");self.db.commit();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertEqual(result['state'],'failed_rolled_back');self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertFalse(self.db.in_transaction);self.assertEqual(len(self.decisions()),1)
    def test_trigger_attempt_to_write_jobs_queue_or_history_rolls_back_all_tables(self):
        for table,statement in [('jobs',"update jobs set error='bad'"),('queue',"insert into harness_queue_v3 values('other','held',NULL)"),('history',"insert into model_history values('other','bad')")]:
            if table=='history':self.db.execute('create table model_history(id,record)')
            self.db.execute('create trigger side_effect after update on processing_outcomes_v2 begin '+statement+';end;');self.db.commit();plan=self.plan();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertIn('side_effect_refused',result['error']);self.assertEqual(self.snapshot(),before);self.db.execute('drop trigger side_effect');self.db.commit()
    def test_commit_failure_before_commit_rolls_back(self):
        plan=self.plan();before=self.snapshot()
        with patch.object(writer,'commit',side_effect=sqlite3.OperationalError('test commit failure')):result=writer.apply(self.db,plan,self.config,True)
        self.assertEqual(result['state'],'failed_rolled_back');self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertFalse(self.db.in_transaction)
    def test_commit_exception_after_commit_is_unknown_then_idempotently_resolved(self):
        plan=self.plan()
        def ambiguous(db,**kwargs):db.commit();raise sqlite3.OperationalError('lost completion response')
        with patch.object(writer,'commit',side_effect=ambiguous):result=writer.apply(self.db,plan,self.config,True)
        self.assertEqual(result['state'],'commit_outcome_unknown');self.assertFalse(result['applied']);self.assertTrue(result['may_have_committed']);self.assertEqual(writer.apply(self.db,plan,self.config,True)['state'],'already_applied')
    def test_existing_corrupt_receipt_is_never_overwritten(self):
        plan=self.plan();preview=writer.apply(self.db,plan,self.config);path=self.root/preview['decision']['file'];path.parent.mkdir(parents=True);path.write_bytes(b'corrupt');before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertEqual(path.read_bytes(),b'corrupt');self.assertEqual(self.snapshot(),before)
    def test_owned_directory_symlink_cannot_create_receipts_in_another_directory(self):
        plan=self.plan();outside=self.root/'unowned';outside.mkdir();(self.root/writer.DIRECTORY).symlink_to(outside,target_is_directory=True);before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertEqual(list(outside.iterdir()),[]);self.assertEqual(self.snapshot(),before)
    def test_final_receipt_symlink_and_fsync_failure_preserve_registry(self):
        plan=self.plan();preview=writer.apply(self.db,plan,self.config);path=self.root/preview['decision']['file'];path.parent.mkdir(parents=True);outside=self.root/'unowned.json';outside.write_bytes(b'original');path.symlink_to(outside);before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertTrue(path.is_symlink());self.assertEqual(outside.read_bytes(),b'original');self.assertEqual(self.snapshot(),before);path.unlink()
        with patch.object(writer.os,'fsync',side_effect=OSError('test fsync failure')):result=writer.apply(self.db,plan,self.config,True)
        self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before);self.assertFalse(path.exists())
    def test_changed_abandoned_registry_row_is_preserved_without_idempotence_claim(self):
        plan=self.plan();self.assertTrue(writer.apply(self.db,plan,self.config,True)['applied']);self.db.execute("update processing_outcomes_v2 set reason='later decision'");self.db.commit();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertEqual(result['state'],'preserved_abandoned');self.assertFalse(result['idempotent']);self.assertEqual(self.snapshot(),before)
    def test_outcome_compare_and_swap_includes_previous_pending_reason(self):
        plan=self.plan();real_begin=writer.begin
        def steal(db,**kwargs):db.execute("update processing_outcomes_v2 set reason='new pending evidence'");db.commit();return real_begin(db,**kwargs)
        with patch.object(writer,'begin',side_effect=steal):result=writer.apply(self.db,plan,self.config,True)
        self.assertFalse(result['applied']);self.assertEqual(self.db.execute('select status,reason from processing_outcomes_v2').fetchone(),('pending','new pending evidence'));self.assertEqual(self.decisions(),[])
    def test_corrupt_receipt_or_changed_job_cannot_claim_idempotent_success(self):
        plan=self.plan();first=writer.apply(self.db,plan,self.config,True);path=self.root/first['decision']['file'];path.chmod(0o600);payload=path.read_bytes();path.write_bytes(b'corrupt');before=self.snapshot();self.assertEqual(writer.apply(self.db,plan,self.config,True)['state'],'preserved_abandoned');self.assertEqual(self.snapshot(),before);path.write_bytes(payload);self.db.execute("update jobs set updated_at='later'");self.db.commit();self.assertEqual(writer.apply(self.db,plan,self.config,True)['state'],'preserved_abandoned')
    def test_parent_transaction_is_preserved_and_publish_needs_real_boolean(self):
        plan=self.plan();self.db.execute('begin')
        with self.assertRaises(writer.Refused):writer.apply(self.db,plan,self.config,True)
        self.assertTrue(self.db.in_transaction);self.db.rollback()
        with self.assertRaises(writer.Refused):writer.apply(self.db,plan,self.config,'false')
    def test_history_pid_only_for_the_exact_verified_terminal_execution_receipt(self):
        self.db.execute('create table '+planner.STAGE+'('+planner.STAGE_COLUMNS+')');stage=(self.identifier,self.record['code_sha256'],self.record['image_sha256'],self.record['source_code_sha256'],self.record['source_image_sha256'],'exec','unsupported_source',55,'a'*32,'run',1,'{}','old');self.db.execute('insert into '+planner.STAGE+' values('+','.join('?'*len(stage))+')',stage);self.db.commit();self.config['execution_policy']='exec';self.stub=lambda *args:{'reason_code':'verified_semantic_fixture','source_construct_classes':['numeric_or_unbound_path_terminal'],'stage_table':planner.STAGE,'stage_snapshot_sha256':planner.json_sha(stage)};plan=self.plan();result=writer.apply(self.db,plan,self.config,True);self.assertTrue(result['applied'],result);receipt=json.loads((self.root/result['decision']['file']).read_bytes());self.assertTrue(receipt['historical_terminal_receipt_owners'][0]['historical_receipt_not_live_lease'])
    def test_terminal_stage_claim_change_is_stale(self):
        self.db.execute('create table '+planner.STAGE+'('+planner.STAGE_COLUMNS+')');stage=(self.identifier,self.record['code_sha256'],self.record['image_sha256'],self.record['source_code_sha256'],self.record['source_image_sha256'],'exec','unsupported_source',55,'a'*32,'run',1,'{}','old');self.db.execute('insert into '+planner.STAGE+' values('+','.join('?'*len(stage))+')',stage);self.db.commit();self.config['execution_policy']='exec';self.stub=lambda *args:{'reason_code':'verified_semantic_fixture','stage_table':planner.STAGE,'stage_snapshot_sha256':planner.json_sha(stage)};plan=self.plan();self.db.execute('update '+planner.STAGE+' set claim_token=?',('b'*32,));self.db.commit();before=self.snapshot();result=writer.apply(self.db,plan,self.config,True);self.assertFalse(result['applied']);self.assertEqual(self.snapshot(),before)
    def test_cli_default_is_dryrun_and_uses_only_report_ids_for_fresh_preparation(self):
        plan=self.plan();tampered=copy.deepcopy(plan);tampered['evidence']['reason_code']='forged report';report=self.root/'report.json';report.write_text(json.dumps({'plans':[tampered]}));path=self.root/'conversion/jobs.sqlite';target=sqlite3.connect(path);self.db.backup(target);target.close();before=path.read_bytes()
        with patch.object(writer.planner,'configuration',return_value=self.config),patch('sys.stdout',new_callable=io.StringIO):status=writer.main(['--root',str(self.root),'--report',str(report)])
        self.assertEqual(status,0);self.assertEqual(path.read_bytes(),before);self.assertEqual(self.decisions(),[])
    def test_cli_publish_is_explicit_and_discards_tampered_report_evidence(self):
        plan=self.plan();tampered=copy.deepcopy(plan);tampered['evidence']['reason_code']='forged report';report=self.root/'report.json';report.write_text(json.dumps({'plans':[tampered]}));path=self.root/'conversion/jobs.sqlite';target=sqlite3.connect(path);self.db.backup(target);target.close()
        with patch.object(writer.planner,'configuration',return_value=self.config),patch('sys.stdout',new_callable=io.StringIO):status=writer.main(['--root',str(self.root),'--report',str(report),'--publish'])
        self.assertEqual(status,0);target=sqlite3.connect(path)
        try:status,raw=target.execute('select status,record from processing_outcomes_v2').fetchone()
        finally:target.close()
        self.assertEqual(status,'abandoned');self.assertEqual(json.loads(raw)['reason_code'],'verified_semantic_fixture');self.assertEqual(len(self.decisions()),1)

if __name__=='__main__':unittest.main()
