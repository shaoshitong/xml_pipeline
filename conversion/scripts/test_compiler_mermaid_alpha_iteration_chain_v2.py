import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import compiler_mermaid_alpha_iteration_chain_v2 as chain


class FiniteChainTests(unittest.TestCase):
    def context(self,root):
        directory=Path(root)
        (directory/'freeze.json').write_text(json.dumps({'nonce':'n','module_pins':{},'frontend':{}}))
        def immutable(path,blob):Path(path).write_bytes(blob)
        from contextlib import ExitStack
        stack=ExitStack()
        stack.enter_context(patch.object(chain,'DIRECTORY',directory))
        stack.enter_context(patch.object(chain,'module_pins',return_value={}))
        stack.enter_context(patch.object(chain,'verify_runtime',return_value={}))
        stack.enter_context(patch.object(chain.program.controller,'process_identity',return_value={'pid':123,'start_ticks':456}))
        stack.enter_context(patch.object(chain.program.common,'wait_ack'))
        stack.enter_context(patch.object(chain.program,'immutable',side_effect=immutable))
        # Keep the actual common.atomic serializer. Passing pre-encoded bytes
        # here is a real schema error and must fail this integration boundary.
        return stack

    def test_success_dispatches_fixed_program_once_and_records_real_handoff(self):
        with tempfile.TemporaryDirectory()as temporary,self.context(temporary):
            with patch.object(chain.pool,'prepare',return_value={'selected':100}),patch.object(chain.program,'prepare',return_value={'program_dir':temporary+'/program'}),patch.object(chain.program,'launch',return_value={'pid':10,'start_ticks':20})as launch:
                chain.execute('n')
            launch.assert_called_once_with(Path(temporary+'/program'),4,900)
            handoff=json.loads((Path(temporary)/'handoff.json').read_bytes())
            self.assertFalse(handoff['goal_complete']);self.assertFalse(handoff['watch'])
            self.assertEqual(handoff['program']['pid'],10)
            self.assertEqual(handoff['predeclared_gate']['minimum_qualified_fraction'],.2)
            self.assertIsInstance(json.loads((Path(temporary)/'owner.json').read_bytes()),dict)

    def test_exhausted_families_never_dispatches_and_keeps_goal_incomplete(self):
        with tempfile.TemporaryDirectory()as temporary,self.context(temporary):
            with patch.object(chain.pool,'prepare',return_value={'selected':0}),patch.object(chain.program,'launch')as launch:
                chain.execute('n')
            launch.assert_not_called()
            handoff=json.loads((Path(temporary)/'handoff.json').read_bytes())
            self.assertFalse(handoff['dispatched']);self.assertFalse(handoff['goal_complete'])

    def test_exhaustive_one_family_does_not_reduce_five_incremental_gate(self):
        with tempfile.TemporaryDirectory()as temporary,self.context(temporary):
            with patch.object(chain.pool,'prepare',return_value={'selected':1}),patch.object(chain.program,'prepare',return_value={'program_dir':temporary+'/program'}),patch.object(chain.program,'launch',return_value={'pid':10,'start_ticks':20}):
                chain.execute('n')
            handoff=json.loads((Path(temporary)/'handoff.json').read_bytes())
            self.assertEqual(handoff['predeclared_gate']['minimum_new_qualified'],5)

    def test_audit_failure_is_durable_without_restart_or_dispatch(self):
        with tempfile.TemporaryDirectory()as temporary,self.context(temporary):
            with patch.object(chain.pool,'prepare',side_effect=RuntimeError('audit_problem')),patch.object(chain.program,'launch')as launch:
                with self.assertRaisesRegex(RuntimeError,'audit_problem'):chain.execute('n')
            launch.assert_not_called()
            failure=json.loads((Path(temporary)/'failure.json').read_bytes())
            self.assertFalse(failure['goal_complete']);self.assertFalse(failure['automatic_restart'])

    def test_changed_chain_module_never_reads_new_source_cohort(self):
        with tempfile.TemporaryDirectory()as temporary,self.context(temporary):
            with patch.object(chain,'module_pins',return_value={'changed':'hash'}),patch.object(chain.pool,'prepare')as prepare:
                with self.assertRaisesRegex(ValueError,'frozen_preparation_implementation_changed'):chain.execute('n')
            prepare.assert_not_called()


if __name__=='__main__':unittest.main()
