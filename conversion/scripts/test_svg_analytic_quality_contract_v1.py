import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import svg_analytic_iteration_controls_v1 as controls
import compiler_svg_scene_quality_ro_v8 as quality
import compiler_types_program_v1 as common
class SVGQualityContractTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve();clean=self.root/'clean';clean.mkdir();implementation=self.root/'implementation.py';implementation.write_bytes(b'pure fixture mechanism');self.pins={str(implementation):controls.sha(implementation.read_bytes())};self.configuration=dict(unit='unit',policy='current_SOURCE_core',pins=self.pins)
  self.record=dict(id='known_SOURCE',native_embedded_fonts=[])
  for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_png','source_render_png_sha256')]:
   p=clean/field;p.write_bytes(field.encode());self.record[field]=str(p.relative_to(self.root));self.record[digest]=controls.sha(p.read_bytes())
  sourcechecks={key:{'ok':True}for key in ('semantics','glyphs','physical_fonts','same_domain_pixels','source_primitive_pixels','actual_native_marker_geometry','complete_source_compositing_guard','actual_source_overlap_paint_order')}
  source=dict(ok=True,evidence=dict(complete_source_coverage=True,candidate_independent_source_scope=True,original_reference_gates_still_required=True,QA_source_session_owners_closed_before_next_observation=True,candidate_code_sha256=self.record['code_sha256'],checks=sourcechecks,fresh_sourceproof=dict(source_code_sha256=self.record['source_code_sha256'],source_image_sha256=self.record['source_image_sha256'],source_engine_png_sha256=self.record['source_render_png_sha256'],source_reference={'ok':True},cairo_browser_physical_font_equivalence={'ok':True},source_dom_extraction_preserved_all_pixels=True,candidate_independent=True,all_image_thresholds_unchanged=True,parameter_search=False,relayout=False)))
  visual=dict(ok=True,all_original_nonlocal_thresholds_unchanged=True,**{key:{'ok':True}for key in ('fresh_source_reference_all_original_gates','same_browser_domain_full_gates','all_source_primitive_full_gates','source_native_marker_contours')})
  edits=dict(ok=True,actual_marker_direction_edits=dict(ok=True,all_actual_editing=True,code_sha256=self.record['code_sha256']),all_endpoint_interventions={'moves':['actual fixture']})
  checks=dict(structure={},resources={},text_paint={},source=source,visual=visual,native_editing=edits,fonts={'all_rendered_fonts_embedded':True},render=dict(code_sha256=self.record['code_sha256'],image_sha256=self.record['image_sha256'],strict_outside_page_pixels=0,strict_clip_canvas_proof={'upstream_proof':True}))
  self.report=dict(version=quality.VERSION,id=self.record['id'],ok=True,canonical_mutations=0,model_calls=0,failures=[],implementation_pins=self.pins,quality_policy=quality.VERSION+':'+quality.sha(quality.canonical(self.pins))[:20],profile_policy=self.configuration['policy'],generation_configuration=self.configuration,generation_source_core=__import__('compiler_source_core_attempts_v3').core_identity(self.configuration),checks=checks)
  p=patch.object(common,'R',self.root);p.start();self.addCleanup(p.stop)
  p=patch.object(controls,'qa_configuration',return_value=self.configuration);p.start();self.addCleanup(p.stop)
 def validate(self):return controls.full_quality(self.report,self.record,self.configuration)
 def test_complete_synthetic_contract_is_accepted_without_rewriting_historical_metadata(self):self.assertTrue(self.validate())
 def test_all_eight_independent_stages_are_mandatory(self):
  del self.report['checks']['resources']
  with self.assertRaisesRegex(ValueError,'8_stage'):self.validate()
 def test_each_complete_SOURCE_native_semantic_gate_is_mandatory(self):
  original=copy.deepcopy(self.report)
  for key in original['checks']['source']['evidence']['checks']:
   self.report=copy.deepcopy(original);self.report['checks']['source']['evidence']['checks'][key]['ok']=False
   with self.assertRaisesRegex(ValueError,'SOURCE_native_gate'):self.validate()
 def test_original_reference_full_gates_cannot_be_replaced_by_same_domain(self):
  self.report['checks']['visual']['fresh_source_reference_all_original_gates']['ok']=False
  with self.assertRaisesRegex(ValueError,'original_reference_or_SOURCE_local'):self.validate()
 def test_actual_marker_edit_restore_is_required(self):
  self.report['checks']['native_editing']['actual_marker_direction_edits']['all_actual_editing']=False
  with self.assertRaisesRegex(ValueError,'actual_endpoint'):self.validate()
 def test_render_PNG_must_be_actual_candidate(self):
  self.report['checks']['render']['image_sha256']='changed'
  with self.assertRaisesRegex(ValueError,'fresh_render'):self.validate()
 def test_clean_SOURCE_engine_image_must_bind_fresh_original_SOURCE(self):
  self.report['checks']['source']['evidence']['fresh_sourceproof']['source_engine_png_sha256']='changed'
  with self.assertRaisesRegex(ValueError,'clean_SOURCE_render'):self.validate()
 def test_final_source_render_asset_cannot_be_under_work(self):
  p=self.root/'conversion/source.png';p.parent.mkdir();p.write_bytes(b'source_render_png');self.record['source_render_png']=str(p.relative_to(self.root))
  with self.assertRaises(Exception):self.validate()
 def test_current_SOURCE_configuration_policy_must_match(self):
  self.report['profile_policy']='older_profile'
  with self.assertRaisesRegex(ValueError,'current_complete_SOURCE_core'):self.validate()
 def test_original_SOURCE_DOM_extraction_must_preserve_all_paint(self):
  self.report['checks']['source']['evidence']['fresh_sourceproof']['source_dom_extraction_preserved_all_pixels']=False
  with self.assertRaisesRegex(ValueError,'fresh_SOURCE_reproduction'):self.validate()
 def test_RO8_cannot_relabel_a_different_generation_as_the_current_core(self):
  self.report['generation_configuration']=dict(self.configuration,policy='other_generation')
  with self.assertRaisesRegex(ValueError,'original_generation_core'):self.validate()
 def test_QA_only_policy_can_differ_without_changing_generation_identity(self):
  current_generation=copy.deepcopy(self.report['generation_source_core']);qa=dict(self.configuration,policy='QA_session_owner_extra_policy')
  self.report['profile_policy']=qa['policy']
  with patch.object(controls,'qa_configuration',return_value=qa):self.assertTrue(self.validate())
  self.assertEqual(self.report['generation_source_core'],current_generation)
 def test_historical_candidate_nested_policy_is_preserved_by_current_independent_QA(self):
  self.record['compiler_svg_scene_frontend_v7']={'historical_configuration':{'policy':'old_candidate_metadata'}}
  self.assertTrue(self.validate());self.assertEqual(self.record['compiler_svg_scene_frontend_v7']['historical_configuration']['policy'],'old_candidate_metadata')
if __name__=='__main__':unittest.main()
