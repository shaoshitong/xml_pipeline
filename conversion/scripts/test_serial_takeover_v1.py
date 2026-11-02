import importlib.util, pathlib, unittest
from unittest.mock import patch,Mock
p=pathlib.Path(__file__).with_name('serial_takeover_v1.py');s=importlib.util.spec_from_file_location('takeover',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def row(pid,ppid,argv,uid=1,birth=10,state='S'):
 return dict(pid=pid,ppid=ppid,argv=argv,uid=uid,birth=birth,state=state)
S=str(m.ROOT/'conversion/scripts')+'/'
class PlanTests(unittest.TestCase):
 def checkplan(self,rows):return m.plan({x['pid']:x for x in rows},own_pid=900,uid=1)
 def test_whole_original_pool_and_browser_family(self):
  x=self.checkplan([row(10,1,['python',S+'text_batch.py']),row(11,10,['python','spawn_main']),row(12,11,['node','helper.js']),row(13,12,['chrome']),row(99,1,['python','other.py'])]);self.assertEqual({a['pid'] for a in x['selected']},{10,11,12,13});self.assertEqual(x['roots'],[10])
 def test_foreign_uid_is_never_selected(self):
  x=self.checkplan([row(10,1,['python',S+'text_batch.py'],uid=2)]);self.assertFalse(x['selected'])
 def test_unknown_independent_script_blocks(self):
  x=self.checkplan([row(10,1,['python',S+'unknown.py'])]);self.assertEqual(x['unknown'][0]['pid'],10)
 def test_unknown_child_justified_by_parent(self):
  x=self.checkplan([row(10,1,['python',S+'text_batch.py']),row(11,10,['python',S+'unknown.py'])]);self.assertFalse(x['unknown']);self.assertEqual(len(x['selected']),2)
 def test_shell_substring_does_not_establish_ownership(self):
  x=self.checkplan([row(10,1,['bash','-c','python '+S+'text_batch.py'])]);self.assertFalse(x['selected']);self.assertFalse(x['unknown'])
 def test_c_substring_not_ownership(self):
  x=self.checkplan([row(10,1,['python','-c',"print('"+S+"text_batch.py')"])]);self.assertFalse(x['selected'])
 def test_own_ancestors_protected(self):
  x=self.checkplan([row(900,20,['python',S+'text_batch.py']),row(20,1,['python',S+'auto_quality_batch_v4b.py'])]);self.assertFalse(x['selected'])
 def test_reused_parent_birth_does_not_capture_child(self):
  k={10:row(10,1,['python'],birth=1)};m.collect_new_descendants(k,{10:row(10,1,['python'],birth=2),11:row(11,10,['chrome'])});self.assertNotIn(11,k)
 def test_late_descendants_recursive(self):
  k={10:row(10,1,['python'])};r={10:k[10],11:row(11,10,['node']),12:row(12,11,['chrome'])};m.collect_new_descendants(k,r);self.assertEqual(set(k),{10,11,12})
 def test_excluded_pid_and_other_gpu_script_untouched(self):
  x=m.plan({10:row(10,1,['python',S+'text_batch.py']),11:row(11,1,['python','/data/train.py'])},own_pid=900,uid=1,excluded=[10]);self.assertFalse(x['selected'])
 def test_other_root_similar_name_not_selected(self):
  x=self.checkplan([row(10,1,['python','/backup/other/conversion/scripts/text_batch.py'])]);self.assertFalse(x['selected'])
 def test_execute_refuses_unknown_before_signal(self):
  x=self.checkplan([row(10,1,['python',S+'unknown.py'])]);self.assertRaises(RuntimeError,m.execute,x,'/does-not-write')
 def test_orphan_known_renderer_is_covered(self):
  x=self.checkplan([row(10,1,['python',str(m.WORK/'rendering_paintbounds_strict/remote_render.py')])]);self.assertEqual(len(x['selected']),1)
 def test_orphan_unknown_task_path_blocks(self):
  x=self.checkplan([row(10,1,['node',str(m.WORK/'unknown.js')])]);self.assertEqual(len(x['unknown']),1)
 def test_send_uses_imported_pidfd_fallback(self):
  x=row(123,1,['python']);events=[]
  with patch.object(m,'same_birth',return_value=x),patch.object(m,'pidfd_open',return_value=77) as op,patch.object(m,'pidfd_send_signal') as send,patch.object(m.os,'close') as close:
   m.send(x,15,events);op.assert_called_once_with(123,0);send.assert_called_once_with(77,15,None,0);close.assert_called_once_with(77)
  self.assertEqual(events[0]['pid'],123)
 def test_birth_changed_after_pidfd_open_no_signal(self):
  x=row(123,1,['python']);events=[]
  with patch.object(m,'same_birth',side_effect=[x,None]),patch.object(m,'pidfd_open',return_value=77),patch.object(m,'pidfd_send_signal') as send,patch.object(m.os,'close') as close:
   m.send(x,15,events);send.assert_not_called();close.assert_called_once_with(77)
  self.assertEqual(events,[])
 def test_preflight_failure_before_any_control_or_signal(self):
  x={'unknown':[]}
  with patch.object(m,'signal_capability_preflight',side_effect=OSError('missing libc')),patch.object(m,'atomic') as write,patch.object(m,'send') as send:
   self.assertRaises(OSError,m.execute,x,'/does-not-write');write.assert_not_called();send.assert_not_called()
 def test_preflight_closes_fd_on_signal0_failure(self):
  x=row(123,1,['python'])
  with patch.object(m,'read_process',return_value=x),patch.object(m,'same_birth',return_value=x),patch.object(m,'pidfd_open',return_value=77),patch.object(m,'pidfd_send_signal',side_effect=OSError('signal0 denied')),patch.object(m.os,'close') as close:
   self.assertRaises(OSError,m.signal_capability_preflight);close.assert_called_once_with(77)
if __name__=='__main__':unittest.main()
