import copy
from pathlib import Path
import tempfile
import unittest

import compiler_python_cosyn_intrinsic_batch_v4 as controller


class RuntimeAliasIdentityTests(unittest.TestCase):
    def fixture(self, root):
        target = root / 'runtime'
        target.write_bytes(b'engine')
        alias = root / 'dot'
        alias.symlink_to(target)
        digest = controller.base.sha(target.read_bytes())
        freeze = dict(pins={str(alias): digest, str(target): digest},
                      qa_policy_sha256='a' * 64, predicate_hashes={'unit': 'b' * 64})
        return alias, target, freeze

    def test_same_runtime_via_two_paths_preserves_both_raw_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias, target, freeze = self.fixture(Path(tmp))
            before = copy.deepcopy(freeze)
            identity = controller.implementation_identity(freeze)
            self.assertEqual(len(identity['pins']), 1)
            self.assertEqual(identity['raw_path_resolutions'],
                             {str(alias.absolute()): str(target.resolve()), str(target.absolute()): str(target.resolve())})
            self.assertEqual(freeze, before)
            controller.base.ensure_pins(freeze['pins'])

    def test_conflicting_digests_for_one_runtime_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias, _, freeze = self.fixture(Path(tmp))
            freeze['pins'][str(alias)] = 'c' * 64
            with self.assertRaisesRegex(ValueError, 'conflicting_canonical'):
                controller.implementation_identity(freeze)

    def test_retargeting_alias_to_identical_bytes_still_changes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alias, target, freeze = self.fixture(root)
            freeze['implementation_identity'] = controller.implementation_identity(freeze)
            freeze['implementation_identity_sha256'] = controller.implementation_digest(freeze)
            other = root / 'other_runtime'
            other.write_bytes(target.read_bytes())
            alias.unlink()
            alias.symlink_to(other)
            controller.base.ensure_pins(freeze['pins'])
            with self.assertRaisesRegex(ValueError, 'identity_changed'):
                controller.check_implementation_identity(freeze)

    def test_changed_runtime_bytes_are_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, target, freeze = self.fixture(Path(tmp))
            target.write_bytes(b'different')
            with self.assertRaises((ValueError, AssertionError, RuntimeError)):
                controller.base.ensure_pins(freeze['pins'])


if __name__ == '__main__':
    unittest.main()
