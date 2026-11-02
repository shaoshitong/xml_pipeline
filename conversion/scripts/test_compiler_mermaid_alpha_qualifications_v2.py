import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import compiler_mermaid_alpha_qualifications_v2 as helper


def sha(data):return hashlib.sha256(data).hexdigest()


class LiveQualifiedLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)

    def fixture(self,identifier='kept',suffix=''):
        clean=self.root/'clean'/('assets_'+identifier+suffix);clean.mkdir(parents=True)
        source=dict(pair_sha256=identifier,format='mermaid',category='scientific_diagram',source='provider')
        manifest=dict(id=identifier,source_pair_sha256=identifier,source_format='mermaid',category=source['category'],source='provider',format='drawio',status='qualified')
        for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
            path=clean/field;path.write_bytes(field.encode());manifest[field]=str(path.relative_to(self.root));manifest[digest]=sha(path.read_bytes())
        source.update(code_sha256=manifest['source_code_sha256'],image_sha256=manifest['source_image_sha256']);return source,manifest

    def ledger(self,name,entries,location='compiler_iterations/runs',columns='id text primary key,status text,result text'):
        path=self.root/'release'/location/name/'status.sqlite';path.parent.mkdir(parents=True)
        with sqlite3.connect(path)as db:
            db.execute('create table samples('+columns+')')
            for identifier,status,result in entries:db.execute('insert into samples values(?,?,?)',(identifier,status,result if isinstance(result,str)or result is None else json.dumps(result)))
        return path

    def qualified(self,manifest):return dict(id=manifest['id'],status='qualified',manifest=manifest)

    def test_live_SQLite_qualification_requires_no_final_or_inprogress_export(self):
        source,manifest=self.fixture();ledger=self.ledger('live',[(manifest['id'],'qualified',self.qualified(manifest))]);before=sha(ledger.read_bytes())
        self.assertEqual(helper.ledger_manifests(self.root),[manifest]);self.assertEqual(helper.find_qualified('kept',source,self.root),manifest)
        self.assertFalse(list(ledger.parent.glob('*.jsonl')));self.assertEqual(sha(ledger.read_bytes()),before)

    def test_multiple_current_and_authoritative_legacy_ledgers_are_covered(self):
        import compiler_iteration_inventory_v1 as inventory
        _,a=self.fixture('a');_,b=self.fixture('b');_,c=self.fixture('c')
        self.ledger('a',[(a['id'],'qualified',self.qualified(a))]);self.ledger('b',[(b['id'],'qualified',self.qualified(b))])
        legacy=self.ledger('legacy',[(c['id'],'qualified',self.qualified(c))],location='compiler_v1')
        with patch.object(inventory,'SOURCES',[('ordinary_graphviz_live','db',str(legacy.relative_to(self.root)))]):
            self.assertEqual({row['id']for row in helper.ledger_manifests(self.root)},{'a','b','c'})

    def test_all_registered_legacy_DB_paths_are_in_the_catalog(self):
        import compiler_iteration_inventory_v1 as inventory
        expected=set()
        for index,(_,kind,relative)in enumerate(inventory.SOURCES):
            if kind!='db':continue
            _,manifest=self.fixture('legacy_'+str(index));path=self.root/relative;path.parent.mkdir(parents=True)
            with sqlite3.connect(path)as db:
                db.execute('create table samples(id text primary key,status text,result text)');db.execute('insert into samples values(?,?,?)',(manifest['id'],'qualified',json.dumps(self.qualified(manifest))))
            expected.add(manifest['id'])
        self.assertTrue(expected);self.assertEqual({row['id']for row in helper.ledger_manifests(self.root)},expected)

    def test_recursive_release_scan_is_never_used_or_unregistered_archive_opened(self):
        _,manifest=self.fixture();current=self.ledger('live',[('kept','qualified',self.qualified(manifest))])
        self.ledger('archived',[('bad','qualified','invalid JSON')],location='archives/huge_nested/data')
        with patch.object(Path,'rglob',side_effect=AssertionError('recursive release scan forbidden')):
            self.assertEqual(helper.discover_ledger_paths(self.root),[current.resolve()]);self.assertEqual(helper.ledger_manifests(self.root),[manifest])

    def test_current_inventory_explicit_DB_catalog_completes_floor_and_deduplicates(self):
        _,a=self.fixture('a');_,b=self.fixture('b');current=self.ledger('a',[('a','qualified',self.qualified(a))])
        legacy=self.ledger('b',[('b','qualified',self.qualified(b))],location='registered_legacy/nested')
        directory=self.root/'release/compiler_iterations';summary=directory/'catalog/summary.json';summary.parent.mkdir(parents=True)
        payload=json.dumps({'sources':[{'path':str(legacy.relative_to(self.root))},{'kind':'db','path':str(current.relative_to(self.root))},{'kind':'manifests','path':'release/not_a_ledger.jsonl'}]}).encode();summary.write_bytes(payload)
        (directory/'current.json').write_text(json.dumps({'inventory':str(summary.relative_to(self.root)),'inventory_sha256':sha(payload)}))
        self.assertEqual(set(helper.discover_ledger_paths(self.root)),{current.resolve(),legacy.resolve()});self.assertEqual({row['id']for row in helper.ledger_manifests(self.root)},{'a','b'})

    def test_current_catalog_hash_or_outside_path_conflict_is_explicit(self):
        directory=self.root/'release/compiler_iterations';directory.mkdir(parents=True);summary=directory/'summary.json';summary.write_text('{"sources": []}')
        pointer=directory/'current.json';pointer.write_text(json.dumps({'inventory':str(summary.relative_to(self.root)),'inventory_sha256':'0'*64}))
        with self.assertRaisesRegex(RuntimeError,'catalog_inventory_hash_mismatch'):helper.discover_ledger_paths(self.root)
        pointer.write_text(json.dumps({'inventory':'../outside.json'}))
        with self.assertRaisesRegex(RuntimeError,'catalog_discovery_failed|catalog_outside_release'):helper.discover_ledger_paths(self.root)

    def test_missing_catalog_and_known_legacy_paths_are_ignored_without_owner_filter(self):
        import compiler_iteration_inventory_v1 as inventory
        _,manifest=self.fixture();legacy=self.ledger('legacy',[('kept','qualified',self.qualified(manifest))],location='compiler_v2')
        (legacy.parent/'owner.json').write_text('{"pid": -1, "start_ticks": -1}')
        with patch.object(inventory,'SOURCES',[('legacy','db',str(legacy.relative_to(self.root))),('missing','db','release/missing/status.sqlite')]):
            self.assertEqual(helper.ledger_manifests(self.root),[manifest])

    def test_queued_running_and_abandoned_are_not_qualifications(self):
        self.ledger('states',[('q','queued',None),('r','running','bad JSON'),('a','abandoned','bad JSON')]);self.assertEqual(helper.ledger_manifests(self.root),[])

    def test_irrelevant_status_schema_is_ignored(self):
        path=self.root/'release/compiler_iterations/runs/other/status.sqlite';path.parent.mkdir(parents=True)
        with sqlite3.connect(path)as db:db.execute('create table samples(id text,state text)')
        self.assertEqual(helper.ledger_manifests(self.root),[])

    def test_filter_is_exact_and_does_not_parse_foreign_corrupt_rows(self):
        source,manifest=self.fixture();self.ledger('filter',[('kept','qualified',self.qualified(manifest)),('kept_extra','qualified','bad JSON')])
        self.assertEqual(helper.ledger_manifests(self.root,identifiers={'kept'}),[manifest]);self.assertEqual(helper.find_qualified('kept',source,self.root),manifest)
        with self.assertRaisesRegex(RuntimeError,'invalid_qualified_result_JSON'):helper.ledger_manifests(self.root)

    def test_empty_filter_never_opens_a_database(self):
        with patch.object(helper.sqlite3,'connect',side_effect=AssertionError('must not scan')):self.assertEqual(helper.ledger_manifests(self.root,identifiers=set()),[])

    def test_result_ID_conflict_is_infrastructure_failure(self):
        _,manifest=self.fixture();value=self.qualified(manifest);value['id']='other';self.ledger('bad',[('kept','qualified',value)])
        with self.assertRaisesRegex(RuntimeError,'infrastructure_qualified_ledger_result_identity_conflict'):helper.ledger_manifests(self.root)

    def test_result_status_conflict_is_infrastructure_failure(self):
        _,manifest=self.fixture();value=self.qualified(manifest);value['status']='abandoned';self.ledger('bad',[('kept','qualified',value)])
        with self.assertRaisesRegex(RuntimeError,'result_identity_conflict'):helper.ledger_manifests(self.root)

    def test_manifest_ID_conflict_is_infrastructure_failure(self):
        _,manifest=self.fixture();manifest['id']='other';value=dict(id='kept',status='qualified',manifest=manifest);self.ledger('bad',[('kept','qualified',value)])
        with self.assertRaisesRegex(RuntimeError,'manifest_identity_conflict'):helper.ledger_manifests(self.root)

    def test_missing_or_invalid_qualified_payload_is_never_ignored(self):
        self.ledger('bad',[('kept','qualified',None)])
        with self.assertRaisesRegex(RuntimeError,'invalid_qualified_result_JSON'):helper.ledger_manifests(self.root)

    def test_damaged_asset_is_infrastructure_error_instead_of_missing_qualification(self):
        source,manifest=self.fixture();self.ledger('valid',[(manifest['id'],'qualified',self.qualified(manifest))]);(self.root/manifest['image_file']).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'infrastructure_qualified_ledger_asset_or_source_conflict.*hash_mismatch'):helper.find_qualified('kept',source,self.root)

    def test_every_qualification_is_checked_even_if_first_one_is_good(self):
        source,manifest=self.fixture();conflict=copy.deepcopy(manifest);conflict['image_sha256']='0'*64
        self.ledger('a_good',[('kept','qualified',self.qualified(manifest))]);self.ledger('b_conflict',[('kept','qualified',self.qualified(conflict))])
        with self.assertRaisesRegex(RuntimeError,'asset_or_source_conflict'):helper.find_qualified('kept',source,self.root)

    def test_distinct_valid_versions_of_same_source_are_both_validated(self):
        source,a=self.fixture();_,b=self.fixture(suffix='_v2');self.ledger('a',[('kept','qualified',self.qualified(a))]);self.ledger('b',[('kept','qualified',self.qualified(b))])
        self.assertEqual(len(helper.ledger_manifests(self.root)),2);self.assertEqual(helper.find_qualified('kept',source,self.root),a)

    def test_original_dataset_or_hash_mismatch_is_infrastructure_error(self):
        source,manifest=self.fixture();self.ledger('valid',[('kept','qualified',self.qualified(manifest))]);source['source']='different_provider'
        with self.assertRaisesRegex(RuntimeError,'dataset_mismatch'):helper.find_qualified('kept',source,self.root)

    def test_no_qualification_returns_none(self):
        source,_=self.fixture();self.assertIsNone(helper.find_qualified('kept',source,self.root))

    def test_large_ID_filter_is_chunked_below_SQLite_parameter_limit(self):
        _,manifest=self.fixture();self.ledger('ids',[('kept','qualified',self.qualified(manifest))]);wanted={'id_'+str(i)for i in range(1200)}|{'kept'}
        self.assertEqual(helper.ledger_manifests(self.root,identifiers=wanted),[manifest])


if __name__=='__main__':unittest.main()
