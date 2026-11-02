import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch

import html_paragraph_iteration_case_v10 as case
import compiler_html_source_family_v1 as families
import sys
import html_paragraph_iteration_pool_v10 as pool
import html_paragraph_iteration_program_v10 as program


def document():
    return dict(name='G',directed=True,strict=False,_subgraph_cnt=0,
                objects=[dict(_gvid=i,name=name,label=name)for i,name in enumerate(('a','b','c'))],
                edges=[dict(_gvid=0,tail=0,head=1,style='invis'),dict(_gvid=1,tail=1,head=2)])


def source(identifier='a'*64):
    return dict(pair_sha256=identifier,category='poster',format='html',source='dataset',code_sha256='b'*64,image_sha256='c'*64)


class ComponentTests(unittest.TestCase):
    @staticmethod
    def record(identifier,keys,known=True):
        original=dict(code_sha256=identifier+'code',image_sha256=identifier+'image')
        return dict(audit={},request=dict(id=identifier,source=original),keys=set(keys),known=known,pending=True)

    def test_development_contamination_closes_through_unselected_bridge(self):
        records=[self.record('bridge',{'dev_AST','DOT_x'}),self.record('otherwise_fresh',{'AST_other','DOT_x'})]
        eligible,counts=pool.independent_components(records,set(),set(),set(),{'dev_AST'})
        self.assertEqual(eligible,[]);self.assertEqual(counts['development_or_reserved_connected_components'],1)
        self.assertTrue(all('overlap'in r['audit']['disposition']for r in records))

    def test_unsupported_nonselected_bridge_still_closes_development_contamination(self):
        bridge=self.record('unsupported_bridge',{'dev_AST','DOT_shared'});bridge['pending']=False
        fresh=self.record('eligible',{'DOT_shared','new_AST'})
        eligible,_=pool.independent_components([bridge,fresh],set(),set(),set(),{'dev_AST'})
        self.assertEqual(eligible,[])

    def test_unknown_connected_family_never_claims_independent_validation(self):
        records=[self.record('unknown',{'same_AST'},False),self.record('known',{'same_AST','DOT_known'}),self.record('fresh',{'separate_AST','separate_DOT'})]
        eligible,_=pool.independent_components(records,set(),set(),set(),set())
        self.assertEqual([x['id']for x in eligible],['fresh'])
        self.assertTrue(all('unknown_component'in r['audit']['disposition']for r in records[:2]))

    def test_exact_image_and_family_keys_allow_only_one_component_representative(self):
        records=[self.record('a',{'same_image','AST_a'}),self.record('b',{'same_image','AST_b'})]
        eligible,_=pool.independent_components(records,set(),set(),set(),set())
        self.assertEqual(len(eligible),1);self.assertEqual(sum(r['audit']['disposition'].startswith('duplicate')for r in records),1)


