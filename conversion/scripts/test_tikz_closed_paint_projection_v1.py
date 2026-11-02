import copy,math,unittest,xml.etree.ElementTree as E
import tikz_closed_paint_projection_v1 as m
class ProjectionTests(unittest.TestCase):
 def test_complete_viewbox_uniform_meet_no_crop(self):
  r=m.meet_frame([0,0,200,100],[528,528]);self.assertEqual(r['scale'],2.64);self.assertEqual(r['translate'],[0,132]);self.assertFalse(r['pixel_fitting_used']);self.assertFalse(r['provider_DPI_recovered']);self.assertFalse(r['clip_source_objects'])
 def test_nonzero_source_origin_is_accounted_without_tight_crop(self):
  r=m.meet_frame([10,20,100,100],[200,200]);self.assertEqual(r['matrix'],[2,0,0,2,-20,-40])
 def test_square_reference_does_not_stretch_source_circle(self):
  r=m.meet_frame([0,0,189.9199981689453,189.97999572753906],[528,528]);self.assertEqual(r['matrix'][0],r['matrix'][3]);self.assertAlmostEqual(r['translate'][0],.08337380684787377,places=5);self.assertEqual(r['translate'][1],0)
 def test_projection_only_changes_root_viewport_and_declares_one_rule(self):
  s='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10" viewBox="0 0 20 10"><path id="original" d="M1,1L2,2"/><text x="1" y="3">Abc</text></svg>';a=E.fromstring(s);out,frame=m.project_svg(s,[528,528]);b=E.fromstring(out);self.assertEqual([E.tostring(x) for x in a],[E.tostring(x) for x in b]);self.assertEqual(b.get('viewBox'),a.get('viewBox'));self.assertEqual(b.get('preserveAspectRatio'),'xMidYMid meet');self.assertEqual(b.get('width'),'528')
 def test_no_reference_pixels_or_search_options_are_accepted(self):
  import inspect
  self.assertEqual(list(inspect.signature(m.meet_frame).parameters),['viewbox','viewport']);self.assertEqual(list(inspect.signature(m.project_svg).parameters),['svg','viewport'])
 def test_invalid_or_nonfinite_frame_rejected(self):
  for vb,vp in [([0,0,0,20],[10,10]),([0,0,20,-1],[10,10]),([0,0,float('nan'),20],[10,10]),([0,0,20,20],[0,20]),([0,0,20,20],[2.3,20]),([0,0,20,20],[True,20])]:
   with self.assertRaises(ValueError):m.meet_frame(vb,vp)
 def test_actual_source_geometry_frame_shear_cannot_be_hidden(self):
  f=m.meet_frame([0,0,10,10],[100,100]);o={'id':'a','type':'shape','matrix':[10,.5,0,10,0,0],'bbox':{'x':1,'y':1,'w':10,'h':10}};self.assertFalse(m.check_dom_frame({'objects':[o]},f)['ok'])
 def test_off_page_source_object_not_silently_cropped(self):
  f=m.meet_frame([0,0,10,10],[100,100]);o={'id':'a','type':'shape','matrix':f['matrix'],'bbox':{'x':95,'y':1,'w':10,'h':10}};self.assertFalse(m.check_dom_frame({'objects':[o]},f)['ok'])
 def test_exact_source_frame_with_complete_inside_object(self):
  f=m.meet_frame([0,0,10,10],[100,100]);o={'id':'a','type':'shape','matrix':f['matrix'],'bbox':{'x':1,'y':1,'w':10,'h':10}};self.assertTrue(m.check_dom_frame({'objects':[o]},f)['ok'])
 def invalid_profile(self,change=None,dom=None,roles=None):
  xml='<mxfile/>';r={'source_format':'tikz','id':'id','source_pair_sha256':'id','source_code_sha256':'original-code','source_image_sha256':'original-reference','code_sha256':m.sha(xml.encode())};identity=copy.deepcopy(r);identity.pop('code_sha256');r.update(change or {});return m.check_source_profile(r,xml,dom=dom or {'objects':[]},roles=roles or {'ok':True,'all_source_and_PDF_paint_accounted':True,'objects':[]},frame=m.meet_frame([0,0,10,10],[100,100]),physical_fonts={'ok':True,'fonts':[]},source_identity=identity)
 def test_authoritative_format_cannot_be_relabelled_svg(self):self.assertFalse(self.invalid_profile({'source_format':'svg'})['supported'])
 def test_candidate_code_hash_bound(self):self.assertFalse(self.invalid_profile({'code_sha256':'wrong'})['supported'])
 def test_original_source_hash_bound(self):self.assertFalse(self.invalid_profile({'source_code_sha256':'wrong'})['supported'])
 def test_pair_identity_bound(self):self.assertFalse(self.invalid_profile({'source_pair_sha256':'wrong'})['supported'])
 def test_free_arrows_cannot_slip_through_closed_paint_profile(self):self.assertFalse(self.invalid_profile(roles={'ok':True,'all_source_and_PDF_paint_accounted':True,'objects':[{'role':'explicit_numeric_coordinate_axis_free_edge'}]})['supported'])
 def test_named_graph_source_cannot_use_paint_bridge(self):self.assertFalse(self.invalid_profile(dom={'objects':[],'nodes':{'named':{}}})['supported'])
 def test_unsuccessful_QA_report_has_no_publication_or_revalidation_authority(self):
  r=m.revalidate(None,{'id':'x','policy':m.POLICY,'read_only_new_profile_full_QA_passed':False},{})
  self.assertFalse(r['current']);self.assertFalse(r['accepted']);self.assertFalse(r['published'])
 def test_changed_report_rejected_before_any_DB_or_browser_access(self):
  r=m.revalidate(None,{'id':'x','policy':m.POLICY,'read_only_new_profile_full_QA_passed':True,'accepted':False,'published':False,'report_sha256':'wrong'},{})
  self.assertFalse(r['current']);self.assertIn('report damaged',r['reason'])
 def test_unknown_source_feature_cannot_be_silently_ignored(self):self.assertFalse(self.invalid_profile(dom={'objects':[],'issues':[{'reason':'clip_unresolved'}]})['supported'])
if __name__=='__main__':unittest.main()
