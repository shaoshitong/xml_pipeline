"""Typed scheduling diagnostics: booleans and actual exceptions, never keys."""
import json
import copy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import html_paragraph_iteration_pool_v9 as pool
from unittest.mock import patch

import html_paragraph_iteration_case_v9 as case
import html_paragraph_iteration_program_v9 as program


class InfrastructureTests(unittest.TestCase):
    def test_known_RO_QA_type_field_is_explicitly_normalized_without_mutation(self):
        report=dict(infrastructure_failure=False,failures=[dict(type='ImportError',reason='missing runtime')]);before=copy.deepcopy(report)
        self.assertTrue(case.quality_failure_diagnosis(report)['infrastructure_failure']);self.assertEqual(report,before)

    def test_RO_normalization_never_recurses_into_ordinary_source_detail(self):
        report=dict(infrastructure_failure=False,failures=[dict(type='ValueError',reason='source_glyph_mismatch',detail=dict(type='ImportError',infrastructure_failure=True))])
        self.assertFalse(case.quality_failure_diagnosis(report)['infrastructure_failure'])

    def test_false_flag_name_itself_is_not_a_failure(self):
        for value in (dict(ok=False,infrastructure_failure=False),dict(ok=False,reason='source_reference_pending:source_reference_canvas_mismatch',infrastructure_failure=False)):
            self.assertFalse(case.is_infrastructure(value))

    def test_nested_false_flags_and_stringified_false_fields_are_not_failures(self):
        values=[dict(detail=dict(infrastructure_failure=False,reason='invisible_or_unlaid_graphviz_node_not_supported')),
                dict(detail=dict(source_reproduction=dict(infrastructure_failure=False,reason='source_reference_canvas_mismatch'))),
                dict(message="{'infrastructure_failure': False, 'source': 'pending'}"),
                dict(error='{"infrastructure_failure": false, "detail": "source_reference_pending"}')]
        self.assertTrue(all(not case.is_infrastructure(value)for value in values))

    def test_partial_candidate_metadata_is_not_runtime_diagnostics(self):
        value=dict(ok=False,reason='source_coverage_pending',record=dict(error_type='ImportError',infrastructure_failure=True))
        self.assertFalse(case.is_infrastructure(value))

    def test_true_typed_flags_remain_infrastructure(self):
        for value in (dict(infrastructure_failure=True),dict(failures=[dict(infrastructure_failure=True)])):
            self.assertTrue(case.is_infrastructure(value))
        self.assertFalse(case.is_infrastructure(dict(detail=dict(infrastructure_failure=True))))

    def test_actual_import_failures_and_subclasses_remain_infrastructure(self):
        class MissingRuntime(ImportError):pass
        values=[ImportError('runtime'),MissingRuntime('runtime'),dict(error_type='ImportError'),dict(exception_type='builtins.ModuleNotFoundError'),dict(failures=[dict(exception_type='ImportError',reason='missing package')]),dict(error='ModuleNotFoundError: No module named runtime')]
        self.assertTrue(all(case.is_infrastructure(value)for value in values))

    def test_actual_browser_failures_remain_infrastructure(self):
        values=[dict(error_type='TargetClosedError'),dict(detail='Page.captureScreenshot: Target page, context or browser has been closed'),dict(error='Browser crashed'),dict(message='Connection closed while reading from the driver')]
        self.assertTrue(all(case.is_infrastructure(value)for value in values))

    def test_actual_infrastructure_reason_requires_a_reason_token_not_a_key(self):
        for value in (dict(reason='infrastructure_capture_payload_changed: source_dot'),dict(error='RuntimeError: infrastructure_graphviz_runtime_failed: missing shared library')):
            self.assertTrue(case.is_infrastructure(value))
        self.assertFalse(case.is_infrastructure(dict(reason='source_reference_pending:invisible_or_unlaid_graphviz_node_not_supported',detail=dict(infrastructure_failure=False))))

    def test_normal_source_and_native_quality_failures_do_not_stop_dispatch(self):
        values=[dict(reason='source_reference_pending:invisible_or_unlaid_graphviz_node_not_supported',detail=dict(reason='invisible_or_unlaid_graphviz_node_not_supported',infrastructure_failure=False,exception_type='ValueError')),
                dict(reason='source_reference_pending:source_reference_canvas_mismatch',detail=dict(reason='source_reference_canvas_mismatch',infrastructure_failure=False)),
                dict(failures=[dict(type='ValueError',reason='source_arrow_missing_attached_native_marker')],infrastructure_failure=False)]
        self.assertTrue(all(not case.is_infrastructure(value)for value in values))

    def test_next_repair_groups_source_reasons_without_false_runtime_keys(self):
        self.assertEqual(program.failure_family(dict(reason='source_reference_pending',detail=dict(reason='invisible_or_unlaid_graphviz_node_not_supported',infrastructure_failure=False))),'nodes_edges_and_arrows')
        self.assertEqual(program.failure_family(dict(reason='source_reference_pending',detail=dict(reason='source_reference_canvas_mismatch',infrastructure_failure=False))),'canvas_and_coordinates')
        self.assertEqual(program.failure_family(dict(error_type='ImportError')),'runtime_or_environment')


class PriorAttemptTests(unittest.TestCase):
    def test_mass_preserves_normal_prior_failure_without_reexecution(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);p=root/'program';p.mkdir()
            (p/'implementation.json').write_text('{}');(p/'release_gate.json').write_text('{}')
            (p/'selected.jsonl').write_bytes(program.raw(dict(id='fresh_validation')))
            (p/'preserved_qualified.jsonl').write_bytes(b'')
            population=[dict(id=identifier,compiler_unit='unit',source={})for identifier in ('prior_source_failure','fresh_validation','never_attempted')]
            (p/'supported_population.jsonl').write_bytes(b''.join(program.raw(row)for row in population))
            prior=[dict(id='prior_source_failure',status='abandoned',raw_result_json='original evidence remains unchanged')]
            with patch.object(pool,'fresh_qualified',return_value={}),patch.object(program.case,'bindings',return_value=(SimpleNamespace(configuration=lambda:{}),None)),patch.object(program.common,'R',root),patch.object(program.controller,'FLOOR',root/'runs'),patch.object(program.controller,'create')as create,patch.object(program,'prior_attempts',return_value=prior),patch.object(program,'validate_source_requests'),patch.object(program.history,'collect',return_value=[]),patch.object(program.history,'validate',return_value=True),patch('compiler_mermaid_alpha_iteration_overlap_v2.snapshot',return_value={'active':{}}):
                program.build_mass(p,dict(approved_units=['unit']))
            self.assertEqual([row['id']for row in program.readrows(p/'mass.jsonl')],['never_attempted']);create.assert_called_once()
            self.assertEqual(program.readrows(p/'mass_preserved_prior_SOURCE_attempts.jsonl'),prior)

    def test_prior_attempt_evidence_file_is_required(self):
        with tempfile.TemporaryDirectory()as temporary:
            with self.assertRaisesRegex(ValueError,'missing_prior_SOURCE_frontend_attempt_bookkeeping'):program.prior_attempts(Path(temporary))


if __name__=='__main__':unittest.main()
