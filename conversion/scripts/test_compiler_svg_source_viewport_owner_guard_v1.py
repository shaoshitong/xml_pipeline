import json,os,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import compiler_svg_source_viewport_iteration_case_v1 as case
class OwnerGuardTests(unittest.TestCase):
 def test_no_claim_is_not_modified(self):self.assertEqual(case.canonical_owner_evidence(None)['decision'],'no_claim')
 def test_current_live_pid_is_deferred(self):
  if not Path('/proc/self/stat').is_file():self.skipTest('Linux proc control')
  self.assertEqual(case.canonical_owner_evidence(os.getpid())['decision'],'live_or_uncertain_defer')
 def test_definite_ENOENT_records_proc_mount_and_time(self):
  if not Path('/proc/self/stat').is_file():self.skipTest('Linux proc control')
  q=case.canonical_owner_evidence(99999999);self.assertEqual(q['decision'],'definite_dead_ENOENT');self.assertTrue(q['proc_mount']['readable']);self.assertEqual(q['proc_mount']['filesystem'],'proc');self.assertIn('checked_utc',q)
 def test_unreadable_proc_is_not_claimed_dead(self):
  with patch.object(case.Path,'read_text',side_effect=PermissionError('uncertain')):self.assertEqual(case.canonical_owner_evidence(123)['decision'],'live_or_uncertain_defer')
 def test_private_QA_copy_only_clears_worker_pid_and_preserves_raw_authority(self):
  if not Path('/proc/self/stat').is_file():self.skipTest('Linux proc control')
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);db=root/'authority.sqlite';job=('id','scientific_diagram','svg','dataset',json.dumps({'source':'entire nested record','nested':{'kept':True}}),'pending',None,0,None,None,None,'original manifest',99999999)
   with sqlite3.connect(db)as d:d.execute('create table jobs (id,category,format,source,input_record,state,route,attempts,updated_at,output_record,error,input_manifest,worker_pid)');d.execute('insert into jobs values (?,?,?,?,?,?,?,?,?,?,?,?,?)',job)
   private,proof,audit=case.quality_database(job,root,database=db)
   with sqlite3.connect(db)as d:self.assertEqual(d.execute('select * from jobs').fetchone(),job)
   with sqlite3.connect(private)as d:actual=d.execute('select * from jobs').fetchone()
   self.assertEqual(actual[:-1],job[:-1]);self.assertIsNone(actual[12]);self.assertEqual(proof['changed_columns'],['worker_pid']);self.assertEqual(proof['original_worker_pid'],99999999);self.assertEqual(json.loads(audit.read_bytes())['canonical_raw_row_sha256'],case.sha(case.raw(list(job))))
if __name__=='__main__':unittest.main()
