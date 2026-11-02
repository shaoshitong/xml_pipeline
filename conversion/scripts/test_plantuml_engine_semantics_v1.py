"""Source IR identities, real finite fullQA, and frozen control contracts."""
import copy,json,unittest,xml.etree.ElementTree as E
from pathlib import Path
import plantuml_engine_source_model_index_v1 as index
import compiler_plantuml_engine_iteration_case_v1 as case
import compiler_plantuml_engine_iteration_program_v1 as program
import compiler_plantuml_engine_iteration_batch_v1 as batch
W=index.W;R=index.R
class Family(unittest.TestCase):
 def setUp(self):
  self.model={'diagram_class':'net.sourceforge.plantuml.descdiagram.DescriptionDiagram','cuca_supported':True,'entities':[{'uid':'a','parent_uid':'g','is_group':False,'kind':'COMPONENT','hidden':False,'removed':False,'display':'[A]','name':'A'},{'uid':'b','parent_uid':'g','is_group':False,'kind':'DESCRIPTION','hidden':False,'removed':False,'display':'[B]','name':'B'}],'groups':[{'uid':'g','parent_uid':'root','is_group':True,'kind':'PACKAGE','hidden':False,'removed':False,'display':'[P]'}],'links':[{'uid':'x','entity1_uid':'a','entity2_uid':'b','decor1':'NONE','decor2':'ARROW','hidden':False,'removed':False,'invisible':False,'constraint':True,'inverted':False,'port1':None,'port2':None,'label':'[go]'}]}
 def key(self,m=None):return index.family_of_model(m or self.model)[0]
 def test_renamed_labels_and_aliases_same_family(self):
  m=copy.deepcopy(self.model)
  for e in m['entities']+m['groups']:e['uid']='alias_'+e['uid'];e['parent_uid']='alias_'+e['parent_uid'];e['name']='Other';e['display']='[Other words]'
  for e in m['links']:e['entity1_uid']='alias_'+e['entity1_uid'];e['entity2_uid']='alias_'+e['entity2_uid'];e['uid']='renamed';e['label']='[different words]'
  self.assertEqual(self.key(),self.key(m))
 def test_actual_parent_changes_family(self):
  m=copy.deepcopy(self.model);m['entities'][0]['parent_uid']='root';self.assertNotEqual(self.key(),self.key(m))
 def test_actual_endpoint_direction_changes_family(self):
  m=copy.deepcopy(self.model);m['links'][0]['entity1_uid']='b';m['links'][0]['entity2_uid']='a';self.assertNotEqual(self.key(),self.key(m))
 def test_hidden_layout_semantics_change_family(self):
  m=copy.deepcopy(self.model);m['links'][0]['invisible']=True;self.assertNotEqual(self.key(),self.key(m))
 def test_decorator_changes_family(self):
  m=copy.deepcopy(self.model);m['links'][0]['decor2']='COMPOSITION';self.assertNotEqual(self.key(),self.key(m))
 def test_named_port_presence_changes_family(self):
  m=copy.deepcopy(self.model);m['links'][0]['port1']='out';self.assertNotEqual(self.key(),self.key(m))
 def test_extra_actual_link_changes_family(self):
  m=copy.deepcopy(self.model);m['links'].append(copy.deepcopy(m['links'][0]));self.assertNotEqual(self.key(),self.key(m))
 def test_duplicate_entity_not_hidden(self):
  m=copy.deepcopy(self.model);m['entities'].append(copy.deepcopy(m['entities'][0]))
  with self.assertRaisesRegex(ValueError,'not_unique'):self.key(m)
 def test_dangling_engine_endpoint_not_guessed(self):
  m=copy.deepcopy(self.model);m['links'][0]['entity2_uid']='unknown'
  with self.assertRaisesRegex(ValueError,'endpoint_not_in'):self.key(m)
 def test_different_engine_diagram_is_other_family(self):
  m=copy.deepcopy(self.model);m['diagram_class']='net.sourceforge.plantuml.statediagram.StateDiagram';self.assertNotEqual(self.key(),self.key(m))
class ActualEvidence(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.report=json.loads((W/'plantuml_engine_reverify_v1/53b97d60c7dc4120a3eaaad593772d8d/report.json').read_bytes());cls.good=[r for r in cls.report['results'] if r['QA']['ok']]
 def test_actual_three_complete_positives(self):
  self.assertEqual({r['case']['name'] for r in self.good},{'styled_nested_description','regression05d','regression741d'})
  for r in self.good:case.full_quality(r['QA'],json.loads(Path(r['case']['record']).read_bytes()))
 def test_actual_hierarchy_and_hidden_relation_preserved(self):
  q=next(r['QA'] for r in self.good if r['case']['name']=='styled_nested_description');s=q['checks']['source']['evidence']['semantic_and_paint']['source_engine_semantics'];self.assertEqual((s['entities'],s['groups'],s['links'],s['invisible_layout_relations']),(3,2,2,1));self.assertFalse(s['geometry_used_to_infer_connections_or_parents'])
 def test_every_actual_semantic_entity_and_waypoints_move(self):
  for r in self.good:
   p=r['QA']['checks']['native_editing']['actual_every_engine_entity_container_and_owned_paint_editing'];self.assertTrue(p['actual_model_XML_exactly_restored']);self.assertGreater(p['entities_checked'],0)
   for d in p['details']:self.assertLessEqual(d['actual_owned_and_unowned_waypoint_translation_error_px'],.05)
 def test_whole_original_RGBA_and_uncropped_viewport(self):
  for r in self.good:
   p=r['QA']['checks']['source']['evidence']['fresh_source_proof'];self.assertTrue(p['whole_original_source_RGBA_exact']['ok']);v=p['source_viewport_independent_proof'];self.assertTrue(v['raw_default_and_fixed_viewport_all_primitive_screen_geometry_and_CSS_identical']);self.assertTrue(v['canonical_clipped_and_unclipped_pixels_equal']);self.assertFalse(v['reference_pixels_used_to_choose_viewport'])
 def test_all_actual_graphemes_keep_original_tolerance(self):
  for r in self.good:
   p=r['QA']['checks']['source']['evidence']['fresh_source_grapheme_layout'];self.assertEqual(p['position_tolerance_px'],.03)
   for d in p['details']:self.assertLessEqual(d['actual_grapheme_position_max_error_px'],.03)
 def test_class_state_visual_failures_remain_visible(self):
  failed=[r for r in self.report['results'] if r['case']['name'] in ('class_members','nested_state')];self.assertEqual(len(failed),2);self.assertTrue(all(not r['QA']['ok'] for r in failed))
 def test_scope_source_metadata_all_7463(self):
  m=json.loads(index.MANIFEST.read_bytes());self.assertEqual(m['source_rows'],7463);self.assertTrue(m['no_images_or_references_read']);self.assertEqual(m['errors'],[])
 def test_static_index_contains_all_source_engine_types(self):
  models=index._index();types={x['diagram_class'] for x in models.values()};self.assertIn('net.sourceforge.plantuml.activitydiagram3.ActivityDiagram3',types);self.assertNotIn('net.sourceforge.plantuml.activitydiagram3.ActivityDiagram3',index.SUPPORTED_TYPES)
 def test_runtime_control_paths_cannot_escape(self):
  with self.assertRaises(ValueError):batch.owned(R/'clean')
  with self.assertRaises(ValueError):program.owned(R/'clean')
if __name__=='__main__':unittest.main(verbosity=2)
