import json
import unittest

from compiler_mermaid_alpha_iteration_pool_v3 import JOB_COLUMNS, static_support_from_job


class Compiler:
    def static_support(self, record):
        assert isinstance(record, dict)
        assert tuple(record) == JOB_COLUMNS
        assert record['worker_pid'] == 12345
        assert record['output_record'] == '{"unchanged":"baseline"}'
        assert json.loads(record['input_record'])['format'] == 'mermaid'
        return {'supported': True, 'unit': 'existing-source-unit'}


def job():
    source = dict(pair_sha256='identity', category='scientific_diagram', format='mermaid', source='provider')
    values = dict(id='identity', category=source['category'], format='mermaid', source='provider',
                  input_record=json.dumps(source), output_record='{"unchanged":"baseline"}', worker_pid=12345)
    return tuple(values.get(key) for key in JOB_COLUMNS)


class SourceSupportContractTests(unittest.TestCase):
    def test_full_SQLite_tuple_adapted_without_changing_values(self):
        original = job()
        self.assertEqual(static_support_from_job(Compiler(), original),
                         {'supported': True, 'unit': 'existing-source-unit'})
        self.assertEqual(original, job())

    def test_incomplete_SQLite_row_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete_SQLite_job'):
            static_support_from_job(Compiler(), job()[:5])

    def test_mapping_cannot_be_accidentally_zipped_as_SQLite_values(self):
        with self.assertRaisesRegex(ValueError, 'complete_SQLite_job'):
            static_support_from_job(Compiler(), dict(zip(JOB_COLUMNS, job())))

    def test_source_identity_mismatch_rejected_before_frontend(self):
        changed = list(job())
        changed[2] = 'svg'
        with self.assertRaisesRegex(ValueError, 'canonical_identity_mismatch'):
            static_support_from_job(Compiler(), changed)


if __name__ == '__main__':
    unittest.main()
