"""Finite synthetic metadata tests; no dataset, source, renderer or model runs."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock,patch

import compiler_release_program_v2 as release
import initial_conversion_process_v1 as process

REAL_PRIOR_CONVERSIONS=release.prior_conversions


class SyntheticRoot(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compiler-release-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.work=self.root/'conversion'
        self.floor=self.root/'release/compiler_v2';self.floor.mkdir(parents=True)
        self.case=self.work/'scripts/compiler_case_v2.py';self.case.parent.mkdir(parents=True)
        self.case.write_text('raise AssertionError("must never execute synthetic case")\n')
        patches=[patch.multiple(release,R=self.root,W=self.work),
                 patch.multiple(release.base,R=self.root,W=self.work),
                 patch.multiple(release.controller,R=self.root,W=self.work,FLOOR=self.floor,
                                WORK=self.work/'compiler_v2',CASE=self.case)]
        for item in patches:item.start();self.addCleanup(item.stop)
        self.bindings={'synthetic':True};self.qa=release.base.sha(release.base.raw(self.bindings))
        self.freeze=dict(pins={str(p.resolve()):release.file_sha(p) for p in
                         (self.case,Path(release.controller.__file__),Path(release.base.__file__),Path(process.__file__))},
                         qa_policy_sha256=self.qa,predicate_hashes={release.UNIT:release._predicate_digest()})
        self.freeze['implementation_identity']=release.controller.implementation_identity(self.freeze)
        self.freeze['implementation_identity_sha256']=release.controller.implementation_digest(self.freeze)

    def save(self,path,value):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(release.base.raw(value));return path

    def source(self,index,fmt='python'):
        return dict(pair_sha256=f'{index:064x}',category='scientific_diagram',format=fmt,
                    code_sha256=release.base.sha(b'source'),image_sha256=release.base.sha(b'reference'),
                    provider='synthetic')

    def manifest(self,source,name='original'):
        folder=self.root/'clean'/name/source['pair_sha256'];folder.mkdir(parents=True,exist_ok=True)
        result=dict(id=source['pair_sha256'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
        for field,digest in release.ASSETS:
            blob=b'source' if field=='original_source_code' else b'reference' if field=='original_reference' else field.encode()
            target=folder/field;target.write_bytes(blob);result[field]=str(target.relative_to(self.root))
            result[digest]=release.base.sha(blob)
        return result

    def task(self,source,seq=1):
        return dict(id=source['pair_sha256'],seq=seq,compiler_unit=release.UNIT,source=source,
                    source_record_sha256='a'*64,source_capture_snapshot={'synthetic':True},cluster='cluster:'+source['pair_sha256'])

    def outcome(self,task,status='qualified',name='new'):
        result=dict(release.controller.task_identity(task),status=status,cluster=task['cluster'],model_calls=0,
                    case_cleanup_complete=True,reason='synthetic_'+status)
        if status=='qualified':
            result['manifest']=self.manifest(task['source'],name)
            policy='compiler_source_ir_and_full_native_quality_v2:'+self.qa[:20]
            checks={key:{'ok':True} for key in ('structure','resources','source','render','text_paint','fonts','visual','native_editing')}
            checks['fonts']['all_rendered_fonts_embedded']=True
            checks['compiler_text_render']={'supported':True,'ok':True,'failures':[]}
            checks['compiler_render_domain']={'supported':True,'ok':True,'failures':[]}
            report=self.save(self.work/'qa'/name/(task['id']+'.json'),dict(id=task['id'],policy=policy,state='qualified',
                             failures=[],compiler_quality_bindings=self.bindings,checks=checks))
            result.update(quality_report=str(report.relative_to(self.root)),quality_policy=policy)
        return result


class OutcomeRenderDomainTests(SyntheticRoot):
    def test_current_qualified_outcome_with_common_proof_passes(self):
        task=self.task(self.source(1));result=self.outcome(task)
        release._validate_outcome(task,result,self.freeze,audit_assets=False)

    def test_qualified_outcome_without_common_proof_is_rejected(self):
        task=self.task(self.source(1));result=self.outcome(task)
        path=self.root/result['quality_report'];report=release.load(path)
        report['checks'].pop('compiler_render_domain');self.save(path,report)
        with self.assertRaisesRegex(ValueError,'compiler_render_domain_not_passed'):
            release._validate_outcome(task,result,self.freeze,audit_assets=False)

    def test_qualified_outcome_failed_common_proof_is_not_waived_by_C_proof(self):
        task=self.task(self.source(1));result=self.outcome(task)
        path=self.root/result['quality_report'];report=release.load(path)
        report['checks']['compiler_render_domain']=dict(supported=True,ok=False,failures=['missing primitive'])
        self.save(path,report)
        with self.assertRaisesRegex(ValueError,'compiler_render_domain_not_passed'):
            release._validate_outcome(task,result,self.freeze,audit_assets=False)


class GateTests(SyntheticRoot):
    def setUp(self):
        super().setUp()
        self.seal=self.floor/'seal_synthetic';self.seal.mkdir()
        self.audit=self.root/'release/compiler_validation_v1/audit';self.audit.mkdir(parents=True)
        self.save(self.audit/'compiler_validation_summary.json',dict(files=[],outcomes_viewed=False,validation_executions=0))
        prior=self.save(self.root/'release/compiler_v1/prior/release_gate.json',{'passed':False})
        self.lineage={'prior_failed_gate':release.asset(prior),'synthetic':True}
        self.selected=[];self.phases={'B':{},'C':{}};self.pairs=[]
        for index in range(1,31):
            source=self.source(index);common=self.task(source,index)
            self.selected.append(dict(id=common['id'],audit_cluster=common['cluster'],development_overlap=False,
                                      source_hash_verified=True,support_unit=release.UNIT,audit_disposition='eligible_unconsumed_audited_cluster'))
            for phase in ('B','C'):
                task={**common,'evaluation_phase':'baseline' if phase=='B' else 'candidate'}
                result={'status':'qualified' if phase=='C' and index<=6 else 'abandoned'}
                evidence=self.save(self.work/phase/(common['id']+'.json'),result)
                self.phases[phase][common['id']]=dict(task=task,result=result,result_file=release.asset(evidence))
            self.pairs.append(dict(id=common['id'],cluster=common['cluster'],B='abandoned',
                              C=self.phases['C'][common['id']]['result']['status'],infrastructure_failure=False,
                              B_evidence=self.phases['B'][common['id']]['result_file'],C_evidence=self.phases['C'][common['id']]['result_file']))
        proof_path=self.save(self.floor/'controls/proof.json',{'synthetic':True})
        self.controls=dict(release.asset(proof_path),counts={'positive':5,'negative':1},infrastructure_errors=0,
                           verified_outcomes=[],controls_manifest={})
        receipt=dict(audit_run=str(self.audit),implementation_identity_sha256=self.freeze['implementation_identity_sha256'],
                     controls_proof=self.controls,repair_lineage=self.lineage,runs={})
        for phase in ('B','C'):
            manifest=self.seal/(phase+'.jsonl');manifest.write_bytes(b'{}\n')
            freeze={**self.freeze,'input_sha256':release.file_sha(manifest),'repair_lineage':self.lineage}
            frozen=self.save(self.seal/(phase+'.freeze.json'),freeze)
            run=self.floor/('synthetic_'+phase);run.mkdir()
            self.save(run/'freeze.json',freeze);(run/'targets.jsonl').write_bytes(manifest.read_bytes())
            receipt['runs'][phase]=dict(directory=str(run),freeze=str(frozen),manifest=str(manifest))
        self.save(self.seal/'receipt.json',receipt)
        metrics={**release.evaluator.decision(self.pairs), 'provenance_or_cluster_audit_passed':True}
        self.gate=dict(schema='compiler_release_gate_v2',validation_complete=True,no_outcome_dependent_threshold_changes=True,
                       model_calls=0,source_cohort_seal=release.asset(self.seal/'receipt.json'),
                       implementation_identity=self.freeze['implementation_identity'],
                       implementation_identity_sha256=self.freeze['implementation_identity_sha256'],
                       controls_evidence=self.controls,controls_passed=True,paired_results=self.pairs,
                       units={release.UNIT:metrics},infrastructure_errors=0,approved_units=[release.UNIT])
        self.save(self.seal/'release_gate.json',self.gate)
        self.patches=[patch.object(release.evaluator,'rows',side_effect=lambda run,phase,freeze:self.phases[phase]),
                      patch.object(release.validation,'repair_cohort',return_value=(self.selected,self.lineage)),
                      patch.object(release,'check_frozen_captures'),
                      patch.object(release.validation,'check_controls_proof',return_value=self.controls)]
        for item in self.patches:item.start();self.addCleanup(item.stop)

    def test_reconstructs_passing_actual_gate(self):
        actual=release.verify_gate(self.seal)
        self.assertEqual(actual['metrics']['full_qualified_rate'],.2)
        self.assertEqual(len(actual['candidate_rows']),30)

    def test_absent_gate_rejected(self):
        (self.seal/'release_gate.json').unlink()
        with self.assertRaises(FileNotFoundError):release.verify_gate(self.seal)

    def test_true_pass_flag_does_not_replace_actual_outcomes(self):
        self.phases['C'][f'{1:064x}']['result']['status']='abandoned'
        with self.assertRaisesRegex(ValueError,'paired_evidence_changed'):release.verify_gate(self.seal)

    def test_positive_regression_is_rejected_even_when_claimed_passed(self):
        identifier=f'{7:064x}';self.phases['B'][identifier]['result']['status']='qualified'
        self.gate['paired_results'][6]['B']='qualified';self.save(self.seal/'release_gate.json',self.gate)
        with self.assertRaisesRegex(ValueError,'threshold_regression'):release.verify_gate(self.seal)

    def test_changed_pin_rejected_without_execution(self):
        self.case.write_text('changed\n')
        with self.assertRaisesRegex(RuntimeError,'implementation_changed'):release.verify_gate(self.seal)

    def test_changed_sealed_manifest_rejected(self):
        (self.seal/'C.jsonl').write_bytes(b'{"changed":true}\n')
        with self.assertRaisesRegex(ValueError,'freeze_or_targets_changed'):release.verify_gate(self.seal)

    def test_actual_controls_failure_cannot_be_overridden_by_flag(self):
        with patch.object(release.validation,'check_controls_proof',side_effect=ValueError('actual control failed')):
            with self.assertRaisesRegex(ValueError,'actual control failed'):release.verify_gate(self.seal)


class ReleaseTests(SyntheticRoot):
    def setUp(self):
        super().setUp()
        self.sources=[self.source(n,'mermaid' if n==6 else 'python') for n in range(1,8)]
        self.manifest_path=self.root/'release/manifest.jsonl'
        self.manifest_path.write_bytes(b''.join(release.base.raw(s) for s in self.sources))
        for key,value in dict(EXPECTED=7,EXPECTED_PYTHON=6,CATEGORIES={'scientific_diagram':7},
                              INPUT_SHA=release.file_sha(self.manifest_path)).items():
            item=patch.object(release,key,value);item.start();self.addCleanup(item.stop)
        self.first=self.root/'release/fixed_batch_v1/first';self.first.mkdir(parents=True)
        first_manifest=self.manifest(self.sources[0]);first_file=self.first/'inprogress.qualified.jsonl'
        first_file.write_bytes(release.base.raw(first_manifest))
        self.save(self.first/'progress.json',dict(files={'qualified':dict(file=str(first_file.relative_to(self.root)),
                        sha256=release.file_sha(first_file),records=1)}))
        with sqlite3.connect(self.first/'status.sqlite') as db:
            release.base.create_schema(db)
            for key,value in dict(policy='fixed_program_single_initial_screen_v1',input_manifest_sha256=release.INPUT_SHA,
                                  total=7,full_scope=True,model_calls=0,categories={'scientific_diagram':7}).items():
                release.base.meta(db,key,value)
        self.save(self.first/'owner.json',dict(pins=self.freeze['pins']))
        self.db=self.work/'jobs.sqlite'
        with sqlite3.connect(self.db) as db:
            db.execute('create table jobs(id text primary key,input_record text,output_record text)')
            for source in self.sources:
                record=dict(id=source['pair_sha256'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
                db.execute('insert into jobs values(?,?,?)',(source['pair_sha256'],json.dumps(source),json.dumps(record)))
        self.seal=self.floor/'seal';self.seal.mkdir();self.save(self.seal/'receipt.json',{'synthetic':True})
        gate=dict(implementation_identity=self.freeze['implementation_identity'],implementation_identity_sha256=self.freeze['implementation_identity_sha256'],
                  approved_units=[release.UNIT],controls_passed=True,infrastructure_errors=0,
                  units={release.UNIT:dict(passed=True,audited_clusters=30,full_qualified_rate=.2,new_qualified_clusters=6,
                                          positive_regressions=0,provenance_or_cluster_audit_passed=True)})
        self.save(self.seal/'release_gate.json',gate)
        self.prior=[]
        for index,origin,status in [(2,'validation_C','qualified'),(3,'validation_C','abandoned'),(7,'positive_control','qualified')]:
            task=self.task(self.sources[index-1]);result=self.outcome(task,status)
            evidence=self.save(self.work/'prior'/(task['id']+'.json'),result)
            self.prior.append(dict(id=task['id'],task=task,result=result,origin=origin,evidence=release.asset(evidence)))
        self.prior.sort(key=lambda row:row['id'])
        self.proof=dict(seal=str(self.seal),gate=release.asset(self.seal/'release_gate.json'),receipt=release.asset(self.seal/'receipt.json'),
                        freeze=self.freeze,controls={},candidate_rows={},metrics={})
        self.run=self.floor/'batch_synthetic'
        patches=[patch.object(release,'verify_gate',return_value=self.proof),
                 patch.object(release,'prior_conversions',return_value=self.prior),
                 patch.object(release.scene,'static_support',side_effect=lambda r:dict(supported=r['id']!=f'{5:064x}',
                                  group=release.UNIT,reasons=['synthetic_unsupported'])),
                 patch.object(release.capture,'seal_snapshot',side_effect=lambda r,e:dict(id=r['id'],synthetic=True))]
        for item in patches:item.start();self.addCleanup(item.stop)

    def prepare(self):
        return release.prepare(self.seal,self.run,manifest=self.manifest_path,jobs_db=self.db,first_run=self.first,io_workers=2)

    def advance_first(self,indices):
        target=self.first/'inprogress.qualified.jsonl'
        rows=[self.manifest(self.sources[index-1],'advancing_first') for index in indices]
        target.write_bytes(b''.join(release.base.raw(row) for row in rows))
        self.save(self.first/'progress.json',dict(files={'qualified':dict(file=str(target.relative_to(self.root)),
                  sha256=release.file_sha(target),records=len(rows))}))
        return rows

    def complete(self,status='qualified'):
        self.prepare();task=next(release.lines(self.run/'targets.jsonl'));result=self.outcome(task,status,'batch')
        with sqlite3.connect(self.run/'status.sqlite') as db:
            db.execute('update samples set status=?,attempts=1,result=?',(status,json.dumps(result)))
            release.base.meta(db,'finished',True)
        release.controller.export(self.run,True)
        command=[str(Path(release.sys.executable)),'-B',str(Path(release.controller.__file__).resolve()),'run','--run-id',self.run.name,
                 '--workers','2','--case-timeout','30.0']
        owner=dict(pid=987654321,start_ticks=123,argv=command)
        self.save(self.run/'release_launch.json',dict(token='synthetic',workers=2,case_timeout_seconds=30.0))
        self.save(self.run/'release_child.json',dict(token='synthetic',owner=owner,command=command))
        self.save(self.run/'release_child_completion.json',dict(token='synthetic',owner=owner,command=command,returncode=0,
                  interrupted_signals=[],child_reaped=True))
        return task,result

    def test_full_scope_selection_and_original_source_identity(self):
        result=self.prepare();targets=list(release.lines(self.run/'targets.jsonl'))
        self.assertEqual(result['queued'],1);self.assertEqual(targets[0]['id'],f'{4:064x}')
        self.assertEqual(targets[0]['source_input_record'],self.sources[3])
        self.assertEqual(targets[0]['source'],self.sources[3])
        self.assertEqual(result['supported_population'],5)
        self.assertEqual(result['counts'],dict(preexisting_qualified=1,version_qualified=2,version_failed=1,queued_batch=1,unsupported=1,validation_group_blocked=1))
        self.assertEqual(release.controller.snapshot(self.run)['dispatch_attempt_counts'],{0:1})

    def test_positive_controls_consume_ids_and_artificial_negative_does_not(self):
        manifest=[];verified=[]
        for index,kind in [(7,'positive'),(4,'negative')]:
            task=self.task(self.sources[index-1]);task['pins']=self.freeze['pins']
            if kind=='negative':task['development_candidate']='synthetic_corrupted_candidate.json'
            request=self.save(self.work/'controls'/(kind+'.request.json'),task)
            result=self.outcome(task,'qualified' if kind=='positive' else 'abandoned','control')
            result_path=self.save(self.work/'controls'/(kind+'.result.json'),result)
            manifest.append(dict(control_id=kind,kind=kind,input_assets=[dict(release.asset(request),role='request')]))
            verified.append(dict(control_id=kind,result=str(result_path),result_sha256=release.file_sha(result_path)))
        control_manifest=self.floor/'controls/manifest.jsonl';control_manifest.parent.mkdir()
        control_manifest.write_bytes(b''.join(release.base.raw(row) for row in manifest))
        proof_path=self.save(self.floor/'controls/proof.json',{'synthetic':True})
        controls=dict(file=str(proof_path),controls_manifest=release.asset(control_manifest),verified_outcomes=verified)
        proof={**self.proof,'controls':controls,'candidate_rows':{
            row['id']:dict(task=row['task'],result=row['result'],result_file=row['evidence']) for row in self.prior if row['origin']=='validation_C'}}
        with patch.object(release.validation,'check_controls_proof',return_value=controls):actual=REAL_PRIOR_CONVERSIONS(proof)
        self.assertEqual({row['id'] for row in actual},{f'{n:064x}' for n in (2,3,7)})
        self.assertNotIn(f'{4:064x}',{row['id'] for row in actual})

    def test_frozen_capture_check_requires_original_raw_record_hash(self):
        task=self.task(self.sources[3])
        with sqlite3.connect(self.db) as db:raw=db.execute('select output_record from jobs where id=?',(task['id'],)).fetchone()[0]
        task['source_record_sha256']=release.base.sha(raw.encode())
        with patch.object(release.capture,'check_snapshot') as check:
            release.check_frozen_captures([task],self.db);check.assert_called_once()
        task['source_record_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'output_record_changed'):release.check_frozen_captures([task],self.db)

    def test_prepare_is_read_only_for_canonical_db_and_first_run(self):
        before={str(p):release.file_sha(p) for p in (self.db,self.first/'inprogress.qualified.jsonl',self.first/'progress.json')}
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('preparation spawned')):
            self.prepare()
        self.assertEqual(before,{path:release.file_sha(path) for path in before})

    def test_completed_first_summary_index_takes_precedence_over_stale_progress(self):
        expected=[self.manifest(self.sources[index-1],'completed_first') for index in (1,5)]
        final=self.first/'qualified.jsonl';final.write_bytes(b''.join(release.base.raw(row) for row in expected))
        self.save(self.first/'summary.json',dict(finished=True,files={'qualified':dict(
                  file=str(final.relative_to(self.root)),sha256=release.file_sha(final),records=len(expected))}))
        actual,reference=release.first_qualified(self.first)
        self.assertEqual(actual,{row['id']:row for row in expected})
        self.assertEqual(reference,release.asset(final))
        self.assertEqual(len(list(release.lines(self.first/'inprogress.qualified.jsonl'))),1)

    def test_exact_source_full_record_mismatch_aborts_before_create(self):
        with sqlite3.connect(self.db) as db:db.execute('update jobs set input_record=? where id=?',('{}',f'{4:064x}'))
        with self.assertRaisesRegex(ValueError,'source_input_record_differs'):self.prepare()
        self.assertFalse(self.run.exists())

    def test_unindexed_canonical_lookup_is_rejected(self):
        with sqlite3.connect(self.db) as db:
            db.execute('alter table jobs rename to old_jobs')
            db.execute('create table jobs as select * from old_jobs')
        with self.assertRaisesRegex(ValueError,'not_indexed'):self.prepare()

    def test_input_full_file_digest_is_mandatory(self):
        with self.manifest_path.open('ab') as stream:stream.write(b'\n')
        with self.assertRaisesRegex(ValueError,'source_index_hash_changed'):self.prepare()

    def test_existing_run_never_overwritten(self):
        self.prepare();before=release.file_sha(self.run/'targets.jsonl')
        with self.assertRaisesRegex(ValueError,'already_exists'):self.prepare()
        self.assertEqual(before,release.file_sha(self.run/'targets.jsonl'))

    def test_changed_prior_conversion_inventory_prevents_launch(self):
        self.prepare()
        with patch.object(release,'prior_conversions',return_value=[]),patch.object(release.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with self.assertRaisesRegex(ValueError,'inventory_changed'):release.launch(self.run,2,30)

    def test_prior_attempt_or_stale_owner_prevents_launch(self):
        self.prepare();self.save(self.run/'owner.json',dict(pid=987654321,start_ticks=1))
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with self.assertRaisesRegex(ValueError,'fresh_undispatched'):release.launch(self.run,2,30)

    def test_fresh_ledger_source_mutation_prevents_launch(self):
        self.prepare()
        with sqlite3.connect(self.run/'status.sqlite') as db:db.execute('update samples set source=?',('{}',))
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with self.assertRaisesRegex(ValueError,'does_not_match_frozen_targets'):release.launch(self.run,2,30)

    def test_auxiliary_mutation_prevents_launch(self):
        self.prepare();link=release.load(self.run/'release_preparation.json')
        Path(link['plan']['file']).write_text('{}\n')
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with self.assertRaisesRegex(ValueError,'asset_changed'):release.launch(self.run,2,30)

    def test_first_original_can_advance_after_prepare_without_invalidating_launch(self):
        self.prepare();plan,_=release.read_plan(self.run)
        snapshot=release.checked_asset(plan['first_snapshot']);snapshot_hash=release.file_sha(snapshot)
        self.advance_first((1,5))
        self.assertNotEqual(plan['first_original']['sha256'],release.file_sha(plan['first_original']['file']))
        self.assertEqual(snapshot_hash,release.file_sha(snapshot))
        release.read_plan(self.run,revalidate_prior=True)
        with patch.object(release.subprocess,'Popen',side_effect=RuntimeError('synthetic launch reached Popen')) as spawn:
            with self.assertRaisesRegex(RuntimeError,'launch reached Popen'):release.launch(self.run,2,30)
        spawn.assert_called_once()

    def test_latest_first_accepts_merge_preserve_older_copy_and_prefer_v2(self):
        task,result=self.complete()
        # A newer completed first index may omit an old record. Our immutable
        # copied accept still survives; newer first accepts are added safely.
        self.advance_first((4,5,7))
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('finalization must not dispatch')):
            summary=release.finalize(self.run)
        accepted={row['id']:row for row in release.lines(self.run/'release_final/qualified.jsonl')}
        self.assertEqual(summary['qualified'],5)
        self.assertIn(f'{1:064x}',accepted)
        self.assertIn(f'{5:064x}',accepted)
        self.assertEqual(accepted[f'{4:064x}'],result['manifest'])
        self.assertEqual(accepted[f'{7:064x}'],self.prior[-1]['result']['manifest'])
        self.assertEqual(summary['first_snapshot_merge']['new_first_qualified_ids_since_preparation'],3)
        self.assertEqual(release.load(self.run/'release_final/asset_audit.json')['file_hash_checks'],25)
        disposition=list(release.lines(self.run/'release_final/dispositions.jsonl'))[4]
        self.assertEqual(disposition['disposition'],'preexisting_qualified')
        self.assertFalse(disposition['converted_by_current_v2'])

    def test_new_first_accept_requires_same_frozen_first_policy(self):
        self.complete();self.advance_first((1,5))
        with sqlite3.connect(self.first/'status.sqlite') as db:release.base.meta(db,'policy','different_policy')
        with self.assertRaisesRegex(ValueError,'first_run_policy_or_source_scope_not_frozen'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())

    def test_new_first_accept_source_identity_is_checked_even_when_v2_would_override(self):
        self.complete();rows=self.advance_first((1,4));rows[-1]['source_code_sha256']='0'*64
        target=self.first/'inprogress.qualified.jsonl';target.write_bytes(b''.join(release.base.raw(row) for row in rows))
        self.save(self.first/'progress.json',dict(files={'qualified':dict(file=str(target.relative_to(self.root)),
                  sha256=release.file_sha(target),records=len(rows))}))
        with self.assertRaisesRegex(ValueError,'latest_first_qualified_source_identity_changed'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())

    def test_new_first_accept_requires_all_five_actual_clean_asset_hashes(self):
        self.complete();rows=self.advance_first((1,5))
        (self.root/rows[-1]['metadata_file']).write_bytes(b'corrupt new first metadata')
        with self.assertRaisesRegex(ValueError,'outside_clean_or_changed'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())

    def test_finite_finalizer_combines_and_audits_all_five_actual_assets(self):
        self.complete();summary=release.finalize(self.run)
        self.assertTrue(summary['finished']);self.assertEqual(summary['scope_total'],7)
        self.assertEqual(summary['qualified'],4);self.assertEqual(summary['batch_converted'],1)
        self.assertEqual(summary['current_v2_converted'],4)
        audit=release.load(self.run/'release_final/asset_audit.json');self.assertEqual(audit['file_hash_checks'],20)
        scope=list(release.lines(self.run/'release_final/dispositions.jsonl'));self.assertEqual(len(scope),7)
        self.assertEqual(scope[4]['disposition'],'unsupported');self.assertEqual(scope[5]['disposition'],'validation_group_blocked')
        self.assertFalse(scope[4]['converted_by_current_v2']);self.assertFalse(scope[5]['converted_by_current_v2'])
        self.assertEqual(release.finalize(self.run),summary)

    def test_finalizer_refuses_corrupt_actual_asset_before_any_exports(self):
        task,result=self.complete();(self.root/result['manifest']['original_reference']).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'outside_clean_or_changed'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())

    def test_finalizer_refuses_missing_common_domain_proof_before_any_exports(self):
        _,result=self.complete();path=self.root/result['quality_report'];report=release.load(path)
        report['checks'].pop('compiler_render_domain');self.save(path,report)
        with self.assertRaisesRegex(ValueError,'compiler_render_domain_not_passed'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())

    def test_mid_export_failure_is_unpublished_and_manual_finalize_recovers_without_conversion(self):
        self.complete();real_write=release.write_rows
        processed_before=release.file_sha(self.run/'processed.jsonl')
        def fail_midway(path,rows):
            self.assertFalse((self.run/'release_final').exists())
            if Path(path).name=='failed.jsonl':raise RuntimeError('synthetic mid-export failure')
            return real_write(path,rows)
        with patch.object(release,'write_rows',side_effect=fail_midway):
            with self.assertRaisesRegex(RuntimeError,'mid-export failure'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())
        abandoned=release.staging_directories(self.run)
        self.assertEqual(len(abandoned),1);self.assertTrue((abandoned[0]/'qualified.jsonl').is_file())
        self.assertFalse((abandoned[0]/'summary.json').exists())
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('recovery must not dispatch')):
            summary=release.finalize(self.run)
        self.assertEqual(summary['recovered_from_unpublished_staging'],[str(abandoned[0])])
        self.assertEqual(processed_before,release.file_sha(self.run/'processed.jsonl'))
        self.assertEqual(release.controller.snapshot(self.run)['dispatch_attempt_counts'],{1:1})
        self.assertEqual(release.staging_directories(self.run),abandoned)
        for reference in summary['files'].values():
            self.assertEqual(Path(reference['file']).parent,self.run/'release_final')
            release.checked_asset(reference)
        self.assertEqual(release.finalize(self.run),summary)

    def test_interrupted_legacy_final_directory_is_preserved_and_recovered(self):
        self.complete();partial=self.run/'release_final';partial.mkdir()
        (partial/'qualified.jsonl').write_bytes(b'synthetic interrupted bytes\n')
        summary=release.finalize(self.run)
        self.assertTrue((partial/'summary.json').is_file())
        preserved=[Path(path) for path in summary['recovered_from_unpublished_staging']]
        self.assertEqual(len(preserved),1)
        self.assertEqual((preserved[0]/'qualified.jsonl').read_bytes(),b'synthetic interrupted bytes\n')

    def test_crash_after_completed_staging_before_rename_is_recoverable(self):
        self.complete();real_rename=release.os.rename
        def fail_publish(source,destination):
            if Path(destination)==self.run/'release_final':
                self.assertTrue((Path(source)/'summary.json').is_file())
                self.assertFalse(Path(destination).exists())
                raise RuntimeError('synthetic failure before atomic publication')
            return real_rename(source,destination)
        with patch.object(release.os,'rename',side_effect=fail_publish):
            with self.assertRaisesRegex(RuntimeError,'before atomic publication'):release.finalize(self.run)
        self.assertFalse((self.run/'release_final').exists())
        unpublished=release.staging_directories(self.run)
        self.assertEqual(len(unpublished),1);self.assertTrue((unpublished[0]/'summary.json').is_file())
        with patch.object(release.subprocess,'Popen',side_effect=AssertionError('recovery must not dispatch')):
            summary=release.finalize(self.run)
        self.assertEqual(summary['recovered_from_unpublished_staging'],[str(unpublished[0])])
        self.assertTrue((self.run/'release_final/summary.json').is_file())

    def test_infrastructure_stop_cannot_be_finalized(self):
        self.complete('abandoned');self.save(self.run/'infrastructure_stop.json',{'synthetic':True})
        with self.assertRaisesRegex(ValueError,'incomplete_interrupted_or_infrastructure'):release.finalize(self.run)

    def test_interrupted_child_cannot_be_finalized(self):
        self.complete();completion=release.load(self.run/'release_child_completion.json');completion['interrupted_signals']=[15]
        self.save(self.run/'release_child_completion.json',completion)
        with self.assertRaisesRegex(ValueError,'clean_actual_controller_completion'):release.finalize(self.run)

    def test_supervisor_starts_actual_cli_once_and_waits_before_finalizer(self):
        self.prepare();self.save(self.run/'release_launch.json',dict(token='token',workers=3,case_timeout_seconds=35.0))
        events=[];child=Mock(pid=1234);child.wait.side_effect=lambda:events.append('wait') or 0
        child.poll.return_value=None
        def finish(run):
            events.append('finalize');self.save(self.run/'release_final/summary.json',{'finished':True});return {'finished':True}
        with patch.object(release.subprocess,'Popen',return_value=child) as popen,patch.object(release,'process_identity',return_value={'pid':1234,'start_ticks':2,'argv':[]}),patch.object(release,'finalize',side_effect=finish) as final:
            release.supervise(self.run,3,35.0,'token')
        self.assertEqual(events,['wait','finalize']);self.assertEqual(popen.call_count,1);self.assertEqual(final.call_count,1)
        command=popen.call_args.args[0]
        self.assertEqual(command[2],str(Path(release.controller.__file__).resolve()))
        self.assertEqual(command[3:6],['run','--run-id',self.run.name]);self.assertEqual(command[-4:],['--workers','3','--case-timeout','35.0'])

    def test_supervisor_nonzero_child_records_error_and_never_finalizes(self):
        self.prepare();self.save(self.run/'release_launch.json',dict(token='token',workers=2,case_timeout_seconds=30.0))
        child=Mock(pid=1234);child.wait.return_value=9
        with patch.object(release.subprocess,'Popen',return_value=child),patch.object(release,'process_identity',return_value={'pid':1234,'start_ticks':2,'argv':[]}),patch.object(release,'finalize',side_effect=AssertionError('must not finalize')):
            with self.assertRaisesRegex(RuntimeError,'interrupted_or_nonzero'):release.supervise(self.run,2,30.0,'token')
        self.assertFalse(release.load(self.run/'release_error.json')['finalized'])


if __name__=='__main__':unittest.main()
