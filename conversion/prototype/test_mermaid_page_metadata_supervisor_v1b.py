import copy,io,json,sqlite3,tempfile,threading,time,types,sys,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import bounded_sqlite_transaction_v1 as busy
import mermaid_page_metadata_supervisor_v1b as m
import mermaid_page_metadata_batch_v1 as base
import mermaid_page_metadata_candidate_v1 as core
import test_mermaid_page_metadata_v1 as fixture
import test_bounded_program_terminal_planner_v1 as dbfixture

class AtomicSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.CandidateTests();self.case.setUp();self.addCleanup(self.case.doCleanups);self.root=self.case.root;self.record=self.case.record;self.source=self.case.source;self.id=self.case.id;self.database=self.root/'conversion/jobs.sqlite';self.database.parent.mkdir(exist_ok=True);self.db=sqlite3.connect(self.database,timeout=30,isolation_level=None);self.addCleanup(self.db.close);self.db.execute('pragma journal_mode=WAL');self.db.executescript('create table jobs(id primary key,'+dbfixture.m.JOB_COLUMNS+');create table processing_outcomes_v2(id primary key,category,format,source_code_hash,source_image_hash,status,reason,record,updated_at);create table harness_queue_v3(id,state,worker_pid,attempts,priority);');self.db.execute('insert into jobs values('+','.join('?'*11)+')',(self.id,'needs_quality_repair',None,json.dumps(self.source),json.dumps(self.record),'old',None,1,'sample','scientific_diagram','mermaid'));self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)',(self.id,'scientific_diagram','mermaid',self.record['source_code_sha256'],self.record['source_image_sha256'],'pending',None,None,'old'));self.db.execute('insert into harness_queue_v3 values(?,?,?,?,?)',(self.id,'held_for_quality_v2',None,2,30));m.initialize(self.db);self.audit={'records':[{'id':self.id,'code_sha256':self.record['code_sha256'],'image_sha256':self.record['image_sha256'],'source_image_sha256':self.record['source_image_sha256']}]};self.validation='validation:test';self.files={};self.generations=0;self.preparations=0;m.DRAIN.clear()
    def selected(self,publish=False):return m.next_selection(self.db,self.audit,self.validation,publish)
    def generate(self,record,source,work,root):
        self.assertFalse(self.db.in_transaction);self.generations+=1;return core.generate(record,source,work,root,native_job=Mock(side_effect=[copy.deepcopy(self.case.native),copy.deepcopy(self.case.native)]),source_check=self.case.source_check,resources=lambda *a:{'verified_files':[],'verified_raster_cells':[]},quality=lambda *a:{'ok':False,'failures':['known_local_text']},pins={})
    def artifacts(self,*args):
        self.assertFalse(self.db.in_transaction);self.preparations+=1
        with patch.dict(sys.modules,{'auto_quality_common_v4':types.SimpleNamespace(resource_checks=lambda *a:{})}):return base.publish_artifacts(*args)
    def prepare(self,publish=False):
        selected=self.selected(publish);work=self.root/'conversion'/('work'+str(self.generations));return m.prepare(self.db,selected,work,self.validation,'supervisor:test',self.files,publish,self.root,self.generate,self.artifacts)
    def original(self):return {'job':base.snapshot(self.db,'jobs',self.id),'outcome':base.snapshot(self.db,'processing_outcomes_v2',self.id),'queues':base.queues(self.db,self.id)}
    def assert_unowned(self):self.assertEqual(self.db.execute('select worker_pid from jobs').fetchone()[0],None);self.assertFalse(self.db.execute('select 1 from '+base.TABLE+" where state='running'").fetchone())
    def test_heavy_generation_preparation_and_full_file_reads_are_outside_transaction(self):
        before=self.original();path,intent=self.prepare(True);self.assertEqual(self.original(),before);self.assertEqual(self.db.execute('select count(*) from '+base.TABLE).fetchone()[0],0);original_read=Path.read_bytes;original_sync=m.os.fsync
        def read(p):self.assertFalse(self.db.in_transaction,'Full file read while holding writer lock');return original_read(p)
        def sync(fd):self.assertFalse(self.db.in_transaction,'Artifact fsync while holding writer lock');return original_sync(fd)
        with patch.object(Path,'read_bytes',read),patch.object(m.os,'fsync',sync):receipt=m.commit_prepared(self.db,path,intent)
        self.assertTrue(receipt['published']);self.assert_unowned();self.assertEqual(self.generations,1);self.assertEqual(self.preparations,1);self.assertEqual(base.snapshot(self.db,'processing_outcomes_v2',self.id),before['outcome']);self.assertLess(max(receipt['transaction_seconds']),1)
    def test_dry_run_atomic_claim_and_restore_never_exposes_owned_job(self):
        before=self.original();path,intent=self.prepare(False);observer=sqlite3.connect(self.database,isolation_level=None);self.addCleanup(observer.close);actual=m._sql_once
        def observe(db,value):
            actual(db,value);self.assertEqual(observer.execute('select state,worker_pid from jobs').fetchone(),('needs_quality_repair',None))
        with patch.object(m,'_sql_once',side_effect=observe):receipt=m.commit_prepared(self.db,path,intent)
        self.assertEqual(receipt['state'],'validated_dry_run');self.assertEqual(self.original(),before);self.assert_unowned()
    def test_busy_budget_exhaustion_leaves_recoverable_intent_without_owned_jobs(self):
        path,intent=self.prepare(True);before=self.original();blocker=sqlite3.connect(self.database,timeout=0,isolation_level=None);self.addCleanup(blocker.close);blocker.execute('begin immediate');started=time.monotonic()
        with self.assertRaises(m.PendingIntent) as error:m.commit_prepared(self.db,path,intent,seconds=.06,step_seconds=.02)
        self.assertLess(time.monotonic()-started,.7);self.assertEqual(error.exception.state,'busy_prepared_unowned');self.assertTrue(path.exists());self.assertEqual(self.original(),before);self.assert_unowned();blocker.rollback();receipt=m.commit_prepared(self.db,path,intent);self.assertTrue(receipt['published']);self.assertEqual(self.generations,1);self.assertEqual(self.preparations,1);self.assert_unowned()
    def test_transient_writer_busy_waits_without_regeneration(self):
        path,intent=self.prepare(True);blocker=sqlite3.connect(self.database,timeout=0,isolation_level=None,check_same_thread=False);blocker.execute('begin immediate');timer=threading.Timer(.10,blocker.rollback);timer.start()
        try:receipt=m.commit_prepared(self.db,path,intent,seconds=2,step_seconds=.03)
        finally:timer.join();blocker.close()
        self.assertTrue(receipt['published']);self.assertGreater(receipt['db_budget']['wait_seconds'],.02);self.assertEqual(self.generations,1);self.assert_unowned()
    def test_busy_after_sql_mutations_rolls_back_then_retries_only_short_sql(self):
        path,intent=self.prepare(True);actual=m._sql_once;calls=[]
        def once(db,value):
            actual(db,value);calls.append(1)
            if len(calls)==1:raise sqlite3.OperationalError('database is locked')
        with patch.object(m,'_sql_once',side_effect=once):receipt=m.commit_prepared(self.db,path,intent,seconds=2)
        self.assertTrue(receipt['published']);self.assertEqual(len(calls),2);self.assertEqual(self.generations,1);self.assertEqual(self.preparations,1);self.assertEqual(self.db.execute('select count(*) from '+base.TABLE).fetchone()[0],1);self.assert_unowned()
    def test_commit_busy_retries_original_transaction_without_replaying_body(self):
        path,intent=self.prepare(True);actual=busy.durable_commit;calls=[];body=Mock(wraps=m._sql_once)
        def once(db,**kwargs):
            calls.append(1)
            if len(calls)==1:raise sqlite3.OperationalError('database is locked')
            return actual(db,**kwargs)
        with patch.object(busy,'durable_commit',side_effect=once),patch.object(m,'_sql_once',body):receipt=m.commit_prepared(self.db,path,intent,seconds=2)
        self.assertTrue(receipt['published']);self.assertEqual(body.call_count,1);self.assertEqual(len(calls),2);self.assert_unowned()
    def test_nonbusy_sql_failure_is_single_attempt_and_rolls_back_claim(self):
        path,intent=self.prepare(True);before=self.original();actual=m._sql_once;calls=[]
        def fail(db,value):actual(db,value);calls.append(1);raise sqlite3.OperationalError('no such table: intentional_fixture')
        with patch.object(m,'_sql_once',side_effect=fail):
            with self.assertRaises(m.PendingIntent) as error:m.commit_prepared(self.db,path,intent)
        self.assertEqual(error.exception.state,'nonbusy_failed_closed_unowned');self.assertEqual(len(calls),1);self.assertEqual(self.original(),before);self.assert_unowned()
    def test_commit_ack_error_probes_nonce_and_never_replays_publication(self):
        path,intent=self.prepare(True)
        class AckBudget(busy.BusyBudget):
            def commit(self,db):db.commit();raise sqlite3.OperationalError('lost completion acknowledgement')
        body=Mock(wraps=m._sql_once)
        with patch.object(m,'_sql_once',body):
            with self.assertRaises(m.CommittedThenFailed) as error:m.commit_prepared(self.db,path,intent,budget_factory=AckBudget)
        self.assertTrue(error.exception.receipt['confirmed_committed_receipt']);self.assertEqual(error.exception.state,'confirmed_commit_nonbusy_failure_draining');self.assertEqual(body.call_count,1);changes=self.db.total_changes;again=m.commit_prepared(self.db,path,intent);self.assertTrue(again['confirmed_committed_receipt']);self.assertEqual(self.db.total_changes,changes);self.assert_unowned()
    def test_busy_receipt_probe_exhaustion_preserves_intent_without_new_render(self):
        path,intent=self.prepare(True);before=self.original();actual=m._receipt
        with patch.object(m,'_receipt',side_effect=sqlite3.OperationalError('database is locked')):
            with self.assertRaises(m.PendingIntent) as error:m.commit_prepared(self.db,path,intent,seconds=.06,step_seconds=.02)
        self.assertEqual(error.exception.state,'receipt_probe_busy_prepared_unowned');self.assertEqual(self.original(),before);self.assert_unowned();self.assertTrue(m.commit_prepared(self.db,path,intent)['published']);self.assertEqual(self.generations,1)
    def test_busy_probe_after_unknown_commit_does_not_replay_sql_or_generation(self):
        path,intent=self.prepare(True);actual=m._receipt;calls=[]
        class AckBudget(busy.BusyBudget):
            def commit(self,db):db.commit();raise sqlite3.OperationalError('lost completion acknowledgement')
        def probe(db,value):
            calls.append(1)
            if len(calls)>1:raise sqlite3.OperationalError('database is locked')
            return actual(db,value)
        with patch.object(m,'_receipt',side_effect=probe),patch.object(m,'_sql_once',wraps=m._sql_once) as body:
            with self.assertRaises(m.PendingIntent) as error:m.commit_prepared(self.db,path,intent,seconds=.06,step_seconds=.02,budget_factory=AckBudget)
        self.assertEqual(error.exception.state,'receipt_probe_busy_prepared_unowned');self.assertEqual(body.call_count,1);self.assert_unowned();changes=self.db.total_changes;self.assertTrue(m.commit_prepared(self.db,path,intent)['confirmed_committed_receipt']);self.assertEqual(self.db.total_changes,changes);self.assertEqual(self.generations,1)
    def test_sibling_drain_while_waiting_cancels_before_atomic_claim(self):
        path,intent=self.prepare(True);before=self.original();cancel=threading.Event()
        class CancelBudget(busy.BusyBudget):
            def begin(self,db):super().begin(db);cancel.set()
        result=m.commit_prepared(self.db,path,intent,budget_factory=CancelBudget,cancel_check=cancel.is_set);self.assertEqual(result['state'],'drained_prepared_unowned');self.assertEqual(self.original(),before);self.assert_unowned()
    def test_job_outcome_queue_or_stage_stolen_is_preserved(self):
        for mode in ('job','outcome','queue','stage'):
            path,intent=self.prepare(True)
            if mode=='job':self.db.execute("update jobs set error='foreign'")
            elif mode=='outcome':self.db.execute("update processing_outcomes_v2 set status='qualified'")
            elif mode=='queue':self.db.execute("update harness_queue_v3 set state='running'")
            else:self.db.execute('insert into '+base.TABLE+' values(?,?,?,?,?,?,?,?,?,?,?)',(*intent['selection']['key'][:5],'another-policy','deferred_retained_prior',99,'foreign','{}','later'))
            before=self.original();receipt=m.commit_prepared(self.db,path,intent);self.assertEqual(receipt['state'],'stale_prepared_unowned');self.assertEqual(self.original(),before);self.assert_unowned();self.db.execute('delete from '+base.TABLE);self.db.execute("update jobs set error=NULL");self.db.execute("update processing_outcomes_v2 set status='pending'");self.db.execute("update harness_queue_v3 set state='held_for_quality_v2'")
    def test_source_or_pins_changed_during_lock_wait_fail_stat_cas_before_claim(self):
        path,intent=self.prepare(True);before=self.original();target=self.root/self.record['original_source_code']
        class MutatingBudget(busy.BusyBudget):
            def begin(self,db):super().begin(db);target.write_bytes(b'foreign source')
        receipt=m.commit_prepared(self.db,path,intent,budget_factory=MutatingBudget);self.assertEqual(receipt['state'],'stale_prepared_unowned');self.assertEqual(self.original(),before);self.assert_unowned()
    def test_immutable_intent_or_prepared_artifact_damage_never_claims(self):
        path,intent=self.prepare(True);before=self.original();(Path(intent['report']['work'])/'candidate.png').write_bytes(b'bad')
        with self.assertRaises(m.Stale):m.commit_prepared(self.db,path,intent)
        self.assertEqual(self.original(),before);self.assert_unowned()
    def test_terminal_lookup_survives_supervisor_and_validation_policy_changes(self):
        key=self.selected()['key'];self.db.execute('insert into '+base.TABLE+' values(?,?,?,?,?,?,?,?,?,?,?)',(*key[:5],'older-supervisor-policy','deferred_retained_prior',99,'old-token','{}','old'));self.assertIsNone(m.next_selection(self.db,self.audit,'new-validation-policy',True));self.db.execute("update "+base.TABLE+" set state='validated_dry_run'");self.assertIsNotNone(m.next_selection(self.db,self.audit,'new-validation-policy',True));self.assertIsNone(m.next_selection(self.db,self.audit,'new-validation-policy',False))
    def test_status_write_failure_after_commit_does_not_hide_nonce_receipt(self):
        path,intent=self.prepare(True);actual=m.atomic
        def fail(path,data):
            if Path(path).name=='recovery_status.json':raise OSError('status fsync failure')
            return actual(path,data)
        with patch.object(m,'atomic',side_effect=fail):receipt=m.commit_prepared(self.db,path,intent)
        self.assertTrue(receipt['confirmed_committed_receipt']);self.assert_unowned()
    def test_process_death_safe_revision_flock_prevents_duplicate_preparation(self):
        key=self.selected()['key'];a=m.revision_lock(self.root,key)
        try:
            with self.assertRaises(BlockingIOError):m.revision_lock(self.root,key)
        finally:a.close()
        b=m.revision_lock(self.root,key);b.close()
    def test_prepare_and_preselection_refuse_callers_open_transaction(self):
        self.db.execute('begin')
        with self.assertRaises(m.Stale):self.selected()
        self.assertTrue(self.db.in_transaction);self.db.rollback()

if __name__=='__main__':unittest.main()
