import copy,io,json,tempfile,unittest
import importlib,sys,types
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as E
from PIL import Image
import initial_native_canvas_recovery_v1 as recovery
import initial_conversion_supervisor_v1b as initial
import test_initial_conversion_supervisor_v1 as fixture

def png(size,color='white'):
    stream=io.BytesIO();Image.new('RGB',size,color).save(stream,format='PNG');return stream.getvalue()

class ContextTests(unittest.TestCase):
    add=fixture.StateTests.add
    claim=fixture.StateTests.claim
    def setUp(self):
        self.bind=patch.object(fixture,'b',initial);self.bind.start();fixture.StateTests.setUp(self);self.config={'root':str(self.root),'policy':recovery.POLICY+':fixture','pins':{}};self.patches2=[patch.object(recovery,'R',self.root),patch.object(recovery,'W',self.root/'conversion')]
        for p in self.patches2:p.start()
    def tearDown(self):
        for p in reversed(self.patches2):p.stop()
        fixture.StateTests.tearDown(self);self.bind.stop()
    def retained(self,reason='native_outside_reference_canvas_requires_registered_recovery'):
        self.add(stage='native');row=initial.snapshot(self.db,'case');source=json.loads(row[4]);manifest=json.loads(row[11]);reference=png((20,10));(self.root/manifest['reference_image']).write_bytes(reference);source['image_sha256']=initial.sha(reference);manifest['image_sha256']=source['image_sha256'];self.db.execute('UPDATE jobs SET input_record=?,input_manifest=?',(json.dumps(source),json.dumps(manifest)));self.db.execute('UPDATE processing_outcomes_v2 SET source_image_hash=?',(source['image_sha256'],));self.db.commit();current=self.claim(stage='native');work=self.root/initial.OWNER/'case/native'/current['token'];work.mkdir(parents=True);initial.make_request(current,work,{},180,8192)
        payloads={'source.tex':(self.root/manifest['source_code']).read_bytes(),'reference.bin':reference,'source.pdf':(self.root/json.loads(current['prior_execution'][2])['pdf_file']).read_bytes(),'source_render.svg':b'<svg/>','source_render.png':reference,'source_dom.json':b'{"objects":[]}', 'candidate.drawio':b'<mxfile><diagram><mxGraphModel pageWidth="20" pageHeight="10"><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>','candidate.png':png((23,12)),'native_render.json':b'{"selected_image":"complete_tight_graph","content_outside_declared_canvas":true,"output_size":[23,12]}'}
        for name,data in payloads.items():(work/name).write_bytes(data)
        result={'id':'case','stage':'native','code_sha256':current['key'][2],'image_sha256':current['key'][3],'stage_input_hash':current['key'][4],'ok':False,'reason':reason,'accepted':False,'model_calls':0};initial.atomic(work/'result.json',initial.raw_json(result));result['partial_artifact_inventory']=initial.partial_inventory(work);initial.finish(self.db,current,result,work,True);return current,work
    def test_complete_same_source_terminal_canvas_context_is_readonly(self):
        current,work=self.retained();changes=self.db.total_changes;before=initial.snapshot(self.db,'case');ctx=recovery.context(self.db,'case',self.config);self.assertEqual(ctx['claim_token'],current['token']);self.assertEqual(ctx['key'],current['key']);self.assertEqual(self.db.total_changes,changes);self.assertEqual(initial.snapshot(self.db,'case'),before);self.assertTrue(recovery.revalidate(self.db,ctx))
    def test_screenshot_runtime_and_larger_tier_are_not_canvas_class(self):
        for reason in ['typed_runtime_exception','larger_canvas_tier_required']:
            with self.subTest(reason=reason):
                current,work=self.retained(reason)
                with self.assertRaisesRegex(recovery.Retained,'not_canvas'):recovery.context(self.db,'case',self.config)
                self.db.execute('DELETE FROM jobs');self.db.execute('DELETE FROM processing_outcomes_v2');self.db.execute('DELETE FROM tikz_renders');self.db.execute('DELETE FROM harness_queue_v3');self.db.execute('DELETE FROM '+initial.TABLE);self.db.execute('DELETE FROM '+initial.RECOVERY);self.db.commit();import shutil;shutil.rmtree(self.root/'conversion/inputs/case')
    def test_accepted_or_qualified_or_busy_cases_are_refused(self):
        self.retained();row=initial.snapshot(self.db,'case')
        for field,value in [('state','accepted'),('worker_pid',9),('output_record','{}')]:
            self.db.execute('UPDATE jobs SET '+field+'=?',(value,));self.db.commit()
            with self.assertRaises(recovery.Retained):recovery.context(self.db,'case',self.config)
            initial._restore(self.db,row);self.db.commit()
        self.db.execute('UPDATE processing_outcomes_v2 SET status="qualified"');self.db.commit()
        with self.assertRaises(recovery.Retained):recovery.context(self.db,'case',self.config)
    def test_all_three_model_queue_generations_guard_paid_ownership(self):
        self.retained()
        for table in ['harness_queue','harness_queue_v2']:
            self.db.execute('CREATE TABLE '+table+'(id,state,worker_pid)');self.db.execute('INSERT INTO '+table+' VALUES("case","held",77)');self.db.commit()
            with self.assertRaises(recovery.Retained):recovery.context(self.db,'case',self.config)
            self.db.execute('DROP TABLE '+table);self.db.commit()
        self.db.execute('UPDATE harness_queue_v3 SET state="running"');self.db.commit()
        with self.assertRaises(recovery.Retained):recovery.context(self.db,'case',self.config)
    def test_source_pdf_or_terminal_nonce_change_refuses_original_partial(self):
        self.retained();self.db.execute('UPDATE '+initial.TABLE+' SET claim_token="changed"');self.db.commit()
        with self.assertRaises(recovery.Retained):recovery.context(self.db,'case',self.config)
    def test_missing_or_modified_raw_artifact_is_retained_not_reclassified(self):
        current,work=self.retained();(work/'candidate.drawio').write_bytes(b'tampered')
        with self.assertRaisesRegex(recovery.Retained,'hash_changed'):recovery.context(self.db,'case',self.config)
        self.assertEqual(initial.as_job(initial.snapshot(self.db,'case'))['state'],'initial_conversion_deferred_v1');self.assertEqual(self.db.execute('SELECT status FROM processing_outcomes_v2').fetchone()[0],'pending')
    def test_full_snapshot_cas_detects_new_pending_outcome_or_queue_revision(self):
        self.retained();ctx=recovery.context(self.db,'case',self.config);self.db.execute('UPDATE harness_queue_v3 SET priority=44');self.db.commit();self.assertFalse(recovery.revalidate(self.db,ctx))
    def test_source_asset_hash_is_checked_separately_from_raw_copy(self):
        self.retained();row=initial.snapshot(self.db,'case');manifest=json.loads(row[11]);(self.root/manifest['source_code']).write_bytes(b'new authoritative bytes')
        with self.assertRaisesRegex(recovery.Retained,'source_payload_changed'):recovery.context(self.db,'case',self.config)

