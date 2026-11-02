import contextlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import compiler_svg_source_viewport_iteration_launch_chain_v1 as chain
import compiler_svg_source_viewport_iteration_program_v1 as program
import compiler_svg_source_viewport_unseen_pool_v1 as pool
class ChainTests(unittest.TestCase):
 def fixture(self,audit=None,prepare_error=None):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)/'preparation';root.mkdir();(root/'pins.json').write_text('{}');calls=[]
  def write(p,v):Path(p).write_bytes(v if isinstance(v,bytes)else json.dumps(v).encode())
  def audit_run(*a):calls.append('source_only_audit');return audit or {'minimum100_met':True,'selected':100}
  def prepare(*a):
   calls.append('prepare_BC')
   if prepare_error:raise prepare_error
   return {'program_dir':str(root/'program')}
  def launch(*a):calls.append(('launch',a[1],a[2]));return {'pid':321,'start_ticks':123}
  stack=contextlib.ExitStack();self.addCleanup(stack.close)
  for p in [patch.object(chain,'ROOT',root),patch.object(chain,'POOL',root/'source_pool'),patch.object(chain,'identity',return_value={'pid':1,'start_ticks':2}),patch.object(chain,'atomic',side_effect=write),patch.object(chain,'immutable',side_effect=write),patch.object(chain,'wait_ack'),patch.object(chain,'ensure'),patch.object(chain,'preconditions',return_value={}),patch.object(chain,'asset',side_effect=lambda p:{'file':str(p),'sha256':'a'*64}),patch.object(pool,'prepare',side_effect=audit_run),patch.object(program,'prepare',side_effect=prepare),patch.object(program,'launch',side_effect=launch)]:stack.enter_context(p)
  return root,calls
 def test_source_audit_precedes_BC_prepare_and_fixed_launch(self):
  root,calls=self.fixture();chain.supervise(Path('/inventory'),'nonce');self.assertEqual(calls,['source_only_audit','prepare_BC',('launch',4,900)]);j=json.loads((root/'ready.json').read_bytes());self.assertEqual(j['stage'],'fixed_program_launched');self.assertFalse(j['agent_watch']);self.assertFalse(j['goal_complete'])
 def test_insufficient_fresh100_records_failure_without_preparing_or_launching(self):
  root,calls=self.fixture({'minimum100_met':False,'selected':99})
  with self.assertRaisesRegex(ValueError,'fewer_than100'):chain.supervise(Path('/inventory'),'n')
  self.assertEqual(calls,['source_only_audit']);self.assertTrue((root/'failure.json').exists());self.assertFalse((root/'ready.json').exists())
 def test_registry_prepare_failure_does_not_launch_or_relax_gate(self):
  root,calls=self.fixture(prepare_error=ValueError('reserved_identity_overlap'))
  with self.assertRaisesRegex(ValueError,'reserved_identity'):chain.supervise(Path('/inventory'),'n')
  self.assertEqual(calls,['source_only_audit','prepare_BC']);j=json.loads((root/'failure.json').read_bytes());self.assertTrue(j['new_gate_not_relaxed']);self.assertFalse(j['runtime_diagnosis']['infrastructure_failure'])
 def test_true_runtime_exception_in_preparation_is_recorded(self):
  root,calls=self.fixture(prepare_error=ModuleNotFoundError('runtime'))
  with self.assertRaises(ModuleNotFoundError):chain.supervise(Path('/inventory'),'n')
  self.assertTrue(json.loads((root/'failure.json').read_bytes())['runtime_diagnosis']['infrastructure_failure'])
 def test_preconditions_fail_before_any_new_directory_or_process(self):
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp)/'new';inventory=Path(temp)/'inventory';inventory.mkdir()
   with patch.object(chain,'ROOT',root),patch.object(chain,'preconditions',side_effect=ValueError('controls_changed')),patch.object(chain.subprocess,'Popen')as start:
    with self.assertRaisesRegex(ValueError,'controls_changed'):chain.launch(inventory)
   self.assertFalse(root.exists());start.assert_not_called()
 def test_main_program_resource_profile_is_frozen(self):
  for workers,seconds in [(12,900),(4,600),(1,10)]:
   with self.assertRaisesRegex(ValueError,'requires4_workers900'):program.launch(Path('/no_actual_program'),workers,seconds)
if __name__=='__main__':unittest.main()
