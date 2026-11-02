import copy,json,unittest
from pathlib import Path
import compiler_html_paragraph_controls_v9 as controls
R=controls.R
@unittest.skipUnless(R.is_dir(),'HKUST evidence only')
class QualityContract(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.bundle=json.loads((controls.OUTPUT/'proof.json').read_bytes());cls.row=cls.bundle['positive_cases'][0];cls.record=json.loads(Path(cls.row['candidate']['file']).read_bytes());cls.qa=json.loads(Path(cls.row['qa']['file']).read_bytes())
 def test_two_actual_full_positive_and_three_actual_rehashed_semantic_negatives(self):self.assertTrue(controls.check_controls(self.bundle))
 def test_mandatory_fields_and_exact_geometry_cannot_be_waived(self):
  mutations=[('missing_stage',lambda q,r:q['checks'].pop('fonts')),('source_coverage',lambda q,r:q['checks']['source']['evidence'].update(complete_source_coverage=False)),('SOURCE_ink',lambda q,r:q['checks']['source']['evidence']['all_fresh_HTML_native_text_ink'].update(exact_same_domain_source_native_ink=False)),('physical_strut',lambda q,r:q['checks']['fonts'].update(all_element_and_host_primary_physical_struts_bound_to_embedded_faces=False)),('glyph_geometry',lambda q,r:q['checks']['fonts']['source_glyph_checks'][0].update(maximum_grapheme_Range_error=.031)),('candidate_PNG',lambda q,r:r.update(image_sha256='0'*64)),('native_model_export',lambda q,r:q['checks']['render'].update(model_geometry_preserved_by_export=False)),('missing_complete_inspection',lambda q,r:q['checks']['render'].update(strict_outside_inspection_pixels=1)),('invented_original_view_diagnostic',lambda q,r:q['checks']['render'].update(unclipped_native_outside_original_source_viewport_pixels=-1)),('different_viewport',lambda q,r:q['checks']['render']['export_frame'].update(x=31)),('partial_actual_editing',lambda q,r:q['checks']['native_editing'].update(actual_native_text_edits=0)),('extra_unproved_native_object',lambda q,r:r.update(vertices=r['vertices']+1))]
  for name,change in mutations:
   with self.subTest(name=name):
    qa,record=copy.deepcopy(self.qa),copy.deepcopy(self.record);change(qa,record)
    with self.assertRaises(ValueError):controls.full_quality(qa,record)
 def test_legal_original_view_clipping_is_honest_diagnostic_not_zero_claim(self):
  qa=copy.deepcopy(self.qa);qa['checks']['render']['unclipped_native_outside_original_source_viewport_pixels']=100;self.assertTrue(controls.full_quality(qa,self.record))
if __name__=='__main__':unittest.main()
