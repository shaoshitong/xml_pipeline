"""Synthetic controller/ledger tests. No dataset, renderer, or model execution."""
import concurrent.futures
import copy
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import compiler_svg_source_viewport_iteration_batch_v2 as c
import initial_conversion_process_v1 as process


def hold_shared(path,connection):
    with open(path,'a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_SH)
        connection.send('locked');connection.recv()


def orphan_queued(task,paths,connection):
    c.R=Path(paths['root']);c.W=c.R/'conversion';c.FLOOR=c.R/'release/compiler_iterations'
    c.WORK=c.W/'compiler_iterations';c.CASE=Path(paths['case'])
    def forbidden(*args,**kwargs):
        Path(paths['spawned']).write_text('unexpected spawn')
        raise AssertionError('stale task spawned')
    process.run=forbidden
    connection.send('queued');connection.recv()
    connection.send(c.execute(task))


class ImmediatePool:
    calls=[]
    def __init__(self,**kwargs):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def submit(self,fn,task):
        self.calls.append(task)
        future=concurrent.futures.Future()
        future.set_result(c.failure(task,'synthetic_rejection',case_cleanup_complete=True))
        return future


class RejectPool(ImmediatePool):
    def submit(self,fn,task):
        self.calls.append(task);raise RuntimeError('synthetic submit failure')


class UnsafePool(ImmediatePool):
    def submit(self,fn,task):
        self.calls.append(task);c.phase(task,'spawn_intent')
        future=concurrent.futures.Future()
        future.set_result(c.failure(task,'synthetic_cleanup_failed',
                                    case_cleanup_complete=False,infrastructure_failure=True))
        return future


class CompilerBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compiler-controller-test-')
        self.root=Path(self.temp.name).resolve();self.work=self.root/'conversion'
        self.case=self.work/'scripts/compiler_svg_source_viewport_iteration_case_v2.py';self.case.parent.mkdir(parents=True)
        self.case.write_text('raise AssertionError("synthetic fixture must not execute")\n')
        self.patches=[patch.object(c,'validate_requests',return_value=True),patch.multiple(c,R=self.root,W=self.work,FLOOR=self.root/'release/compiler_iterations',
                                    WORK=self.work/'compiler_iterations',CASE=self.case),
                      patch.multiple(c.base,R=self.root,W=self.work)]
        for p in self.patches:p.start()
        self.addCleanup(self.temp.cleanup)
        for p in reversed(self.patches):self.addCleanup(p.stop)
        self.pins={str(path.resolve()):c.base.sha(path.read_bytes()) for path in
                   [self.case,Path(c.__file__),Path(c.base.__file__),Path(process.__file__),Path(c.__file__).with_name('compiler_svg_source_viewport_iteration_program_v2.py')]}
        self.freeze=dict(pins=self.pins,qa_policy_sha256='3'*64,predicate_hashes={'unit':'4'*64})
        self.freeze['implementation_identity_sha256']=c.implementation_digest(self.freeze)
        ImmediatePool.calls=[];RejectPool.calls=[]

    def make_run(self,count=1,name='synthetic'):
        rows=[]
        for seq in range(1,count+1):
            ident=f'{seq:064x}'
            source=dict(pair_sha256=ident,category='scientific_diagram',format='mermaid',
                        code_sha256='1'*64,image_sha256='2'*64)
            rows.append(dict(seq=seq,id=ident,compiler_unit='unit',cluster='cluster'+str(seq),source=source))
        payload=b''.join(c.base.raw(row) for row in rows);freeze=copy.deepcopy(self.freeze)
        freeze['input_sha256']=c.base.sha(payload)
        manifest=self.root/(name+'.jsonl');manifest.write_bytes(payload)
        frozen=self.root/(name+'.freeze.json');frozen.write_bytes(c.base.raw(freeze))
        run=c.FLOOR/name;c.create(run,manifest,frozen,'development')
        return run,sqlite3.connect(run/'status.sqlite'),rows

    def claim(self,run,db):
        claimed=c.base.claim(db,1);row=claimed.pop('source')
        generation=json.loads((run/'generation.json').read_bytes())['token']
        return c.prepare_dispatch(run,row,claimed,self.pins,10,'development',generation)

    def clean_result(self,task):
        return c.failure(task,'synthetic_rejection')

    def install_proof(self,task,result=None,cleanup=True,tracked=()):
        work=Path(task['work']);c.durable(work/'isolation.json',dict(
            ok=True,cleanup_complete=cleanup,tracked_processes=list(tracked)))
        if result is not None:c.durable(work/'result.json',result)

    def gate(self):
        identity=c.implementation_identity(self.freeze)
        gate=dict(implementation_identity=identity,implementation_identity_sha256=c.implementation_digest(self.freeze),
                  approved_units=['unit'],controls_passed=True,infrastructure_errors=0,
                  units={'unit':dict(passed=True,audited_clusters=30,full_qualified_rate=.2,
                                     new_qualified_clusters=5,provenance_or_cluster_audit_passed=True)})
        path=self.root/'gate.json';path.write_bytes(c.base.raw(gate));freeze=copy.deepcopy(self.freeze)
        freeze['release_gate']={'file':str(path),'sha256':c.base.sha(path.read_bytes())}
        return freeze

    def test_gate_exact_identity_and_canonical_order(self):
        freeze=self.gate();freeze['pins']=dict(reversed(list(freeze['pins'].items())))
        with patch('compiler_svg_source_viewport_iteration_program_v2.verify_release_gate',return_value={}) as rebuild:
            self.assertEqual(c.release_gate(freeze,{'unit'})['approved_units'],['unit']);rebuild.assert_called_once()

    def test_gate_pass_boolean_cannot_bypass_evidence_rebuild(self):
        freeze=self.gate()
        with patch('compiler_svg_source_viewport_iteration_program_v2.verify_release_gate',side_effect=ValueError('missing_actual_BC_evidence')):
            with self.assertRaisesRegex(ValueError,'missing_actual_BC_evidence'):c.release_gate(freeze,{'unit'})

    def test_existing_infrastructure_stop_blocks_all_new_claims(self):
        run,db,rows=self.make_run();c.durable(run/'infrastructure_stop.json',{'reason':'old failure'})
        with self.assertRaisesRegex(RuntimeError,'existing_infrastructure_stop'):c._run_batch_locked(run,1,10,db)
        self.assertEqual(db.execute('select status,attempts from samples').fetchone(),('queued',0));db.close()

    def test_gate_rejects_different_converter_policy_or_predicate(self):
        for field in ('pins','qa_policy_sha256','predicate_hashes'):
            with self.subTest(field=field):
                freeze=self.gate()
                if field=='pins':freeze[field][str(self.case)]='5'*64
                elif field=='predicate_hashes':freeze[field]['unit']='5'*64
                else:freeze[field]='5'*64
                freeze['implementation_identity_sha256']=c.implementation_digest(freeze)
                with self.assertRaisesRegex(ValueError,'validation_gate_implementation_identity_mismatch'):
                    c.release_gate(freeze,{'unit'})

    def test_claim_is_single_attempt_and_unlaunched_resume_closes_once(self):
        run,db,rows=self.make_run();task=self.claim(run,db)
        with self.assertRaisesRegex(RuntimeError,'exactly_once'):c.base.claim(db,1)
        before=task['generation'];recovery=c.resume_interrupted(run,db)
        self.assertNotEqual(before,recovery['generation'])
        status,attempts,body=db.execute('select status,attempts,result from samples').fetchone()
        self.assertEqual((status,attempts),('abandoned',1))
        self.assertEqual(json.loads(body)['reason'],'compiler_dispatch_interrupted')
        self.assertEqual(c.resume_interrupted(run,db)['recovered'],[]);db.close()

    def test_claim_crash_before_work_creation_is_proved_unlaunched(self):
        run,db,rows=self.make_run();c.base.claim(db,1)
        self.assertEqual(c.resume_interrupted(run,db)['recovered'][0]['reason'],'compiler_dispatch_interrupted');db.close()

    def test_live_worker_shared_lock_blocks_recovery(self):
        run,db,rows=self.make_run();self.claim(run,db);before=(run/'generation.json').read_bytes()
        ctx=multiprocessing.get_context('spawn');parent,child=ctx.Pipe()
        worker=ctx.Process(target=hold_shared,args=(str(run/'execution.lock'),child));worker.start()
        try:
            self.assertTrue(parent.poll(10));self.assertEqual(parent.recv(),'locked')
            with self.assertRaisesRegex(RuntimeError,'workers_still_locked'):c.resume_interrupted(run,db)
            self.assertEqual((run/'generation.json').read_bytes(),before)
        finally:
            parent.send('release');worker.join(10)
            if worker.is_alive():worker.terminate();worker.join()
        self.assertEqual(worker.exitcode,0);db.close()

    def test_orphan_queued_old_generation_cannot_spawn(self):
        run,db,rows=self.make_run();task=self.claim(run,db);spawned=self.root/'unexpected-spawn'
        ctx=multiprocessing.get_context('spawn');parent,child=ctx.Pipe()
        worker=ctx.Process(target=orphan_queued,args=(task,dict(root=str(self.root),case=str(self.case),spawned=str(spawned)),child));worker.start()
        try:
            self.assertTrue(parent.poll(10));self.assertEqual(parent.recv(),'queued')
            c.resume_interrupted(run,db);parent.send('resume')
            self.assertTrue(parent.poll(10));self.assertEqual(parent.recv()['reason'],'compiler_stale_generation')
            self.assertFalse(spawned.exists())
        finally:
            worker.join(10)
            if worker.is_alive():worker.terminate();worker.join()
        self.assertEqual(worker.exitcode,0);db.close()

    def test_spawn_intent_without_cleanup_never_infers_gone(self):
        run,db,rows=self.make_run();task=self.claim(run,db);c.phase(task,'spawn_intent')
        with patch.object(process,'identity',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'cleanup_proof'):c.resume_interrupted(run,db)
        self.assertEqual(db.execute('select status,attempts from samples').fetchone(),('running',1));db.close()

    def test_cleanup_false_or_live_tracked_process_refuses_recovery(self):
        for cleanup,tracked in [(False,[]),(True,[dict(pid=123456,start_ticks=77)])]:
            with self.subTest(cleanup=cleanup):
                run,db,rows=self.make_run(name='cleanup'+str(cleanup));task=self.claim(run,db)
                self.install_proof(task,self.clean_result(task),cleanup,tracked)
                with patch.object(process,'identity',return_value=dict(state='S',start_ticks=77)):
                    with self.assertRaisesRegex(RuntimeError,'not_clean|still_live'):c.resume_interrupted(run,db)
                db.close()

    def test_resume_revalidates_unit_and_manifest_before_export(self):
        run,db,rows=self.make_run();task=self.claim(run,db);result=self.clean_result(task);result['compiler_unit']='other'
        self.install_proof(task,result);recovery=c.resume_interrupted(run,db)
        self.assertTrue(recovery['infrastructure_failures'])
        result=json.loads(db.execute('select result from samples').fetchone()[0])
        self.assertEqual(result['compiler_unit'],'unit');self.assertEqual(result['reason'],'compiler_interrupted_result_invalid')
        good=self.clean_result(task);good['status']='qualified'
        with self.assertRaisesRegex(RuntimeError,'missing_manifest'):c.validate_case_result(good,c.task_identity(task))
        db.close()

    def test_valid_recovery_does_not_reexecute(self):
        run,db,rows=self.make_run();task=self.claim(run,db);self.install_proof(task,self.clean_result(task))
        with patch.object(process,'run',side_effect=AssertionError('must not execute')):
            result=c.resume_interrupted(run,db)['recovered'][0]
        self.assertTrue(result['recovered_without_reexecution']);self.assertEqual(db.execute('select attempts from samples').fetchone()[0],1);db.close()

    def test_execute_holds_shared_lock_before_spawn_and_persists_phase(self):
        run,db,rows=self.make_run();task=self.claim(run,db)
        def isolated(argv,work,timeout,env):
            marker=json.loads((work/'execution.json').read_bytes())
            self.assertEqual(marker['phase'],'spawn_intent');self.assertEqual(marker['generation'],task['generation'])
            self.assertEqual(marker['owner']['pid'],os.getpid())
            with (run/'execution.lock').open('a+') as lock:
                with self.assertRaises(BlockingIOError):fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            c.durable(work/'result.json',self.clean_result(task))
            return dict(ok=True,cleanup_complete=True,tracked_processes=[])
        with patch.object(process,'run',side_effect=isolated):result=c.execute(task)
        self.assertTrue(result['case_cleanup_complete'])
        self.assertEqual(json.loads((Path(task['work'])/'execution.json').read_bytes())['phase'],'isolation_complete');db.close()

    def test_submit_failure_is_terminal_infra_and_stops_new_dispatch(self):
        run,db,rows=self.make_run(count=3);db.close()
        with patch.object(c.concurrent.futures,'ProcessPoolExecutor',RejectPool):result=c.run_batch(run,2,10)
        db=sqlite3.connect(run/'status.sqlite');records=db.execute('select status,attempts,result from samples order by seq').fetchall()
        self.assertEqual(len(RejectPool.calls),1);self.assertEqual(records[0][:2],('abandoned',1))
        self.assertEqual([r[:2] for r in records[1:]],[('queued',0),('queued',0)])
        failure=json.loads(records[0][2]);self.assertEqual(failure['reason'],'compiler_submit_failed');self.assertTrue(failure['infrastructure_failure']);self.assertEqual(failure['compiler_unit'],'unit')
        self.assertTrue((run/'infrastructure_stop.json').is_file());self.assertFalse(result['finished']);db.close()

    def test_source_wrapper_and_failed_export_are_complete(self):
        run,db,rows=self.make_run(count=2);db.close()
        with patch.object(c.concurrent.futures,'ProcessPoolExecutor',ImmediatePool):result=c.run_batch(run,2,10)
        self.assertTrue(result['finished']);self.assertEqual(len(ImmediatePool.calls),2)
        for task in ImmediatePool.calls:self.assertEqual(task['source']['pair_sha256'],task['id'])
        failed=[json.loads(line) for line in (run/'failed.jsonl').read_bytes().splitlines()]
        self.assertEqual([r['compiler_unit'] for r in failed],['unit','unit']);self.assertTrue(all(r['source_code_sha256']=='1'*64 for r in failed))

    def test_unclean_worker_failure_stays_running_and_blocks_resume(self):
        run,db,rows=self.make_run(count=3);db.close()
        with patch.object(c.concurrent.futures,'ProcessPoolExecutor',UnsafePool):
            with self.assertRaisesRegex(RuntimeError,'cleanup_proof'):c.run_batch(run,1,10)
        db=sqlite3.connect(run/'status.sqlite')
        self.assertEqual(db.execute('select status,attempts from samples order by seq').fetchall(),
                         [('running',1),('queued',0),('queued',0)])
        self.assertTrue((run/'infrastructure_stop.json').is_file());db.close()


if __name__=='__main__':unittest.main(verbosity=2)
