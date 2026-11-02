import copy
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import compiler_native_materialized_text_node_iteration_case_v3 as case
import compiler_native_materialized_text_node_iteration_pool_v4 as pool
import compiler_native_materialized_text_node_iteration_program_v4 as program
import compiler_native_materialized_text_node_iteration_chain_v4 as chain


class SourceContractTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.work=self.root/'conversion';self.work.mkdir()
        self.source=dict(pair_sha256='a'*64,category='scientific_diagram',format='drawio',source='provider',code_sha256='b'*64,image_sha256='c'*64,clean_file='clean/original_source.parquet',clean_row=7,code_key='code',image_key='image',source_document_id='paper-17')
        capture=json.dumps({'code_sha256':'d'*64,'image_sha256':'e'*64})
        self.job=(self.source['pair_sha256'],self.source['category'],self.source['format'],self.source['source'],json.dumps(self.source),'pending',None,0,None,capture,None,None,None)
        self.snapshot=dict(id=self.job[0],source_code_sha256=self.source['code_sha256'],source_image_sha256=self.source['image_sha256'],source_dot='clean/original.dot',source_dot_sha256='f'*64)
        with sqlite3.connect(self.work/'jobs.sqlite')as database:
            database.execute('create table jobs(id text,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)');database.execute('insert into jobs values('+','.join('?'for _ in self.job)+')',self.job)
        self.compiler=SimpleNamespace(UNIT='unit',original=Mock(side_effect=lambda record,job:(record,job)))

    def request(self):return pool.request_from_job(self.job,self.source,'unit',self.snapshot)

    def validate(self,rows):
        with patch.object(program,'W',self.work),patch.object(case,'bindings',return_value=(self.compiler,None)):return program.validate_source_requests(rows)

    def test_consumed_positive_preflight_uses_hash_bound_accepted_clean_metadata(self):
        metadata=self.root/'clean/accepted.json';metadata.parent.mkdir();record=dict(id=self.job[0],source_code_sha256=self.source['code_sha256'],source_image_sha256=self.source['image_sha256']);metadata.write_bytes(program.raw(record))
        row={**record,'metadata_file':str(metadata),'metadata_sha256':program.sha(metadata.read_bytes())};manifest=self.root/'qualified.jsonl';manifest.write_bytes(program.raw(row))
        bundle=dict(qualified_manifest=dict(file=str(manifest),sha256=program.sha(manifest.read_bytes())),positive_cases=[dict(id=self.job[0],candidate=dict(file='conversion/scratch_candidate.json'))])
        with patch.object(program.common,'R',self.root):self.assertEqual(chain.positive_metadata(bundle,self.job[0]),str(metadata.resolve()))

    def test_consumed_positive_requires_unique_accepted_manifest_entry(self):
        manifest=self.root/'qualified.jsonl';manifest.write_bytes(b'');bundle=dict(qualified_manifest=dict(file=str(manifest),sha256=program.sha(manifest.read_bytes())))
        with patch.object(program.common,'R',self.root):
            with self.assertRaisesRegex(ValueError,'manifest_missing_or_duplicate'):chain.positive_metadata(bundle,self.job[0])

    def test_pool_static_support_uses_full_canonical_dictionary_and_can_be_true(self):
        def support(value):
            self.assertIsInstance(value,dict);self.assertEqual(value['input_record'],self.job[4]);self.assertEqual(value['id'],self.job[0]);self.assertEqual(len(value),13)
            return dict(supported=True,source_capture_snapshot=self.snapshot)
        actual=pool.static_support_from_job(SimpleNamespace(static_support=support),self.job)
        self.assertIs(actual['supported'],True);self.assertEqual(actual['source_capture_snapshot'],self.snapshot)

    def test_short_job_or_mismatched_source_never_reaches_static_support(self):
        with self.assertRaisesRegex(ValueError,'all13_columns'):pool.canonical_job(self.job[:5])
        changed=list(self.job);changed[0]='different'
        with self.assertRaisesRegex(ValueError,'source_identity_changed'):pool.canonical_job(changed)

    def test_static_support_requires_typed_boolean(self):
        with self.assertRaisesRegex(RuntimeError,'static_source_contract_not_typed'):pool.static_support_from_job(SimpleNamespace(static_support=lambda _:dict(supported='true')),self.job)

    def test_actual_pool_constructor_carries_complete_worker_source_to_actual_validator(self):
        row=self.request();self.assertEqual(row['source'],self.source);self.assertEqual(row['source']['clean_row'],7);self.assertTrue(self.validate([row]))
        self.assertEqual(self.compiler.original.call_args.args[0]['compiler_source_capture_snapshot'],self.snapshot)

    def test_five_field_inventory_summary_is_not_a_canonical_worker_source(self):
        summary={k:self.source[k]for k in ('category','format','source','code_sha256','image_sha256')}
        with self.assertRaisesRegex(ValueError,'complete_canonical_source'):pool.request_from_job(self.job,summary,'unit',self.snapshot)
        row=self.request();row['source']=summary
        with self.assertRaisesRegex(ValueError,'complete_canonical_source'):self.validate([row])

    def test_native_format_is_explicit_and_does_not_inherit_mermaid_check(self):
        self.assertTrue(self.validate([self.request()]));row=self.request();row['source']=dict(self.source,format='mermaid')
        with self.assertRaisesRegex(ValueError,'canonical_source'):self.validate([row])

    def test_baseline_record_revision_and_both_asset_snapshots_are_checked(self):
        for field in ('source_record_sha256','baseline_code_sha256','baseline_image_sha256'):
            row=self.request();row[field]='0'*64
            with self.assertRaisesRegex(ValueError,'baseline_.*snapshot_changed'):self.validate([row])

    def test_capture_is_required_and_original_verifies_it_without_resealing(self):
        row=self.request();row.pop('source_capture_snapshot')
        with self.assertRaisesRegex(ValueError,'capture_snapshot_missing'):self.validate([row])
        with self.assertRaisesRegex(ValueError,'capture_snapshot_identity_changed'):pool.request_from_job(self.job,self.source,'unit',dict(self.snapshot,id='other'))

    def test_duplicate_ID_does_not_reenter_population(self):
        row=self.request()
        with self.assertRaisesRegex(ValueError,'duplicate_source_request_ID'):self.validate([row,copy.deepcopy(row)])

    def test_invalid_unselected_population_fails_before_mkdir_or_reservation(self):
        directory=self.root/'pool';directory.mkdir();row=dict(self.request(),seq=1);bad=dict(row,id='other',source=dict(row['source'],pair_sha256='other'))
        (directory/'selected.jsonl').write_bytes(program.raw(row));(directory/'supported_population.jsonl').write_bytes(program.raw(row)+program.raw(bad));(directory/'prior_candidate_attempts.jsonl').write_bytes(b'');(directory/'preserved_qualified.jsonl').write_bytes(b'')
        info=dict(all_remaining_observed_families_selected=True,files={name:dict(sha256=program.sha((directory/name).read_bytes()))for name in ('selected.jsonl','supported_population.jsonl')})
        (directory/'summary.json').write_text(json.dumps(info))
        with patch.object(program,'W',self.work),patch.object(program,'PROGRAMS',self.root/'programs'),patch.object(program,'template',return_value={}),patch.object(case,'bindings',return_value=(self.compiler,None)),patch.object(program,'control_bundle',return_value={}),patch.object(program,'check_controls'),patch.object(program,'reserve')as reserve:
            with self.assertRaisesRegex(ValueError,'canonical_job_missing'):program.prepare(directory,'new_run')
        reserve.assert_not_called();self.assertFalse((self.root/'programs/new_run').exists())

    def test_precall_deferral_can_retry_but_ambiguous_dead_owner_cannot_duplicate_normal(self):
        request={'evaluation_phase':'candidate'}
        self.assertTrue(pool.normal_candidate_was_called(request,{},None))
        self.assertFalse(pool.normal_candidate_was_called(request,{},dict(normal_source_conversion_called=False)))
        self.assertTrue(pool.normal_candidate_was_called(request,{},dict(ok=False,infrastructure_failure=False)))
        self.assertFalse(pool.normal_candidate_was_called({'existing_development_candidate':'case'}, {},None))
        self.assertFalse(pool.normal_candidate_was_called(request,dict(error_type='ValueError',reason='retryable_iteration_case_failure',detail='already_qualified_complete_original_preserved'),None))

    def case_request(self,overrides,history_state):
        work=self.work/'compiler_iterations/current/000001';work.mkdir(parents=True)
        request=dict(id=self.job[0],seq=1,source=self.source,compiler_unit='unit',work=str(work),pins={},mode='validation',run='current',evaluation_phase='candidate',source_capture_snapshot=self.snapshot,source_record_sha256=program.sha(self.job[9].encode()))
        request.update(overrides);path=work/'request.json';path.write_text(json.dumps(request))
        compiler=SimpleNamespace(UNIT='unit',VERSION='mock_source',configuration=lambda:{},static_support=Mock(return_value=dict(supported=True,source_capture_snapshot=self.snapshot)),original=Mock(side_effect=lambda record,job:(record,job)),convert=Mock(return_value=dict(ok=False,reason='fixture_normal_failure')))
        database=Mock();database.__enter__=Mock(return_value=database);database.__exit__=Mock(return_value=False);database.execute.return_value.fetchone.return_value=self.job
        with patch.object(case,'R',self.root),patch.object(case,'W',self.work),patch.object(case,'bindings',return_value=(compiler,None)),patch.object(case,'ordinary_overlap_guard'),patch.object(case,'qualified_guard'),patch.object(case.sqlite3,'connect',return_value=database),patch('compiler_source_core_attempts_v3.guard',return_value=history_state):
            result=case.run(path)
        return result,compiler,work

    def test_before_normal_guard_blocks_same_core_attempt_at_actual_case_entry(self):
        result,compiler,_=self.case_request({},dict(already_attempted=True,events=[]))
        self.assertEqual(result['detail'],'same_source_core_already_attempted_preserved');self.assertFalse(result['infrastructure_failure']);compiler.convert.assert_not_called()

    def test_real_failure_evidence_replay_calls_no_normal_frontend(self):
        old=self.work/'old_frontend.json';old.write_bytes(program.raw(dict(ok=False,reason='real_prior_canvas_failure',infrastructure_failure=False)));reference=dict(file=str(old),sha256=program.sha(old.read_bytes()))
        result,compiler,work=self.case_request(dict(mode='development',evaluation_phase='control_failure_replay',existing_development_failure=reference),dict(already_attempted=True,events=[dict(frontend=reference)]))
        self.assertEqual(result['phase'],'control_failure_replay');self.assertEqual(result['reason'],'real_prior_canvas_failure');self.assertFalse(result['normal_source_conversion_called']);compiler.convert.assert_not_called();self.assertFalse(json.loads((work/'frontend_result.json').read_bytes())['normal_source_conversion_called'])

    def test_prepare_checks_latest_core_history_before_any_reservation(self):
        directory=self.root/'pool';directory.mkdir();row=dict(self.request(),seq=1)
        for name in ('selected.jsonl','supported_population.jsonl'):(directory/name).write_bytes(program.raw(row))
        (directory/'prior_candidate_attempts.jsonl').write_bytes(b'');(directory/'preserved_qualified.jsonl').write_bytes(b'')
        info=dict(all_remaining_observed_families_selected=True,files={name:dict(sha256=program.sha((directory/name).read_bytes()))for name in ('selected.jsonl','supported_population.jsonl')});(directory/'summary.json').write_text(json.dumps(info));self.compiler.configuration=lambda:{}
        with patch.object(program,'W',self.work),patch.object(program,'PROGRAMS',self.root/'programs'),patch.object(program,'template',return_value={}),patch.object(case,'bindings',return_value=(self.compiler,None)),patch.object(program,'control_bundle',return_value={}),patch.object(program,'check_controls'),patch.object(program.history,'collect',return_value=[dict(id=self.job[0])]),patch.object(program.history,'validate',return_value=True),patch.object(program,'reserve')as reserve:
            with self.assertRaisesRegex(ValueError,'source_core_already_attempted_before_reservation'):program.prepare(directory,'new_run')
        reserve.assert_not_called();self.assertFalse((self.root/'programs/new_run').exists())

    def test_mass_rechecks_new_development_attempts_after_pool_snapshot(self):
        p=self.root/'program';p.mkdir();(p/'implementation.json').write_text('{}');(p/'release_gate.json').write_text('{}');(p/'selected.jsonl').write_bytes(program.raw(dict(id='selected')));(p/'prior_candidate_attempts.jsonl').write_bytes(b'');(p/'preserved_qualified.jsonl').write_bytes(b'')
        population=[dict(id=identifier,source={},compiler_unit='unit')for identifier in ('selected','development_normal','never_attempted')];(p/'supported_population.jsonl').write_bytes(b''.join(program.raw(row)for row in population))
        with patch.object(pool,'fresh_qualified',return_value={}),patch.object(case,'bindings',return_value=(SimpleNamespace(configuration=lambda:{}),None)),patch.object(program.common,'R',self.root),patch.object(program.controller,'FLOOR',self.root/'runs'),patch.object(program.controller,'create'),patch.object(program,'validate_source_requests'),patch.object(program.history,'collect',return_value=[dict(id='development_normal')]),patch.object(program.history,'validate',return_value=True),patch('compiler_mermaid_alpha_iteration_overlap_v2.snapshot',return_value={'active':{}}):program.build_mass(p,dict(approved_units=['unit']))
        self.assertEqual([row['id']for row in program.readrows(p/'mass.jsonl')],['never_attempted'])

    def test_terminal_failure_archive_supports_manual_and_SQL_history_without_old_fields(self):
        p=self.root/'program';p.mkdir();front=self.work/'prior_frontend.json';front.write_bytes(program.raw(dict(ok=False,reason='source_canvas_pending',infrastructure_failure=False)));reference=dict(file=str(front),sha256=program.sha(front.read_bytes()))
        receipt=self.work/'manual_summary.json';receipt.write_bytes(program.raw(dict(cases=[dict(id='manual_fail',failures=[dict(reason='local_pixel_failure')],report_file='manual.qa.json')])));receipt_ref=dict(file=str(receipt),sha256=program.sha(receipt.read_bytes()))
        events=[dict(id='sql_fail',evidence_kind='SQLite_normal_or_ambiguous',status='abandoned',result_json='{}',frontend=reference,ledger='old_ledger'),dict(id='manual_fail',evidence_kind='manual_development',frontend=reference,declaration=dict(receipt=receipt_ref,rows_key='cases',row_index=0)),dict(id='already_qualified',evidence_kind='manual_development')]
        with patch.object(program.common,'R',self.root),patch.object(program,'results',return_value={}),patch.object(program,'prior_attempts',return_value=events),patch.object(program,'preserved_qualified',return_value={'already_qualified':{}}):report=program.next_repair(p,{},None)
        identifiers={row['id']for group in report['failure_families'].values()for row in group['examples']}
        self.assertEqual(identifiers,{'sql_fail','manual_fail'});self.assertFalse(report['goal_complete']);self.assertTrue((p/'next_repair.json').is_file())

    def test_qualified_guard_returns_no_normal_permission_on_valid_existing_pair(self):
        with patch('compiler_mermaid_alpha_qualifications_v2.find_qualified',return_value={'id':'a'}):
            with self.assertRaisesRegex(ValueError,'already_qualified_complete_original_preserved'):case.qualified_guard('a',self.source)

    def test_qualified_guard_never_swallows_actual_asset_corruption(self):
        with patch('compiler_mermaid_alpha_qualifications_v2.find_qualified',side_effect=RuntimeError('infrastructure_qualified_ledger_asset_or_source_conflict')):
            with self.assertRaisesRegex(RuntimeError,'infrastructure_qualified'):case.qualified_guard('a',self.source)


if __name__=='__main__':unittest.main()
