import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import svg_analytic_private_QA_lease_v1 as lease
class PrivateLeaseTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve();self.db=self.root/'canonical.sqlite';self.work=self.root/'work';self.work.mkdir();self.job=('id','scientific_diagram','svg','provider',json.dumps({'raw':'complete','nested':{'retained':True}}),'pending','route',3,'2026-01-01T00:00:00Z','baseline','error','full manifest',99999999)
  with sqlite3.connect(self.db)as d:d.execute('create table jobs(id,category,format,source,input_record,state,route,attempts,updated_at,output_record,error,input_manifest,worker_pid)');d.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)',self.job)
 def prepare(self,status='stale_dead',allowed=True):
  with patch.object(lease,'diagnose',return_value=dict(status=status,conversion_allowed=allowed)):return lease.quality_database(self.job,self.work,database=self.db)
 def test_definite_dead_copy_changes_only_worker_pid(self):
  private,proof,audit=self.prepare();actual=lease.read_row(private,'id');self.assertEqual(actual[:-1],self.job[:-1]);self.assertIsNone(actual[-1]);self.assertEqual(lease.read_row(self.db,'id'),self.job);self.assertEqual(proof['changed_columns'],['worker_pid']);self.assertFalse(private.stat().st_mode&0o222);self.assertTrue(audit.is_file())
 def test_proved_birth_reuse_also_uses_private_copy(self):self.assertTrue(self.prepare('stale_pid_reused')[1]['private_copy'])
 def test_live_claim_stops_before_private_copy(self):
  with self.assertRaisesRegex(ValueError,'live_or_uncertain'):self.prepare('live_or_uncertain_owner',False)
  self.assertFalse((self.work/'canonical_owner_guard').exists());self.assertEqual(lease.read_row(self.db,'id'),self.job)
 def test_other_allowed_status_does_not_clear_nonnull_pid(self):
  with self.assertRaisesRegex(ValueError,'unproved_canonical_lease'):self.prepare('unknown',True)
 def test_unclaimed_row_uses_canonical_readonly_database(self):
  with sqlite3.connect(self.db)as d:d.execute('update jobs set worker_pid=NULL where id=?',('id',))
  self.job=tuple(list(self.job[:-1])+[None]);private,proof,audit=self.prepare('unclaimed');self.assertEqual(private,self.db);self.assertFalse(proof['private_copy']);self.assertIsNone(audit)
 def test_changed_canonical_row_rejected_before_copy(self):
  with sqlite3.connect(self.db)as d:d.execute('update jobs set input_record=? where id=?',('changed','id'))
  with self.assertRaisesRegex(RuntimeError,'raw13_changed'):self.prepare()
 def test_post_QA_live_owner_or_changed_canonical_cannot_publish(self):
  private,proof,_=self.prepare()
  with patch.object(lease,'diagnose',return_value=dict(conversion_allowed=False)):
   with self.assertRaisesRegex(ValueError,'became_live'):lease.verify_after_quality(self.job,private,proof,self.work)
  with sqlite3.connect(self.db)as d:d.execute('update jobs set output_record=? where id=?',('changed','id'))
  with self.assertRaisesRegex(RuntimeError,'raw13_changed'):lease.verify_after_quality(self.job,private,proof,self.work)
 def test_post_QA_proves_both_raw_rows_and_source_authority_unchanged(self):
  private,proof,_=self.prepare()
  with patch.object(lease,'diagnose',return_value=dict(conversion_allowed=True,status='stale_dead')):result=lease.verify_after_quality(self.job,private,proof,self.work)
  self.assertTrue(result['canonical_raw13_unchanged']);self.assertTrue(result['private_raw13_unchanged']);self.assertEqual(lease.read_row(self.db,'id'),self.job)
if __name__=='__main__':unittest.main()
