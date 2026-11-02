"""Synthetic routing/interlock tests; no source, browser or real QA runs."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import compiler_quality_v2 as quality


class QualityInterlockTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compiler-quality-v2-test-');self.root=Path(self.temp.name).resolve()
        self.work=self.root/'conversion/compiler_v2/case';self.work.mkdir(parents=True)
        self.addCleanup(self.temp.cleanup);self.events=[];self.render_ok=True;self.domain_ok=True
        self.original_visual={'ok':True,'failures':[],'ssim_1024':.99}
        def old_source(*args):self.events.append('old_source');return dict(supported=True,ok=True,failures=[],evidence={})
        def old_text(*args):self.events.append('old_text');return {'ok':True}
        self.qa=SimpleNamespace(POLICY='unchanged_original_qa',profile=old_source,require_rendered_text=old_text,
                                source_baseline=lambda record,xml:(record,xml),ensure_pinned=lambda:None,
                                image_quality=lambda *args:dict(self.original_visual))
        def domain(record,xml,info,png,reference,work):
            self.events.append('independent_domain_'+record['compiler_quality_phase_v2'])
            self.assertTrue(info['actually_fresh'])
            self.assertTrue(work.is_relative_to(self.root/'conversion/compiler_render_domain_v3'))
            self.assertEqual(work.parts[-2:],('case','attempt_0'))
            return dict(supported=True,ok=self.domain_ok,failures=[] if self.domain_ok else ['native_source_pixel_loss'],source_replay_visual={'ok':self.domain_ok})
        def scene(*args):self.events.append('scene_v1');return dict(supported=True,ok=True,failures=[],evidence={})
        def setup(record,xml):
            self.events.append('text_setup')
            if not record.get('compiler_scene_text_v2'):return dict(supported=False,ok=False,failures=['missing_text_v2_proof'],evidence={})
            return dict(supported=True,ok=True,failures=[],evidence={'source_scene_v1':scene(record,xml)})
        def fresh(record,xml,info):
            self.events.append('fresh_text_check');self.assertTrue(info['actually_fresh'])
            self.assertEqual(record['_verified_reference_registration'],{'real_current':'registration'})
            return dict(supported=True,ok=self.render_ok,failures=[] if self.render_ok else ['glyph_offset_wrong'],evidence={'fresh':True})
        self.text=SimpleNamespace(validate=setup,validate_text_render=fresh)
        self.registration=SimpleNamespace(registration_record=lambda record,reference,xml:(record,None))
        def verify(item):
            record=json.loads(item[2]);record['_verified_reference_registration']={'real_current':'registration'}
            directory=self.work/'fake_qa';directory.mkdir(exist_ok=True)
            report=dict(policy=self.qa.POLICY,id='fixture',checks={},failures=[],state='repair_required')
            out=None
            try:
                report['checks']['source']=self.qa.profile(record,'synthetic xml','source')
                if not report['checks']['source']['ok']:raise ValueError('source_coverage_failure')
                self.events.append('fresh_render')
                report['checks']['text_paint']=self.qa.require_rendered_text('synthetic xml',{'actually_fresh':True})
                self.events.append('visual');report['checks']['visual']=self.qa.image_quality(b'reference',b'png',record,[])
                if not report['checks']['visual']['ok']:raise ValueError('raster_anomaly')
                out={'candidate':True};report['state']='qualified'
            except Exception as error:report['failures']=[str(error)];report['exception_type']=type(error).__name__
            return item,report,out,directory
        self.qa.verify=verify
        modules={'auto_quality_batch_v4b':self.qa,'clip_canvas_render_v4b':SimpleNamespace(OWNER=''),
                 'round2_font_canvas_registration_v1':self.registration,
                 'compiler_scene_v1':SimpleNamespace(validate=scene),'compiler_scene_text_v2':self.text,
                 'compiler_render_domain_v3':SimpleNamespace(check=domain),
                 'compiler_capture_snapshot_v1':SimpleNamespace(check_snapshot=lambda *args:None)}
        self.patches=[patch.dict(sys.modules,modules),patch.multiple(quality,R=self.root,W=self.root/'conversion'),
                      patch.object(quality,'configuration',return_value=dict(policy='v2_policy',bindings={'frozen':'test'}))]
        for item in self.patches:item.start()
        for item in reversed(self.patches):self.addCleanup(item.stop)

    def call(self,phase='candidate',proof=True):
        record={'compiler_quality_phase_v2':phase,'compiler_source_capture_snapshot':{}}
        if proof:record['compiler_scene_text_v2']={'proof':'synthetic'}
        return quality.verify(record,('fixture','unused','unused','unused','source','state','route'),self.work)

    def test_candidate_actual_fresh_text_check_precedes_visual_and_acceptance(self):
        report,out,_=self.call()
        self.assertIsNotNone(out);self.assertEqual(report['state'],'qualified')
        self.assertLess(self.events.index('old_text'),self.events.index('fresh_text_check'))
        self.assertLess(self.events.index('fresh_text_check'),self.events.index('visual'))
        self.assertTrue(report['checks']['compiler_text_render']['ok']);self.assertIn('scene_v1',self.events)
        self.assertTrue(report['checks']['compiler_render_domain']['ok'])

    def test_bad_actual_text_geometry_blocks_an_otherwise_passing_candidate(self):
        self.render_ok=False;report,out,_=self.call()
        self.assertIsNone(out);self.assertEqual(report['state'],'repair_required')
        self.assertFalse(report['checks']['compiler_text_render']['ok']);self.assertNotIn('visual',self.events)

    def test_candidate_without_new_proof_cannot_fall_back_to_old_checker(self):
        report,out,_=self.call(proof=False)
        self.assertIsNone(out);self.assertFalse(report['checks']['source']['ok'])
        self.assertNotIn('old_source',self.events);self.assertNotIn('fresh_render',self.events)

    def test_baseline_preserves_old_source_and_native_checks_without_new_proof(self):
        report,out,_=self.call(phase='baseline',proof=False)
        self.assertIsNotNone(out);self.assertEqual(report['state'],'qualified')
        self.assertIn('old_source',self.events);self.assertIn('old_text',self.events)
        self.assertNotIn('text_setup',self.events);self.assertNotIn('fresh_text_check',self.events)
        self.assertIn('independent_domain_baseline',self.events)

    def test_domain_failure_blocks_baseline_and_candidate_equally(self):
        self.domain_ok=False
        for phase in ('baseline','candidate'):
            with self.subTest(phase=phase):
                report,out,_=self.call(phase=phase)
                self.assertIsNone(out);self.assertFalse(report['checks']['compiler_render_domain']['ok'])

    def test_cross_renderer_local_failure_diagnostic_only_after_full_independent_pass(self):
        self.original_visual={'ok':False,'failures':['local_text_line_ssim_below_0.55'],'ssim_1024':.99}
        for phase in ('baseline','candidate'):
            with self.subTest(phase=phase):
                report,out,_=self.call(phase=phase)
                self.assertIsNotNone(out)
                self.assertFalse(report['checks']['visual']['original_reference_visual']['ok'])
                self.assertTrue(report['checks']['compiler_render_domain']['ok'])

    def test_global_tile_and_foreground_original_failures_are_never_waived(self):
        for failure in ('global_fidelity_below_0.90','foreground_tile_p10_below_0.72','foreground_coverage_below_0.90'):
            self.original_visual={'ok':False,'failures':['local_text_line_ssim_below_0.55',failure]}
            for phase in ('baseline','candidate'):
                with self.subTest(failure=failure,phase=phase):
                    report,out,_=self.call(phase=phase)
                    self.assertIsNone(out);self.assertIn(failure,report['checks']['visual']['failures'])

    def test_existing_canvas_and_new_span_compose_without_claiming_same_pixels(self):
        current_xml='<mxfile><mxGraphModel pageWidth="100" pageHeight="80"/></mxfile>'
        origin={'auto_quality_canvas_repair':{'proof':'old-origin'}}
        current={**origin,'compiler_quality_phase_v2':'candidate','compiler_scene_text_v2':{'proof':'new-text'}}
        contract=dict(output_page=[100,80],reference_page=[98,78],original_page_offset=[1,1],
                      font_only_delta_verified=True,same_renderer_font_delta_verified=True,current_revision_verified=True)
        def legacy(record,reference,xml):
            if xml==current_xml:raise AssertionError('current text is not the old canvas/font XML')
            self.assertEqual(xml,'before-text-xml');return record,contract
        self.registration.registration_record=legacy
        self.text.validate_registration_setup=lambda record,xml:dict(supported=True,ok=True,failures=[],evidence={'hash_bound':True},
                                                                     baseline_record=origin,baseline_xml='before-text-xml')
        registered,proof=quality.registration_record(current,b'reference',current_xml)
        self.assertEqual(proof['original_page_offset'],[1,1]);self.assertTrue(proof['source_derived_text_delta_verified'])
        self.assertNotIn('font_only_delta_verified',proof);self.assertNotIn('same_renderer_font_delta_verified',proof)
        self.assertIs(registered['_verified_reference_registration'],proof)

    def test_invalid_text_delta_cannot_reuse_a_valid_old_canvas_contract(self):
        self.registration.registration_record=lambda *args:(_ for _ in ()).throw(AssertionError('not current'))
        self.text.validate_registration_setup=lambda *args:dict(supported=False,ok=False,failures=['wrong delta'])
        with self.assertRaisesRegex(ValueError,'text_registration_setup_failed'):
            quality.registration_record({'compiler_scene_text_v2':{'proof':'bad'}},b'ref','bad-xml')


if __name__=='__main__':unittest.main(verbosity=2)