class GeometryTests(unittest.TestCase):
    def setUp(self):
        try:importlib.import_module('native_padding_proof')
        except ModuleNotFoundError as error:
            if error.name!='pyarrow':raise
            dummy=types.ModuleType('native_worker');dummy.R=Path('/fixture');dummy.W=Path('/fixture/conversion');dummy.native=types.SimpleNamespace(__file__='/fixture/native.py')
            with patch.dict(sys.modules,{'native_worker':dummy}):pure=importlib.import_module('native_padding_proof')
            sys.modules['native_padding_proof']=pure
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.work=Path(self.temp.name);self.xml='<mxfile><diagram><mxGraphModel pageWidth="10" pageHeight="10"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="v" vertex="1" parent="1" style="fontStyle=1;fillColor=#000000;"><mxGeometry x="-1" y="3" width="1" height="1" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>';self.reference=png((10,10));self.mutate=None;self.after_outside=0;self.after_font='same';self.before_outside=1;self.dx_override=None
    def renderer(self,xml,width,height,directory):
        directory.mkdir(parents=True);candidate=directory.name=='candidate';graph=E.fromstring(xml).find('.//mxCell[@id="v"]/mxGeometry');x=int(graph.get('x'));y=int(graph.get('y'));padded=Image.new('RGB',(width+6,height+6),'white');padded.putpixel((x+3,y+3),(0,0,0));padded.putpixel((2+(2 if candidate and x==1 else 0)+3,2+3),(0,0,0));page=padded.crop((3,3,width+3,height+3));font=self.after_font if candidate else 'same'
        if candidate and self.mutate=='paint':padded.putpixel((5,5),(100,100,100))
        if candidate and self.mutate=='fake_zero':padded.putpixel((0,0),(254,255,255))
        if candidate and self.mutate=='page':page.putpixel((4,2),(254,254,254))
        padded.save(directory/'render.padded.png');page.save(directory/'render.stable_page.png');page.save(directory/'render.png');outside=self.after_outside if candidate else self.before_outside;info={'canvas':[width,height],'selected_image':'declared_first_page' if candidate or outside==0 else 'complete_tight_graph','output_size':[width,height],'content_outside_declared_canvas':bool(outside),'renderer_profile':'native_page_padding_strict_v1','renderer_module_sha256':'renderer','actual_platform_font_usage':[font],'outside_page_pixel_audit':{'offset':[3,3],'padded_native_render_size':[width+6,height+6],'white_threshold':255,'nonwhite_outside_pixels':outside},'page_capture_policy':'exact_fixture'};return (directory/'render.png').read_bytes(),info
    def test_integer_registration_preserves_full_original_page_and_complete_paint(self):
        out=recovery.registered_canvas(self.xml,self.reference,self.work/'proof',self.renderer);self.assertEqual(out['geometry']['translation'],[2,0]);self.assertEqual(out['geometry']['new_page'],[12,10]);self.assertEqual(out['after']['outside_page_pixel_audit']['nonwhite_outside_pixels'],0);self.assertTrue(out['exact_pixel_proof']['complete_same_view_native_paint_pixel_identical']);self.assertTrue(out['exact_pixel_proof']['original_page_actual_browser_export_pixel_identical']);self.assertTrue(out['reference_composition']['full_reference_pixels_preserved']);self.assertIn('fontStyle=1;',out['xml'])
    def test_changed_native_paint_is_rejected_even_with_fake_zero_outside_metadata(self):
        self.mutate='paint'
        with self.assertRaisesRegex(AssertionError,'Complete native paint changed'):recovery.registered_canvas(self.xml,self.reference,self.work/'proof',self.renderer)
    def test_original_page_pixel_change_is_rejected(self):
        self.mutate='page'
        with self.assertRaisesRegex(AssertionError,'Original page pixels changed'):recovery.registered_canvas(self.xml,self.reference,self.work/'proof',self.renderer)
    def test_changed_actual_physical_font_usage_is_rejected(self):
        self.after_font='different-face'
        with self.assertRaisesRegex(AssertionError,'physical fonts changed'):recovery.registered_canvas(self.xml,self.reference,self.work/'proof',self.renderer)
    def test_nonzero_strict_outside_is_rejected(self):
        self.after_outside=1
        with self.assertRaises(AssertionError):recovery.registered_canvas(self.xml,self.reference,self.work/'proof',self.renderer)
    def test_zero_outside_metadata_cannot_hide_one_rgb254_pixel(self):
        self.mutate='fake_zero'
        with self.assertRaisesRegex(recovery.Retained,'actual_padded_outside_count_differs'):recovery.registered_canvas(self.xml,self.reference,self.work/'proof',self.renderer)
    def test_explicit_page_mismatch_is_never_normalized_by_scaling(self):
        with self.assertRaisesRegex(AssertionError,'Explicit page size differs'):recovery.registered_canvas(self.xml,png((11,10)),self.work/'proof',self.renderer)
    def test_half_pixel_translation_cannot_pass_existing_transform_verifier(self):
        from auto_quality_canvas_repair import transform
        with self.assertRaises(AssertionError):transform(self.xml,(10,10),{'dx':.5,'dy':0,'width':11,'height':10})
    def test_large_union_remains_a_separate_bounded_tier(self):
        from auto_quality_canvas_repair import transform
        with self.assertRaisesRegex(AssertionError,'separate layout review'):transform(self.xml,(10,10),{'dx':40,'dy':0,'width':50,'height':10})

if __name__=='__main__':unittest.main()
