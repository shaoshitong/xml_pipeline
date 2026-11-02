"""Isolated SQLite ownership/publication and runtime-font evidence corruptions."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
import auto_quality_html_repair_batch_v3 as batch
sha=lambda blob:hashlib.sha256(blob).hexdigest()
POLICY='isolated-test-policy'


def schema(db,model=True):
    db.execute('create table jobs(id text primary key,format text,state text,output_record text,worker_pid integer,error text,updated_at text,input_record text,input_manifest text)')
    db.execute('create table auto_quality_exceptions_v1(id text,code_hash text,image_hash text,policy text,route text,state text,reason text,updated_at text)')
    if model:db.execute('create table harness_queue_v3(id text primary key,state text,attempts int default 0,priority int default 0,worker_pid int,started_at text,heartbeat text,session_dir text,error text)')
    db.commit();batch.init(db)


def add_job(db,id='case',state='needs_quality_repair',fmt='html',category='poster',worker=None,exception_state='pending',route='source_geometry_or_harness',reason='source_coverage_failure: word_spans_multiple_lines',model_state='held_for_source_v5',record=None):
    out=record or {'id':id,'source_format':fmt,'category':category,'code_sha256':'old-code','image_sha256':'old-image','code_file':'clean/fixture/old.drawio','image_file':'clean/fixture/old.png'}
    raw=json.dumps(out);db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?)',(id,fmt,state,raw,worker,'prior-error','prior-time','input-json','prepared-json'))
    db.execute('insert into auto_quality_exceptions_v1 values(?,?,?,?,?,?,?,?)',(id,out['code_sha256'],out['image_sha256'],'old-qa',route,exception_state,reason,'prior-time'))
    if batch.exists(db,'harness_queue_v3') and model_state is not None:db.execute('insert into harness_queue_v3 values(?,?,?,?,?,?,?,?,?)',(id,model_state,7,42,None,'old-start','old-heart','old-session','old-model-error'))
    db.commit();return raw


class StateTests(unittest.TestCase):
    def test_current_source_exception_selection_only(self):
        db=sqlite3.connect(':memory:');schema(db)
        cases=[('accepted',{'state':'accepted'}),('busy',{'worker':123}),('chart',{'category':'chart'}),('wrong_format',{'fmt':'svg'}),('resolved_exception',{'exception_state':'resolved'}),('wrong_route',{'route':'deterministic_font_embedding'}),('metric_only',{'reason':'raster_anomaly: local_text_line_ssim_below_0.55'}),('paid_call',{'model_state':'running'}),('eligible',{})]
        for id,options in cases:add_job(db,id=id,**options)
        self.assertEqual(batch.select_candidate(db,POLICY)[0],'eligible')
        db.execute("update auto_quality_exceptions_v1 set code_hash='stale' where id='eligible'");db.commit();self.assertIsNone(batch.select_candidate(db,POLICY))
    def test_different_image_revision_is_not_selected(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db)
        db.execute("update auto_quality_exceptions_v1 set image_hash='old-other-image'");db.commit();self.assertIsNone(batch.select_candidate(db,POLICY))
    def test_claim_full_snapshot_compare_and_swap(self):
        for column,value in [('updated_at','new-time'),('error','changed-error'),('input_record','changed-input'),('input_manifest','changed-prepared'),('state','accepted'),('worker_pid',321)]:
            with self.subTest(column=column):
                db=sqlite3.connect(':memory:');schema(db);add_job(db);selected=batch.select_candidate(db,POLICY)
                db.execute('update jobs set '+column+'=? where id="case"',(value,));db.commit();self.assertIsNone(batch.claim(db,selected,POLICY,pid=111));db.close()
    def test_claim_does_not_take_new_running_paid_call(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db);selected=batch.select_candidate(db,POLICY)
        db.execute("update harness_queue_v3 set state='running'");db.commit();self.assertIsNone(batch.claim(db,selected,POLICY,pid=111))
    def test_only_one_competing_owner_can_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'state.sqlite';a=sqlite3.connect(file);schema(a);add_job(a);b=sqlite3.connect(file)
            first=batch.select_candidate(a,POLICY);second=batch.select_candidate(b,POLICY)
            self.assertIsNotNone(batch.claim(a,first,POLICY,pid=111));self.assertIsNone(batch.claim(b,second,POLICY,pid=222))
    def test_failure_restores_prior_state_record_and_model_queue(self):
        db=sqlite3.connect(':memory:');schema(db);raw=add_job(db,state='harness_review_pending');before=db.execute('select * from harness_queue_v3').fetchall();c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,pid=111)
        stage=batch.finish(db,c,{'error':'rejected source text','accepted':False})
        self.assertEqual(stage,'retained_prior_candidate');self.assertEqual(batch.snapshot(db,'case')[:4],('harness_review_pending',raw,None,'prior-error'));self.assertEqual(before,db.execute('select * from harness_queue_v3').fetchall())
    def test_running_paid_call_during_repair_is_deferred_and_untouched(self):
        db=sqlite3.connect(':memory:');schema(db);raw=add_job(db);c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,pid=111)
        db.execute("update harness_queue_v3 set state='running',worker_pid=888");db.commit();called=[]
        stage=batch.finish(db,c,{'accepted':False},{'fake':'candidate'},None,True,artifact_writer=lambda *args:called.append(args))
        self.assertEqual(stage,'deferred_model_running');self.assertFalse(called);self.assertEqual(batch.snapshot(db,'case')[1],raw);self.assertEqual(db.execute('select state,worker_pid,attempts,priority from harness_queue_v3').fetchone(),('running',888,7,42))
        self.assertIsNone(batch.select_candidate(db,POLICY,True))
        db.execute("update harness_queue_v3 set state='attempt_finished'");db.commit();self.assertIsNotNone(batch.select_candidate(db,POLICY,True))
    def test_changed_ownership_and_accepted_revision_are_never_overwritten(self):
        for update in ["state='accepted',worker_pid=NULL,output_record='new accepted record'","state='repair_running',worker_pid=999"]:
            with self.subTest(update=update):
                db=sqlite3.connect(':memory:');schema(db);add_job(db);c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,pid=111)
                db.execute('update jobs set '+update);db.commit();before=batch.snapshot(db,'case');called=[]
                self.assertEqual(batch.finish(db,c,{'accepted':False},{'fake':'candidate'},None,True,artifact_writer=lambda *args:called.append(args)),'stale_revision_or_ownership');self.assertFalse(called);self.assertEqual(before,batch.snapshot(db,'case'))
    def test_dry_run_can_be_explicitly_published_later(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db);c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,pid=111)
        self.assertEqual(batch.finish(db,c,{'accepted':False},{'fake':'candidate'},None,False),'validated_dry_run')
        self.assertIsNone(batch.select_candidate(db,POLICY,False));self.assertIsNotNone(batch.select_candidate(db,POLICY,True))
    def test_success_holds_model_without_changing_history_or_accepting(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db);c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,True,pid=111);out={'code_sha256':'new-code','image_sha256':'new-image'}
        stage=batch.finish(db,c,{'accepted':False,'requires_canvas_repair':True},out,None,True,artifact_writer=lambda *args:None)
        self.assertEqual(stage,'published_candidate');self.assertEqual(batch.snapshot(db,'case')[0],'needs_quality_repair');self.assertEqual(json.loads(batch.snapshot(db,'case')[1]),out)
        row=db.execute('select state,attempts,priority,started_at,session_dir,error from harness_queue_v3').fetchone();self.assertEqual(row,('held_for_quality_v2',7,42,'old-start','old-session','old-model-error'))
    def test_success_inserts_missing_idle_queue_entry(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db,model_state=None);c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,True,pid=111)
        batch.finish(db,c,{'accepted':False},{'code_sha256':'new'},None,True,artifact_writer=lambda *args:None)
        self.assertEqual(db.execute('select state,attempts,priority from harness_queue_v3').fetchone(),('held_for_quality_v2',0,1000))
    def test_writer_failure_rolls_back_publication_and_model_queue(self):
        db=sqlite3.connect(':memory:');schema(db);raw=add_job(db);c=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,True,pid=111);owned=batch.snapshot(db,'case');before=db.execute('select * from harness_queue_v3').fetchall()
        def reject(*args):raise OSError('synthetic disk failure')
        with self.assertRaises(OSError):batch.finish(db,c,{'accepted':False},{'code_sha256':'new'},None,True,artifact_writer=reject)
        self.assertEqual(batch.snapshot(db,'case'),owned);self.assertEqual(before,db.execute('select * from harness_queue_v3').fetchall())
        batch.finish(db,c,{'error':'synthetic disk failure','accepted':False});self.assertEqual(batch.snapshot(db,'case')[1],raw)


class FilesystemPublicationTests(unittest.TestCase):
    def fixture(self,root):
        case=root/'clean/case';case.mkdir(parents=True);work=root/'conversion/work';work.mkdir(parents=True)
        blobs={'old.drawio':b'<mxfile>old</mxfile>','old.png':b'old-native-png','source.html':b'<html>preserved source</html>','reference.png':b'original-reference'}
        for name,blob in blobs.items():(case/name).write_bytes(blob)
        old={'id':'case','source_pair_sha256':'case','source_format':'html','category':'poster','code_file':'clean/case/old.drawio','code_sha256':sha(blobs['old.drawio']),'image_file':'clean/case/old.png','image_sha256':sha(blobs['old.png']),'original_source_code':'clean/case/source.html','source_code_sha256':sha(blobs['source.html']),'original_reference':'clean/case/reference.png','source_image_sha256':sha(blobs['reference.png'])}
        out={**old,'code_file':'clean/case/versioned.drawio','code_sha256':sha(b'<mxfile>new</mxfile>'),'image_file':'clean/case/versioned.png','image_sha256':sha(b'new-native-png'),'source_coverage':{'ok':True},'native_font_validation':{'output_code_sha256':sha(b'<mxfile>new</mxfile>')},'quality_state':'pending_automatic_quality_v2_recheck','previous_candidate_archive':'conversion/harness_sessions/test/baseline'}
        (work/'candidate.drawio').write_bytes(b'<mxfile>new</mxfile>');(work/'candidate.png').write_bytes(b'new-native-png');(work/'candidate_record.json').write_text(json.dumps(out))
        report={'policy':POLICY,'candidate_checks_passed':True,'output_code_sha256':out['code_sha256'],'output_image_sha256':out['image_sha256'],'accepted':False}
        db=sqlite3.connect(':memory:');schema(db);raw=add_job(db,record=old);(case/'conversion.json').write_text(raw);claim=batch.claim(db,batch.select_candidate(db,POLICY),POLICY,True,pid=111)
        return db,old,out,report,claim,work,raw
    def test_real_versioned_files_and_archive_preserve_old_pair(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(batch,'R',Path(directory)):
            root=Path(directory);db,old,out,report,claim,work,raw=self.fixture(root)
            self.assertEqual(batch.finish(db,claim,report,out,work,True),'published_candidate')
            self.assertEqual((root/old['code_file']).read_bytes(),b'<mxfile>old</mxfile>')
            self.assertEqual((root/old['image_file']).read_bytes(),b'old-native-png')
            self.assertEqual((root/out['code_file']).read_bytes(),b'<mxfile>new</mxfile>')
            self.assertEqual((root/out['image_file']).read_bytes(),b'new-native-png')
            self.assertEqual((root/out['previous_candidate_archive']/'conversion.json').read_text(),raw)
            self.assertEqual(json.loads((root/'clean/case/conversion.json').read_text()),out)
            self.assertEqual(json.loads(batch.snapshot(db,'case')[1]),out);self.assertEqual(batch.snapshot(db,'case')[0],'needs_quality_repair')
    def test_metadata_pointer_restored_after_filesystem_sql_boundary_failure(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(batch,'R',Path(directory)):
            root=Path(directory);db,old,out,report,claim,work,raw=self.fixture(root)
            def interrupted(*args):batch.publish_artifacts(*args);raise OSError('interrupt after metadata replacement')
            with self.assertRaises(OSError):batch.finish(db,claim,report,out,work,True,artifact_writer=interrupted)
            self.assertEqual((root/'clean/case/conversion.json').read_text(),raw)
            self.assertEqual(batch.snapshot(db,'case')[1],raw)
            self.assertEqual(db.execute('select state,attempts from harness_queue_v3').fetchone(),('held_for_source_v5',7))
            batch.finish(db,claim,{'error':'interrupted','accepted':False})
            self.assertEqual(batch.snapshot(db,'case')[0],'needs_quality_repair')
    def test_changed_source_or_resource_hash_blocks_pointer_publication(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(batch,'R',Path(directory)):
            root=Path(directory);db,old,out,report,claim,work,raw=self.fixture(root)
            (root/old['original_source_code']).write_bytes(b'changed source')
            with self.assertRaises(ValueError):batch.finish(db,claim,report,out,work,True)
            self.assertEqual((root/'clean/case/conversion.json').read_text(),raw)
            self.assertEqual(db.execute('select state from harness_queue_v3').fetchone()[0],'held_for_source_v5')


class FontTests(unittest.TestCase):
    def fixture(self):
        old='<mxfile><mxCell id="2" vertex="1" value="Old" style="shape=text;fontFamily=Embedded;"/></mxfile>'
        new=old.replace('</mxfile>','<mxCell id="3" vertex="1" value="New" style="shape=text;fontFamily=Embedded;fontSize=18;"/></mxfile>')
        font={'postScriptName':'ArialPS','glyphCount':3,'isCustomFont':True}
        before={'actual_platform_font_usage':[{'cell':'2','fonts':[dict(font)]}]}
        after={'actual_platform_font_usage':[{'cell':'2','fonts':[dict(font)]},{'cell':'3','fonts':[dict(font)]}],'actual_text_positions':[{'cell':'3','runs':[{'chars':[{'text':x} for x in 'New']}]}]}
        common={'fontFamilyRaw':'Arial','bold':False,'italic':False,'underline':False,'fontSize':18};dom={'objects':[{**common,'id':1},{**common,'id':2,'text':'New','qaWrappedFragment':True}]};proposal={'new_editable_text_fragments':[{'cell':'3','font_donor_cell':'2'}]}
        return before,after,old,new,dom,proposal
    def test_actual_old_cell_and_css_matched_added_face_pass(self):
        result=batch.font_evidence(*self.fixture());self.assertTrue(result['ok']);self.assertEqual(result['original_text_cell_count'],1)
    def test_changed_original_physical_face_or_count_rejected(self):
        for key,value in [('postScriptName','WrongFace'),('glyphCount',2)]:
            args=list(self.fixture());args[1]=copy.deepcopy(args[1]);args[1]['actual_platform_font_usage'][0]['fonts'][0][key]=value
            with self.assertRaises(ValueError):batch.font_evidence(*args)
    def test_system_fallback_and_unproven_donor_face_rejected(self):
        for change in [{'isCustomFont':False},{'postScriptName':'DifferentCustomFace'}]:
            args=list(self.fixture());args[1]=copy.deepcopy(args[1]);args[1]['actual_platform_font_usage'][1]['fonts'][0].update(change)
            with self.assertRaises(ValueError):batch.font_evidence(*args)
    def test_changed_source_style_and_missing_rendered_characters_rejected(self):
        args=list(self.fixture());args[4]['objects'][1]['bold']=True
        with self.assertRaises(ValueError):batch.font_evidence(*args)
        args=list(self.fixture());args[1]['actual_text_positions'][0]['runs'][0]['chars'].pop()
        with self.assertRaises(ValueError):batch.font_evidence(*args)



class QA2SelectorTests(unittest.TestCase):
    def test_qa2_missing_wrapped_fragments_are_selected_without_legacy_alias(self):
        db=sqlite3.connect(':memory:');schema(db)
        reason='source_coverage_failure: [{"reason":"poster_object_coverage_mismatch","missing":["94","95"],"extra":[]},{"reason":"source_paint_object_missing","cell":"94"}]'
        add_job(db,reason=reason)
        selected=batch.select_candidate(db,POLICY)
        self.assertEqual(selected[0],'case')
        self.assertIsNotNone(batch.claim(db,selected,POLICY,pid=111))
    def test_qa2_paint_missing_only_alias_is_selected(self):
        db=sqlite3.connect(':memory:');schema(db)
        add_job(db,reason='source_coverage_failure: [{"reason":"source_paint_object_missing","cell":"319"}]')
        self.assertEqual(batch.select_candidate(db,POLICY)[0],'case')
    def test_previous_terminal_v2_pair_is_not_reprocessed_with_identical_helpers(self):
        for stage in ('running','published_candidate','retained_prior_candidate','no_change_required'):
            with self.subTest(stage=stage):
                db=sqlite3.connect(':memory:');schema(db);add_job(db)
                db.execute('create table '+batch.PRIOR_TABLE+'(id,code_hash,image_hash,state)')
                db.execute('insert into '+batch.PRIOR_TABLE+' values(?,?,?,?)',('case','old-code','old-image',stage));db.commit()
                self.assertIsNone(batch.select_candidate(db,POLICY))
                db.close()
    def test_v2_history_on_different_xml_or_image_does_not_hide_new_pair(self):
        for code,image in [('other-code','old-image'),('old-code','other-image')]:
            db=sqlite3.connect(':memory:');schema(db);add_job(db)
            db.execute('create table '+batch.PRIOR_TABLE+'(id,code_hash,image_hash,state)')
            db.execute('insert into '+batch.PRIOR_TABLE+' values(?,?,?,?)',('case',code,image,'retained_prior_candidate'));db.commit()
            self.assertEqual(batch.select_candidate(db,POLICY)[0],'case');db.close()
    def test_v2_claim_between_selection_and_claim_is_not_stolen(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db);selected=batch.select_candidate(db,POLICY)
        db.execute('create table '+batch.PRIOR_TABLE+'(id,code_hash,image_hash,state)')
        db.execute('insert into '+batch.PRIOR_TABLE+' values(?,?,?,?)',('case','old-code','old-image','running'));db.commit()
        self.assertIsNone(batch.claim(db,selected,POLICY,pid=111))
    def test_verified_stale_exception_cache_skips_heavy_snapshot(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db)
        db.execute('create table auto_quality_inventory_rows_v2(id,code_hash,image_hash,seen_version,seen_payload_version)')
        db.execute('create table auto_quality_dirty_v2(id,version,payload_version)')
        db.execute('insert into auto_quality_inventory_rows_v2 values("case","current-other-code","current-other-image",7,3)')
        db.execute('insert into auto_quality_dirty_v2 values("case",7,3)');db.commit()
        with patch.object(batch,'snapshot',side_effect=AssertionError('fat record should not be read for a known stale exception')):
            self.assertIsNone(batch.select_candidate(db,POLICY))
    def test_dirty_cache_falls_back_to_exact_current_snapshot(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db)
        db.execute('create table auto_quality_inventory_rows_v2(id,code_hash,image_hash,seen_version,seen_payload_version)')
        db.execute('create table auto_quality_dirty_v2(id,version,payload_version)')
        db.execute('insert into auto_quality_inventory_rows_v2 values("case","old-stale-code","old-stale-image",7,3)')
        db.execute('insert into auto_quality_dirty_v2 values("case",8,4)');db.commit()
        self.assertEqual(batch.select_candidate(db,POLICY)[0],'case')
    def test_selector_does_not_json_extract_all_font_heavy_job_payloads(self):
        db=sqlite3.connect(':memory:');schema(db);add_job(db);queries=[];db.set_trace_callback(queries.append)
        self.assertIsNotNone(batch.select_candidate(db,POLICY))
        self.assertFalse(any('json_extract' in query.lower() for query in queries))
    def test_new_alias_never_selects_accepted_busy_paid_or_stale_revision(self):
        reason='source_coverage_failure: poster_object_coverage_mismatch source_paint_object_missing'
        for label,kwargs in [('accepted',{'state':'accepted'}),('busy',{'worker':99}),('paid',{'model_state':'running'}),('not_poster',{'category':'chart'})]:
            with self.subTest(label=label):
                db=sqlite3.connect(':memory:');schema(db);add_job(db,reason=reason,**kwargs)
                self.assertIsNone(batch.select_candidate(db,POLICY));db.close()
        db=sqlite3.connect(':memory:');schema(db);add_job(db,reason=reason)
        db.execute("update auto_quality_exceptions_v1 set code_hash='old-other-code'");db.commit()
        self.assertIsNone(batch.select_candidate(db,POLICY))

if __name__=='__main__':unittest.main()
