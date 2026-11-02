"""Live admission is independent from historical eligibility and root allowlists."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import bounded_patch_gateway_v2 as g

XML='<mxfile><diagram><mxGraphModel pageWidth="200" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="Alpha"><mxGeometry x="10" y="10" width="30" height="20" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='gateway_v2_admission_')
        self.root=Path(self.tmp.name).resolve()
        work=self.root/'conversion';work.mkdir()
        clean=self.root/'clean/case';clean.mkdir(parents=True)
        source=b'authoritative original source';reference=b'authoritative source image';image=b'actual current native PNG'
        for name,data in [('diagram.drawio',XML.encode()),('image.png',image),('source.drawio',source),('reference.png',reference)]:
            (clean/name).write_bytes(data)
        self.identifier='a'*64
        self.record={'id':self.identifier,'source_pair_sha256':self.identifier,'source_format':'drawio',
                     'source_code_sha256':g.core.sha(source),'source_image_sha256':g.core.sha(reference),
                     'code_file':'clean/case/diagram.drawio','image_file':'clean/case/image.png',
                     'code_sha256':g.core.sha(XML.encode()),'image_sha256':g.core.sha(image),
                     'original_source_code':'clean/case/source.drawio','original_reference':'clean/case/reference.png',
                     'source_record':{'code_sha256':g.core.sha(source),'image_sha256':g.core.sha(reference)}}
        self.original={'code_sha256':self.record['source_code_sha256'],'image_sha256':self.record['source_image_sha256']}
        self.expected={'scientific_diagram':1,'poster':1}
        self.live_path=work/'jobs.sqlite'
        self.live=sqlite3.connect(self.live_path)
        self.live.execute('PRAGMA journal_mode=WAL')
        self.live.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,category TEXT,format TEXT,state TEXT,worker_pid INT,input_record TEXT,output_record TEXT,input_manifest TEXT,updated_at TEXT)')
        self.live.execute('CREATE TABLE processing_outcomes_v2(id TEXT PRIMARY KEY,category TEXT,format TEXT,source_code_hash TEXT,source_image_hash TEXT,status TEXT,reason TEXT,record TEXT,updated_at TEXT)')
        self.live.execute('CREATE TABLE harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,attempts INT,worker_pid INT,session_dir TEXT,error TEXT)')
        for identifier,category,fmt in [(self.identifier,'scientific_diagram','drawio'),('d'*64,'poster','html')]:
            record={**self.record,'id':identifier,'source_pair_sha256':identifier,'source_format':fmt}
            self.live.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(identifier,category,fmt,'needs_quality_repair',None,json.dumps(self.original),json.dumps(record),'clean/source/input.parquet','job-stamp'))
            self.live.execute('INSERT INTO processing_outcomes_v2 VALUES(?,?,?,?,?,?,?,?,?)',(identifier,category,fmt,self.record['source_code_sha256'],self.record['source_image_sha256'],'pending',None,None,'outcome-stamp'))
        self.live.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?)',(self.identifier,'held_by_root_policy',7,None,'old-session','historic-error'))
        self.live.commit()
        self.private=sqlite3.connect(':memory:');g.initialize(self.private);self.private.commit()
        self.history={'original_id':self.identifier,'history_snapshot_id':'history-frozen-snapshot','max_calls':2,
                      'confirmed_calls':0,'unknown_reservations':0,'conservative_budget_used':0,
                      'coverage_complete_for_id':True,'unknown_usage':False,'remaining_calls':2,
                      'eligible_for_new_call':True,'covered_gateway_request_keys':[]}
        self.policy=json.loads((Path(__file__).parents[1]/'model_usage_policy_v2.json').read_text())
        self.policy.update(input_root=str(self.root),expected_input_pairs=2,categories=self.expected,
                           new_gateway_enabled=True,authorized_model_sample_ids=[self.identifier])
        self.policy_path=work/'isolated-model-policy.json';self.policy_path.write_text(json.dumps(self.policy))
        self.prepared=g.prepare(self.record,XML,['a'],source_context={'source':'immutable'},errors=[{'reason':'text mismatch','cell':'a'}],
          repair_plan={'source':'fixed_program','base_code_sha256':self.record['code_sha256'],'evidence_sha256':'e'*64,
                       'defects':[{'reason':'localized text mismatch','cells':['a'],'allowed_operations':['set_value']}]})

    def tearDown(self):
        self.private.close();self.live.close();self.tmp.cleanup()

    def mutate(self,sql,args=()):
        self.live.execute(sql,args);self.live.commit()

    def admission(self,**kwargs):
        return g.check_current_admission(self.prepared,db_path=self.live_path,expected=self.expected,**kwargs)

    def reserve(self):
        return g.reserve(self.private,self.prepared,lambda _:copy.deepcopy(self.history),policy_path=self.policy_path)

    def send(self,reservation,callback=None,history_lookup=None,**kwargs):
        return g.send_once(self.private,self.prepared,reservation,callback or (lambda *_:{'response_id':'fake-message','usage':{'outputTokens':4}}),
          policy_path=self.policy_path,history_lookup=history_lookup or (lambda _:copy.deepcopy(self.history)),**kwargs)

    def test_pending_registered_current_pair_is_read_only_and_snapshot_bound(self):
        before=list(self.live.iterdump())
        result=self.admission()
        self.assertTrue(result['current_admission_verified'])
        self.assertTrue(result['read_only'])
        self.assertEqual(result['snapshot']['expected_inputs'],2)
        self.assertEqual(before,list(self.live.iterdump()))
        self.admission(expected_snapshot=result)

    def test_reservation_atomically_contains_fresh_canonical_admission(self):
        reservation=self.reserve()
        evidence=json.loads(self.private.execute('SELECT evidence_json FROM '+g.TABLE).fetchone()[0])
        admission=evidence['history'][g.ADMISSION_KEY]
        self.assertEqual(admission['snapshot']['original_id'],self.identifier)
        self.assertEqual(admission['snapshot']['code_sha256'],self.record['code_sha256'])
        self.assertEqual(reservation['gateway_version'],2)

    def test_history_snapshot_quality_is_not_live_admission(self):
        self.history.update(eligible_for_new_call=False,qualified=True,current_job_state='accepted',current_code_sha256='stale')
        reservation=self.reserve()
        self.assertEqual(self.send(reservation)['response_id'],'fake-message')

    def test_live_accepted_is_refused_even_if_history_and_allowlist_say_eligible(self):
        self.mutate("UPDATE jobs SET state='accepted' WHERE id=?",(self.identifier,))
        with self.assertRaisesRegex(ValueError,'already_accepted_or_qualified'):self.reserve()
        self.assertEqual(self.private.execute('SELECT count(*) FROM '+g.TABLE).fetchone()[0],0)

    def test_live_qualified_outcome_is_refused_even_with_current_idle_job(self):
        self.mutate("UPDATE processing_outcomes_v2 SET status='qualified',record='{}' WHERE id=?",(self.identifier,))
        with self.assertRaisesRegex(ValueError,'already_accepted_or_qualified'):self.admission()

    def test_abandoned_or_unknown_outcome_requires_explicit_reopening(self):
        for status in ['abandoned','unknown']:
            self.mutate('UPDATE processing_outcomes_v2 SET status=?,reason=? WHERE id=?',(status,'reasoned outcome',self.identifier))
            with self.assertRaisesRegex(ValueError,'terminal_or_unknown'):self.admission()

    def test_missing_database_is_not_created_and_unknown_schema_locks_admission(self):
        missing=self.root/'missing/conversion/jobs.sqlite'
        with self.assertRaisesRegex(ValueError,'database_missing'):
            g.check_current_admission(self.prepared,db_path=missing,expected=self.expected)
        self.assertFalse(missing.exists())
        self.mutate('DROP TABLE processing_outcomes_v2')
        with self.assertRaisesRegex(ValueError,'registry_schema_missing'):self.admission()

    def test_current_id_must_exist_in_exact_registered_input_scope(self):
        self.mutate('DELETE FROM jobs WHERE id=?',('d'*64,))
        with self.assertRaisesRegex(ValueError,'input_scope_changed'):self.admission()

    def test_outcome_count_and_all_registered_ids_must_match(self):
        self.mutate('UPDATE processing_outcomes_v2 SET id=? WHERE id=?',('f'*64,'d'*64))
        with self.assertRaisesRegex(ValueError,'registered_original_id_set'):self.admission()

    def test_unregistered_original_is_never_treated_as_zero_history(self):
        prepared=copy.deepcopy(self.prepared);prepared['identity']['id']='c'*64
        with self.assertRaisesRegex(ValueError,'original_not_registered'):
            g.check_current_admission(prepared,db_path=self.live_path,expected=self.expected)

    def test_input_registry_and_output_source_identities_are_all_checked(self):
        operations=[('UPDATE jobs SET input_record=? WHERE id=?',(json.dumps({**self.original,'code_sha256':'f'*64}),self.identifier)),
                    ('UPDATE processing_outcomes_v2 SET source_image_hash=? WHERE id=?',('f'*64,self.identifier)),
                    ('UPDATE processing_outcomes_v2 SET category=? WHERE id=?',('poster',self.identifier))]
        for sql,args in operations:
            with self.subTest(sql=sql):
                self.live.execute('SAVEPOINT change');self.live.execute(sql,args)
                # A separate read-only connection must see committed mutations.
                self.live.execute('RELEASE change');self.live.commit()
                with self.assertRaises(ValueError):self.admission()
                self.live.execute('UPDATE jobs SET input_record=? WHERE id=?',(json.dumps(self.original),self.identifier))
                self.live.execute('UPDATE processing_outcomes_v2 SET category=?,source_image_hash=? WHERE id=?',('scientific_diagram',self.record['source_image_sha256'],self.identifier));self.live.commit()

    def test_current_code_image_and_metadata_hash_changes_are_refused(self):
        for changes in [{'code_sha256':'f'*64},{'image_sha256':'f'*64},{'code_file':'clean/other.drawio'},{'new_review':'changed after planning'},
                        {'source_pair_sha256':'f'*64},{'source_code_sha256':'f'*64}]:
            self.mutate('UPDATE jobs SET output_record=? WHERE id=?',(json.dumps({**self.record,**changes}),self.identifier))
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.admission()
        self.mutate('UPDATE jobs SET output_record=? WHERE id=?',(json.dumps(self.record),self.identifier))

    def test_live_clean_file_hashes_are_rechecked_not_just_metadata(self):
        for relative in ['code_file','image_file','original_source_code','original_reference']:
            path=self.root/self.record[relative];old=path.read_bytes();path.write_bytes(old+b' changed')
            with self.subTest(file=relative),self.assertRaisesRegex(ValueError,'file_hash_changed'):self.admission()
            path.write_bytes(old)

    def test_job_owner_or_unknown_running_state_is_a_hard_refusal(self):
        for state,owner in [('needs_quality_repair',1),('needs_quality_repair',0),('repair_running',None),('auto_quality_font_repairing',None),('unknown',None)]:
            self.mutate('UPDATE jobs SET state=?,worker_pid=? WHERE id=?',(state,owner,self.identifier))
            with self.subTest(state=state,owner=owner),self.assertRaisesRegex(ValueError,'busy_owned_or_unknown'):self.admission()

    def test_every_model_queue_generation_blocks_running_or_owner_including_old_schema(self):
        for table in g.MODEL_TABLES:
            if table=='harness_queue_v3':
                self.mutate("UPDATE harness_queue_v3 SET state='running' WHERE id=?",(self.identifier,))
            else:
                self.mutate('CREATE TABLE '+table+'(id TEXT,state TEXT)')
                self.mutate('INSERT INTO '+table+' VALUES(?,?)',(self.identifier,'running'))
            with self.subTest(table=table),self.assertRaisesRegex(ValueError,'model_queue_running_or_owned'):self.admission()
            if table!='harness_queue_v3':self.mutate('DROP TABLE '+table)
            else:self.mutate("UPDATE harness_queue_v3 SET state='attempt_finished' WHERE id=?",(self.identifier,))
        self.mutate('UPDATE harness_queue_v3 SET worker_pid=9 WHERE id=?',(self.identifier,))
        with self.assertRaisesRegex(ValueError,'model_queue_running_or_owned'):self.admission()

    def test_send_rejects_new_qualification_and_marks_proven_local_refusal(self):
        reservation=self.reserve();self.mutate("UPDATE processing_outcomes_v2 SET status='qualified' WHERE id=?",(self.identifier,))
        calls=[]
        with self.assertRaisesRegex(ValueError,'already_accepted_or_qualified'):self.send(reservation,lambda *_:calls.append(1))
        state,evidence=self.private.execute('SELECT state,evidence_json FROM '+g.TABLE).fetchone()
        self.assertEqual(calls,[]);self.assertEqual(state,'blocked_local')
        self.assertFalse(json.loads(evidence)['upstream_send_performed'])

    def test_full_reservation_snapshot_includes_input_outcome_stamp_and_idle_queue_history(self):
        for sql,args in [("UPDATE jobs SET input_manifest='changed' WHERE id=?",(self.identifier,)),
                         ("UPDATE processing_outcomes_v2 SET updated_at='changed' WHERE id=?",(self.identifier,)),
                         ("UPDATE harness_queue_v3 SET error='changed' WHERE id=?",(self.identifier,))]:
            before=self.admission();self.mutate(sql,args)
            with self.assertRaisesRegex(ValueError,'snapshot_changed_after_reservation'):self.admission(expected_snapshot=before)

    def test_transport_boundary_catches_qualification_after_initial_send_check(self):
        reservation=self.reserve();calls=[]
        def history(_):
            self.mutate("UPDATE jobs SET state='accepted' WHERE id=?",(self.identifier,))
            return copy.deepcopy(self.history)
        with self.assertRaisesRegex(ValueError,'already_accepted_or_qualified'):
            self.send(reservation,lambda *_:calls.append(1),history_lookup=history)
        self.assertEqual(calls,[])
        self.assertEqual(self.private.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'blocked_local')

    def test_pre_send_observer_cannot_free_another_already_sent_reservation(self):
        reservation=self.reserve();g.core.mark_sent(self.private,reservation)
        g._locally_block(self.private,reservation,ValueError('concurrent stale observer'),'before_send')
        self.assertEqual(self.private.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'sent_unknown')

    def test_successful_fake_transport_records_live_admission_without_changing_canonical_db(self):
        reservation=self.reserve();before=list(self.live.iterdump());calls=[]
        result=self.send(reservation,lambda request,key:(calls.append(key) or {'response_id':'fake-response','usage':{'outputTokens':3}}))
        self.assertEqual(calls,[reservation['request_key']]);self.assertEqual(result['response_id'],'fake-response')
        self.assertEqual(before,list(self.live.iterdump()))
        evidence=json.loads(self.private.execute('SELECT evidence_json FROM '+g.TABLE).fetchone()[0])
        self.assertTrue(evidence['root_policy_and_live_current_revision_checked_before_transport'])

    def test_caller_cannot_swap_an_enabled_root_policy_to_another_current_database(self):
        with self.assertRaisesRegex(ValueError,'canonical_database'):
            g.reserve(self.private,self.prepared,lambda _:self.history,policy_path=self.policy_path,live_db_path=self.root/'other/conversion/jobs.sqlite')

    def test_missing_default_transport_and_root_disabled_policy_remain_hard_gates(self):
        reservation=self.reserve()
        with self.assertRaisesRegex(RuntimeError,'transport_not_enabled'):g.send_once(self.private,self.prepared,reservation)
        self.policy['new_gateway_enabled']=False;self.policy_path.write_text(json.dumps(self.policy));calls=[]
        with self.assertRaisesRegex(RuntimeError,'disabled_by_model_usage_policy'):self.send(reservation,lambda *_:calls.append(1))
        self.assertEqual(calls,[])

    def test_unknown_historical_usage_still_blocks_despite_current_idle_valid_pair(self):
        self.history['unknown_usage']=True
        with self.assertRaisesRegex(ValueError,'history_unknown'):self.reserve()


if __name__=='__main__':
    unittest.main()
