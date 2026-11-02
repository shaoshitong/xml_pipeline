import unittest,tempfile,os
from pathlib import Path
import compiler_plantuml_engine_canonical_claim_v1 as c
class Claims(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.proc=Path(self.tmp.name);self.root=self.proc/'42';self.root.mkdir();(self.root/'cmdline').write_bytes(b'/usr/bin/python3\0-safe.py\0');(self.proc/'stat').write_text('btime 1000\n');self.job={'worker_pid':42,'updated_at':'1970-01-01T00:50:00+00:00','state':'converting'};self.live={'pid':42,'start_ticks':int(os.sysconf('SC_CLK_TCK')*500),'state':'S'}
 def tearDown(self):self.tmp.cleanup()
 def run_claim(self,observe=None):return c.diagnose(self.job,self.proc,observe or(lambda pid:dict(self.live)))
 def test_null_allowed(self):self.job['worker_pid']=None;self.assertEqual(self.run_claim()['status'],'unclaimed')
 def test_missing_proc_allowed(self):self.root.rmdir()if not list(self.root.iterdir())else (self.root/'cmdline').unlink();self.root.rmdir()if self.root.exists()else None;self.assertTrue(self.run_claim(lambda pid:None)['conversion_allowed'])
 def test_unreadable_existing_proc_deferred(self):self.assertEqual(self.run_claim(lambda pid:None)['status'],'uncertain')
 def test_zombie_claim_allowed(self):self.live['state']='Z';self.assertTrue(self.run_claim()['conversion_allowed'])
 def test_actual_live_process_deferred(self):self.assertFalse(self.run_claim()['conversion_allowed'])
 def test_birth_after_historical_claim_proves_reuse(self):self.job['updated_at']='1970-01-01T00:20:00+00:00';self.assertEqual(self.run_claim()['status'],'stale_pid_reused')
 def test_one_second_boundary_not_definitive_reuse(self):self.job['updated_at']='1970-01-01T00:24:59.500000+00:00';self.assertFalse(self.run_claim()['conversion_allowed'])
 def test_missing_timezone_not_proof(self):self.job['updated_at']='1970-01-01T00:00:00';self.assertFalse(self.run_claim()['conversion_allowed'])
 def test_invalid_timestamp_not_proof(self):self.job['updated_at']='broken';self.assertFalse(self.run_claim()['conversion_allowed'])
 def test_birth_race_deferred(self):values=iter([dict(self.live),{**self.live,'start_ticks':self.live['start_ticks']+1}]);self.assertEqual(self.run_claim(lambda pid:next(values))['reason'],'pid_birth_changed_during_observation')
 def test_malformed_claim_deferred(self):self.job['worker_pid']='42';self.assertFalse(self.run_claim()['conversion_allowed'])
 def test_no_canonical_mutation(self):before=dict(self.job);self.run_claim();self.assertEqual(before,self.job)
if __name__=='__main__':unittest.main(verbosity=2)
