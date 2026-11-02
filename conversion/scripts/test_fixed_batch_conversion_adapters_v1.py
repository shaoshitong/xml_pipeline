import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import fixed_batch_conversion_adapters_v1 as adapter


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.work=self.root/'conversion'/'attempt';self.work.mkdir(parents=True)
        self.db=self.work/'private.sqlite'
        with sqlite3.connect(self.db) as db:db.execute('create table jobs(id text)');db.execute('insert into jobs values(?)',('one',))
        self.source={'format':'svg','category':'scientific_diagram','source':'fixture',
                     'code_sha256':'code','image_sha256':'image'}
        self.job=dict.fromkeys(adapter.JOB_COLUMNS)
        self.job.update(id='one',format='svg',category='scientific_diagram',source='fixture',
                        input_record=json.dumps(self.source),state='queued',worker_pid=None)
        self.addCleanup(patch.stopall)
        patch.object(adapter,'R',self.root).start();patch.object(adapter,'W',self.root/'conversion').start()

    def run_adapter(self):return adapter.convert(self.job,self.db,self.work)

    def test_private_database_only_requested_id(self):
        with sqlite3.connect(self.db) as db:db.execute('insert into jobs values(?)',('two',))
        self.assertEqual(self.run_adapter()['reason'],'private_database_must_contain_only_requested_id')

    def test_canonical_database_refused_even_one_id(self):
        canonical=self.root/'conversion/jobs.sqlite';self.db.rename(canonical)
        self.assertEqual(adapter.convert(self.job,canonical,self.work)['reason'],'canonical_database_is_not_private')

    def test_symlink_to_canonical_database_refused(self):
        canonical=self.root/'conversion/jobs.sqlite';self.db.rename(canonical);self.db.symlink_to(canonical)
        self.assertEqual(self.run_adapter()['reason'],'canonical_database_is_not_private')

    def test_existing_candidate_returned_exactly_without_new_generation(self):
        record={'id':'one','source_pair_sha256':'one','source_code_sha256':'code','source_image_sha256':'image','code_file':'clean/old.drawio'}
        self.job['output_record']=json.dumps(record)
        with patch.object(adapter,'_generate',side_effect=AssertionError('must not generate')):
            result=self.run_adapter()
        self.assertTrue(result['ok']);self.assertTrue(result['existing_candidate']);self.assertEqual(result['record'],record)

    def test_existing_candidate_wrong_source_rejected(self):
        self.job['output_record']=json.dumps({'id':'other'})
        self.assertEqual(self.run_adapter()['reason'],'existing_candidate_identity_mismatch')

    def test_historical_failure_never_reexecuted(self):
        self.job['state']='needs_fallback'
        with patch.object(adapter,'_generate',side_effect=AssertionError('must not generate')):
            self.assertEqual(self.run_adapter()['reason'],'historical_failure_requires_recorded_skip')

    def test_foreign_worker_never_reexecuted(self):
        self.job['worker_pid']=123
        self.assertEqual(self.run_adapter()['reason'],'job_is_owned_by_another_worker')

    def test_missing_manifest_typed_failure(self):
        result=self.run_adapter();self.assertFalse(result['ok']);self.assertEqual(result['reason'],'missing_prepared_input_manifest');self.assertEqual(result['model_calls'],0)

    def test_read_rejects_wrong_hash_and_escape(self):
        path=self.root/'source';path.write_bytes(b'good')
        with self.assertRaisesRegex(adapter.AdapterFailure,'authoritative_input_hash_changed'):adapter._read('source','wrong')
        outside=self.root.parent/'outside-fixed-adapter-test'
        outside.write_bytes(b'x');self.addCleanup(lambda:outside.unlink(missing_ok=True))
        with self.assertRaisesRegex(adapter.AdapterFailure,'input_locator_outside_dataset'):adapter._read('../'+outside.name,hashlib.sha256(b'x').hexdigest())

    def test_write_is_exclusive(self):
        path=self.work/'payload';adapter._write(path,b'first')
        with self.assertRaises(FileExistsError):adapter._write(path,b'replace')
        self.assertEqual(path.read_bytes(),b'first')

    def test_tuple_contract(self):
        self.assertEqual(adapter._job(tuple(self.job[k] for k in adapter.JOB_COLUMNS)),self.job)
        with self.assertRaisesRegex(adapter.AdapterFailure,'invalid_full_job_snapshot'):adapter._job(('one',))

    def test_complete_six_format_dispatch(self):
        self.assertEqual(set(adapter.FORMATS),{'svg','html','python','plantuml','mermaid','drawio'})
        self.job['format']='web'
        self.assertEqual(self.run_adapter()['reason'],'unsupported_adapter_format')

    def test_private_db_remains_byte_identical_after_failure(self):
        before=self.db.read_bytes();self.run_adapter();self.assertEqual(self.db.read_bytes(),before)


if __name__=='__main__':unittest.main()
