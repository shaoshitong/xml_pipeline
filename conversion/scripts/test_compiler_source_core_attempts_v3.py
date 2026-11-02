import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import compiler_source_core_attempts_v3 as history


class OncePerSourceCoreTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        sourcefile=self.root/'conversion/scripts/frozen_source.py';sourcefile.parent.mkdir(parents=True);sourcefile.write_text('source semantics')
        self.configuration=dict(unit='unit',policy='stable_source_policy',pins={str(sourcefile):history.sha(sourcefile.read_bytes())})
        self.source=dict(pair_sha256='a'*64,format='python',category='scientific_diagram',source='provider',code_sha256='b'*64,image_sha256='c'*64,clean_row=19)
        self.catalog=self.root/history.CATALOG;self.catalog.parent.mkdir(parents=True);self.catalog.write_bytes(history.raw(dict(schema='source_core_manual_attempt_catalog_v3',entries=[])))

    def ledger(self,name='run',phase='candidate',result_phase='conversion',attempt=True,status='abandoned',front=None,mode='development',identifier=None,source=None):
        identifier=identifier or self.source['pair_sha256'];source=source or self.source
        directory=self.root/'release/compiler_iterations/runs'/name;directory.mkdir(parents=True)
        directory.joinpath('freeze.json').write_bytes(history.raw(dict(pins={**self.configuration['pins'],'orchestration_v1.py':'d'*64})))
        request=dict(id=identifier,source=source,compiler_unit='unit',evaluation_phase=phase)
        result=None if status=='running'else dict(id=identifier,status=status,phase=result_phase,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],reason='ordinary_source_failure')
        if front is not None:
            work=self.root/'conversion/compiler_iterations'/name/identifier;work.mkdir(parents=True);(work/'frontend_result.json').write_bytes(history.raw(front));result['evidence_directory']=str(work.relative_to(self.root))
        path=directory/'status.sqlite'
        with sqlite3.connect(path)as db:
            db.execute('create table metadata(key text,value text)');db.execute('insert into metadata values(?,?)',('mode',json.dumps(mode)))
            db.execute('create table samples(id text,status text,attempts integer,source text,result text)');db.execute('insert into samples values(?,?,?,?,?)',(identifier,status,int(attempt),json.dumps(request),json.dumps(result)if result is not None else None))
        return path

    def collect(self,**kwargs):return history.collect(self.configuration,self.root,**kwargs)

    def manual(self):
        identifier=self.source['pair_sha256'];directory=self.root/'conversion/finite_development';directory.mkdir(parents=True)
        receipt=directory/'summary.json';receipt.write_bytes(history.raw(dict(cases=[dict(id=identifier,normal_calls=1)])))
        front=directory/'frontend_result.json';front.write_bytes(history.raw(dict(ok=False,reason='source_pixel_pending',infrastructure_failure=False)))
        declaration=dict(id=identifier,source=self.source,source_core_key=history.core_identity(self.configuration)['key'],receipt=dict(file=str(receipt),sha256=history.sha(receipt.read_bytes())),rows_key='cases',row_index=0,normal_count_key='normal_calls',frontend=dict(file=str(front),sha256=history.sha(front.read_bytes())))
        self.catalog.write_bytes(history.raw(dict(schema='source_core_manual_attempt_catalog_v3',entries=[declaration])))
        return declaration

    def test_development_normal_call_is_authoritative_without_any_export(self):
        path=self.ledger(front=dict(ok=False,infrastructure_failure=False,reason='canvas_pending'));before=history.sha(path.read_bytes());events=self.collect()
        self.assertEqual(len(events),1);self.assertTrue(history.validate(events,self.configuration,self.root));self.assertEqual(history.sha(path.read_bytes()),before)
        self.assertFalse(list(path.parent.glob('*qualified.jsonl')))

    def test_existing_positive_negative_baseline_and_failure_replay_are_never_normal(self):
        for index,phase in enumerate(('baseline','control_positive','control_failure_replay')):self.ledger(str(index),phase=phase,front=dict(ok=False))
        self.assertEqual(self.collect(),[])
        self.assertFalse(history.normal_was_called({'negative_control':True},{},None))
        self.assertFalse(history.normal_was_called({'existing_development_candidate':'candidate'},{},None))
        self.assertFalse(history.normal_was_called({'existing_development_failure':{} ,'evaluation_phase':'control_failure_replay'},{},None))

    def test_explicit_precall_false_flag_and_input_failure_can_retry(self):
        self.ledger('guard',front=dict(ok=False,reason='guard',normal_source_conversion_called=False))
        self.ledger('input',result_phase='input')
        self.assertEqual(self.collect(),[])

    def test_dead_owner_ambiguous_started_attempt_does_not_reset_history(self):
        path=self.ledger(status='running');(path.parent/'owner.json').write_text('{"pid":-1}')
        events=self.collect();self.assertEqual(len(events),1);self.assertTrue(events[0]['ambiguity_conservatively_preserved'])

    def test_queued_unclaimed_row_has_no_normal_attempt(self):
        self.ledger(attempt=False,status='running');self.assertEqual(self.collect(),[])

    def test_orchestration_version_change_is_not_a_source_version_change(self):
        self.ledger('old_orchestration');self.ledger('new_orchestration');events=self.collect()
        self.assertEqual(len(events),2);self.assertEqual({event['source_core']['key']for event in events},{history.core_identity(self.configuration)['key']})

    def test_changed_source_core_can_retry_under_new_identity(self):
        self.ledger();changed=copy.deepcopy(self.configuration);changed['pins'][next(iter(changed['pins']))]='f'*64
        self.assertNotEqual(history.core_identity(changed),history.core_identity(self.configuration));self.assertEqual(history.collect(changed,self.root),[])

    def test_only_own_current_run_is_ignored_by_before_normal_guard(self):
        self.ledger('current',status='running')
        self.assertFalse(history.guard(self.source['pair_sha256'],self.source,self.configuration,current_run='current',root=self.root)['already_attempted'])
        self.ledger('prior',front=dict(ok=False));self.assertTrue(history.guard(self.source['pair_sha256'],self.source,self.configuration,current_run='current',root=self.root)['already_attempted'])

    def test_manual_development_calls_are_preserved_independently_of_ledger(self):
        self.manual();events=self.collect();self.assertEqual(len(events),1);self.assertEqual(events[0]['evidence_kind'],'manual_development');self.assertTrue(history.validate(events,self.configuration,self.root))

    def test_missing_history_evidence_is_infrastructure_before_any_new_normal_call(self):
        declaration=self.manual();Path(declaration['frontend']['file']).unlink()
        with self.assertRaisesRegex(RuntimeError,'infrastructure_source_core_attempt_history:FileNotFoundError'):self.collect()

    def test_manual_catalog_never_silently_ignores_corrupt_receipt(self):
        declaration=self.manual();Path(declaration['receipt']['file']).write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'immutable_evidence_changed'):self.collect()

    def test_guard_rejects_same_ID_with_different_original_source_hash(self):
        self.manual();source=dict(self.source,code_sha256='f'*64)
        with self.assertRaisesRegex(RuntimeError,'original_source_conflicts'):history.guard(self.source['pair_sha256'],source,self.configuration,root=self.root)

    def test_ID_filter_is_exact_across_multiple_ledger_modes(self):
        self.ledger('dev',front=dict(ok=False));other=dict(self.source,pair_sha256='e'*64);self.ledger('batch',source=other,identifier=other['pair_sha256'],mode='batch',front=dict(ok=False))
        self.assertEqual([x['id']for x in self.collect(identifiers={self.source['pair_sha256']})],[self.source['pair_sha256']]);self.assertEqual(len(self.collect()),2)

    def test_immutable_frontend_evidence_is_rechecked_before_guard_allows_reuse(self):
        self.ledger(front=dict(ok=False));events=self.collect();Path(events[0]['frontend']['file']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'immutable_evidence_changed'):history.validate(events,self.configuration,self.root)


if __name__=='__main__':unittest.main()
