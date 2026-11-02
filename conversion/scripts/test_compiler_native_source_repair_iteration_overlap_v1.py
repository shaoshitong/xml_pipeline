import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import compiler_native_source_repair_iteration_overlap_v1 as overlap


class ActiveOverlapTests(unittest.TestCase):
    def program(self, root, name, ids):
        directory=root/'release/compiler_iterations/programs'/name
        directory.mkdir(parents=True)
        (directory/'implementation.json').write_text('{}')
        (directory/'owner.json').write_text('{}')
        payload=b''.join((json.dumps({'id':identifier})+'\n').encode()for identifier in ids)
        (directory/'C.jsonl').write_bytes(payload)
        (directory/'C.freeze.json').write_text(json.dumps({'input_sha256':overlap.sha(payload)}))
        return directory

    def test_whole_snapshot_keeps_all_programs_and_following_standalone_ledger(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)
            self.program(root,'a_program',['first_id','second_id'])
            self.program(root,'b_program',['third_id','fourth_id'])
            self.ledger(root,'standalone')
            with patch.object(overlap,'live_owner',return_value={'pid':123,'start_ticks':456}):
                state=overlap.snapshot(root=root)
            self.assertEqual(set(state['active']),{'first_id','second_id','third_id','fourth_id','queued_id','running_id'})

    def test_explicit_target_guard_checks_later_program_without_early_program_poison(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)
            self.program(root,'a_program',['first_id'])
            self.program(root,'b_program',['target_id'])
            with patch.object(overlap,'live_owner',return_value={'pid':123,'start_ticks':456}):
                state=overlap.snapshot(root=root,identifier='target_id')
            self.assertEqual(set(state['active']),{'target_id'})

    def ledger(self,root,name):
        directory=root/'release/compiler_iterations/runs'/name;directory.mkdir(parents=True)
        db=sqlite3.connect(directory/'status.sqlite');db.execute('create table samples(id text,status text)');db.executemany('insert into samples values(?,?)',[('queued_id','queued'),('running_id','running'),('qualified_id','qualified')]);db.commit();db.close();(directory/'freeze.json').write_text('{}');return directory

    def test_dead_owner_does_not_permanently_defer_orphan_queue(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);self.ledger(root,'dead')
            with patch.object(overlap,'live_owner',return_value=None):result=overlap.snapshot(root=root)
            self.assertEqual(result['active'],{});self.assertTrue(result['dead_or_unowned_queued_rows_not_deferred'])

    def test_only_live_queued_running_rows_are_active(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);self.ledger(root,'live')
            with patch.object(overlap,'live_owner',return_value=dict(pid=123,start_ticks=456,live=True)):result=overlap.snapshot(root=root,identifier='running_id')
            self.assertEqual(set(result['active']),{'running_id'});self.assertEqual(result['live_ledgers'][0]['pending_rows'],1)

    def test_live_program_reserves_frozen_undispatched_C_manifest(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);p=root/'release/compiler_iterations/programs/live';p.mkdir(parents=True);(p/'implementation.json').write_text('{}')
            payload=b'{"id":"future_id"}\n';(p/'C.jsonl').write_bytes(payload);(p/'C.freeze.json').write_text(json.dumps(dict(input_sha256=overlap.sha(payload))))
            with patch.object(overlap,'live_owner',side_effect=lambda path,freeze:dict(pid=123,start_ticks=456)if path.parent==p else None):result=overlap.snapshot(root=root)
            self.assertEqual(set(result['active']),{'future_id'});self.assertEqual(result['active']['future_id'][0]['kind'],'live_program_frozen_pending_manifest')

    def test_own_program_prefix_is_ignored_without_ignoring_other_owner(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);self.ledger(root,'own_C');self.ledger(root,'other_C')
            with patch.object(overlap,'live_owner',return_value=dict(pid=123,start_ticks=456)):result=overlap.snapshot(root=root,ignore_runs=('own',))
            self.assertEqual(len(result['live_ledgers']),1);self.assertIn('other_C',result['live_ledgers'][0]['ledger'])

    def test_reused_PID_with_different_birth_is_not_live(self):
        with tempfile.TemporaryDirectory()as temporary:
            p=Path(temporary)/'owner.json';p.write_text(json.dumps(dict(pid=123,start_ticks=456)))
            with patch('initial_conversion_process_v1.identity',return_value=dict(state='S',start_ticks=457)):
                self.assertIsNone(overlap.live_owner(p,dict(pins={})))

    def test_live_owner_requires_actual_frozen_entrypoint_bytes(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);p=root/'owner.json';p.write_text(json.dumps(dict(pid=123,start_ticks=456)));entry=root/'controller.py';entry.write_text('pass')
            original=Path.read_bytes
            def read(path):return ('python\0'+str(entry)+'\0').encode()if str(path)=='/proc/123/cmdline'else original(path)
            with patch('initial_conversion_process_v1.identity',return_value=dict(state='S',start_ticks=456)),patch.object(Path,'read_bytes',read):
                self.assertIsNotNone(overlap.live_owner(p,dict(pins={str(entry):overlap.sha(entry.read_bytes())})))
                self.assertIsNone(overlap.live_owner(p,dict(pins={str(entry):'a'*64})))

    def test_unfrozen_live_pending_manifest_is_an_infrastructure_error(self):
        with tempfile.TemporaryDirectory()as temporary:
            p=Path(temporary)/'targets.jsonl';p.write_text('{"id":"a"}')
            with self.assertRaisesRegex(RuntimeError,'live_overlap_manifest_not_frozen'):overlap.frozen_ids(p,dict(input_sha256='a'*64))


if __name__=='__main__':unittest.main()
