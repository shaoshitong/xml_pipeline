import json,os,signal,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import initial_conversion_process_v1 as m

@unittest.skipUnless(sys.platform=='linux','Linux pidfd required')
class ProcessTree(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.work=Path(self.tmp.name);self.prior=m.subreaper()
 def command(self,code,timeout=1,env=None):return m.run([sys.executable,'-u','-c',code],self.work,timeout,env)
 def check_clean(self,receipt):
  self.assertTrue(receipt['cleanup_complete'],receipt)
  self.assertFalse(m.children(os.getpid()))
  self.assertEqual(m.subreaper(),self.prior)
  for process in receipt['tracked_processes']:
   self.assertFalse(m.same_birth(process,m.identity(process['pid'])),process)
 def test_normal_success_logs_and_exit_code(self):
  r=self.command("import sys;print('out');print('err',file=sys.stderr)");self.assertTrue(r['ok']);self.assertEqual(r['returncode'],0);self.assertFalse(r['deadline_exceeded']);self.assertIn('out',Path(r['stdout_file']).read_text());self.assertIn('err',Path(r['stderr_file']).read_text());self.check_clean(r)
 def test_normal_failure_is_typed_not_deadline(self):
  r=self.command('import sys;sys.exit(7)');self.assertFalse(r['ok']);self.assertEqual(r['returncode'],7);self.assertFalse(r['deadline_exceeded']);self.check_clean(r)
 def test_deadline_root_receipt_has_birth_identity(self):
  r=self.command('import time;time.sleep(30)',timeout=.2);self.assertFalse(r['ok']);self.assertTrue(r['deadline_exceeded']);self.assertIsNotNone(r['root_process']['start_ticks']);self.assertLess(r['seconds'],4);self.check_clean(r)
 def test_escaped_setsid_grandchild_is_cleaned(self):
  grandchild="import os,signal,time;os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN);print('grandchild',os.getpid(),flush=True);time.sleep(30)"
  child="import subprocess,sys,time;subprocess.Popen([sys.executable,'-u','-c',"+repr(grandchild)+"]);time.sleep(30)"
  root="import subprocess,sys,time;subprocess.Popen([sys.executable,'-u','-c',"+repr(child)+"],start_new_session=True);time.sleep(30)"
  r=self.command(root,timeout=.45);self.assertTrue(r['deadline_exceeded']);self.assertGreaterEqual(len(r['tracked_processes']),3);self.assertTrue(any(p['session']!=r['root_process']['session'] for p in r['tracked_processes']));self.assertTrue(any(action.get('signal')==signal.SIGKILL and action.get('sent') for p in r['tracked_processes'] for action in p['actions']));self.check_clean(r)
 def test_term_resistant_child_requires_kill(self):
  child="import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
  root="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"],start_new_session=True);time.sleep(30)"
  r=self.command(root,timeout=.35);self.assertTrue(r['deadline_exceeded']);self.assertTrue(any(a.get('signal')==signal.SIGKILL and a.get('sent') for p in r['tracked_processes'] for a in p['actions']));self.check_clean(r)
 def test_normal_exit_does_not_leave_background_child(self):
  child="import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
  code="import subprocess,sys;subprocess.Popen([sys.executable,'-c',"+repr(child)+"],start_new_session=True)"
  r=self.command(code);self.assertTrue(r['ok']);self.assertFalse(r['deadline_exceeded']);self.assertGreaterEqual(len(r['tracked_processes']),2);self.check_clean(r)
 def test_double_fork_orphan_is_adopted_even_if_parent_exits_fast(self):
  daemon="import os,time,signal;from pathlib import Path;pid=os.fork();\nif pid==0:\n os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(\'daemon.ready\').write_text(str(os.getpid()));time.sleep(30)"
  code="import subprocess,sys,time;from pathlib import Path;subprocess.Popen([sys.executable,'-c',"+repr(daemon)+"],start_new_session=True)\nwhile not Path('daemon.ready').exists():time.sleep(.005)"
  r=self.command(code,timeout=2);self.assertTrue(r['ok']);daemon_pid=int((self.work/'daemon.ready').read_text());self.assertIn(daemon_pid,[p['pid'] for p in r['tracked_processes']]);self.check_clean(r)
 def test_existing_child_refused_and_never_signalled(self):
  existing=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
  try:
   with patch.object(m,'safe_signal',side_effect=AssertionError('Must not signal existing child')):r=self.command("raise RuntimeError('must not launch')")
   self.assertTrue(r['refused']);self.assertFalse(r['ok']);self.assertIsNone(r['root_process']);self.assertIn('preexisting children',r['error']);self.assertIsNone(existing.poll());self.assertEqual(m.subreaper(),self.prior)
  finally:existing.terminate();existing.wait(timeout=3)
 def test_birth_mismatch_never_signals_reused_numeric_pid(self):
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);fd=None
  try:
   born=m.identity(child.pid);fd=m.pidfd_open(child.pid,0);record={**born,'start_ticks':born['start_ticks']+1,'_pidfd':fd}
   with patch.object(m,'pidfd_send_signal') as sender:r=m.safe_signal(record,signal.SIGKILL)
   self.assertFalse(r['sent']);sender.assert_not_called();self.assertIsNone(child.poll())
  finally:
   if fd is not None:os.close(fd)
   child.terminate();child.wait(timeout=3)
 def test_missing_safe_pidfd_refuses_before_launch(self):
  with patch.object(m,'pidfd_open',side_effect=OSError('unsupported')):r=self.command("raise RuntimeError('must not launch')")
  self.assertTrue(r['refused']);self.assertIsNone(r['root_process']);self.assertFalse(r['ok']);self.check_clean(r)
 def test_invalid_deadline_refuses(self):
  r=self.command('pass',timeout=0);self.assertTrue(r['refused']);self.assertFalse(r['ok']);self.check_clean(r)
 def test_supplied_clean_environment(self):
  r=self.command("import os;print(os.environ['CASE_TEST'])",env={'CASE_TEST':'only-this-value'});self.assertTrue(r['ok']);self.assertIn('only-this-value',Path(r['stdout_file']).read_text());self.check_clean(r)
 def test_nonexistent_executable_is_launch_failure(self):
  r=m.run(['/does-not-exist/conversion-helper'],self.work,1);self.assertTrue(r['refused']);self.assertFalse(r['ok']);self.assertIsNone(r['root_process']);self.check_clean(r)
 def test_child_created_by_nonmain_thread_is_tracked(self):
  child="import time;time.sleep(30)"
  root="import subprocess,sys,threading,time\ndef launch():\n subprocess.Popen([sys.executable,'-c',"+repr(child)+"],start_new_session=True);time.sleep(30)\nt=threading.Thread(target=launch);t.start();time.sleep(30)"
  r=self.command(root,timeout=.3);self.assertGreaterEqual(len(r['tracked_processes']),2);self.check_clean(r)

if __name__=='__main__':unittest.main()
