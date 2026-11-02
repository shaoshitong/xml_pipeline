"""Private SQLite transaction/FS boundaries; no real QA render or model call."""
from pathlib import Path
import copy,json,sqlite3,tempfile,unittest
from unittest.mock import patch
import visual_failure_terminal_outcomes_v1 as writer
import visual_failure_route_guard_v1 as guard
import test_visual_failure_route_guard_v1 as fixture
class WriterTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.GuardTests('test_real_capture_and_full_shape');self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root;self.db=self.f.db;self.id=self.f.id;self.root.joinpath('conversion/prototype/visual_failure_terminal_private_v1').mkdir(parents=True);self.private=self.root/'conversion/prototype/visual_failure_terminal_private_v1'/'a'*0 if False else self.root/'conversion/prototype/visual_failure_terminal_private_v1'/('1'*32);self.private.mkdir();self.config={'root':str(self.root),'decision_root':str(self.root),'private_validation_only':False,'policy':writer.POLICY,'guard':self.f.config,'pins':{},'qa_policy':self.f.qpolicy,'writer_begin_seconds':.2,'writer_commit_seconds':.2};self.case=self.root/'conversion/prototype/visual_failure_certificate_v1/finite_runs'/('2'*32)/'cases'/self.id/'case_result.json';self.case.parent.mkdir(parents=True);self.case.write_bytes(b'fixture_effective');self.evidence=self.case.parent/'report.json';self.evidence.write_bytes(b'fresh report');self.metric={'ok':False,'failures':['foreground_tile_p10_below_0.72'],'thresholds':{'ssim':.90,'tile_p10':.72,'foreground_precision_recall':.90,'each_text_line_ssim':.55}};self.bundle={'id':self.id,'files':{str(self.case):{'sha256':writer.sha(self.case.read_bytes()),'bytes':self.case.stat().st_size},str(self.evidence):{'sha256':writer.sha(self.evidence.read_bytes()),'bytes':self.evidence.stat().st_size}},'fresh_certificate':{'file':str(self.evidence),'sha256':writer.sha(self.evidence.read_bytes()),'certificate_sha256':'f'*64},'effective_case':{'file':str(self.case),'sha256':writer.sha(self.case.read_bytes())},'supervisor_state':{'file':str(self.case),'sha256':writer.sha(self.case.read_bytes())},'supervisor_request':{'file':str(self.case),'sha256':writer.sha(self.case.read_bytes())},'supervisor_manifest':{'file':str(self.case),'sha256':writer.sha(self.case.read_bytes())}}
  # These two seams stand in only for existing renderer-evidence reading and
  # fidelity computation. Real guard/SQL/full snapshots/crypto/durability run.
  self.patches=[patch.object(writer,'_effective_files',return_value=self.bundle),patch.object(writer,'_independent',side_effect=lambda *a:(copy.deepcopy(self.metric),{}, {'schema':writer.INDEPENDENT_SCHEMA,'id':self.id,'metrics':copy.deepcopy(self.metric),'no_renderer_or_model_invoked':True}))]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def prepare(self,publish=False):self.db.commit();return writer.prepare_decision(self.db,self.case,self.config,publish)
 def test_dry_run_preserves_all_rows_and_pair(self):
  before=list(self.db.iterdump());p=self.prepare();r=writer.apply_prepared(self.db,p,self.config);self.assertEqual(r['state'],'dry_run_current',r);self.assertEqual(list(self.db.iterdump()),before);self.assertFalse((self.root/writer.DIRECTORY).exists());self.assertIs(p['document']['native_editing']['ok'],None)
 def test_exactly_one_outcome_and_immutable_nonce_receipt(self):
  before_job=self.db.execute('select * from jobs').fetchall();p=self.prepare(True);raw=(self.root/p['receipt']['file']).read_bytes();self.assertEqual(writer.sha(raw),p['receipt']['sha256']);self.assertEqual(writer.canonical(p['document']),raw);self.assertEqual((self.root/p['receipt']['file']).stat().st_mode&0o777,0o444);r=writer.apply_prepared(self.db,p,self.config);self.assertTrue(r['applied'],r);self.assertEqual(self.db.execute('select * from jobs').fetchall(),before_job);self.assertEqual(writer._registry(self.db,self.id),p['expected']);self.assertEqual(json.loads(p['expected'][6])[writer.MARKER]['commit_nonce'],p['receipt']['commit_nonce']);self.assertIn('visual_gate_failure',p['expected'][5]);self.assertNotIn('semantics',p['expected'][5]);self.assertTrue(json.loads(p['expected'][6])['deterministic_recovery_permitted'])
 def test_complete_nonjob_row_and_empty_table_CAS(self):
  p=self.prepare(True);self.db.execute('create table new_empty(id text,state text)');self.db.commit();r=writer.apply_prepared(self.db,p,self.config);self.assertEqual(r['state'],'failed_rolled_back');self.assertIn('CAS',r['error']);self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_job_metadata_change_refuses(self):
  p=self.prepare(True);self.db.execute('update jobs set error="new error"');self.db.commit();r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_foreign_owner_after_preparation_does_not_get_cleared(self):
  p=self.prepare(True);self.db.execute('insert into stage values(?,?,?,?,?)',(self.id,'f'*64,'running',989,'keep'));self.db.commit();r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertEqual(self.db.execute('select owner_pid from stage').fetchone()[0],989)
 def test_asset_mutation_refuses_before_SQL_update(self):
  p=self.prepare(True);self.evidence.write_bytes(b'changed');r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertIn('identity_changed',r['error']);self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_logical_alias_retarget_refuses(self):
  original=self.root/'target';original.write_bytes(b'one');other=self.root/'other';other.write_bytes(b'one');link=self.root/'clean_link';link.symlink_to(original);self.f.record['alias']=str(link.relative_to(self.root));self.f.change_record(alias='clean_link');self.db.commit();p=self.prepare(True);p['witnesses']['logical_alias']=writer.shared.file_witness(self.root,'clean_link',writer.sha(b'one'));link.unlink();link.symlink_to(other);r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_registry_trigger_side_effect_rolls_back_everything(self):
  self.db.execute('create table trap(id text,value text)');self.db.execute('create trigger registry_side after update on processing_outcomes_v2 begin insert into trap values(new.id,"bad"); end');self.db.commit();p=self.prepare(True);r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertIn('trigger_side_effect',r['error']);self.assertEqual(self.db.execute('select * from trap').fetchall(),[]);self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_SQL_error_rolls_back_and_retains_source(self):
  self.db.execute('create trigger reject before update on processing_outcomes_v2 begin select raise(abort,"fixture error"); end');self.db.commit();p=self.prepare(True);r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertEqual(writer._registry(self.db,self.id)[4],'pending');self.assertFalse(self.db.in_transaction)
 def test_immutable_decision_directory_symlink_refused(self):
  (self.root/'elsewhere').mkdir();(self.root/'conversion/visual_failure_terminal_outcomes_v1').symlink_to(self.root/'elsewhere',target_is_directory=True)
  with self.assertRaises(OSError):self.prepare(True)
 def test_fsync_failure_never_opens_writer_transaction(self):
  with patch.object(writer.os,'fsync',side_effect=OSError('fixture fsync failure')):
   with self.assertRaises(OSError):self.prepare(True)
  self.assertEqual(writer._registry(self.db,self.id)[4],'pending');self.assertFalse(self.db.in_transaction)
 def test_canonical_state_qualified_abandoned_preserved(self):
  for status in ('qualified','abandoned'):
   self.db.execute('update processing_outcomes_v2 set status=?',(status,));self.db.commit();r=writer.apply(self.db,self.case,self.config,True);self.assertEqual(r['state'],'preserved_'+status);self.assertFalse(r['applied'])
 def test_unknown_config_changes_refuse_after_prepare(self):
  p=self.prepare(True);self.config['qa_policy']='different';r=writer.apply_prepared(self.db,p,self.config);self.assertFalse(r['applied']);self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_guard_current_route_change_refuses_preparation(self):
  self.f.change_record(route_on=True);self.db.commit()
  with self.assertRaisesRegex(ValueError,'route_or_owner_guard_refused'):self.prepare(True)
 def test_model_or_reserved_source_guard_refuses_before_hash(self):
  self.db.execute('insert into harness_queue_v3 values(?,?,?,?,?,?)',(self.id,'running',None,2,'keep','old'));self.db.commit()
  with self.assertRaisesRegex(ValueError,'route_or_owner_guard_refused'):self.prepare(True)
 def test_independent_recompute_failure_is_not_suppressed(self):
  with patch.object(writer,'_independent',side_effect=ValueError('now qualifies')):
   result=writer.apply(self.db,self.case,self.config,True)
  self.assertEqual(result['state'],'preparation_refused');self.assertEqual(writer._registry(self.db,self.id)[4],'pending')
 def test_seal_and_foreign_target_DB_protected(self):
  p=self.prepare();fake=dict(p);fake['_seal']=object()
  with self.assertRaises(ValueError):writer.apply_prepared(self.db,fake,self.config)
  other=sqlite3.connect(':memory:');self.addCleanup(other.close)
  with self.assertRaisesRegex(ValueError,'real_registry_database'):writer.apply_prepared(other,p,self.config)
 def test_private_clone_commits_only_isolated_registry(self):
  self.config.update(decision_root=str(self.private),private_validation_only=True);p=self.prepare(True);private=writer.clone_private_database(p,self.config);self.addCleanup(private.close);self.assertEqual(writer._snapshot(private,self.id),p['snapshot']);r=writer.apply_prepared(private,p,self.config);self.assertTrue(r['applied'],r);self.assertEqual(writer._registry(self.db,self.id)[4],'pending');self.assertEqual(writer._registry(private,self.id)[4],'abandoned');self.assertTrue(p['document']['private_validation_only'])
 def test_private_config_cannot_target_canonical_file(self):
  self.config.update(decision_root=str(self.private),private_validation_only=True);p=self.prepare(True)
  with self.assertRaisesRegex(ValueError,'wrong_registry_database'):writer.apply_prepared(self.db,p,self.config)
 def test_commit_ack_loss_recovers_only_exact_receipt(self):
  p=self.prepare(True);original=writer.BusyBudget.commit
  def lost(self,db):original(self,db);raise OSError('lost ACK after commit')
  with patch.object(writer.BusyBudget,'commit',lost):r=writer.apply_prepared(self.db,p,self.config)
  self.assertTrue(r['applied'],r);self.assertTrue(r['commit_receipt_recovered']);self.assertEqual(writer._registry(self.db,self.id),p['expected'])
if __name__=='__main__':unittest.main(verbosity=2)
