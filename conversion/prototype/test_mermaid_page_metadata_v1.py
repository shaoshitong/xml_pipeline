import copy,json,sqlite3,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import mermaid_page_metadata_candidate_v1 as core
import mermaid_page_metadata_batch_v1 as batch
import test_clip_canvas_render_v4b as render_fixture
import test_bounded_program_terminal_planner_v1 as database_fixture

class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);clean=self.root/'clean/pair';clean.mkdir(parents=True);self.manifest=self.root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';self.manifest.parent.mkdir(parents=True);self.manifest.write_text('{}');self.xml='<mxfile><!-- 😀 <mxGraphModel fake="yes"> --><diagram><mxGraphModel tool="&gt;"  ><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" parent="1" vertex="1" value="x" style="shape=text;"><mxGeometry x="1" y="2" width="3" height="4" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>';self.id=core.sha(b'pair');self.record={'id':self.id,'source_pair_sha256':self.id,'source_format':'mermaid','category':'scientific_diagram','source':'sample'}
        for key,digest,name,blob in [('code_file','code_sha256','diagram.drawio',self.xml.encode()),('image_file','image_sha256','image.png',render_fixture.png()),('original_source_code','source_code_sha256','source.mmd',b'graph TD; A[x]'),('original_reference','source_image_sha256','source.png',render_fixture.png())]:
            path=clean/name;path.write_bytes(blob);self.record[key]=str(path.relative_to(self.root));self.record[digest]=core.sha(blob)
        self.native=render_fixture.native(self.manifest,strict=True);self.native['native_render']['translate']={'x':0,'y':0};self.record['render']=copy.deepcopy(self.native['native_render']);self.source={'pair_sha256':self.id,'source':'sample','format':'mermaid','category':'scientific_diagram','code_sha256':self.record['source_code_sha256'],'image_sha256':self.record['source_image_sha256']};self.counter=0
    def source_check(self,record,xml):return {'supported':True,'ok':True,'profile':'official_AST_fixture','failures':[],'evidence':{'source_semantic_check':{'status':'node_edge_text_match'}}}
    def run_case(self,old=None,new=None,record=None,source_check=None,resources=None,quality=None):
        self.counter+=1;work=self.root/'conversion'/('case'+str(self.counter));work.parent.mkdir(exist_ok=True);renderer=Mock(side_effect=[copy.deepcopy(old or self.native),copy.deepcopy(new or self.native)]);out,proof=core.generate(record or self.record,self.source,work,self.root,native_job=renderer,source_check=source_check or self.source_check,resources=resources or (lambda *a:{'verified_files':[],'verified_raster_cells':[]}),quality=quality or (lambda *a:{'ok':False,'failures':['old_local_text_failure']}),pins={});return out,proof,work,renderer
    def test_byte_preservation_handles_unicode_comments_quotes_and_all_other_xml(self):
        after,proof=core.add_page_metadata(self.xml,[20,10]);self.assertTrue(core.verify_metadata(self.xml,after,proof));self.assertIn('😀 <mxGraphModel fake=',after);self.assertIn('tool="&gt;"  ',after);self.assertTrue(proof['all_other_xml_bytes_unchanged']);self.assertEqual(core.model(after)[1].get('pageWidth'),'20')
        with self.assertRaises(core.Deferred):core.verify_metadata(self.xml,after.replace('width="3"','width="4"'),proof)
    def test_only_both_missing_single_native_page_and_bounded_dimensions(self):
        for xml,size in [(self.xml.replace('tool="&gt;"','pageWidth="20"'),[20,10]),(self.xml,[8192,8192]),(self.xml,[True,10]),(self.xml.replace('</diagram>','</diagram><diagram/>'),[20,10])]:
            with self.assertRaises(core.Deferred):core.add_page_metadata(xml,size)
    def test_crlf_and_utf8_bom_are_preserved_outside_exact_attribute_insertion(self):
        xml='\ufeff'+self.xml.replace('><','>\r\n<');after,proof=core.add_page_metadata(xml,[20,10]);self.assertTrue(core.verify_metadata(xml,after,proof));offset=proof['insertion_byte_offset'];length=len(proof['inserted_utf8'].encode());self.assertEqual(after.encode()[:offset]+after.encode()[offset+length:],xml.encode())
    def test_two_fresh_explicit_viewports_and_identical_signatures_are_required(self):
        out,proof,work,renderer=self.run_case();self.assertIsNotNone(out,proof);self.assertTrue(proof['candidate_checks_passed']);self.assertFalse(proof['accepted']);self.assertFalse(proof['original_quality_after']['ok']);self.assertEqual(renderer.call_count,2);self.assertEqual(renderer.call_args_list[0].args[1:3],(20,10));self.assertEqual(renderer.call_args_list[1].args[1:3],(20,10));self.assertEqual((work/'fresh_before.png').read_bytes(),(work/'candidate.png').read_bytes());self.assertEqual((work/'stored_baseline.png').read_bytes(),(self.root/self.record['image_file']).read_bytes())
    def test_stored_png_may_differ_while_fresh_before_and_after_match(self):
        different=copy.deepcopy(self.native);different['png']=render_fixture.png(20,10)+b'harmless trailing stored distinction';(self.root/self.record['image_file']).write_bytes(different['png']);self.record['image_sha256']=core.sha(different['png']);out,proof,work,_=self.run_case();self.assertIsNotNone(out,proof);self.assertFalse(proof['old_stored_png_equals_fresh']);self.assertEqual((work/'stored_baseline.png').read_bytes(),different['png'])
    def test_fresh_png_font_glyph_and_actual_text_changes_are_rejected(self):
        for mode in ('png','face','glyphs','text','style'):
            new=copy.deepcopy(self.native)
            if mode=='png':new['png']+=b'changed'
            elif mode=='face':new['native_render']['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='Other'
            elif mode=='glyphs':new['native_render']['actual_platform_font_usage'][0]['fonts'][0]['glyphCount']=2
            elif mode=='text':new['native_render']['actual_text_positions'][0]['runs'][0]['chars'][0]['x']+=1
            else:new['native_render']['actual_text_positions'][0]['runs'][0]['letterSpacing']='1px'
            out,proof,_,_=self.run_case(new=new);self.assertIsNone(out,mode);self.assertFalse(proof['candidate_checks_passed']);self.assertFalse(proof['accepted'])
    def test_outside_pixels_translation_or_fake_canvas_proof_are_rejected(self):
        for mode in ('outside','translate','probe','runtime'):
            new=copy.deepcopy(self.native);info=new['native_render']
            if mode=='outside':info['outside_page_pixel_audit']['nonwhite_outside_pixels']=1
            elif mode=='translate':info['translate']={'x':1,'y':0}
            elif mode=='probe':info['probe_includes_actual_dom_paint_bounds']=False
            else:info['runtime_cache_manifest_sha256']='a'*64
            out,proof,_,_=self.run_case(new=new);self.assertIsNone(out,mode);self.assertFalse(proof['candidate_checks_passed'])
    def test_old_incompatible_canvas_and_source_hash_are_explicit_deferred(self):
        for mode in ('translate','bounds','size','lineage','source'):
            old=copy.deepcopy(self.record)
            if mode=='translate':old['render']['translate']={'x':2,'y':0}
            elif mode=='bounds':old['render']['native_graph_bounds_outside_declared_canvas']=True
            elif mode=='size':old['render']['canvas']=[21,10]
            elif mode=='lineage':old['native_canvas_contract']={'offset':[1,0]}
            else:old['source_code_sha256']='a'*64
            out,proof,_,renderer=self.run_case(record=old);self.assertIsNone(out,mode);self.assertEqual(renderer.call_count,0);self.assertIn('defer_' if mode!='source' else 'identity',proof['error'])
    def test_ast_or_resource_failure_is_not_repaired_by_changing_page(self):
        check=lambda *a:{'supported':True,'ok':False,'profile':'official','failures':['lost edge'],'evidence':{}};out,proof,_,renderer=self.run_case(source_check=check);self.assertIsNone(out);self.assertEqual(renderer.call_count,0)
        resources=Mock(side_effect=[{'verified_files':['a']},{'verified_files':['b']}]);out,proof,_,renderer=self.run_case(resources=resources);self.assertIsNone(out);self.assertEqual(renderer.call_count,0)
    def test_reference_gate_regression_vs_stored_is_not_hidden_by_fresh_equality(self):
        quality=Mock(side_effect=[{'ok':False,'failures':['new']},{'ok':False,'failures':['new']},{'ok':True,'failures':[]}]);out,proof,_,_=self.run_case(quality=quality);self.assertIsNone(out);self.assertIn('regressed_versus_stored',proof['error'])

class LedgerTests(unittest.TestCase):
    def setUp(self):
        database_fixture.Guards.setUp(self);self.record['source_format']='mermaid';self.original['format']='mermaid';self.db.execute('update jobs set format=?,input_record=?,output_record=?',('mermaid',json.dumps(self.original),json.dumps(self.record)));self.db.execute('update processing_outcomes_v2 set format="mermaid"');self.db.commit();batch.initialize(self.db);self.policy='test:abc';self.audit={'records':[{'id':self.identifier,'code_sha256':self.record['code_sha256'],'image_sha256':self.record['image_sha256'],'source_image_sha256':self.record['source_image_sha256']}]};self.out={**self.record,'quality_state':'pending_QA4b','code_sha256':'c'*64,'image_sha256':'d'*64};self.proof={'candidate_checks_passed':True,'accepted':False,'output_code_sha256':'c'*64,'output_image_sha256':'d'*64}
    def claim(self,files=None,publish=False):return batch.claim(self.db,self.audit,self.policy,files or {},pid=77,root=self.root,publish=publish)
    def finish(self,current,out=None,publish=False,writer=None):return batch.finish(self.db,current,out,self.proof,self.root/'conversion/work',publish,self.root,artifact_writer=writer or (lambda *a:self.out))
    def test_claim_owns_full_job_and_dryrun_restores_exact_prior(self):
        prior=batch.snapshot(self.db,'jobs',self.identifier);current=self.claim();self.assertEqual(self.db.execute('select state,worker_pid from jobs').fetchone(),(batch.STATE,77));result=self.finish(current,self.out);self.assertEqual(result['state'],'validated_dry_run');self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),prior);self.assertIsNone(self.claim());self.assertIsNotNone(self.claim(publish=True))
    def test_each_three_model_queue_running_or_worker_owned_blocks_claim(self):
        for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
            if not batch.exists(self.db,table):self.db.execute('create table '+table+'(id,state,worker_pid)')
            for state,pid in [('running',None),('held',98)]:
                self.db.execute('insert into '+table+' values(?,?,?)',(self.identifier,state,pid));self.db.commit();self.assertIsNone(self.claim());self.db.execute('delete from '+table);self.db.commit()
    def test_outcome_qualified_abandoned_and_source_conflict_block_claim(self):
        for status in ('qualified','abandoned'):
            self.db.execute('update processing_outcomes_v2 set status=?',(status,));self.db.commit();self.assertIsNone(self.claim())
        self.db.execute("update processing_outcomes_v2 set status='pending',source_code_hash='wrong'");self.db.commit();self.assertIsNone(self.claim())
    def test_job_or_ledger_ownership_stolen_does_not_overwrite_other_actor(self):
        current=self.claim();self.db.execute("update jobs set error='other actor'");self.db.commit();before=batch.snapshot(self.db,'jobs',self.identifier);writer=Mock();result=self.finish(current,self.out,True,writer);self.assertEqual(result['state'],'stale_revision_or_ownership');self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),before);writer.assert_not_called()
    def test_stage_claim_token_stolen_is_preserved(self):
        current=self.claim();self.db.execute('update '+batch.TABLE+' set claim_token=?',('another-token',));self.db.commit();before=batch.snapshot(self.db,'jobs',self.identifier);result=self.finish(current,self.out,True,Mock());self.assertEqual(result['state'],'stale_revision_or_ownership');self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),before);self.assertEqual(self.db.execute('select claim_token,state from '+batch.TABLE).fetchone(),('another-token','running'))
    def test_qualified_outcome_during_generation_is_never_reopened(self):
        current=self.claim();self.db.execute("update processing_outcomes_v2 set status='qualified'");self.db.commit();result=self.finish(current,self.out,True,Mock());self.assertEqual(result['state'],'outcome_or_queue_snapshot_changed');self.assertEqual(self.db.execute('select status from processing_outcomes_v2').fetchone()[0],'qualified');self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['prior_job'])
    def test_model_started_during_render_restores_only_our_job(self):
        current=self.claim();self.db.execute('insert into harness_queue_v3 values(?,?,?)',(self.identifier,'running',None));self.db.commit();q=batch.queues(self.db,self.identifier);result=self.finish(current,self.out,True);self.assertEqual(result['state'],'deferred_model_running');self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['prior_job']);self.assertEqual(batch.queues(self.db,self.identifier),q)
    def test_queue_or_outcome_cas_change_during_render_prevents_publication(self):
        current=self.claim();self.db.execute('insert into harness_queue_v3 values(?,?,?)',(self.identifier,'held',None));self.db.commit();writer=Mock();result=self.finish(current,self.out,True,writer);self.assertEqual(result['state'],'outcome_or_queue_snapshot_changed');writer.assert_not_called();self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['prior_job'])
    def test_policy_pin_change_cleans_our_owned_job_without_publish(self):
        pin=self.root/'conversion/pin';pin.write_bytes(b'old');files={str(pin):batch.sha(pin.read_bytes())};current=self.claim(files);pin.write_bytes(b'new');writer=Mock();result=self.finish(current,self.out,True,writer);self.assertEqual(result['state'],'policy_changed_retained_prior');self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['prior_job']);writer.assert_not_called()
    def test_pending_publication_holds_idle_models_without_changing_outcome_or_history(self):
        self.db.execute('alter table harness_queue_v3 add column attempts');self.db.execute('alter table harness_queue_v3 add column priority');self.db.execute('insert into harness_queue_v3 values(?,?,?,?,?)',(self.identifier,'held_for_source_v5',None,2,99));self.db.commit();before_outcome=batch.snapshot(self.db,'processing_outcomes_v2',self.identifier);current=self.claim();result=self.finish(current,self.out,True);self.assertTrue(result['published']);self.assertFalse(result['accepted']);self.assertEqual(self.db.execute('select state,worker_pid from jobs').fetchone(),('needs_quality_repair',None));self.assertEqual(self.db.execute('select state,attempts,priority from harness_queue_v3').fetchone(),('held_for_quality_v2',2,99));self.assertEqual(batch.snapshot(self.db,'processing_outcomes_v2',self.identifier),before_outcome)
    def test_accepted_or_source_mutating_artifact_writer_cannot_publish(self):
        for mode in ('accepted','source'):
            current=self.claim(publish=True);bad=copy.deepcopy(self.out)
            if mode=='accepted':bad['quality_state']='accepted'
            else:bad['source_code_sha256']='wrong'
            with self.assertRaises(ValueError):self.finish(current,self.out,True,lambda *a:bad)
            self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['owned_job']);self.finish(current,None)
            self.db.execute('delete from '+batch.TABLE);self.db.commit()
    def test_sql_abort_rolls_back_pointer_and_queue_but_keeps_our_claim_for_safe_cleanup(self):
        current=self.claim();self.db.execute("create trigger stop_page_publication before update on jobs when NEW.output_record!=OLD.output_record begin select raise(ABORT,'test publication abort');end;");self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):self.finish(current,self.out,True)
        self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['owned_job']);self.assertEqual(self.db.execute('select state from '+batch.TABLE).fetchone()[0],'running');self.finish(current,None);self.assertEqual(batch.snapshot(self.db,'jobs',self.identifier),current['prior_job'])
    def test_control_drain_prevents_new_claim(self):
        (self.root/'conversion'/batch.CONTROL).write_text('{"drain":true}');self.assertIsNone(self.claim());self.assertEqual(self.db.execute('select worker_pid from jobs').fetchone()[0],None)