class CaseSealTests(unittest.TestCase):
    def run_case(self,drift=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);work=root/'conversion/compiler_iterations/run/001';work.mkdir(parents=True)
        original=source();identifier=original['pair_sha256'];capture=json.dumps({'id':identifier})
        job=(identifier,original['category'],'html',original['source'],json.dumps(original),'pending',None,0,None,capture,None,None,None)
        snapshot=dict(schema='compiler_capture_snapshot_v1',id=identifier,source_code_sha256=original['code_sha256'],source_image_sha256=original['image_sha256'],source_dot='source.dot')
        compiler=SimpleNamespace(UNIT='unit',VERSION='mock_source_frontend',assert_snapshot=Mock(return_value=True),static_support=Mock(return_value=dict(supported=True,source_capture_snapshot={**snapshot,'source_dot':'different.dot'}if drift else snapshot)),
                                 original=Mock(side_effect=lambda record,given:(record,given)),convert=Mock(return_value=dict(ok=False,reason='fixture_conversion_stops_here')))
        database=Mock();database.__enter__=Mock(return_value=database);database.__exit__=Mock(return_value=False);database.execute.return_value.fetchone.return_value=job
        request=dict(id=identifier,seq=1,source=original,compiler_unit='unit',work=str(work),pins={},mode='validation',evaluation_phase='candidate',source_capture_snapshot=snapshot,source_record_sha256=case.sha(capture.encode()))
        path=work/'request.json';path.write_text(json.dumps(request))
        with patch.object(case,'W',root/'conversion'),patch.object(case,'bindings',return_value=(compiler,None)),patch.object(case,'ordinary_overlap_guard'),patch.object(case,'qualified_guard'),patch.object(case,'once_guard'),patch.object(case.sqlite3,'connect',return_value=database):
            result=case.run(path)
        return result,compiler,snapshot

    def test_frozen_capture_is_injected_before_frontend_conversion(self):
        result,compiler,snapshot=self.run_case()
        self.assertEqual(result['phase'],'conversion');compiler.convert.assert_called_once()
        self.assertEqual(compiler.convert.call_args.args[0]['compiler_source_capture_snapshot'],snapshot)
        self.assertEqual(compiler.original.call_args.args[0]['compiler_source_capture_snapshot'],snapshot)

    def test_changed_capture_stops_before_original_resealing_or_conversion(self):
        result,compiler,_=self.run_case(True)
        self.assertTrue(result['infrastructure_failure']);compiler.original.assert_not_called();compiler.convert.assert_not_called()

    def test_ordinary_queue_overlap_is_rejected_without_claiming_that_queue(self):
        with patch('compiler_mermaid_alpha_iteration_overlap_v2.guard',return_value=dict(active=True)),self.assertRaisesRegex(ValueError,'birth_verified_active_HTML_conversion_overlap'):
            case.ordinary_overlap_guard('id')



