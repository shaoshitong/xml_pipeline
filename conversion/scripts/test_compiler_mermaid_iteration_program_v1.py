import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import compiler_mermaid_iteration_program_v1 as program


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
            (p / 'protocol.json').write_text(json.dumps({'controls':{'positive_cases':[{'id':'already_published_control'}]}}))
            population = [dict(id=i, compiler_unit='unit', source={}) for i in ('validated_good', 'validated_failed', 'already_published_control', 'other1', 'other2')]
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

    def test_control_QA_cannot_be_reused_for_a_different_rehashed_candidate(self):
        row={'id':'original','source_code_sha256':'sourcecode','source_image_sha256':'sourceimage',
             'candidate':{'file':'record','sha256':'new_candidate_hash'},'qa':{'file':'qa','sha256':'qahash'}}
        record={'id':'original','source_code_sha256':'sourcecode','source_image_sha256':'sourceimage'}
        report={'id':'original','input_record_sha256':'other_candidate_hash'}
        def checked(ref):return Path(ref['file']),program.raw(record if ref['file']=='record' else report)
        with patch.object(program,'checked',side_effect=checked),patch.object(program.case,'full_quality') as quality:
            with self.assertRaisesRegex(ValueError,'not_bound_to_actual_candidate'):
                program.check_control_case(row,'positive')
            quality.assert_not_called()

    def test_negative_must_fail_the_fresh_source_replay(self):
        row={'id':'original','source_code_sha256':'sourcecode','source_image_sha256':'sourceimage',
             'candidate':{'file':'record','sha256':'candidatehash'},'qa':{'file':'qa','sha256':'qahash'}}
        record={'id':'original','source_code_sha256':'sourcecode','source_image_sha256':'sourceimage',
                'code_file':'code','code_sha256':'codehash','image_file':'image','image_sha256':'imagehash',
                'original_source_code':'originalcode','original_reference':'originalimage'}
        report={'id':'original','input_record_sha256':'candidatehash','ok':False,'failures':[{'reason':'some_visual_failure'}],
                'checks':{'source_preliminary':{'ok':True}}}
        def checked(ref):
            return Path(ref['file']),program.raw(record if ref['file']=='record' else report) if ref['file'] in ('record','qa') else b'asset'
        with patch.object(program,'checked',side_effect=checked):
            with self.assertRaisesRegex(ValueError,'not_rejected_by_fresh_source_replay'):
                program.check_control_case(row,'negative')


if __name__ == '__main__':
    unittest.main()
