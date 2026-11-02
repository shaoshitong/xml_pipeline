import copy
import json
import sqlite3
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

import auto_quality_html_text_layout_batch_v5a as b

RULE='layout-v5a-test';QA='current-fixed-qa'


def schema(db,models=True):
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,category TEXT,format TEXT,state TEXT,output_record TEXT,worker_pid INT,error TEXT,updated_at TEXT,input_record TEXT,input_manifest TEXT)')
    db.execute('CREATE TABLE processing_outcomes_v2(id TEXT PRIMARY KEY,category TEXT,format TEXT,source_code_hash TEXT,source_image_hash TEXT,status TEXT,reason TEXT,record TEXT,updated_at TEXT)')
    db.execute('CREATE TABLE auto_quality_exceptions_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,route TEXT,state TEXT,reason TEXT,updated_at TEXT)')
    if models:db.execute('CREATE TABLE harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,attempts INT DEFAULT 0,priority INT DEFAULT 0,worker_pid INT,started_at TEXT,heartbeat TEXT,session_dir TEXT,error TEXT)')
    db.commit();b.init(db)


def add(db,id='case',state='needs_quality_repair',outcome='pending',worker=None,qa=QA,reason='raster_anomaly: local_text_line_ssim_below_0.55',fmt='html',category='poster',model='held_by_user_policy',record=None):
    old=record or {'id':id,'source_pair_sha256':id,'source_format':fmt,'category':category,'source_code_sha256':'a'*64,'source_image_sha256':'b'*64,
                   'code_file':'clean/case/old.drawio','image_file':'clean/case/old.png','code_sha256':'c'*64,'image_sha256':'d'*64}
    original={'code_sha256':old['source_code_sha256'],'image_sha256':old['source_image_sha256']};raw=json.dumps(old)
    db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',(id,category,fmt,state,raw,worker,'old-error','old-time',json.dumps(original),'old-input-manifest'))
    db.execute('INSERT INTO processing_outcomes_v2 VALUES(?,?,?,?,?,?,?,?,?)',(id,category,fmt,old['source_code_sha256'],old['source_image_sha256'],outcome,'reason' if outcome=='abandoned' else None,None,'old-outcome-time'))
    db.execute('INSERT INTO auto_quality_exceptions_v1 VALUES(?,?,?,?,?,?,?,?)',(id,old['code_sha256'],old['image_sha256'],qa,'source_geometry_or_harness','pending',reason,'old-qa-time'))
    if b.exists(db,'harness_queue_v3') and model is not None:
        db.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?,?,?,?)',(id,model,7,42,None,'old-start','old-heart','old-session','historic-error'))
    db.commit();return old,raw


def select(db,publish=False,**kwargs):return b.select_candidate(db,RULE,publish,qa_policy=QA,**kwargs)
def claim(db,publish=False):return b.claim(db,select(db,publish),RULE,publish,pid=111)
def finish(db,current,report,out=None,work=None,publish=False,**kwargs):return b.finish(db,current,report,out,work,publish,qa_policy=QA,**kwargs)


