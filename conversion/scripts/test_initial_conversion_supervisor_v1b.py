import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import os
import sys
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import test_initial_conversion_supervisor_v1 as fixtures
import initial_conversion_supervisor_v1b as b


class HardeningTests(unittest.TestCase):
    add=fixtures.StateTests.add
    claim=fixtures.StateTests.claim
    result=fixtures.StateTests.result
    def setUp(self):
        self.binding=patch.object(fixtures,'b',b);self.binding.start();fixtures.StateTests.setUp(self)
    def tearDown(self):
        fixtures.StateTests.tearDown(self);self.binding.stop()
    def disk_fixture(self,stage='compile',policy='policy-v1'):
        path=self.root/'contention.sqlite';old=self.db;self.db=sqlite3.connect(path,timeout=0);fixtures.schema(self.db);b.create_run(self.db,'run',policy,True,{'compile':2,'native':2});prior=self.add(stage=stage);self.db.close();self.db=old;return path,prior
    def test_real_claim_wait_longer_than_five_seconds_then_exactly_one_claim(self):
        path,prior=self.disk_fixture();holder=sqlite3.connect(path,timeout=0);holder.execute('begin immediate');start=time.monotonic()
        def claiming():
            db=sqlite3.connect(path,timeout=0)
            try:return b.claim(db,prior,'compile','run','policy-v1',111,99,admission_timeout=20,busy_step_seconds=5,intent_dir=self.root/b.OWNER/'intents')
            finally:db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(claiming);time.sleep(6.3);holder.commit();result=future.result(timeout=10)
        self.assertGreaterEqual(time.monotonic()-start,6.2);self.assertIsNotNone(result);self.assertGreaterEqual(result['db_admission']['wait_seconds'],6.);db=sqlite3.connect(path);self.assertEqual(db.execute('select claimed from '+b.RUNS+' where stage="compile"').fetchone()[0],1);self.assertEqual(db.execute('select count(*) from '+b.TABLE).fetchone()[0],1);self.assertEqual(b.as_job(b.snapshot(db,'case'))['attempts'],4);db.close();holder.close()
    def test_real_finish_wait_longer_than_five_seconds_does_not_consume_publication_budget(self):
        path,prior=self.disk_fixture('native');db=sqlite3.connect(path,timeout=0);old=self.db;self.db=db;current=self.claim(stage='native');work,result=self.result(current,True);self.db=old;db.close();holder=sqlite3.connect(path,timeout=0);holder.execute('begin immediate');calls=[];digest=b.sha((work/'candidate.drawio').read_bytes());start=time.monotonic()
        def finishing():
            db=sqlite3.connect(path,timeout=0)
            def writer(*args):calls.append(1);return b.publish_native(*args)
            try:return b.finish(db,current,result,work,True,artifact_writer=writer,admission_timeout=20,busy_step_seconds=5,publication_timeout=.5)
            finally:db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(finishing);time.sleep(6.3);holder.commit();report=future.result(timeout=10)
        self.assertGreaterEqual(time.monotonic()-start,6.2);self.assertEqual(report['state'],'published_pending_quality');self.assertEqual(calls,[1]);self.assertGreaterEqual(report['db_admission']['wait_seconds'],6.);self.assertEqual(b.sha((work/'candidate.drawio').read_bytes()),digest);db=sqlite3.connect(path);self.assertIsNone(b.as_job(b.snapshot(db,'case'))['worker_pid']);self.assertEqual(db.execute('select claimed from '+b.RUNS+' where stage="native"').fetchone()[0],1);db.close();holder.close()
    def test_claim_budget_exhaustion_has_intent_and_no_committed_claim(self):
        path,prior=self.disk_fixture();holder=sqlite3.connect(path,timeout=0);holder.execute('begin immediate');db=sqlite3.connect(path,timeout=0)
        try:
            with self.assertRaises(b.AdmissionDeferred) as failure:b.claim(db,prior,'compile','run','policy-v1',111,99,admission_timeout=.15,busy_step_seconds=.1,intent_dir=self.root/b.OWNER/'intents')
            intent=json.loads(Path(failure.exception.intent_file).read_text());self.assertEqual(intent['status'],'not_claimed');self.assertTrue(intent['no_claim_committed']);self.assertFalse(db.in_transaction)
        finally:holder.rollback();holder.close()
        self.assertEqual(b.snapshot(db,'case'),prior);self.assertEqual(db.execute('select count(*) from '+b.TABLE).fetchone()[0],0);db.close()
    def test_finish_budget_exhaustion_parks_exact_lease_then_explicit_resume_without_regeneration(self):
        policy='bounded_offline_initial_tikz_v1b:test';path,prior=self.disk_fixture('native',policy);db=sqlite3.connect(path,timeout=0);old=self.db;self.db=db;current=self.claim(stage='native',policy=policy);work,result=self.result(current,True);self.db=old;db.close();holder=sqlite3.connect(path,timeout=0);holder.execute('begin immediate')
        def finish_timed():
            db=sqlite3.connect(path,timeout=0)
            try:
                with self.assertRaises(b.AdmissionDeferred) as failure:b.finish(db,current,result,work,True,admission_timeout=.15,busy_step_seconds=.1,handoff_timeout=3)
                return failure.exception.intent_file
            finally:db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(finish_timed);time.sleep(.8);holder.commit();intent_file=future.result(timeout=5)
        holder.close();journal=json.loads(Path(intent_file).read_text());self.assertEqual(journal['status'],'prepared_unowned_recovery');db=sqlite3.connect(path,timeout=0);job=b.as_job(b.snapshot(db,'case'));self.assertIsNone(job['worker_pid']);self.assertEqual(job['state'],'initial_conversion_prepared_v1b');self.assertIsNone(job['output_record']);self.assertEqual(db.execute('select status from processing_outcomes_v2').fetchone()[0],'pending')
        with patch.object(b,'run_case',side_effect=AssertionError('Prepared child must not regenerate')):report=b.resume_prepared_intent(db,intent_file,pid=222,pid_start=99,admission_timeout=2)
        self.assertEqual(report['state'],'published_pending_quality');self.assertEqual(db.execute('select claimed from '+b.RUNS+' where stage="native"').fetchone()[0],1);self.assertEqual(b.as_job(b.snapshot(db,'case'))['attempts'],4);db.close()
    def test_nonbusy_publication_error_is_once_failclosed_and_retains_prepared_unowned(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);self.db.execute("CREATE TRIGGER fail_publish BEFORE UPDATE OF state ON jobs WHEN NEW.state='needs_quality_repair' BEGIN SELECT RAISE(ABORT,'nonbusy fixture'); END");self.db.commit();calls=[]
        def writing(*args):calls.append(1);return b.publish_native(*args)
        with self.assertRaises(sqlite3.IntegrityError) as failure:b.finish(self.db,current,result,work,True,artifact_writer=writing,admission_timeout=1,handoff_timeout=1)
        self.assertEqual(calls,[1]);journal=json.loads(Path(failure.exception.intent_file).read_text());self.assertEqual(journal['status'],'prepared_unowned_recovery');job=b.as_job(b.snapshot(self.db,'case'));self.assertIsNone(job['worker_pid']);self.assertIsNone(job['output_record']);self.assertFalse(b.pointer_path('case').exists())
    def test_busy_claim_commit_ack_recovers_receipt_without_second_quota(self):
        self.add();prior=b.snapshot(self.db,'case');real=b.BusyBudget.commit
        def ack(budget,db):real(budget,db);raise sqlite3.OperationalError('database is locked')
        with patch.object(b.BusyBudget,'commit',ack):current=b.claim(self.db,prior,'compile','run','policy-v1',111,99)
        self.assertTrue(current['db_admission']['committed_claim_receipt_recovered']);self.assertEqual(self.db.execute('select claimed from '+b.RUNS+' where stage="compile"').fetchone()[0],1);self.assertEqual(self.db.execute('select count(*) from '+b.TABLE).fetchone()[0],1)

    def test_busy_mutation_retry_budget_exhaustion_keeps_claim_uncommitted(self):
        prior=self.add()
        with patch.object(b.BusyBudget,'commit',side_effect=sqlite3.OperationalError('database is locked')):
            with self.assertRaises(b.AdmissionDeferred) as failure:b.claim(self.db,prior,'compile','run','policy-v1',111,99,admission_timeout=.1)
        self.assertEqual(b.snapshot(self.db,'case'),prior);self.assertEqual(self.db.execute('select count(*) from '+b.TABLE).fetchone()[0],0);self.assertEqual(self.db.execute('select claimed from '+b.RUNS+' where stage="compile"').fetchone()[0],0);self.assertTrue(json.loads(Path(failure.exception.intent_file).read_text())['no_claim_committed'])

    def test_nonbusy_claim_error_is_not_retried_or_claimed(self):
        prior=self.add();self.db.execute("CREATE TRIGGER fail_claim BEFORE UPDATE ON jobs BEGIN SELECT RAISE(ABORT,'claim fixture'); END");self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):b.claim(self.db,prior,'compile','run','policy-v1',111,99,admission_timeout=.1)
        self.assertEqual(b.snapshot(self.db,'case'),prior);self.assertEqual(self.db.execute('select count(*) from '+b.TABLE).fetchone()[0],0);self.assertEqual(len(list((self.root/b.OWNER/'database_intents_v1b').glob('claim_nonbusy_failure.*.json'))),1)
    def test_busy_finish_commit_ack_recovers_receipt_without_second_fs_publication(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);calls=[];real=b.BusyBudget.commit
        def ack(budget,db):real(budget,db);raise sqlite3.OperationalError('database is locked')
        def writer(*args):calls.append(1);return b.publish_native(*args)
        with patch.object(b.BusyBudget,'commit',ack):report=b.finish(self.db,current,result,work,True,artifact_writer=writer)
        self.assertEqual(report['state'],'published_pending_quality');self.assertTrue(report['db_admission']['committed_finish_receipt_recovered']);self.assertEqual(calls,[1]);self.assertEqual(json.loads(b.pointer_path('case').read_text()),result['record'])
    def test_changed_foreign_lease_during_wait_is_not_restored_or_published(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);self.db.execute('UPDATE jobs SET worker_pid=222,state="foreign_lease"');self.db.commit();foreign=b.snapshot(self.db,'case');calls=[];report=b.finish(self.db,current,result,work,True,artifact_writer=lambda *args:calls.append(1));self.assertEqual(report['state'],'stale_revision');self.assertEqual(b.snapshot(self.db,'case'),foreign);self.assertEqual(calls,[])

    def test_publication_execution_timeout_retains_successful_prepared_result(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True)
        def slow(*a):b.publish_native(*a);time.sleep(.03)
        with self.assertRaises(TimeoutError) as failure:b.finish(self.db,current,result,work,True,artifact_writer=slow,publication_timeout=.01)
        journal=json.loads(Path(failure.exception.intent_file).read_text());self.assertTrue(journal['prepared_result']['ok']);self.assertEqual(journal['status'],'prepared_unowned_recovery');self.assertIsNone(b.as_job(b.snapshot(self.db,'case'))['worker_pid']);self.assertFalse(b.pointer_path('case').exists())

    def test_unwritable_handoff_retains_durable_exact_lease_then_dead_owner_resume(self):
        policy='bounded_offline_initial_tikz_v1b:test';path,prior=self.disk_fixture('native',policy);db=sqlite3.connect(path,timeout=0);old=self.db;self.db=db;current=self.claim(stage='native',policy=policy);work,result=self.result(current,True);self.db=old;holder=sqlite3.connect(path,timeout=0);holder.execute('begin immediate')
        with self.assertRaises(b.AdmissionDeferred) as failure:b.finish(db,current,result,work,True,admission_timeout=.1,busy_step_seconds=.1,handoff_timeout=.1)
        intent_file=failure.exception.intent_file;journal=json.loads(Path(intent_file).read_text());self.assertEqual(journal['status'],'lease_retained_with_durable_intent');self.assertEqual(b.snapshot(db,'case'),tuple(current['owned_snapshot']));holder.rollback();holder.close()
        with self.assertRaises(RuntimeError):b.resume_prepared_intent(db,intent_file,pid=222,pid_start=100)
        with patch.object(b,'birth',side_effect=lambda pid:None if pid==111 else 100),patch.object(b,'run_case',side_effect=AssertionError('no regeneration')):report=b.resume_prepared_intent(db,intent_file,pid=222,pid_start=100)
        self.assertEqual(report['state'],'published_pending_quality');self.assertIsNone(b.as_job(b.snapshot(db,'case'))['worker_pid']);self.assertEqual(db.execute('select claimed from '+b.RUNS+' where stage="native"').fetchone()[0],1);db.close()
    def test_v1_terminal_stage_is_not_reset_by_v1b_policy(self):
        self.add();prior=b.snapshot(self.db,'case');current=self.claim();work,result=self.result(current);b.finish(self.db,current,result,work);self.db.execute('UPDATE jobs SET state="queued",worker_pid=NULL');self.db.commit();b.create_run(self.db,'later','bounded_offline_initial_tikz_v1b:new',True,{'compile':2,'native':2});self.assertIsNone(b.select_candidate(self.db,'later','compile'))

    def test_real_startup_waits_over_five_seconds_and_run_nonce_is_idempotent(self):
        path,prior=self.disk_fixture();holder=sqlite3.connect(path,timeout=0);holder.execute('begin immediate')
        def starting():
            db=sqlite3.connect(path,timeout=30)
            try:
                initialization=b.init(db,20);b.create_run(db,'startup','policy',True,{'compile':2,'native':2},20);b.create_run(db,'startup','policy',True,{'compile':2,'native':2},20);return initialization,db.execute('select count(*) from '+b.RUNS+' where run_id="startup"').fetchone()[0]
            finally:db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(starting);time.sleep(6.3);holder.commit();diagnostics,count=future.result(timeout=10)
        holder.close();self.assertGreaterEqual(diagnostics['wait_seconds'],6.);self.assertEqual(count,2)

    def slot_fixture(self,stage='native'):
        path,prior=self.disk_fixture(stage);run=self.root/'runtime';run.mkdir();owner=run/'owner.json';metadata={'pid':os.getppid(),'pid_start_ticks':99,'run_id':'run','policy':'policy-v1','pins':{},'owner_file':str(owner),'events_file':str(run/'events.jsonl')};owner.write_bytes(b.raw_json(metadata));meta=run/'run.json';meta.write_bytes(b.raw_json(metadata))
        args=SimpleNamespace(db=str(path),run_metadata=str(meta),run_id='run',control=str(run/'control.json'),stage=stage,watch=False,publish=True,timeout=.01,max_side=8192,claim_admission_timeout=1,finish_admission_timeout=2,publication_timeout=30,handoff_timeout=2)
        return args,metadata,prior

    def test_slot_admission_deferred_is_not_replayed_or_changed_and_requests_drain(self):
        args,metadata,prior=self.slot_fixture();failure=b.AdmissionDeferred('fixture_prepared',self.root/'intent.json');calls=[]
        def run(current,*a,**kw):
            work,result=self.result(current,True);return work,result,{'cleanup_complete':True}
        def finish(*a,**kw):calls.append((a,kw));raise failure
        with patch.object(b.signal,'signal'),patch.object(b,'owner_valid',return_value=True),patch.object(b,'run_case',side_effect=run),patch.object(b,'finish',side_effect=finish):
            with self.assertRaises(b.AdmissionDeferred) as raised:b.slot(args)
        self.assertIs(raised.exception,failure);self.assertEqual(len(calls),1);self.assertTrue(calls[0][0][2]['ok']);self.assertNotIn('deadline',calls[0][1]);self.assertEqual(calls[0][1]['publication_timeout'],30);self.assertTrue(b.draining(args.control));self.assertEqual(json.loads(Path(metadata['events_file']).read_text().splitlines()[0])['state'],'slot_failed_closed')

    def test_expired_child_deadline_does_not_limit_finish_publication(self):
        args,metadata,prior=self.slot_fixture();calls=[];real=b.finish
        def run(current,*a,**kw):
            work,result=self.result(current,True);time.sleep(.03);return work,result,{'cleanup_complete':True}
        def finish(*a,**kw):calls.append(kw);return real(*a,**kw)
        with patch.object(b.signal,'signal'),patch.object(b,'owner_valid',return_value=True),patch.object(b,'run_case',side_effect=run),patch.object(b,'finish',side_effect=finish):report=b.slot(args)
        self.assertEqual(report['counts'],{'published_pending_quality':1});self.assertEqual(len(calls),1);self.assertNotIn('deadline',calls[0]);self.assertEqual(calls[0]['publication_timeout'],30)

    def test_durable_intent_fsyncs_file_then_rename_then_directory_before_return(self):
        events=[];real_fsync=b.os.fsync;real_replace=Path.replace
        def syncing(fd):events.append(('fsync',os.fstat(fd).st_mode));return real_fsync(fd)
        def replacing(path,target):events.append(('replace',str(path)));return real_replace(path,target)
        with patch.object(b.os,'fsync',side_effect=syncing),patch.object(Path,'replace',replacing):path=b.save_intent('durable',{'status':'prepared'},self.root/'intents','nonce')
        import stat
        self.assertEqual(json.loads(path.read_text())['status'],'prepared');regular=[i for i,e in enumerate(events) if e[0]=='fsync' and stat.S_ISREG(e[1])];directories=[i for i,e in enumerate(events) if e[0]=='fsync' and stat.S_ISDIR(e[1])];replacement=next(i for i,e in enumerate(events) if e[0]=='replace');self.assertLess(regular[0],replacement);self.assertGreater(directories[-1],replacement)

    def test_failed_slot_drains_healthy_watch_sibling_and_reports_failure(self):
        control=self.root/'monitor-control.json';work=self.root/'monitor';work.mkdir();code='from pathlib import Path;import time,sys;p=Path(sys.argv[1]);end=time.monotonic()+5\nwhile time.monotonic()<end and not p.exists():time.sleep(.01)\nsys.exit(0 if p.exists() else 7)'
        a=subprocess.Popen([sys.executable,'-c','import sys;sys.exit(3)']);c=subprocess.Popen([sys.executable,'-c',code,str(control)]);started=time.monotonic()
        try:report=b.monitor_slots([(a,None),(c,None)],control,work,.01,watch=True)
        finally:
            for child in [a,c]:
                if child.poll() is None:child.terminate()
                child.wait(timeout=5)
        self.assertTrue(report['failed']);self.assertLess(time.monotonic()-started,3);self.assertEqual(a.returncode,3);self.assertEqual(c.returncode,0);self.assertTrue(json.loads(control.read_text())['drain']);self.assertEqual(len(report['failures']),1)

if __name__=='__main__':unittest.main()