class ProgramTests(unittest.TestCase):
    def setUp(self):
        guard=patch.object(pool,'current_selected_exclusion_guard',return_value={});guard.start();self.addCleanup(guard.stop)

    def test_claimed_release_gate_must_equal_rebuilt_actual_outcomes(self):
        with tempfile.TemporaryDirectory()as temporary:
            p=Path(temporary);path=p/'release_gate.json';path.write_text(json.dumps(dict(approved_units=['unit'])))
            with patch.object(program,'owned',return_value=p),patch.object(program,'computed_gate',return_value=dict(approved_units=[])):
                with self.assertRaisesRegex(ValueError,'not_reproducible'):program.verify_release_gate(path,{}, {'unit'})

    def test_mass_skips_both_selected_outcomes_and_preserves_prior_qualified(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);p=root/'program';p.mkdir()
            (p/'implementation.json').write_text('{}');(p/'release_gate.json').write_text('{}')
            (p/'selected.jsonl').write_bytes(b''.join(program.raw(dict(id=i))for i in ('validated_good','validated_failed')))
            old=dict(id='preserved',source_code_sha256='code',source_image_sha256='image',code_file='code',code_sha256='d',image_file='image',image_sha256='d',metadata_file='metadata',metadata_sha256='d',original_source_code='original_code',original_reference='original_image')
            (p/'preserved_qualified.jsonl').write_bytes(program.raw(old))
            (p/'prior_candidate_attempts.jsonl').write_bytes(b'')
            population=[dict(id=i,compiler_unit='unit',source=dict(code_sha256='code',image_sha256='image'))for i in ('validated_good','validated_failed','preserved','remaining')]
            (p/'supported_population.jsonl').write_bytes(b''.join(program.raw(x)for x in population))
            with patch.object(pool,'fresh_qualified',return_value={}),patch.object(program.case,'bindings',return_value=(SimpleNamespace(configuration=lambda:{}),None)),patch.object(program.common,'R',root),patch.object(program.common,'checked'),patch.object(program.controller,'FLOOR',root/'runs'),patch.object(program.controller,'create')as create,patch.object(program,'validate_source_requests'),patch.object(program.history,'collect',return_value=[]),patch.object(program.history,'validate',return_value=True),patch('compiler_mermaid_alpha_iteration_overlap_v2.snapshot',return_value={'active':{}}):
                mass=program.build_mass(p,dict(approved_units=['unit']))
            self.assertEqual([x['id']for x in program.readrows(p/'mass.jsonl')],['remaining'])
            self.assertEqual(mass.name,'program_mass');create.assert_called_once()
            self.assertEqual(program.readrows(p/'mass_preserved_qualified_controls.jsonl')[0]['id'],'preserved')

    def test_failed_gate_never_dispatches_mass_or_marks_pending_irrecoverable(self):
        with tempfile.TemporaryDirectory()as temporary:
            p=Path(temporary);(p/'supported_population.jsonl').write_text('pending')
            with patch.object(program.controller,'create')as create:
                self.assertIsNone(program.build_mass(p,dict(approved_units=[])));create.assert_not_called()
            self.assertTrue((p/'supported_population.jsonl').exists())

    def test_prepare_only_reserves_B_C_without_dispatch_and_keeps_five_gain_gate(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);source_pool=root/'pool';source_pool.mkdir()
            original=source();snapshot=dict(id=original['pair_sha256'],source_code_sha256=original['code_sha256'],source_image_sha256=original['image_sha256'])
            row=dict(id=original['pair_sha256'],seq=1,source=original,compiler_unit='unit',cluster='family',audit_cluster='family',cluster_keys=['family'],source_capture_snapshot=snapshot,source_record_sha256='d'*64,baseline_code_sha256=None,baseline_image_sha256=None)
            for name in ('selected.jsonl','supported_population.jsonl'):(source_pool/name).write_bytes(program.raw(row))
            (source_pool/'preserved_qualified.jsonl').write_bytes(b'')
            (source_pool/'prior_candidate_attempts.jsonl').write_bytes(b'')
            info=dict(prior_same_SOURCE_frontend_distinct_candidate_attempts=0,all_remaining_observed_families_selected=True,eligible_observed_families=1,source_component_counts={},counters=dict(supported_remaining_population=1),files={name:dict(sha256=program.sha((source_pool/name).read_bytes()))for name in ('selected.jsonl','supported_population.jsonl','preserved_qualified.jsonl','prior_candidate_attempts.jsonl')})
            (source_pool/'summary.json').write_text(json.dumps(info));freeze=dict(implementation_identity_sha256='e'*64)
            with patch.object(program,'PROGRAMS',root/'programs'),patch.object(program.common,'R',root),patch.object(program,'template',return_value=freeze),patch.object(program.case,'bindings',return_value=(SimpleNamespace(configuration=lambda:{}),None)),patch.object(program,'control_bundle',return_value={}),patch.object(program,'check_controls'),patch.object(program,'runtime_controls',return_value=dict(file='runtime',sha256='f'*64)),patch.object(program,'reserve',return_value=dict(state='reserved',consumed=False)),patch.object(program.controller,'FLOOR',root/'runs'),patch.object(program.controller,'create')as create,patch.object(program,'run_phase')as dispatch,patch.object(program,'launch')as launch,patch.object(program,'validate_source_requests'),patch.object(program.history,'collect',return_value=[]),patch.object(program.history,'validate',return_value=True):
                result=program.prepare(source_pool,'finite_prepare')
            self.assertFalse(result['dispatched']);self.assertTrue(result['reserved']);self.assertEqual(create.call_count,2);dispatch.assert_not_called();launch.assert_not_called()
            protocol=json.loads((root/'programs/finite_prepare/protocol.json').read_bytes())
            self.assertEqual(protocol['minimum_new_qualified'],5);self.assertEqual(protocol['minimum_qualified_fraction'],.20)
            self.assertFalse(protocol['goal_complete_when_this_program_finishes'])


if __name__=='__main__':unittest.main()