class StateTests(unittest.TestCase):
    def setUp(self):self.db=sqlite3.connect(':memory:');schema(self.db)
    def tearDown(self):self.db.close()

    def test_only_exact_current_active_qa_idle_pending_html_poster_is_selected(self):
        for id,options in [('accepted',{'state':'accepted'}),('qualified',{'outcome':'qualified'}),('abandoned',{'outcome':'abandoned'}),
                           ('busy',{'worker':9}),('paid',{'model':'running'}),('stale-qa',{'qa':'old-policy'}),
                           ('other-error',{'reason':'global_fidelity_below_0.90'}),('wrong-format',{'fmt':'svg'}),('wrong-category',{'category':'scientific_diagram'}),('eligible',{})]:
            add(self.db,id=id,**options)
        self.assertEqual(select(self.db)[0],'eligible')
        self.db.execute("UPDATE auto_quality_exceptions_v1 SET image_hash='stale' WHERE id='eligible'");self.db.commit()
        self.assertIsNone(select(self.db))

    def test_all_three_paid_model_generations_and_nonrunning_owner_are_guarded(self):
        add(self.db)
        for table in ('harness_queue','harness_queue_v2'):
            self.db.execute('CREATE TABLE '+table+'(id TEXT,state TEXT)');self.db.execute('INSERT INTO '+table+' VALUES("case","running")');self.db.commit()
            self.assertIsNone(select(self.db));self.db.execute('DROP TABLE '+table);self.db.commit()
        self.db.execute('UPDATE harness_queue_v3 SET worker_pid=8');self.db.commit();self.assertIsNone(select(self.db))

    def test_full_snapshot_and_registered_source_identity_claim_cas(self):
        add(self.db);selection=select(self.db);positions={name:i for i,name in enumerate(b.SNAPSHOT_COLUMNS.split(','))}
        for field,value in [('state','accepted'),('worker_pid',9),('input_record','{}'),('input_manifest','changed'),('updated_at','changed'),('error','changed')]:
            self.db.execute('UPDATE jobs SET '+field+'=?',(value,));self.db.commit()
            self.assertIsNone(b.claim(self.db,selection,RULE,pid=111))
            self.db.execute('UPDATE jobs SET '+field+'=?',(selection[1][positions[field]],));self.db.commit()
        self.db.execute("UPDATE processing_outcomes_v2 SET source_code_hash='changed'");self.db.commit();self.assertIsNone(b.claim(self.db,selection,RULE,pid=111))

    def test_only_frozen_same_revision_qa3_failure_can_trigger_unchanged_html_under_exact_qa4_owner(self):
        add(self.db,qa=b.FROZEN_QA3_TRIGGER)
        selection=b.select_candidate(self.db,RULE,qa_policy=b.EQUIVALENT_QA4)
        self.assertEqual(selection[2:],(b.EQUIVALENT_QA4,b.FROZEN_QA3_TRIGGER))
        current=b.claim(self.db,selection,RULE,pid=111)
        self.assertTrue(current['trigger_equivalence_used'])
        calls=[]
        stage=b.finish(self.db,current,{'accepted':False},{'fake':'pending candidate'},publish=True,
                       artifact_writer=lambda *args:calls.append(1),qa_policy=b.EQUIVALENT_QA4)
        self.assertEqual(stage,'published_candidate');self.assertEqual(calls,[1])
        self.assertEqual(self.db.execute('SELECT status FROM processing_outcomes_v2').fetchone()[0],'pending')

    def test_trigger_equivalence_does_not_apply_to_new_layout_revision_or_another_qa_owner(self):
        add(self.db,qa=b.FROZEN_QA3_TRIGGER)
        self.assertIsNone(b.select_candidate(self.db,RULE,qa_policy=b.EQUIVALENT_QA4+'-different-implementation'))
        old=json.loads(b.snapshot(self.db,'case')[1]);old['html_text_layout_v5']={'version':5}
        self.db.execute('UPDATE jobs SET output_record=?',(json.dumps(old),));self.db.commit()
        self.assertIsNone(b.select_candidate(self.db,RULE,qa_policy=b.EQUIVALENT_QA4))
        forced=('case',tuple(b.snapshot(self.db,'case')),b.EQUIVALENT_QA4,b.FROZEN_QA3_TRIGGER)
        self.assertIsNone(b.claim(self.db,forced,RULE,pid=111))
        self.db.execute('UPDATE auto_quality_exceptions_v1 SET policy=?',(b.EQUIVALENT_QA4,));self.db.commit()
        self.assertIsNotNone(b.select_candidate(self.db,RULE,qa_policy=b.EQUIVALENT_QA4))

    def test_equivalent_failure_still_requires_exact_current_code_and_image(self):
        add(self.db,qa=b.FROZEN_QA3_TRIGGER)
        self.db.execute("UPDATE auto_quality_exceptions_v1 SET image_hash='different-image'");self.db.commit()
        self.assertIsNone(b.select_candidate(self.db,RULE,qa_policy=b.EQUIVALENT_QA4))

    def test_competing_owner_cannot_take_one_revision_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.sqlite';a=sqlite3.connect(path);schema(a);add(a);other=sqlite3.connect(path)
            first,second=select(a),select(other)
            self.assertIsNotNone(b.claim(a,first,RULE,pid=1));self.assertIsNone(b.claim(other,second,RULE,pid=2))
            a.close();other.close()

    def test_failure_restores_exact_prior_snapshot_and_leaves_policy_queue_intact(self):
        add(self.db);prior=b.snapshot(self.db,'case');queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();current=claim(self.db)
        self.assertEqual(finish(self.db,current,{'error':'unsupported source','accepted':False}),'retained_prior_candidate')
        self.assertEqual(b.snapshot(self.db,'case'),prior);self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue)
        self.assertIsNone(select(self.db));self.assertIsNone(select(self.db,True))

    def test_new_terminal_outcome_cannot_publish_or_be_reset_by_producer(self):
        add(self.db);current=claim(self.db);self.db.execute("UPDATE processing_outcomes_v2 SET status='abandoned',reason='fixed reason'");self.db.commit();calls=[]
        self.assertEqual(finish(self.db,current,{'accepted':False},{'fake':True},publish=True,artifact_writer=lambda *args:calls.append(1)),'retained_prior_candidate')
        self.assertEqual(calls,[]);self.assertEqual(self.db.execute('SELECT status FROM processing_outcomes_v2').fetchone()[0],'abandoned')

    def test_new_paid_owner_preserves_queue_and_prior_pair(self):
        _,raw=add(self.db);current=claim(self.db)
        self.db.execute("UPDATE harness_queue_v3 SET state='running',worker_pid=8");self.db.commit();queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();calls=[]
        stage=finish(self.db,current,{'accepted':False,'cache':{'work':'frozen'}},{'fake':True},publish=True,artifact_writer=lambda *args:calls.append(1))
        self.assertEqual(stage,'validated_dry_run');self.assertEqual(calls,[]);self.assertEqual(b.snapshot(self.db,'case')[1],raw);self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue)

    def test_stolen_job_or_ledger_owner_is_not_overwritten(self):
        add(self.db);current=claim(self.db);self.db.execute("UPDATE jobs SET state='repair_running',worker_pid=222");self.db.commit();before=b.snapshot(self.db,'case')
        self.assertEqual(finish(self.db,current,{'accepted':False}),'stale_revision_or_ownership');self.assertEqual(b.snapshot(self.db,'case'),before)

    def test_changed_active_qa_keeps_pending_cache_without_publishing_or_rebuilding(self):
        add(self.db);current=claim(self.db);prior=tuple(current['prior_snapshot']);calls=[]
        stage=b.finish(self.db,current,{'accepted':False,'cache':{'work':'frozen'}},{'fake':True},publish=True,
             artifact_writer=lambda *args:calls.append(1),qa_policy='new-current-qa')
        self.assertEqual(stage,'validated_dry_run');self.assertEqual(calls,[]);self.assertEqual(b.snapshot(self.db,'case'),prior)

    def test_stolen_ledger_token_is_not_written_by_prior_owner(self):
        add(self.db);current=claim(self.db)
        self.db.execute('UPDATE '+b.TABLE+' SET owner_pid=222,claim_token="foreign-token"');self.db.commit()
        ledger=self.db.execute('SELECT * FROM '+b.TABLE).fetchone();job=b.snapshot(self.db,'case')
        self.assertEqual(finish(self.db,current,{'accepted':False}),'stale_revision_or_ownership')
        self.assertEqual(self.db.execute('SELECT * FROM '+b.TABLE).fetchone(),ledger);self.assertEqual(b.snapshot(self.db,'case'),job)

    def test_success_only_publishes_pending_and_preserves_queue_history_under_user_trigger(self):
        add(self.db);self.db.execute('''CREATE TRIGGER user_hold AFTER UPDATE OF state ON harness_queue_v3 WHEN NEW.state='held_for_quality_v2' BEGIN UPDATE harness_queue_v3 SET state='held_by_user_policy' WHERE id=NEW.id; END''');self.db.commit()
        current=claim(self.db,True);out={'code_sha256':'new','image_sha256':'new-image','quality_state':'pending_qa4'}
        stage=finish(self.db,current,{'accepted':False},out,publish=True,artifact_writer=lambda *args:None)
        self.assertEqual(stage,'published_candidate');self.assertEqual(b.snapshot(self.db,'case')[0],'needs_quality_repair')
        self.assertEqual(self.db.execute('SELECT state,attempts,priority,started_at,session_dir,error FROM harness_queue_v3').fetchone(),('held_by_user_policy',7,42,'old-start','old-session','historic-error'))
        self.assertEqual(self.db.execute('SELECT status FROM processing_outcomes_v2').fetchone()[0],'pending')

    def test_failed_publisher_is_sql_atomic_and_can_restore_prior_without_retrying_builder(self):
        add(self.db);current=claim(self.db,True);owned=b.snapshot(self.db,'case');queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone()
        def fail(*args):raise OSError('FS failure')
        with self.assertRaises(OSError):finish(self.db,current,{'accepted':False},{'code_sha256':'new'},publish=True,artifact_writer=fail)
        self.assertEqual(b.snapshot(self.db,'case'),owned);self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue)
        finish(self.db,current,{'error':'FS failure','accepted':False});self.assertIsNone(select(self.db,True))


