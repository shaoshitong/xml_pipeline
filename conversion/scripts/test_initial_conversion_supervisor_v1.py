import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import initial_conversion_supervisor_v1 as b


def schema(db):
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,category TEXT,format TEXT,source TEXT,input_record TEXT,state TEXT,route TEXT,attempts INT,updated_at TEXT,output_record TEXT,error TEXT,input_manifest TEXT,worker_pid INT)')
    db.execute('CREATE TABLE processing_outcomes_v2(id TEXT PRIMARY KEY,category TEXT,format TEXT,source_code_hash TEXT,source_image_hash TEXT,status TEXT,reason TEXT,record TEXT,updated_at TEXT)')
    db.execute('CREATE TABLE tikz_renders(id TEXT PRIMARY KEY,state TEXT,record TEXT,error TEXT,updated_at TEXT)')
    db.execute('CREATE TABLE harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,attempts INT,priority INT,worker_pid INT,started_at TEXT,heartbeat TEXT,session_dir TEXT,error TEXT)');db.commit();b.init(db)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.patches=[patch.object(b,'R',self.root),patch.object(b,'W',self.root/'conversion'),patch.object(b,'birth',return_value=99)]
        for p in self.patches:p.start()
        self.db=sqlite3.connect(':memory:');schema(self.db);b.create_run(self.db,'run','policy-v1',False,{'compile':2,'native':2})
    def tearDown(self):
        self.db.close()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def add(self,id='case',stage='compile',outcome='pending',worker=None,output=None):
        directory=self.root/'conversion/inputs'/id;directory.mkdir(parents=True);code=b'Original TeX source';image=b'Original reference bytes';(directory/'source.txt').write_bytes(code);(directory/'reference.bin').write_bytes(image)
        source={'pair_sha256':id,'format':'tikz','source':'original-dataset','category':'scientific_diagram','code_sha256':b.sha(code),'image_sha256':b.sha(image)}
        manifest={'id':id,'source_format':'tikz','source_code':str((directory/'source.txt').relative_to(self.root)),'reference_image':str((directory/'reference.bin').relative_to(self.root)),'code_sha256':source['code_sha256'],'image_sha256':source['image_sha256'],'width':20,'height':10}
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,'scientific_diagram','tikz','original-dataset',json.dumps(source),b.INPUT_STATES[stage],stage,3,'original-time',json.dumps(output) if output is not None else None,'historical-error',json.dumps(manifest),worker))
        self.db.execute('INSERT INTO processing_outcomes_v2 VALUES(?,?,?,?,?,?,?,?,?)',(id,'scientific_diagram','tikz',source['code_sha256'],source['image_sha256'],outcome,None,None,'old-outcome'))
        self.db.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?,?,?,?)',(id,'held_by_user_patch_only_policy',7,9,None,'historic-start','historic-heart','historic-session','historic-error'))
        if stage=='native':
            pdf=directory/'source.pdf';pdf.write_bytes(b'%PDF-1.7 compiled');execution={'id':id,'source_code_sha256':source['code_sha256'],'pdf_sha256':b.sha(pdf.read_bytes()),'pdf_file':str(pdf.relative_to(self.root)),'pages':1,'directory':str(directory.relative_to(self.root))};self.db.execute('INSERT INTO tikz_renders VALUES(?,?,?,?,?)',(id,'tikz_source_rendered',json.dumps(execution),None,'old-execution'))
        self.db.commit();return b.snapshot(self.db,id)
    def claim(self,id='case',stage='compile',run='run',policy='policy-v1'):
        return b.claim(self.db,b.snapshot(self.db,id),stage,run,policy,pid=111,pid_start=99)
    def result(self,current,ok=False):
        result={'id':current['id'],'stage':current['stage'],'code_sha256':current['key'][2],'image_sha256':current['key'][3],'stage_input_hash':current['key'][4],'ok':ok,'reason':'whole_case_deadline_requires_recovery_tier','accepted':False,'model_calls':0}
        work=self.root/b.OWNER/current['id']/current['stage']/current['token'];work.mkdir(parents=True,exist_ok=True)
        if not ok:return work,result
        if current['stage']=='compile':
            pdf=work/'source.pdf';pdf.write_bytes(b'%PDF-1.7 new');record={'id':current['id'],'source_code_sha256':current['key'][2],'source_image_sha256':current['key'][3],'pdf_file':str(pdf.relative_to(self.root)),'pdf_sha256':b.sha(pdf.read_bytes()),'pages':1,'directory':str(work.relative_to(self.root))};recordfile=work/'preparation.json';recordfile.write_bytes(b.raw_json(record));result.update(state='compile_ready',record=record,record_file={'file':str(recordfile.relative_to(self.root)),'sha256':b.sha(recordfile.read_bytes())},artifacts={'pdf':{'file':str(pdf.relative_to(self.root)),'sha256':record['pdf_sha256']}})
        else:
            source=json.loads(current['prior_snapshot'][4]);manifest=json.loads(current['prior_snapshot'][11]);dest=Path('clean/drawio_unified')/current['id'][:2]/current['id'];blobs={'candidate.drawio':b'<mxfile>native</mxfile>','candidate.png':b'new native PNG','source.tex':(self.root/manifest['source_code']).read_bytes(),'reference.bin':(self.root/manifest['reference_image']).read_bytes(),'source.pdf':(self.root/json.loads(current['prior_execution'][2])['pdf_file']).read_bytes(),'source.svg':b'<svg>source</svg>'}
            files={};mapping={}
            for name,data in blobs.items():
                path=work/name;path.write_bytes(data);entry={'file':str(path.relative_to(self.root)),'sha256':b.sha(data)};files[name]=entry;mapping[str(dest/('versioned-'+name))]=entry
            record={'id':current['id'],'source_pair_sha256':current['id'],'source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],'code_file':str(dest/'versioned-candidate.drawio'),'code_sha256':b.sha(blobs['candidate.drawio']),'image_file':str(dest/'versioned-candidate.png'),'image_sha256':b.sha(blobs['candidate.png']),'original_source_code':str(dest/'versioned-source.tex'),'original_reference':str(dest/'versioned-reference.bin'),'source_format':'tikz','format':'drawio','source_record':source,'source_render_pdf':str(dest/'versioned-source.pdf'),'source_render_pdf_sha256':b.sha(blobs['source.pdf']),'source_render_svg':str(dest/'versioned-source.svg'),'source_render_svg_sha256':b.sha(blobs['source.svg']),'model':None,'quality_state':'pending_source_semantic_and_visual_validation'}
            file=work/'candidate_record.json';file.write_bytes(b.raw_json(record));result.update(state='native_ready',record=record,record_file={'file':str(file.relative_to(self.root)),'sha256':b.sha(file.read_bytes())},publish_files=mapping,artifacts=files,requires_quality_repair=True)
        return work,result
    def test_initial_format_state_source_outcome_and_empty_output_admission(self):
        self.add();self.assertIsNotNone(b.select_candidate(self.db,'run','compile'))
        for field,value in [('format','html'),('state','accepted'),('worker_pid',5),('output_record','{}'),('input_manifest',None),('source','other-source'),('category','poster')]:
            before=b.snapshot(self.db,'case');self.db.execute('UPDATE jobs SET '+field+'=?',(value,));self.db.commit();self.assertIsNone(b.select_candidate(self.db,'run','compile'));b._restore(self.db,before);self.db.commit()
        self.db.execute("UPDATE processing_outcomes_v2 SET status='abandoned'");self.db.commit();self.assertIsNone(b.select_candidate(self.db,'run','compile'))
    def test_all_model_generations_and_nonrunning_worker_ownership_guarded(self):
        self.add()
        for table in ['harness_queue','harness_queue_v2']:
            self.db.execute('CREATE TABLE '+table+'(id TEXT,state TEXT)');self.db.execute('INSERT INTO '+table+' VALUES("case","running")');self.db.commit();self.assertIsNone(b.select_candidate(self.db,'run','compile'));self.db.execute('DROP TABLE '+table);self.db.commit()
        self.db.execute('UPDATE harness_queue_v3 SET worker_pid=9');self.db.commit();self.assertIsNone(b.select_candidate(self.db,'run','compile'))
    def test_every_job_column_is_compared_at_claim_and_changed_registry_source_blocks(self):
        prior=self.add()
        for index,field in enumerate(b.JOB_COLUMNS[1:],1):
            self.db.execute('UPDATE jobs SET '+field+'=?',('changed' if field not in ['attempts','worker_pid'] else 8,));self.db.commit();self.assertIsNone(b.claim(self.db,prior,'compile','run','policy-v1',111,99));b._restore(self.db,prior);self.db.commit()
        self.db.execute("UPDATE processing_outcomes_v2 SET source_image_hash='foreign'");self.db.commit();self.assertIsNone(b.claim(self.db,prior,'compile','run','policy-v1',111,99))
    def test_unknown_jobs_columns_fail_closed_instead_of_partial_cas(self):
        self.db.execute('ALTER TABLE jobs ADD COLUMN future_revision TEXT');self.db.commit()
        with self.assertRaises(RuntimeError):b.init(self.db)
    def test_shared_quota_and_duplicate_claim_are_atomic_across_owners(self):
        self.add();selection=b.select_candidate(self.db,'run','compile');one=self.claim();self.assertIsNotNone(one);self.assertIsNone(b.claim(self.db,selection,'compile','run','policy-v1',222,99));self.assertEqual(self.db.execute('SELECT claimed FROM '+b.RUNS+' WHERE stage="compile"').fetchone()[0],1)
    def test_two_independent_connections_cannot_claim_one_source_revision_or_double_count_quota(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        path=self.root/'race.sqlite';a=sqlite3.connect(path);schema(a);a.close();old=self.db;self.db=sqlite3.connect(path);self.add();b.create_run(self.db,'race','policy-v1',True,{'compile':1,'native':1});prior=b.snapshot(self.db,'case');self.db.close();self.db=old;barrier=threading.Barrier(2)
        def compete(pid):
            db=sqlite3.connect(path,timeout=5);barrier.wait();result=b.claim(db,prior,'compile','race','policy-v1',pid,99);db.close();return result
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,[111,222]))
        self.assertEqual(sum(result is not None for result in results),1);db=sqlite3.connect(path);self.assertEqual(db.execute('SELECT claimed FROM '+b.RUNS+' WHERE stage="compile"').fetchone()[0],1);self.assertEqual(db.execute('SELECT count(*) FROM '+b.TABLE).fetchone()[0],1);db.close()

    def test_logical_stage_terminal_survives_new_policy_and_run(self):
        self.add();current=self.claim();work,result=self.result(current);b.finish(self.db,current,result,work)
        b.create_run(self.db,'new-run','changed-version',False,{'compile':2,'native':2});self.db.execute('UPDATE jobs SET state="queued",worker_pid=NULL');self.db.commit();self.assertIsNone(b.select_candidate(self.db,'new-run','compile'))
    def test_native_key_binds_exact_compiled_pdf_and_registry_source(self):
        self.add(stage='native');current=self.claim(stage='native');self.assertEqual(current['key'][4],json.loads(current['prior_execution'][2])['pdf_sha256'])
        work,result=self.result(current);self.db.execute("UPDATE tikz_renders SET updated_at='foreign'");self.db.commit();self.assertEqual(b.finish(self.db,current,result,work)['state'],'stale_revision')
    def test_deadline_preserves_inputs_and_routes_recovery_without_abandon_or_model_queue_change(self):
        prior=self.add();queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();current=self.claim();work,result=self.result(current);report=b.finish(self.db,current,result,work)
        self.assertEqual(report['state'],'deferred_recovery_tier');self.assertTrue(report['larger_or_recovery_tier_required']);job=b.as_job(b.snapshot(self.db,'case'));self.assertEqual(job['state'],'initial_conversion_deferred_v1');self.assertIsNone(job['worker_pid']);self.assertEqual(job['input_record'],prior[4]);self.assertEqual(job['input_manifest'],prior[11]);self.assertIsNone(job['output_record']);self.assertEqual(self.db.execute('SELECT status FROM processing_outcomes_v2').fetchone()[0],'pending');self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue);self.assertEqual(self.db.execute('SELECT count(*) FROM '+b.RECOVERY).fetchone()[0],1)
    def test_nonpublishing_compile_and_native_restore_exact_snapshot_and_write_no_clean_files(self):
        for stage,id in [('compile','compile-case'),('native','native-case')]:
            prior=self.add(id=id,stage=stage);current=self.claim(id,stage);work,result=self.result(current,True);report=b.finish(self.db,current,result,work,False);self.assertEqual(report['state'],'validated_nonpublishing');self.assertEqual(b.snapshot(self.db,id),prior)
        self.assertFalse((self.root/'clean').exists())
    def test_compile_publish_only_feeds_pending_native_and_keeps_outcome_and_queue(self):
        self.add();current=self.claim();work,result=self.result(current,True);before=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();report=b.finish(self.db,current,result,work,True);self.assertEqual(report['state'],'published_pending_native');self.assertEqual(b.as_job(b.snapshot(self.db,'case'))['state'],'tikz_source_rendered');self.assertIsNone(b.as_job(b.snapshot(self.db,'case'))['output_record']);self.assertEqual(json.loads(b.execution_snapshot(self.db,'case')[2])['pdf_sha256'],result['record']['pdf_sha256']);self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),before)
    def test_native_publish_uses_immutable_paths_and_never_accepts_or_changes_models(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);before=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();report=b.finish(self.db,current,result,work,True);self.assertEqual(report['state'],'published_pending_quality');self.assertFalse(report['accepted']);self.assertEqual(b.as_job(b.snapshot(self.db,'case'))['state'],'needs_quality_repair');self.assertEqual(self.db.execute('SELECT status FROM processing_outcomes_v2').fetchone()[0],'pending');self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),before);self.assertEqual(json.loads(b.pointer_path('case').read_text()),result['record'])
    def test_stolen_job_or_owner_token_and_pid_reuse_never_overwrite(self):
        self.add();current=self.claim();work,result=self.result(current)
        self.db.execute("UPDATE jobs SET error='human change'");self.db.commit();saved=b.snapshot(self.db,'case');self.assertEqual(b.finish(self.db,current,result,work)['state'],'stale_revision');self.assertEqual(b.snapshot(self.db,'case'),saved)
        self.db.execute('UPDATE '+b.TABLE+' SET state="running",claim_token="foreign"');b._restore(self.db,tuple(current['owned_snapshot']));self.db.commit();ledger=self.db.execute('SELECT * FROM '+b.TABLE).fetchone();self.assertEqual(b.finish(self.db,current,result,work)['state'],'stale_revision');self.assertEqual(self.db.execute('SELECT * FROM '+b.TABLE).fetchone(),ledger)
    def test_current_worker_birth_must_still_match_before_publication(self):
        self.add();current=self.claim();work,result=self.result(current,True);owned=b.snapshot(self.db,'case')
        with patch.object(b,'birth',return_value=100):self.assertEqual(b.finish(self.db,current,result,work,True)['state'],'stale_revision')
        self.assertEqual(b.snapshot(self.db,'case'),owned)
    def test_model_owner_or_terminal_outcome_change_between_claim_and_publish_blocks(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True)
        self.db.execute('UPDATE harness_queue_v3 SET worker_pid=66');self.db.commit();queue=self.db.execute('SELECT * FROM harness_queue_v3').fetchone();self.assertEqual(b.finish(self.db,current,result,work,True)['state'],'stale_revision');self.assertEqual(self.db.execute('SELECT * FROM harness_queue_v3').fetchone(),queue);self.assertFalse(b.pointer_path('case').exists())
    def test_changed_human_metadata_file_at_same_sql_snapshot_is_not_overwritten(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);pointer=b.pointer_path('case');pointer.parent.mkdir(parents=True);pointer.write_bytes(b'new human metadata')
        self.assertEqual(b.finish(self.db,current,result,work,True)['state'],'stale_revision');self.assertEqual(pointer.read_bytes(),b'new human metadata')
    def test_source_and_artifact_tampering_or_outside_owned_locator_rejects_success(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);(work/'candidate.drawio').write_bytes(b'tampered')
        with self.assertRaises(ValueError):b.finish(self.db,current,result,work,True)
        manifest=json.loads(current['prior_snapshot'][11]);(self.root/manifest['source_code']).write_bytes(b'changed source')
        with self.assertRaises(ValueError):b.finish(self.db,current,result,work,True)
    def test_fs_after_pointer_or_sql_failure_restores_exact_metadata_and_owned_sql(self):
        self.add(stage='native');pointer=b.pointer_path('case');pointer.parent.mkdir(parents=True);before=b'old partial metadata\n\n';pointer.write_bytes(before);current=self.claim(stage='native');work,result=self.result(current,True);owned=b.snapshot(self.db,'case')
        def failing(*args):b.publish_native(*args);raise OSError('after filesystem before SQL')
        with self.assertRaises(OSError):b.finish(self.db,current,result,work,True,artifact_writer=failing)
        self.assertEqual(pointer.read_bytes(),before);self.assertEqual(b.snapshot(self.db,'case'),owned);self.assertTrue((self.root/result['record']['code_file']).exists())
        self.db.execute("CREATE TRIGGER fail_jobs BEFORE UPDATE ON jobs WHEN NEW.state='needs_quality_repair' BEGIN SELECT RAISE(ABORT,'injected'); END");self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):b.finish(self.db,current,result,work,True)
        self.assertEqual(pointer.read_bytes(),before);self.assertEqual(b.snapshot(self.db,'case'),owned)
    def test_publication_deadline_retains_proposal_for_recovery_not_accepted(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);report=b.finish(self.db,current,result,work,True,deadline=time.monotonic()-1);self.assertEqual(report['state'],'deferred_recovery_tier');self.assertTrue(report['prepared_proposal_retained']);self.assertFalse(b.pointer_path('case').exists())
    def test_deadline_after_fs_write_rolls_back_before_any_sql_commit(self):
        self.add(stage='native');current=self.claim(stage='native');work,result=self.result(current,True);owned=b.snapshot(self.db,'case');deadline=time.monotonic()+.01
        def slow(*args):b.publish_native(*args);time.sleep(.03)
        with self.assertRaises(TimeoutError):b.finish(self.db,current,result,work,True,artifact_writer=slow,deadline=deadline)
        self.assertEqual(b.snapshot(self.db,'case'),owned);self.assertFalse(b.pointer_path('case').exists())
    def test_launcher_owner_revision_is_bound_at_claim_and_before_publication(self):
        self.add();owner={'run_id':'run','policy':'policy-v1','pid':222,'pid_start_ticks':99};file=self.root/'launcher_owner.json';file.write_bytes(b.raw_json(owner));context={'file':str(file),'sha256':b.sha(file.read_bytes()),**owner};current=b.claim(self.db,b.snapshot(self.db,'case'),'compile','run','policy-v1',111,99,owner_context=context);self.assertIsNotNone(current);work,result=self.result(current,True)
        file.write_bytes(b.raw_json({**owner,'run_id':'another-run'}));self.assertEqual(b.finish(self.db,current,result,work,True)['state'],'stale_revision');self.assertIsNone(b.execution_snapshot(self.db,'case'))
        self.db.execute('DELETE FROM '+b.TABLE);self.db.commit();self.assertIsNone(b.claim(self.db,b.snapshot(self.db,'case'),'compile','run','policy-v1',111,99,owner_context=context))

    def test_partial_artifacts_are_preserved_and_hash_bound_for_recovery(self):
        work=self.root/b.OWNER/'partial';work.mkdir(parents=True);(work/'source.tex').write_bytes(b'partial source');(work/'candidate.png').write_bytes(b'partial PNG');entry=b.partial_inventory(work);data=json.loads((self.root/entry['file']).read_text());self.assertFalse(data['artifacts_deleted']);self.assertEqual(len(data['files']),2);self.assertEqual((work/'source.tex').read_bytes(),b'partial source');self.assertTrue(all(row['sha256'] for row in data['files']))

    def test_drain_control_stops_new_cases_and_invalid_control_fails_closed(self):
        control=self.root/'control.json';self.assertFalse(b.draining(control));control.write_text('[]');self.assertTrue(b.draining(control));control.write_text('{"drain":true}');self.assertTrue(b.draining(control));control.write_text('{"drain":false}');self.assertFalse(b.draining(control))

    def test_private_bootstrap_opens_canonical_ro_without_canonical_claim_or_owner_table(self):
        path=self.root/'canonical.sqlite';a=sqlite3.connect(path);schema(a);a.close();old=self.db;self.db=sqlite3.connect(path);self.add('c',stage='compile');self.add('n',stage='native');self.db.close();self.db=old
        reader=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);before=reader.execute('SELECT * FROM jobs ORDER BY id').fetchall();reader.close();private=self.root/'private.sqlite';report=b.bootstrap_private(path,private,{'compile':1,'native':1});self.assertTrue(report['canonical_opened_read_only']);self.assertEqual(report['canonical_input_format_counts'],{'tikz':2});reader=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);self.assertEqual(reader.execute('SELECT * FROM jobs ORDER BY id').fetchall(),before);reader.close();db=sqlite3.connect(private);self.assertFalse(b.exists(db,b.TABLE));self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],2);db.close()


if __name__=='__main__':unittest.main()
