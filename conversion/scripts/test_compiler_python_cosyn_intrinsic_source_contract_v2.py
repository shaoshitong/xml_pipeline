import copy
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import compiler_python_cosyn_intrinsic_case_v2 as case
import compiler_python_cosyn_intrinsic_pool_v2 as pool
import compiler_python_cosyn_intrinsic_program_v2 as program


class SourceContractTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.work=self.root/'conversion';self.work.mkdir()
        self.source=dict(pair_sha256='a'*64,category='scientific_diagram',format='python',source='provider',code_sha256='b'*64,image_sha256='c'*64,clean_file='clean/original_source.parquet',clean_row=7,code_key='code',image_key='image',source_document_id='paper-17')
        capture=json.dumps({'code_sha256':'d'*64,'image_sha256':'e'*64})
        self.job=(self.source['pair_sha256'],self.source['category'],self.source['format'],self.source['source'],json.dumps(self.source),'pending',None,0,None,capture,None,None,None)
        self.snapshot=dict(id=self.job[0],source_code_sha256=self.source['code_sha256'],source_image_sha256=self.source['image_sha256'],source_dot='clean/original.dot',source_dot_sha256='f'*64)
        with sqlite3.connect(self.work/'jobs.sqlite')as database:
            database.execute('create table jobs(id text,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)');database.execute('insert into jobs values('+','.join('?'for _ in self.job)+')',self.job)
        self.compiler=SimpleNamespace(UNIT='unit',original=Mock(side_effect=lambda record,job:(record,job)))

    def request(self):return pool.request_from_job(self.job,self.source,'unit',self.snapshot)

    def validate(self,rows):
        with patch.object(program,'W',self.work),patch.object(case,'bindings',return_value=(self.compiler,None)):return program.validate_source_requests(rows)

    def test_actual_pool_constructor_carries_complete_worker_source_to_actual_validator(self):
        row=self.request();self.assertEqual(row['source'],self.source);self.assertEqual(row['source']['clean_row'],7);self.assertTrue(self.validate([row]))
        self.assertEqual(self.compiler.original.call_args.args[0]['compiler_source_capture_snapshot'],self.snapshot)

    def test_five_field_inventory_summary_is_not_a_canonical_worker_source(self):
        summary={k:self.source[k]for k in ('category','format','source','code_sha256','image_sha256')}
        with self.assertRaisesRegex(ValueError,'complete_canonical_source'):pool.request_from_job(self.job,summary,'unit',self.snapshot)
        row=self.request();row['source']=summary
        with self.assertRaisesRegex(ValueError,'complete_canonical_source'):self.validate([row])

    def test_python_format_is_explicit_and_does_not_inherit_mermaid_check(self):
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
        self.assertFalse(pool.normal_candidate_was_called(request,dict(error_type='ValueError',detail='already_qualified_complete_original_preserved'),None))

    def test_qualified_guard_returns_no_normal_permission_on_valid_existing_pair(self):
        with patch('compiler_mermaid_alpha_qualifications_v2.find_qualified',return_value={'id':'a'}):
            with self.assertRaisesRegex(ValueError,'already_qualified_complete_original_preserved'):case.qualified_guard('a',self.source)

    def test_qualified_guard_never_swallows_actual_asset_corruption(self):
        with patch('compiler_mermaid_alpha_qualifications_v2.find_qualified',side_effect=RuntimeError('infrastructure_qualified_ledger_asset_or_source_conflict')):
            with self.assertRaisesRegex(RuntimeError,'infrastructure_qualified'):case.qualified_guard('a',self.source)


if __name__=='__main__':unittest.main()