class ArtifactTests(unittest.TestCase):
    setUp=CandidateTests.setUp
    source_check=CandidateTests.source_check
    run_case=CandidateTests.run_case
    def case(self):
        self.record['native_font_validation']={'ok':True,'output_code_sha256':self.record['code_sha256'],'audit':'conversion/old_font_proof.json'};self.record['previous_candidate_archive']='conversion/harness_sessions/kept_unchanged';out,proof,work,_=self.run_case();self.assertIsNotNone(out,proof);current={'id':self.id,'policy':'page:test-policy','token':'claimtoken','prior_job':{'columns':['output_record','input_record'],'rows':[[json.dumps(self.record),json.dumps(self.source)]]}};return current,out,proof,work
    def publish(self,current,out,proof,work):
        with patch.dict(sys.modules,{'auto_quality_common_v4':types.SimpleNamespace(resource_checks=lambda *a:{})}):return batch.publish_artifacts(current,out,proof,work,self.root)
    def test_versioned_clean_pair_preserves_old_pair_source_and_harness_archive(self):
        current,out,proof,work=self.case();original=copy.deepcopy(out);old_xml=(self.root/self.record['code_file']).read_bytes();old_png=(self.root/self.record['image_file']).read_bytes();new=self.publish(current,out,proof,work);self.assertEqual(out,original);self.assertNotEqual(new['code_file'],self.record['code_file']);self.assertTrue(new['code_file'].startswith('clean/'));self.assertEqual((self.root/new['code_file']).read_text(),(work/'candidate.drawio').read_text());self.assertEqual((self.root/new['image_file']).read_bytes(),(work/'candidate.png').read_bytes());self.assertEqual((self.root/self.record['code_file']).read_bytes(),old_xml);self.assertEqual((self.root/self.record['image_file']).read_bytes(),old_png);self.assertEqual(new['previous_candidate_archive'],self.record['previous_candidate_archive']);archive=self.root/new['mermaid_page_metadata_prior_pair_archive'];self.assertEqual((archive/'image.png').read_bytes(),old_png);self.assertEqual((archive/'diagram.drawio').read_bytes(),old_xml);self.assertEqual(new['native_font_validation']['output_code_sha256'],new['code_sha256']);self.assertEqual(new['native_font_validation']['prior_validation'],self.record['native_font_validation']);self.assertEqual(core.sha((work/'proof.json').read_bytes()),new['mermaid_page_metadata_v1']['proof_sha256']);self.assertTrue(new['quality_state'].startswith('pending_'))
    def test_corrupt_candidate_or_proof_cannot_create_clean_versions(self):
        for mode in ('image','proof','record'):
            current,out,proof,work=self.case()
            if mode=='image':(work/'candidate.png').write_bytes(b'wrong')
            elif mode=='proof':(work/'proof.json').write_text('{}')
            else:(work/'candidate_record.json').write_text('{}')
            with self.assertRaises(ValueError):self.publish(current,out,proof,work)
            self.assertFalse((self.root/self.record['code_file']).parent.joinpath('mermaid_page_metadata_v1').exists())
    def test_repeated_artifact_commit_reuses_immutable_clean_files(self):
        current,out,proof,work=self.case();first=self.publish(current,out,proof,work);target=self.root/first['code_file'];inode=target.stat().st_ino;second=self.publish(current,out,proof,work);self.assertEqual(first,second);self.assertEqual(target.stat().st_ino,inode)
    def test_font_hash_is_not_advanced_without_verified_allcustom_evidence(self):
        current,out,proof,work=self.case();proof['all_current_fonts_custom']=False;(work/'proof.json').write_bytes(core.canonical(proof));new=self.publish(current,out,proof,work);self.assertEqual(new['native_font_validation'],self.record['native_font_validation'])

if __name__=='__main__':unittest.main()
