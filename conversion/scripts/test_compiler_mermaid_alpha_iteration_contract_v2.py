import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import compiler_mermaid_alpha_iteration_program_v2 as program
from compiler_mermaid_alpha_iteration_pool_v2 import request_from_job


class ActualWorkerSourceContractTests(unittest.TestCase):
    def test_actual_pool_request_constructor_carries_provider_specific_identity(self):
        source={'pair_sha256':'id','category':'scientific_diagram','format':'mermaid','source':'provider',
                'code_sha256':'c'*64,'image_sha256':'d'*64,'raw_file':'provider.parquet','raw_row':34}
        job=('id',None,None,None,json.dumps(source),None,None,None,None,None,None,None,None)
        request=request_from_job(job,source,'unit')
        self.assertEqual(request['source'],json.loads(job[4]))
        self.assertEqual(request['source']['raw_file'],'provider.parquet')
        self.assertEqual(request['source_record_sha256'],program.sha(b''))

    def test_pool_constructor_rejects_index_summary_before_emission(self):
        source={'pair_sha256':'id','format':'mermaid','source':'provider'}
        job=('id',None,None,None,json.dumps(source),None,None,None,None,None,None,None,None)
        with self.assertRaisesRegex(ValueError,'complete_canonical_source'):
            request_from_job(job,{'format':'mermaid','source':'provider'},'unit')

    def fixture(self, root):
        source={'pair_sha256':'identifier','category':'scientific_diagram','format':'mermaid','source':'provider',
                'code_sha256':'c'*64,'image_sha256':'d'*64,'raw_file':'source.parquet','raw_row':15,
                'image_provenance':'provided','code_key':'answer'}
        previous={'code_sha256':'e'*64,'image_sha256':'f'*64}
        path=Path(root)/'jobs.sqlite'
        with sqlite3.connect(path)as db:
            db.execute('create table jobs(id text primary key,input_record text,output_record text)')
            db.execute('insert into jobs values(?,?,?)',('identifier',json.dumps(source),json.dumps(previous)))
        row={'id':'identifier','source':source,'source_record_sha256':program.sha(json.dumps(previous).encode()),
             'baseline_code_sha256':previous['code_sha256'],'baseline_image_sha256':previous['image_sha256']}
        return row

    def test_complete_canonical_record_and_snapshot_pass(self):
        with tempfile.TemporaryDirectory()as temporary:
            row=self.fixture(temporary)
            with patch.object(program,'W',Path(temporary)):
                self.assertTrue(program.validate_source_requests([row]))

    def test_five_field_scope_summary_cannot_be_dispatched(self):
        with tempfile.TemporaryDirectory()as temporary:
            row=self.fixture(temporary)
            row['source']={k:row['source'][k]for k in ('category','format','source','code_sha256','image_sha256')}
            with patch.object(program,'W',Path(temporary)),self.assertRaisesRegex(ValueError,'complete_canonical_source_record'):
                program.validate_source_requests([row])

    def test_changed_baseline_record_is_rejected_before_reservation(self):
        with tempfile.TemporaryDirectory()as temporary:
            row=self.fixture(temporary);row['source_record_sha256']='0'*64
            with patch.object(program,'W',Path(temporary)),self.assertRaisesRegex(ValueError,'baseline_record_snapshot_changed'):
                program.validate_source_requests([row])

    def test_wrong_baseline_asset_identity_is_rejected(self):
        with tempfile.TemporaryDirectory()as temporary:
            row=self.fixture(temporary);row['baseline_code_sha256']='0'*64
            with patch.object(program,'W',Path(temporary)),self.assertRaisesRegex(ValueError,'baseline_asset_snapshot_changed'):
                program.validate_source_requests([row])

    def test_prepare_checks_worker_contract_before_reservation_or_phase_creation(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);pool=root/'pool';pool.mkdir()
            (pool/'summary.json').write_text(json.dumps({'all_remaining_observed_families_selected':True,'files':{}}))
            (pool/'selected.jsonl').write_text('{"id":"bad","source":{}}\n')
            with patch.object(program,'owned',return_value=root/'program'),patch.object(program,'template',return_value={}),\
                 patch.object(program.case,'bindings',return_value=(object(),object())),patch.object(program,'control_bundle',return_value={}),\
                 patch.object(program,'check_controls'),patch.object(program,'validate_source_requests',side_effect=ValueError('bad_worker_contract'))as validate,\
                 patch.object(program,'reserve')as reserve,patch.object(program.controller,'create')as create:
                with self.assertRaisesRegex(ValueError,'bad_worker_contract'):program.prepare(pool,'run')
            validate.assert_called_once();reserve.assert_not_called();create.assert_not_called()
            self.assertFalse((root/'program').exists())


if __name__=='__main__':unittest.main()
