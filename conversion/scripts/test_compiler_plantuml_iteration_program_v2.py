import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import compiler_plantuml_iteration_program_v2 as program


class ProgramTests(unittest.TestCase):
    def test_claimed_passing_gate_must_equal_rebuilt_actual_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            alleged = dict(approved_units=['unit'], controls_passed=True)
            (p / 'release_gate.json').write_text(json.dumps(alleged))
            actual = dict(approved_units=[], controls_passed=True)
            with patch.object(program, 'owned', return_value=p), patch.object(program, 'computed_gate', return_value=actual):
                with self.assertRaisesRegex(ValueError, 'not_reproducible'):
                    program.verify_release_gate(p / 'release_gate.json', {}, {'unit'})

    def test_bulk_covers_all_supported_remaining_ids_but_never_repeats_validation_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / 'program'
            p.mkdir()
            (p / 'implementation.json').write_text('{}')
            # Both selected samples are excluded, regardless of success/failure.
            (p / 'selected.jsonl').write_text(json.dumps({'id': 'validated_good'}) + '\n' + json.dumps({'id': 'validated_failed'}) + '\n')
            population = [dict(id=i, compiler_unit='unit', source={}) for i in ('validated_good', 'validated_failed', 'other1', 'other2')]
            (p / 'supported_population.jsonl').write_bytes(b''.join(program.raw(x) for x in population))
            (p / 'release_gate.json').write_text('{}')
            with patch.object(program.common, 'R', root), patch.object(program.controller, 'FLOOR', root / 'runs'), \
                 patch.object(program.controller, 'create') as create:
                run = program.build_mass(p, {'approved_units': ['unit']})
            rows = program.readrows(p / 'mass.jsonl')
            self.assertEqual([x['id'] for x in rows], ['other1', 'other2'])
            self.assertEqual([x['seq'] for x in rows], [1, 2])
            self.assertEqual(run.name, 'program_mass')
            create.assert_called_once()

    def test_failed_release_does_not_dispatch_any_bulk_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'implementation.json').write_text('{}')
            (p / 'selected.jsonl').write_text('')
            (p / 'supported_population.jsonl').write_text(json.dumps(dict(id='pending', compiler_unit='unit')) + '\n')
            with patch.object(program.controller, 'create') as create:
                self.assertIsNone(program.build_mass(p, {'approved_units': []}))
                create.assert_not_called()
            # No failure is converted to irrecoverable input or goal completion.
            self.assertTrue((p / 'supported_population.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
