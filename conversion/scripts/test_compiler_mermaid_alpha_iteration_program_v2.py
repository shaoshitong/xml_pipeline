import json
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch

import compiler_mermaid_alpha_iteration_program_v2 as program
from compiler_mermaid_alpha_iteration_case_v2 import runtime_failure


class FailureClassificationTests(unittest.TestCase):
    def test_ordinary_nested_source_details_do_not_stop_dispatch(self):
        self.assertFalse(runtime_failure(dict(
            infrastructure_failure=False, reason='source_reference_not_reproduced',
            detail=dict(infrastructure_failure=True, error_type='ImportError'))))

    def test_known_quality_exception_type_is_passed_to_typed_classifier(self):
        self.assertTrue(runtime_failure([dict(type='ImportError', reason='missing library')]))
        self.assertFalse(runtime_failure([dict(type='ValueError', reason='source_profile_failed')]))


class CurrentQualificationPreservationTests(unittest.TestCase):
    def fixture(self, root):
        clean = root / 'clean'
        clean.mkdir()
        item = dict(pair_sha256='kept', format='mermaid', category='scientific_diagram',
                    code_sha256='c' * 64, image_sha256='d' * 64)
        row = dict(id='kept', source_pair_sha256='kept', source_format='mermaid',
                   category=item['category'], format='drawio', status='qualified')
        for field, digest_field in [('code_file', 'code_sha256'), ('image_file', 'image_sha256'),
                                    ('metadata_file', 'metadata_sha256'),
                                    ('original_source_code', 'source_code_sha256'),
                                    ('original_reference', 'source_image_sha256')]:
            path = clean / field
            path.write_bytes(field.encode())
            row[field] = str(path.relative_to(root))
            row[digest_field] = program.sha(path.read_bytes())
        item.update(code_sha256=row['source_code_sha256'], image_sha256=row['source_image_sha256'])
        directory = root / 'release/compiler_iterations/controls/other_completed_run'
        directory.mkdir(parents=True)
        (directory / 'qualified.jsonl').write_bytes(program.raw(row))
        return row, item

    def test_newly_qualified_control_is_retained_and_not_reconverted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row, source = self.fixture(root)
            p = root / 'program'
            p.mkdir()
            population = [dict(id='kept', source=source)]
            with patch.object(program, 'R', root), patch.object(program.common, 'R', root):
                self.assertEqual(program.preserve_current_qualified(p, population), {'kept'})
            preserved = program.readrows(p / 'mass_preserved_qualified.jsonl')
            self.assertEqual(preserved, [row])

    def test_changed_accepted_asset_is_an_error_instead_of_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row, source = self.fixture(root)
            (root / row['image_file']).write_bytes(b'changed')
            p = root / 'program'
            p.mkdir()
            with patch.object(program, 'R', root), self.assertRaisesRegex(ValueError, 'hash_mismatch'):
                program.preserve_current_qualified(p, [dict(id='kept', source=source)])

    def test_live_SQLite_qualification_is_preserved_before_any_final_export(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);row,source=self.fixture(root)
            (root/'release/compiler_iterations/controls/other_completed_run/qualified.jsonl').unlink()
            run=root/'release/compiler_iterations/runs/live';run.mkdir(parents=True)
            with sqlite3.connect(run/'status.sqlite')as db:
                db.execute('create table samples(id text,status text,result text)')
                db.execute('insert into samples values(?,?,?)',('kept','qualified',json.dumps({'id':'kept','status':'qualified','manifest':row})))
            p=root/'program';p.mkdir()
            with patch.object(program,'R',root),patch.object(program.common,'R',root):
                self.assertEqual(program.preserve_current_qualified(p,[{'id':'kept','source':source}]),{'kept'})
            self.assertEqual(program.readrows(p/'mass_preserved_qualified.jsonl'),[row])


if __name__ == '__main__':
    unittest.main()