class CacheAndFilesystemTests(unittest.TestCase):
    def fixture(self,root):
        self.db=sqlite3.connect(':memory:');schema(self.db);case=root/'clean/case';case.mkdir(parents=True)
        work=root/b.OWNER/'case'/'revision'/'attempt';work.mkdir(parents=True)
        blobs={'old.drawio':b'<mxfile>old</mxfile>','old.png':b'old-png','source.html':b'<html>source</html>','ref.png':b'original-image'}
        for name,data in blobs.items():(case/name).write_bytes(data)
        old={'id':'case','source_pair_sha256':'case','category':'poster','source_format':'html','code_file':'clean/case/old.drawio','code_sha256':b.sha(blobs['old.drawio']),
             'image_file':'clean/case/old.png','image_sha256':b.sha(blobs['old.png']),'original_source_code':'clean/case/source.html','source_code_sha256':b.sha(blobs['source.html']),
             'original_reference':'clean/case/ref.png','source_image_sha256':b.sha(blobs['ref.png'])}
        out={**old,'code_file':'clean/case/new.drawio','code_sha256':b.sha(b'<mxfile>new</mxfile>'),'image_file':'clean/case/new.png','image_sha256':b.sha(b'new-png'),
             'html_text_layout_prior_pair_archive':str((work/'baseline_archive').relative_to(root)),
             'quality_state':'pending_automatic_quality_v4_recheck','html_text_layout_v5':{'version':5},'native_font_validation':{'ok':True}}
        proof={'policy':RULE,'input_code_sha256':old['code_sha256'],'input_image_sha256':old['image_sha256'],'output_code_sha256':out['code_sha256'],'output_image_sha256':out['image_sha256'],
               'candidate_checks_passed':True,'accepted':False,'published':False,'changed_cells':['2']}
        (work/'candidate.drawio').write_bytes(b'<mxfile>new</mxfile>');(work/'candidate.png').write_bytes(b'new-png');(work/'candidate_record.json').write_text(json.dumps(out));(work/'evidence.json').write_text(json.dumps(proof))
        _,raw=add(self.db,record=old);(case/'conversion.json').write_text(raw+'\n\n');current=claim(self.db)
        report=b._summary(current,work,out,proof)
        return old,out,proof,current,report,work

    def test_validated_dry_run_is_terminal_for_build_and_explicit_publish_reuses_frozen_cache(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'R',Path(directory).resolve()):
            root=Path(directory).resolve();old,out,proof,current,report,work=self.fixture(root)
            finish(self.db,current,report,out,work,False)
            self.assertIsNone(select(self.db));self.assertIsNotNone(select(self.db,True))
            reused=claim(self.db,True)
            with patch.object(b,'ensure_implementation',return_value=None),patch('html_text_layout_candidate_batch_v5a.build',side_effect=AssertionError('must not rebuild')):
                _,again,summary=b.generate(reused,RULE,{})
            self.assertEqual(again,out);self.assertTrue(summary['builder_reused_from_validated_cache'])
            (work/'candidate.png').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):b._cached(reused)

    def test_cached_candidate_cannot_overwrite_new_human_metadata_at_same_xml_png_hash(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'R',Path(directory).resolve()):
            root=Path(directory).resolve();old,out,proof,current,report,work=self.fixture(root)
            finish(self.db,current,report,out,work,False)
            changed={**old,'root_review':{'source':'human','comment':'Keep this new review'}}
            self.db.execute('UPDATE jobs SET output_record=?',(json.dumps(changed),));self.db.commit()
            self.assertIsNone(claim(self.db,True))
            self.assertEqual(json.loads(b.snapshot(self.db,'case')[1])['root_review']['source'],'human')

    def publish_patches(self,root):
        return patch.multiple('harness_source_provenance',R=root),patch('html_text_layout_registration_v5.registration_record',side_effect=lambda *args:(args[0],None))

    @unittest.skipUnless(find_spec('pyarrow') is not None,'Full Harness filesystem test runs on HKUST')
    def test_versioned_pair_archives_old_pair_and_actual_harness_freeze_apis_still_work(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'R',Path(directory).resolve()):
            root=Path(directory).resolve();old,out,proof,current,report,work=self.fixture(root)
            provenance,registration=self.publish_patches(root)
            with provenance,registration:
                self.assertEqual(finish(self.db,current,report,out,work,True),'published_candidate')
                import harness_source_provenance as h
                session=root/'conversion/harness_sessions/next-test';session.mkdir(parents=True)
                frozen=h.freeze(out,session);self.assertEqual(h.validate_frozen(frozen)['code_sha256'],out['code_sha256'])
            self.assertEqual((root/old['code_file']).read_bytes(),b'<mxfile>old</mxfile>')
            self.assertEqual((root/old['image_file']).read_bytes(),b'old-png')
            self.assertEqual((root/out['code_file']).read_bytes(),b'<mxfile>new</mxfile>')
            self.assertEqual(json.loads((root/'clean/case/conversion.json').read_text()),out)
            self.assertEqual(json.loads((work/'baseline_archive/conversion.json').read_text()),old)

    @unittest.skipUnless(find_spec('pyarrow') is not None,'Full Harness filesystem test runs on HKUST')
    def test_filesystem_sql_failure_restores_exact_old_pointer_and_preserves_versioned_audit(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'R',Path(directory).resolve()):
            root=Path(directory).resolve();old,out,proof,current,report,work=self.fixture(root);pointer=root/'clean/case/conversion.json';before=pointer.read_bytes()
            provenance,registration=self.publish_patches(root)
            def interrupted(*args):b.publish_artifacts(*args);raise OSError('after pointer before SQL')
            with provenance,registration,self.assertRaises(OSError):finish(self.db,current,report,out,work,True,artifact_writer=interrupted)
            self.assertEqual(pointer.read_bytes(),before);self.assertEqual(b.snapshot(self.db,'case'),tuple(current['owned_snapshot']))
            self.assertEqual(self.db.execute('SELECT state,attempts FROM harness_queue_v3').fetchone(),('held_by_user_policy',7))
            self.assertTrue((root/out['code_file']).exists())

    def test_changed_source_or_registration_prevents_pointer_and_queue_publication(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'R',Path(directory).resolve()):
            root=Path(directory).resolve();old,out,proof,current,report,work=self.fixture(root);pointer=root/'clean/case/conversion.json';before=pointer.read_bytes()
            (root/old['original_source_code']).write_bytes(b'changed original')
            with self.assertRaises(ValueError):finish(self.db,current,report,out,work,True)
            self.assertEqual(pointer.read_bytes(),before)
            (root/old['original_source_code']).write_bytes(b'<html>source</html>')
            with patch('html_text_layout_registration_v5.registration_record',side_effect=AssertionError('proof changed')),self.assertRaises(AssertionError):finish(self.db,current,report,out,work,True)
            self.assertEqual(pointer.read_bytes(),before)

    @unittest.skipUnless(find_spec('pyarrow') is not None,'Full Harness filesystem test runs on HKUST')
    def test_sql_queue_abort_restores_exact_pointer_job_and_queue_history(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'R',Path(directory).resolve()):
            root=Path(directory).resolve();old,out,proof,current,report,work=self.fixture(root);pointer=root/'clean/case/conversion.json';before=pointer.read_bytes()
            self.db.execute("CREATE TRIGGER abort_queue BEFORE UPDATE ON harness_queue_v3 WHEN NEW.state='held_for_quality_v2' BEGIN SELECT RAISE(ABORT,'injected queue failure'); END");self.db.commit()
            queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();provenance,registration=self.publish_patches(root)
            with provenance,registration,self.assertRaises(sqlite3.IntegrityError):finish(self.db,current,report,out,work,True)
            self.assertEqual(pointer.read_bytes(),before);self.assertEqual(b.snapshot(self.db,'case'),tuple(current['owned_snapshot']))
            self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue)


if __name__=='__main__':unittest.main()
