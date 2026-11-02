"""Bounded edits, cumulative historical reservations and zero-network transport tests."""
import copy
import json
import sqlite3
import tempfile
import threading
import types
import unittest
import xml.etree.ElementTree as E
from pathlib import Path
from unittest import mock

import bounded_patch_gateway_v1 as g

XML = '<mxfile><diagram><mxGraphModel pageWidth="200" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="Alpha" style="rounded;fontSize=12;fillColor=#ffffff;"><mxGeometry x="10" y="20" width="40" height="30" as="geometry"/></mxCell><mxCell id="b" parent="1" vertex="1" value="Beta"><mxGeometry x="120" y="20" width="40" height="30" as="geometry"/></mxCell><mxCell id="e" parent="1" edge="1" source="a" target="b" style="endArrow=block;"><mxGeometry relative="1" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'


class Tests(unittest.TestCase):
    def setUp(self):
        self.record = {'id':'a'*64,'source_pair_sha256':'a'*64,'source_code_sha256':'b'*64,
                       'source_image_sha256':'c'*64,'code_sha256':g.sha(XML.encode())}
        self.history = {'history_snapshot_id':'frozen-history-1','max_calls':2,'confirmed_calls':0,
                        'unknown_reservations':0,'conservative_budget_used':0,'eligible_for_new_call':True,
                        'remaining_calls':2,'coverage_complete_for_id':True,'unknown_usage':False}
        self.prepared = self.prepare()
        self.tmp = tempfile.TemporaryDirectory()
        self.policy_path = Path(self.tmp.name)/'isolated-enabled-policy.json'
        self.policy = json.loads((Path(__file__).parents[1]/'model_usage_policy_v2.json').read_text())
        self.policy['new_gateway_enabled'] = True
        self.policy.update(authorized_model_sample_ids=[self.record['id']],max_new_model_sample_ids=16,
                           automatic_model_case_selection_disabled=True)
        self.policy_path.write_text(json.dumps(self.policy))
        self.db = sqlite3.connect(':memory:')
        g.initialize(self.db)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def prepare(self, errors=None, cells=('a',), **kwargs):
        return g.prepare(self.record,XML,cells,source_context={'source_title':'Original Alpha'},
                         errors=errors if errors is not None else [{'reason':'local_text_wrong','cell':'a'}],
                         embedded_families=['EmbeddedFont'],repair_plan={'source':'fixed_program',
                         'base_code_sha256':self.record['code_sha256'],'evidence_sha256':'d'*64,
                         'defects':[{'reason':'localized_source_text_or_box_mismatch','cells':list(cells),
                         'allowed_operations':['set_value','set_style','set_geometry']}]},**kwargs)

    def patch(self, ops):
        return {'version':1,'base_code_sha256':self.record['code_sha256'],'operations':ops}

    def reserve(self, prepared=None):
        return g.reserve(self.db,prepared or self.prepared,lambda identifier:copy.deepcopy(self.history))

    def test_stable_prefix_reused_and_errors_last_with_off_thinking(self):
        other = self.prepare(errors=[{'reason':'new_post_patch_error','cell':'a'}])
        self.assertEqual(self.prepared['stable_prefix_sha256'],other['stable_prefix_sha256'])
        self.assertNotEqual(self.prepared['request_sha256'],other['request_sha256'])
        request = self.prepared['request']
        self.assertEqual(request['thinking'],{'type':'disabled'})
        self.assertEqual(request['max_tokens'],2048)
        self.assertNotIn('output_config',request)
        self.assertTrue(request['messages'][0]['content'][-1]['text'].startswith('CURRENT_MACHINE_ERRORS_DATA\n'))
        self.assertEqual(self.prepared['actual_api_calls'],0)

    def test_low_thinking_explicit_and_high_or_large_output_rejected(self):
        self.assertEqual(self.prepare(reasoning='low')['request']['output_config'],{'effort':'low'})
        for options in [{'reasoning':'high'},{'max_tokens':131072},{'max_tokens':True}]:
            with self.assertRaises(ValueError):
                self.prepare(**options)

    def test_small_patch_changes_only_named_properties_preserves_graph_page_objects(self):
        patch = self.patch([{'op':'set_value','cell':'a','expect':'Alpha','value':'Original Alpha'},
                            {'op':'set_geometry','cell':'a','key':'x','expect':'10','value':12},
                            {'op':'set_style','cell':'a','key':'fontSize','expect':'12','value':'13'}])
        out,proof = g.validate_and_apply(self.prepared,XML,patch)
        before = E.fromstring(XML)
        after = E.fromstring(out)
        self.assertEqual(before.find('.//mxGraphModel').attrib,after.find('.//mxGraphModel').attrib)
        for identifier in ['0','1','b','e']:
            a=next(x for x in before.iter('mxCell') if x.get('id')==identifier)
            b=next(x for x in after.iter('mxCell') if x.get('id')==identifier)
            self.assertEqual(E.tostring(a),E.tostring(b))
        self.assertTrue(proof['canvas_and_topology_preserved'])
        self.assertFalse(proof['accepted'])
        self.assertTrue(proof['requires_fresh_source_native_render_font_and_visual_qa'])

    def test_precondition_failures_are_atomic_in_memory(self):
        original=XML
        patch=self.patch([{'op':'set_value','cell':'a','expect':'Alpha','value':'Good'},
                          {'op':'set_geometry','cell':'a','key':'x','expect':'WRONG','value':12}])
        with self.assertRaisesRegex(ValueError,'precondition'):
            g.validate_and_apply(self.prepared,XML,patch)
        self.assertEqual(XML,original)

    def test_new_cells_endpoints_parent_assets_page_and_unlisted_cells_forbidden(self):
        for operation in [{'op':'add_cell','cell':'a'}, {'op':'set_style','cell':'a','key':'image','expect':None,'value':'data:fake'},
                          {'op':'set_style','cell':'a','key':'endArrow','expect':None,'value':'none'},
                          {'op':'set_geometry','cell':'a','key':'pageWidth','expect':'200','value':201},
                          {'op':'set_parent','cell':'a','expect':'1','value':'b'},
                          {'op':'set_value','cell':'b','expect':'Beta','value':'Changed'}]:
            with self.subTest(operation=operation),self.assertRaises(ValueError):
                g.validate_and_apply(self.prepared,XML,self.patch([operation]))

    def test_geometry_scope_is_small_finite_and_not_edge_terminal_points(self):
        for value in [27,float('nan'),float('inf'),True]:
            with self.assertRaises(ValueError):
                g.validate_and_apply(self.prepared,XML,self.patch([{'op':'set_geometry','cell':'a','key':'x','expect':'10','value':value}]))
        edge=self.prepare(cells=('e',))
        with self.assertRaisesRegex(ValueError,'absolute_vertex'):
            g.validate_and_apply(edge,XML,self.patch([{'op':'set_geometry','cell':'e','key':'x','expect':'0','value':1}]))

    def test_font_is_embedded_and_tiny_style_delta_only(self):
        for key,before,value in [('fontFamily',None,'Arial'),('fontSize','12','50'),('fontSize','12','nan'),('fillColor','#ffffff','javascript:alert(1)')]:
            with self.assertRaises(ValueError):
                g.validate_and_apply(self.prepared,XML,self.patch([{'op':'set_style','cell':'a','key':key,'expect':before,'value':value}]))

    def test_adding_style_does_not_introduce_default_style_reset(self):
        prepared=self.prepare(cells=('b',))
        out,_=g.validate_and_apply(prepared,XML,self.patch([{'op':'set_style','cell':'b','key':'fontSize','expect':None,'value':'13'}]))
        cell=next(c for c in E.fromstring(out).iter('mxCell') if c.get('id')=='b')
        self.assertEqual(cell.get('style'),'fontSize=13;')

    def test_duplicate_property_and_large_or_whole_xml_response_refused(self):
        op={'op':'set_value','cell':'a','expect':'Alpha','value':'New'}
        for response in [XML,self.patch([op,op]),self.patch([op]*25),{'xml':XML},'x'*17000]:
            with self.assertRaises((ValueError,json.JSONDecodeError)):
                g.validate_and_apply(self.prepared,XML,response)

    def test_explicit_reasoned_abandonment_preserves_input(self):
        out,proof=g.validate_and_apply(self.prepared,XML,{**self.patch([]),'abandon_reason':'Requires 40-unit movement and unknown source label.'})
        self.assertEqual(out,XML)
        self.assertTrue(proof['abandoned'])
        self.assertFalse(proof['applied'])

    def test_base_revision_and_source_pair_bound(self):
        with self.assertRaises(ValueError):g.validate_and_apply(self.prepared,XML+' ',self.patch([]))
        record={**self.record,'source_pair_sha256':'d'*64}
        with self.assertRaisesRegex(ValueError,'source_pair'):
            g.prepare(record,XML,['a'],source_context={},errors=[])

    def test_max_two_including_confirmed_and_unknown_historical_calls(self):
        self.history.update(confirmed_calls=1,conservative_budget_used=1,remaining_calls=1)
        first=self.reserve()
        self.assertEqual(first['budget_used_with_reservation'],2)
        with self.assertRaisesRegex(ValueError,'two_call'):
            self.reserve(self.prepare(errors=[{'reason':'different'}]))
        self.assertEqual(self.db.execute('SELECT count(*) FROM '+g.TABLE).fetchone()[0],1)

    def test_unknown_or_incomplete_history_does_not_mean_zero(self):
        for change in [{'coverage_complete_for_id':False},{'eligible_for_new_call':False},{'history_snapshot_id':None},{'max_calls':7}]:
            original=copy.deepcopy(self.history)
            self.history.update(change)
            with self.assertRaises(ValueError):self.reserve()
            self.history=original

    def test_duplicate_intent_never_gets_another_call_even_with_remaining_budget(self):
        self.reserve()
        with self.assertRaisesRegex(ValueError,'same_intent'):
            self.reserve()

    def test_no_default_transport_and_reserved_budget_preserved(self):
        reservation=self.reserve()
        with self.assertRaisesRegex(RuntimeError,'no_api'):
            g.send_once(self.db,self.prepared,reservation)
        self.assertEqual(self.db.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'reserved')

    def test_one_explicit_fake_send_actual_usage_raw_and_cache_saved_without_guessing(self):
        reservation=self.reserve()
        calls=[]
        usage={'inputTokens':700,'outputTokens':39,'cacheReadTokens':500,'cacheWriteTokens':0,'totalTokens':1239}
        def fake(request,key):
            calls.append(key)
            return {'response_id':'provider-message','usage':usage,'response':json.dumps(self.patch([]))}
        g.send_once(self.db,self.prepared,reservation,fake,policy_path=self.policy_path,history_lookup=lambda _:self.history)
        row=self.db.execute('SELECT state,raw_usage_json,usage_semantics_json FROM '+g.TABLE).fetchone()
        self.assertEqual(calls,[reservation['request_key']])
        self.assertEqual(row[0],'response_received')
        self.assertEqual(json.loads(row[1]),usage)
        self.assertIsNone(row[2])
        with self.assertRaises(ValueError):g.send_once(self.db,self.prepared,reservation,fake,policy_path=self.policy_path,history_lookup=lambda _:self.history)
        self.assertEqual(len(calls),1)

    def test_transport_timeout_remains_unknown_and_consumes_budget(self):
        self.history['conservative_budget_used']=1
        reservation=self.reserve()
        def fake(*_):raise TimeoutError('No billing/response evidence')
        with self.assertRaises(TimeoutError):g.send_once(self.db,self.prepared,reservation,fake,policy_path=self.policy_path,history_lookup=lambda _:self.history)
        self.assertEqual(self.db.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'sent_unknown')
        with self.assertRaisesRegex(ValueError,'two_call'):
            self.reserve(self.prepare(errors=[{'reason':'retry'}]))

    def test_only_proven_local_refusal_releases_budget(self):
        self.history['conservative_budget_used']=1
        reservation=self.reserve()
        with self.assertRaises(ValueError):g.finish(self.db,reservation,blocked_local=True,evidence={})
        g.finish(self.db,reservation,blocked_local=True,evidence={'upstream_send_performed':False,'charged':False,'guard_receipt':'owned/local/refusal'})
        next_reservation=self.reserve(self.prepare(errors=[{'reason':'new locally rejected scope'}]))
        self.assertEqual(next_reservation['budget_used_with_reservation'],2)

    def test_history_reconciliation_needs_explicit_covered_request_key(self):
        first=self.reserve()
        g.mark_sent(self.db,first)
        g.finish(self.db,first,response_id='msg')
        self.history.update(history_snapshot_id='snapshot2',conservative_budget_used=1)
        second=self.prepare(errors=[{'reason':'post patch error'}])
        with self.assertRaisesRegex(ValueError,'two_call'):self.reserve(second)
        self.history['covered_gateway_request_keys']=[first['request_key']]
        follow=g.prepare_followup(self.prepared,first['request_key'],json.dumps(self.patch([
          {'op':'set_geometry','cell':'a','key':'x','expect':'10','value':11}])),self.record,XML,['a'],
          source_context={'source_title':'Original Alpha'},errors=[{'reason':'post patch error'}],
          embedded_families=['EmbeddedFont'],repair_plan=self.prepared['repair_plan'])
        self.assertEqual(self.reserve(follow)['budget_used_with_reservation'],2)

    def test_real_disabled_policy_cannot_be_bypassed_by_transport(self):
        reservation=self.reserve()
        self.policy['new_gateway_enabled']=False
        self.policy_path.write_text(json.dumps(self.policy))
        calls=[]
        with self.assertRaisesRegex(RuntimeError,'disabled_by_model_usage_policy'):
            g.send_once(self.db,self.prepared,reservation,lambda *_:calls.append(1),policy_path=self.policy_path)
        self.assertEqual(calls,[])
        self.assertEqual(self.db.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'reserved')

    def test_policy_tampering_and_off_thinking_are_fail_closed(self):
        for key,value in [('model_calls_per_original_sample_lifetime_limit',3),('hard_max_output_tokens',131072),
                          ('max_cells_per_patch',99),('reasoning_effort','low'),('history_import_required_before_any_new_call',False),
                          ('automatic_model_critics_disabled',False),('cache_warmup_calls_forbidden',False)]:
            policy={**self.policy,key:value}
            self.policy_path.write_text(json.dumps(policy))
            with self.subTest(key=key),self.assertRaises((ValueError,RuntimeError)):
                g.require_enabled_policy(self.prepared,self.policy_path)
        self.policy_path.write_text(json.dumps(self.policy))
        with self.assertRaisesRegex(ValueError,'off_thinking'):
            g.require_enabled_policy(self.prepare(reasoning='low'),self.policy_path)

    def test_model_call_needs_program_localized_plan(self):
        prepared=copy.deepcopy(self.prepared)
        prepared['repair_plan']=None
        with self.assertRaisesRegex(ValueError,'program_localized'):
            g.require_enabled_policy(prepared,self.policy_path)
        prepared['repair_plan']={**self.prepared['repair_plan'],'base_code_sha256':'wrong'}
        with self.assertRaisesRegex(ValueError,'program_localized'):
            g.require_enabled_policy(prepared,self.policy_path)

    def test_second_gateway_call_keeps_entire_first_request_prefix(self):
        first=self.reserve()
        g.mark_sent(self.db,first)
        patch=json.dumps(self.patch([{'op':'set_geometry','cell':'a','key':'x','expect':'10','value':11}]))
        g.finish(self.db,first,response_id='first-response')
        follow=g.prepare_followup(self.prepared,first['request_key'],patch,self.record,XML,['a'],
           source_context={'source_title':'Original Alpha'},errors=[{'reason':'new_metrics_error'}],
           embedded_families=['EmbeddedFont'],repair_plan=self.prepared['repair_plan'])
        self.assertEqual(follow['request']['messages'][:1],self.prepared['request']['messages'])
        self.assertEqual(follow['request']['messages'][1]['role'],'assistant')
        self.assertTrue(follow['request']['messages'][-1]['content'][-1]['text'].startswith('CURRENT_MACHINE_ERRORS_DATA'))
        self.assertEqual(self.reserve(follow)['budget_used_with_reservation'],2)
        g.require_enabled_policy(follow,self.policy_path)
        follow['request']['messages'][0]['content'][-1]['text']='rewritten first errors would break caching'
        with self.assertRaisesRegex(ValueError,'prefix_changed'):
            g.require_enabled_policy(follow,self.policy_path)

    def test_history_adapter_is_lazy_read_only_and_missing_history_locks_budget(self):
        for error in [ImportError('not deployed'),FileNotFoundError('missing history'),sqlite3.OperationalError('incomplete db')]:
            with mock.patch.object(g.importlib,'import_module',side_effect=error):
                result=g.lookup_sample_budget_adapter(self.record['id'])
                self.assertFalse(result['eligible_for_new_call'])
                self.assertFalse(result['coverage_complete_for_id'])
                self.assertIsNone(result['conservative_budget_used'])
                with self.assertRaisesRegex(ValueError,'history_unknown'):
                    g.reserve(self.db,self.prepared)
        history={**self.history,'covered_gateway_request_keys':['known-key']}
        lookup=mock.Mock(return_value=history)
        module=types.SimpleNamespace(lookup_sample_budget=lookup)
        with mock.patch.object(g.importlib,'import_module',return_value=module):
            result=g.lookup_sample_budget_adapter(self.record['id'],db_path='readonly-history.sqlite',request_keys=['known-key'])
        self.assertEqual(result,history)
        lookup.assert_called_once_with(self.record['id'],db_path='readonly-history.sqlite',request_keys=['known-key'])

    def test_history_adapter_rejects_understated_call_counts(self):
        bad={**self.history,'confirmed_calls':2,'conservative_budget_used':0,'eligible_for_new_call':True}
        module=types.SimpleNamespace(lookup_sample_budget=lambda *_args,**_kwargs:bad)
        with mock.patch.object(g.importlib,'import_module',return_value=module):
            result=g.lookup_sample_budget_adapter(self.record['id'])
        self.assertFalse(result['coverage_complete_for_id'])
        self.assertFalse(result['eligible_for_new_call'])

    def test_history_rechecked_immediately_before_transport(self):
        reservation=self.reserve()
        self.history.update(conservative_budget_used=2,eligible_for_new_call=False)
        calls=[]
        with self.assertRaisesRegex(ValueError,'history_not_verified_at_send'):
            g.send_once(self.db,self.prepared,reservation,lambda *_:calls.append(1),
                        policy_path=self.policy_path,history_lookup=lambda _:self.history)
        self.assertEqual(calls,[])
        self.assertEqual(self.db.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'reserved')

    def test_patch_may_only_perform_program_planned_operation_types(self):
        prepared=copy.deepcopy(self.prepared)
        prepared['repair_plan']['defects'][0]['allowed_operations']=['set_geometry']
        with self.assertRaisesRegex(ValueError,'outside_program_localized_plan'):
            g.validate_and_apply(prepared,XML,self.patch([{'op':'set_value','cell':'a','expect':'Alpha','value':'Unplanned label change'}]))

    def test_root_allowlist_missing_empty_other_id_duplicates_and_oversize_fail_closed(self):
        cases=[{}, {'authorized_model_sample_ids':None}, {'authorized_model_sample_ids':[]},
               {'authorized_model_sample_ids':['e'*64]},
               {'authorized_model_sample_ids':[self.record['id'],self.record['id']]},
               {'authorized_model_sample_ids':[format(i,'064x') for i in range(17)]},
               {'authorized_model_sample_ids':[self.record['id']],'max_new_model_sample_ids':17},
               {'authorized_model_sample_ids':[self.record['id']],'automatic_model_case_selection_disabled':False}]
        for changes in cases:
            policy=copy.deepcopy(self.policy)
            if not changes:policy.pop('authorized_model_sample_ids')
            else:policy.update(changes)
            self.policy_path.write_text(json.dumps(policy))
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                g.require_enabled_policy(self.prepared,self.policy_path)

    def test_transport_and_caller_plan_cannot_authorize_an_unlisted_original_id(self):
        reservation=self.reserve()
        self.policy['authorized_model_sample_ids']=[]
        self.policy_path.write_text(json.dumps(self.policy))
        prepared=copy.deepcopy(self.prepared)
        prepared['authorized_model_sample_ids']=[self.record['id']]
        prepared['repair_plan']['authorized_model_sample_ids']=[self.record['id']]
        calls=[]
        with self.assertRaisesRegex(ValueError,'not_authorized_by_root_policy'):
            g.send_once(self.db,prepared,reservation,lambda *_:calls.append(1),
                        policy_path=self.policy_path,history_lookup=lambda _:self.history)
        self.assertEqual(calls,[])
        self.assertEqual(self.db.execute('SELECT state FROM '+g.TABLE).fetchone()[0],'reserved')

    def test_concurrent_reservations_cannot_exceed_one_remaining_call(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private-gateway.sqlite'
            db=sqlite3.connect(path)
            g.initialize(db);db.commit();db.close()
            history={**self.history,'conservative_budget_used':1}
            barrier=threading.Barrier(2)
            outcomes=[]
            def contender(n):
                own=sqlite3.connect(path,timeout=5)
                prepared=self.prepare(errors=[{'contender':n}])
                barrier.wait()
                try:outcomes.append(('reserved',g.reserve(own,prepared,lambda _:history)))
                except ValueError as e:outcomes.append(('blocked',str(e)))
                finally:own.close()
            threads=[threading.Thread(target=contender,args=(n,)) for n in range(2)]
            for thread in threads:thread.start()
            for thread in threads:thread.join()
            self.assertEqual(sorted(x[0] for x in outcomes),['blocked','reserved'])


if __name__=='__main__':
    unittest.main()
