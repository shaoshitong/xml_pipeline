import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import compiler_iteration_inventory_v1 as inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'clean').mkdir()
        self.item = dict(format='svg', category='scientific_diagram', source='test',
                         code_sha256=self.asset('original.svg', b'<svg/>'),
                         image_sha256=self.asset('reference.png', b'reference'))
        self.row = dict(id='one', source_pair_sha256='one', source_format='svg',
                        category='scientific_diagram', format='drawio', status='qualified',
                        source_code_sha256=self.item['code_sha256'], source_image_sha256=self.item['image_sha256'],
                        original_source_code='clean/original.svg', original_reference='clean/reference.png')
        for field, hash_field, name, data in [('code_file', 'code_sha256', 'diagram.drawio', b'<mxfile/>'),
                                              ('image_file', 'image_sha256', 'render.png', b'render'),
                                              ('metadata_file', 'metadata_sha256', 'metadata.json', b'{}')]:
            self.row[field] = 'clean/' + name
            self.row[hash_field] = self.asset(name, data)

    def asset(self, name, data):
        (self.root / 'clean' / name).write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def test_current_accepted_survives_later_failed_attempt_without_double_count(self):
        events = [dict(id='one', status='qualified', manifest=self.row),
                  dict(id='one', status='abandoned', reason='font_failure'),
                  dict(id='one', status='qualified', manifest=self.row)]
        with patch.object(inventory, 'read_scope', return_value=({'one': self.item}, {})), \
             patch.object(inventory, 'SOURCES', [('test', 'db', 'unused')]), \
             patch.object(inventory, 'read_results', return_value=iter(events)), contextlib.redirect_stdout(io.StringIO()):
            summary = inventory.snapshot(self.root, self.root / 'out')
        self.assertEqual(summary['qualified_total'], 1)
        self.assertEqual(summary['remaining'], 0)
        self.assertEqual(summary['accepted_integrity_errors'], [])
        self.assertEqual(len((self.root / 'out/qualified.jsonl').read_text().splitlines()), 1)

    def test_abandoned_is_pending_retry_and_never_irrecoverable(self):
        with patch.object(inventory, 'read_scope', return_value=({'one': self.item}, {})), \
             patch.object(inventory, 'SOURCES', [('test', 'db', 'unused')]), \
             patch.object(inventory, 'read_results', return_value=iter([dict(id='one', status='abandoned', reason='unsupported')])), \
             contextlib.redirect_stdout(io.StringIO()):
            inventory.snapshot(self.root, self.root / 'out')
        result = json.loads((self.root / 'out/dispositions.jsonl').read_text())
        self.assertEqual(result['state'], 'pending_retry')
        self.assertFalse(result['irrecoverable'])

    def test_stopped_historical_queue_does_not_hide_pending_retry(self):
        events = [dict(id='one', status='abandoned', reason='conversion_failed'),
                  dict(id='one', status='queued')]
        with patch.object(inventory, 'read_scope', return_value=({'one': self.item}, {})), \
             patch.object(inventory, 'SOURCES', [('test', 'db', 'old/status.sqlite')]), \
             patch.object(inventory, 'read_results', return_value=iter(events)), \
             patch.object(inventory, 'live_owner', return_value=False), contextlib.redirect_stdout(io.StringIO()):
            summary = inventory.snapshot(self.root, self.root / 'out')
        self.assertEqual(summary['by_format']['svg'], {'pending_retry': 1})

    def test_wrong_hash_and_external_clean_symlink_rejected(self):
        self.row['code_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'hash_mismatch'):
            inventory.check_manifest(self.root, 'one', self.item, self.row, {})
        self.row['code_sha256'] = hashlib.sha256(b'<mxfile/>').hexdigest()
        outside = self.root / 'outside.drawio'
        outside.write_bytes(b'<mxfile/>')
        (self.root / 'clean/diagram.drawio').unlink()
        (self.root / 'clean/diagram.drawio').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'actual_clean_file'):
            inventory.check_manifest(self.root, 'one', self.item, self.row, {})

    def test_db_status_snapshot_does_not_write_or_reset_attempts(self):
        path = self.root / 'status.sqlite'
        db = sqlite3.connect(path)
        db.execute('create table samples(seq integer,id text,status text,result text,attempts integer)')
        db.execute('insert into samples values(1,?,?,?,1)', ('one', 'abandoned', json.dumps(dict(id='one', status='abandoned'))))
        db.commit()
        db.close()
        before = path.read_bytes()
        self.assertEqual(list(inventory.read_results(self.root, 'db', 'status.sqlite'))[0]['status'], 'abandoned')
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
