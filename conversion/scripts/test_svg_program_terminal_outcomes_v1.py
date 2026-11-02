"""Exact source/owner/file/SQL mutation boundaries; uses the real collector CAS."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import svg_failure_closure_v1 as collector
import svg_program_terminal_outcomes_v1 as writer


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = sqlite3.connect(':memory:')
        self.id = 'a' * 64
        self.original = {'pair_sha256': self.id, 'category': 'scientific_diagram', 'format': 'svg',
                         'source': 'fixture', 'code_sha256': writer.sha(b'original_svg'), 'image_sha256': writer.sha(b'reference')}
        self.record = {'id': self.id, 'source_pair_sha256': self.id, 'category': 'scientific_diagram',
                       'source': 'fixture', 'source_format': 'svg', 'format': 'drawio',
                       'source_code_sha256': self.original['code_sha256'], 'source_image_sha256': self.original['image_sha256'],
                       'code_sha256': writer.sha(b'native_xml'), 'image_sha256': writer.sha(b'native_png')}
        self.record.update(code_file='clean/candidate.drawio', image_file='clean/candidate.png',
                           original_source_code='clean/source.svg', original_reference='clean/reference.png')
        for name, raw in [('candidate.drawio', b'native_xml'), ('candidate.png', b'native_png'),
                          ('source.svg', b'original_svg'), ('reference.png', b'reference')]:
            path = self.root / 'clean' / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
        self.manifest = {'id': self.id, 'source_format': 'svg', 'source_code': 'clean/source.svg',
                         'reference_image': 'clean/reference.png', 'code_sha256': self.original['code_sha256'],
                         'image_sha256': self.original['image_sha256'], 'width': 100, 'height': 100}
        self.db.execute('create table jobs(id text primary key,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)')
        self.db.execute('create table processing_outcomes_v2(id text primary key,category text,format text,source_code_hash text,source_image_hash text,status text,reason text,record text,updated_at text)')
        self.db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)', (self.id, 'scientific_diagram', 'svg', 'fixture', json.dumps(self.original),
                        'needs_quality_repair', 'vector', 0, 'initial', json.dumps(self.record), None, json.dumps(self.manifest), None))
        self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)',
                        (self.id, 'scientific_diagram', 'svg', self.original['code_sha256'], self.original['image_sha256'], 'pending', None, None, 'initial'))
        self.db.commit()
        self.folder = self.root / 'conversion/prototype/source_certificates' / self.id
        self.folder.mkdir(parents=True)
        pin = self.root / 'program.py'
        pin.write_bytes(b'verified frozen program')
        self.config = {'root': str(self.root), 'research_reserved_ids': [], 'authorized_model_ids': [],
                       'pins': {str(pin): writer.sha(pin.read_bytes()), str(Path(collector.__file__).resolve()): writer.sha(Path(collector.__file__).read_bytes()),
                                str(Path(writer.__file__).resolve()): writer.sha(Path(writer.__file__).read_bytes())}, 'scope': 'current program only',
                       'writer_begin_seconds': 1, 'writer_commit_seconds': 1}
        for name in ('svg_dom_source_scene_v1.js', 'auto_quality_svg_closed_scene_v1.py'):
            path = self.root / name
            path.write_bytes(name.encode())
            self.config['pins'][str(path)] = writer.sha(path.read_bytes())
        closure = {'root': str(self.root), 'evidence_root': str(self.folder.parent), 'policy': 'fixture_qa',
                   'catalog_sha256': 'catalog', 'pins': self.config['pins'], 'routes': [],
                   'research': {'production_route': False}}
        self.config['closure'] = closure
        scene = {'supported': False, 'ok': False, 'failures': [{'reason': 'closed_path_requires_an_explicit_role_or_basic_geometry_proof'}]}
        dom = {'sceneCapture': {'completeOfflineSource': True, 'recordId': self.id,
                               'sourcePayloadHashesRecheckedAfterCapture': True, 'blockedResources': [], 'objectIdsV6Compatible': True,
                               'extractorSha256': self.config['pins'][str(self.root / 'svg_dom_source_scene_v1.js')],
                               'moduleSha256': self.config['pins'][str(self.root / 'auto_quality_svg_closed_scene_v1.py')],
                               'recordCodeSha256': self.record['code_sha256'],
                               'sourceCodeSha256': self.record['source_code_sha256'],
                               'sourceImageSha256': self.record['source_image_sha256']}}
        files = {'current.drawio': b'native_xml', 'original_source.svg': b'original_svg',
                 'base_dom.json': b'{"issues":[]}',
                 'full_base_issues.json': b'[]', 'full_scene_issues.json': b'[]', 'full_scene_additional_issues.json': b'[]',
                 'scene_checker.json': collector.canonical(scene), 'scene_dom.json': collector.canonical(dom),
                 'fresh_source_checker.json': collector.canonical({'supported': False, 'ok': False,
                                                                  'failures': [{'reason': 'unsupported_fresh_source_features'}]})}
        inventory = {}
        for name, raw in files.items():
            path = self.folder / name
            path.write_bytes(raw)
            inventory[str(path)] = {'sha256': writer.sha(raw), 'bytes': len(raw)}
        self.plan = {'schema': collector.SCHEMA, 'id': self.id, 'proposal': True, 'catalog_sha256': 'catalog',
                     'policy': 'fixture_qa', 'source_construct_classes': ['closed_path_requires_an_explicit_role_or_basic_geometry_proof'],
                     'evidence_directory': str(self.folder), 'files': inventory, 'pins': closure['pins'],
                     'source_code_sha256': self.record['source_code_sha256'], 'source_image_sha256': self.record['source_image_sha256'],
                     'code_sha256': self.record['code_sha256'], 'image_sha256': self.record['image_sha256'],
                     'snapshot': collector.snapshot(self.db, self.id), 'route_verdicts': []}
        self.save_plan()

    def save_plan(self):
        self.plan.pop('certificate_sha256', None)
        self.plan['certificate_sha256'] = writer.sha(collector.canonical(self.plan))
        (self.folder / 'report.json').write_bytes(writer.canonical(self.plan))

    def rebind(self):
        self.db.commit()
        self.plan['snapshot'] = collector.snapshot(self.db, self.id)
        self.save_plan()

    def evidence_file(self, name, value):
        path = self.folder / name
        raw = collector.canonical(value)
        path.write_bytes(raw)
        self.plan['files'][str(path)] = {'sha256': writer.sha(raw), 'bytes': len(raw)}
        if name in ('full_base_issues.json', 'full_scene_issues.json', 'full_scene_additional_issues.json'):
            target = 'base_dom.json' if name == 'full_base_issues.json' else 'scene_dom.json'
            key = 'sceneIssues' if name == 'full_scene_additional_issues.json' else 'issues'
            dom = json.loads((self.folder / target).read_text())
            dom[key] = value
            self.evidence_file(target, dom)
        self.save_plan()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def dump(self):
        return list(self.db.iterdump())

    def test_valid_collector_proof_is_current(self):
        self.assertTrue(collector.revalidate(self.db, self.plan, self.config['closure'])['current'])

    def test_dry_run_never_writes_database_or_decision(self):
        before = self.dump()
        result = writer.apply(self.db, self.plan, self.config)
        self.assertEqual(result['state'], 'dry_run_current', result)
        self.assertEqual(self.dump(), before)
        self.assertFalse((self.root / writer.DIRECTORY).exists())

    def test_commit_only_changes_one_outcome_with_immutable_nonce_receipt(self):
        before_job = self.db.execute('select * from jobs').fetchall()
        result = writer.apply(self.db, self.plan, self.config, publish=True)
        self.assertEqual(result['state'], 'abandoned', result)
        self.assertTrue(result['applied'])
        self.assertFalse(result['accepted'])
        self.assertEqual(self.db.execute('select * from jobs').fetchall(), before_job)
        row = writer.shared._registry(self.db, self.id)
        evidence = json.loads(row[6])
        receipt = evidence[writer.MARKER]['decision']
        document, payload, _ = writer.read_decision(self.root, receipt)
        self.assertEqual(document['commit_nonce'], receipt['commit_nonce'])
        self.assertEqual(document['plan'], self.plan)
        self.assertIn('not intrinsic drawio', document['scope'] if 'not intrinsic drawio' in document['scope'] else evidence['scope'])
        self.assertEqual(writer.apply(self.db, self.plan, self.config, publish=True)['state'], 'preserved_abandoned')

    def test_research_and_authorized_model_cases_cannot_be_abandoned(self):
        for key in ('research_reserved_ids', 'authorized_model_ids'):
            config = copy.deepcopy(self.config)
            config[key] = [self.id]
            result = writer.apply(self.db, self.plan, config, publish=True)
            self.assertEqual(result['state'], 'preparation_refused', result)
            self.assertEqual(writer.shared._registry(self.db, self.id)[4], 'pending')

    def test_nonnull_unknown_stage_owner_is_not_a_historical_receipt_exception(self):
        for name in ('owner_pid', 'worker_pid'):
            self.db.execute('create table extra_' + name + '(id text,state text,' + name + ' integer)')
            self.db.execute('insert into extra_' + name + ' values(?,?,?)', (self.id, 'published', 12345))
            self.rebind()
            result = writer.apply(self.db, self.plan, self.config, publish=True)
            self.assertEqual(result['state'], 'preparation_refused', result)
            self.db.execute('drop table extra_' + name)
            self.rebind()

    def test_running_stage_without_pid_is_also_refused(self):
        self.db.execute('create table stage(id text,state text)')
        for state in ('running', 'new_running', 'new_repairing', 'producing'):
            self.db.execute('delete from stage')
            self.db.execute('insert into stage values(?,?)', (self.id, state))
            self.rebind()
            self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused')

    def test_all_id_tables_without_state_or_owner_are_in_cas(self):
        self.db.execute('create table source_font_metadata(id text,raw text)')
        self.db.execute('insert into source_font_metadata values(?,?)', (self.id, 'before'))
        self.rebind()
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        self.db.execute('update source_font_metadata set raw="after"')
        self.db.commit()
        result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'failed_rolled_back', result)
        self.assertEqual(writer.shared._registry(self.db, self.id)[4], 'pending')

    def test_schema_or_trigger_change_invalidates_preparation(self):
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        self.db.execute('create table new_stage(id text)')
        self.db.commit()
        result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'failed_rolled_back', result)

    def test_trigger_cross_table_side_effect_rolls_back_all_changes(self):
        self.db.execute('create table touched(id text,raw text)')
        self.db.execute('insert into touched values(?,?)', (self.id, 'before'))
        self.db.execute('create trigger hidden_side_effect after update on processing_outcomes_v2 begin update touched set raw="after"; end')
        self.rebind()
        before = self.dump()
        result = writer.apply(self.db, self.plan, self.config, publish=True)
        self.assertEqual(result['state'], 'failed_rolled_back', result)
        self.assertEqual(self.dump(), before)

    def test_source_resource_modified_after_preparation_cannot_commit(self):
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        (self.folder / 'original_source.svg').write_bytes(b'other_source')
        result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'failed_rolled_back', result)
        self.assertEqual(writer.shared._registry(self.db, self.id)[4], 'pending')

    def test_candidate_identity_change_cannot_hide_behind_rebound_collector_snapshot(self):
        for name in ('id', 'source_pair_sha256', 'source', 'category', 'source_format', 'format', 'source_code_sha256', 'source_image_sha256'):
            record = {**self.record, name: 'wrong'}
            self.db.execute('update jobs set output_record=?', (json.dumps(record),))
            self.rebind()
            result = writer.apply(self.db, self.plan, self.config)
            self.assertEqual(result['state'], 'preparation_refused', (name, result))
        self.db.execute('update jobs set output_record=?', (json.dumps(self.record),))
        self.rebind()

    def test_certificate_file_or_body_cannot_be_forged_in_memory(self):
        plan = copy.deepcopy(self.plan)
        plan['source_construct_classes'] = ['different_failure']
        result = writer.apply(self.db, plan, self.config)
        self.assertEqual(result['state'], 'preparation_refused', result)
        (self.folder / 'report.json').write_bytes(b'{}')
        result = writer.apply(self.db, self.plan, self.config)
        self.assertEqual(result['state'], 'preparation_refused', result)

    def test_original_manifest_identity_hash_and_dimensions_cannot_be_rebound(self):
        for name, value in [('id', 'wrong'), ('source_format', 'html'), ('code_sha256', 'b' * 64),
                            ('image_sha256', 'c' * 64), ('width', 0), ('height', None)]:
            manifest = {**self.manifest, name: value}
            self.db.execute('update jobs set input_manifest=?', (json.dumps(manifest),))
            self.rebind()
            self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused', name)

    def test_source_alias_retarget_after_crypto_preparation_cannot_commit(self):
        link = self.root / 'clean/source-link.svg'
        link.symlink_to(self.root / 'clean/source.svg')
        record = {**self.record, 'original_source_code': 'clean/source-link.svg'}
        self.db.execute('update jobs set output_record=?', (json.dumps(record),))
        self.rebind()
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        alternate = self.root / 'clean/other.svg'
        alternate.write_bytes(b'changed_source')
        link.unlink()
        link.symlink_to(alternate)
        result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'failed_rolled_back', result)
        self.assertEqual(writer.shared._registry(self.db, self.id)[4], 'pending')

    def test_manifest_alias_retarget_even_to_identical_bytes_cannot_commit(self):
        link = self.root / 'clean/manifest-source-link.svg'
        link.symlink_to(self.root / 'clean/source.svg')
        manifest = {**self.manifest, 'source_code': 'clean/manifest-source-link.svg'}
        self.db.execute('update jobs set input_manifest=?', (json.dumps(manifest),))
        self.rebind()
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        alternate = self.root / 'clean/other.svg'
        alternate.write_bytes(b'original_svg')
        link.unlink()
        link.symlink_to(alternate)
        self.assertEqual(writer.apply_prepared(self.db, prepared, self.config)['state'], 'failed_rolled_back')

    def test_unknown_job_column_layout_is_refused(self):
        self.db.execute('alter table jobs add column unreviewed text')
        self.rebind()
        result = writer.apply(self.db, self.plan, self.config)
        self.assertEqual(result['state'], 'preparation_refused', result)

    def test_unknown_failure_mixed_with_known_semantic_reason_stays_pending(self):
        scene = json.loads((self.folder / 'scene_checker.json').read_text())
        scene['failures'].append({'reason': 'unknown_capture_context'})
        self.evidence_file('scene_checker.json', scene)
        self.assertTrue(collector.revalidate(self.db, self.plan, self.config['closure'])['current'])
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused')

    def test_clone_switch_and_unknown_issue_in_any_complete_inventory_stays_pending(self):
        names = ('full_base_issues.json', 'full_scene_issues.json', 'full_scene_additional_issues.json')
        reasons = ('scene_use_expansion_bbox_mismatch', 'scene_use_inherited_css_context_not_forwarded',
                   'scene_use_opacity_context_changed', 'scene_switch_selection_unproven', 'unclassified_effect')
        for name in names:
            for reason in reasons:
                self.evidence_file(name, [{'reason': reason}])
                self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused', (name, reason))
            self.evidence_file(name, [])

    def test_resolved_semantic_reason_still_cannot_hide_nested_capture_error(self):
        self.evidence_file('full_scene_issues.json', [{'reason': 'fill_paint_server', 'error': 'source expansion failed'}])
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused')

    def test_reviewed_paint_server_feature_can_be_recorded_as_current_program_failure(self):
        self.evidence_file('full_scene_issues.json', [{'reason': 'fill_paint_server', 'value': 'url(#gradient)'}])
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'dry_run_current')

    def test_informational_sampling_cap_requires_full_independent_topology(self):
        issue = {'reason': 'scene_geometry_sampling_capped', 'severity': 'informational'}
        self.evidence_file('full_scene_additional_issues.json', [issue])
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused')
        dom = json.loads((self.folder / 'scene_dom.json').read_text())
        dom['objects'] = [{'id': 'path', 'type': 'shape', 'sceneGeometry': {'topology': {
            'parser': 'fontTools.svgLib.path.parse_path/RecordingPen', 'subpath_count': 1,
            'subpaths': [{'operations': [{'operation': 'moveTo'}, {'operation': 'lineTo'}]}]}}}]
        self.evidence_file('scene_dom.json', dom)
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'dry_run_current')

    def test_resealed_source_failure_class_lie_is_rejected(self):
        self.plan['source_construct_classes'] = ['unresolved_source_feature']
        self.save_plan()
        self.assertTrue(collector.revalidate(self.db, self.plan, self.config['closure'])['current'])
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused')

    def test_stripped_derived_inventory_cannot_hide_original_dom_capture_issue(self):
        self.evidence_file('full_scene_issues.json', [{'reason': 'scene_use_expansion_bbox_mismatch'}])
        path = self.folder / 'full_scene_issues.json'
        path.write_bytes(b'[]')
        self.plan['files'][str(path)] = {'sha256': writer.sha(b'[]'), 'bytes': 2}
        self.save_plan()
        self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused')

    def test_capture_author_and_resource_recheck_cannot_be_forged(self):
        original = json.loads((self.folder / 'scene_dom.json').read_text())
        for key, value in [('extractorSha256', 'f' * 64), ('moduleSha256', 'f' * 64),
                           ('sourcePayloadHashesRecheckedAfterCapture', False), ('blockedResources', ['https://example.invalid'])]:
            dom = copy.deepcopy(original)
            dom['sceneCapture'][key] = value
            self.evidence_file('scene_dom.json', dom)
            self.assertEqual(writer.apply(self.db, self.plan, self.config)['state'], 'preparation_refused', key)

    def test_commit_ack_loss_is_recovered_only_by_exact_nonce_bound_row(self):
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        real_commit = writer.BusyBudget.commit

        def lost_ack(budget, db):
            real_commit(budget, db)
            raise sqlite3.OperationalError('commit ack lost')

        with patch.object(writer.BusyBudget, 'commit', lost_ack):
            result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'abandoned', result)
        self.assertTrue(result['commit_receipt_recovered'])

    def test_commit_ack_and_probe_loss_are_reported_unknown_without_replaying(self):
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        real_commit = writer.BusyBudget.commit
        real_registry = writer.shared._registry

        def lost_ack(budget, db):
            real_commit(budget, db)
            raise sqlite3.OperationalError('commit ack lost')

        def failed_probe(db, identifier):
            if not db.in_transaction:
                raise sqlite3.OperationalError('probe temporarily unavailable')
            return real_registry(db, identifier)

        with patch.object(writer.BusyBudget, 'commit', lost_ack), patch.object(writer.shared, '_registry', failed_probe):
            result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'commit_outcome_unknown', result)
        self.assertTrue(result['may_have_committed'])
        self.assertEqual(real_registry(self.db, self.id), prepared['expected'])

    def test_pinned_program_change_cannot_commit(self):
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        (self.root / 'program.py').write_bytes(b'unreviewed_program')
        self.assertEqual(writer.apply_prepared(self.db, prepared, self.config)['state'], 'failed_rolled_back')

    def test_symlink_ancestry_cannot_redirect_decision_write(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'conversion' / writer.DIRECTORY.name).symlink_to(outside, target_is_directory=True)
        result = writer.apply(self.db, self.plan, self.config, publish=True)
        self.assertEqual(result['state'], 'preparation_refused', result)
        self.assertEqual(list(outside.iterdir()), [])

    def test_crypto_and_fsync_are_not_repeated_under_writer_lock(self):
        prepared = writer.prepare_decision(self.db, self.plan, self.config, publish=True)
        with ExitStack() as stack:
            stack.enter_context(patch.object(writer.collector, 'revalidate', side_effect=AssertionError('source hash/read in writer')))
            stack.enter_context(patch.object(writer.shared, 'file_witness', side_effect=AssertionError('crypto read in writer')))
            stack.enter_context(patch.object(writer, '_write_decision', side_effect=AssertionError('fsync in writer')))
            result = writer.apply_prepared(self.db, prepared, self.config)
        self.assertEqual(result['state'], 'abandoned', result)


if __name__ == '__main__':
    unittest.main()
