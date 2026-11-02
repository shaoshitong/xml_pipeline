import json,sqlite3,unittest
import auto_quality_batch_v4b as m

class Selection(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
  self.db.executescript('''create table jobs(id primary key,state,output_record,input_record,worker_pid);
   create table auto_quality_candidates_v1(id,code_hash,image_hash,priority,route);
   create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record);
   create table processing_outcomes_v2(id,status,record);''')
  self.add('one')
 def add(self,id,route='vector',**extras):
  r={'code_sha256':'code','image_sha256':'png','source_format':'html',**extras}
  self.db.execute('insert into jobs values(?,?,?,?,NULL)',(id,'needs_quality_repair',json.dumps(r),'{}'))
  self.db.execute('insert into auto_quality_candidates_v1 values(?,?,?,?,?)',(id,'code','png',10,route))
 def audit(self,policy=None):self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?)',('one','code','png',policy or m.PREDECESSOR,'repair_required','{}'))
 def selected(self,ids=[]):return [r[0] for r in m.select_rows(self.db,ids,20)]
 def test_new_repair_route_included_for_first_inspection(self):
  for route in ('graph','vector','native','repair'):self.add(route,route=route)
  self.assertEqual(set(self.selected()),{'one','graph','vector','native','repair'})
 def test_unchanged_predecessor_failure_reused(self):self.audit();self.assertEqual(self.selected(),[])
 def test_owned_native_font_proof_is_affected_even_if_bad(self):
  self.audit();self.db.execute('update jobs set output_record=?',(json.dumps({'code_sha256':'code','image_sha256':'png','source_format':'drawio','native_font_validation':{'audit':'conversion/auto_quality_font_repair_v1/id/hash/report.json','output_code_sha256':'wrong'}}),));self.assertEqual(self.selected(),['one'])
 def test_new_layout_lineage_affected(self):
  self.audit();self.db.execute('update jobs set output_record=?',(json.dumps({'code_sha256':'code','image_sha256':'png','source_format':'html','html_text_layout_v5':{'proof':'x'}}),));self.assertEqual(self.selected(),['one'])
 def test_current_policy_not_retried(self):self.audit(m.POLICY);self.assertEqual(self.selected(),[])
 def test_abandoned_same_revision_not_retried(self):
  self.db.execute('insert into processing_outcomes_v2 values(?,?,?)',('one','abandoned',json.dumps({'code_sha256':'code','image_sha256':'png'})));self.assertEqual(self.selected(),[])
 def test_native_rule_change_allows_one_deterministic_rescue_of_abandoned(self):
  self.db.execute('insert into processing_outcomes_v2 values(?,?,?)',('one','abandoned',json.dumps({'code_sha256':'code','image_sha256':'png'})))
  self.db.execute('update jobs set output_record=?',(json.dumps({'code_sha256':'code','image_sha256':'png','source_format':'drawio'}),))
  self.audit();self.assertEqual(self.selected(),['one']);self.audit(m.POLICY);self.assertEqual(self.selected(),[])
 def test_new_revision_can_rescue_abandoned(self):
  self.db.execute('insert into processing_outcomes_v2 values(?,?,?)',('one','abandoned',json.dumps({'code_sha256':'old','image_sha256':'old'})));self.assertEqual(self.selected(),['one'])
 def test_retained_fallback_candidates_get_inspected(self):
  for state in ('needs_fallback','harness_rendered'):
   self.db.execute('update jobs set state=?',(state,));self.assertEqual(self.selected(),['one'])
 def test_busy_and_stale_payload_rejected(self):
  self.db.execute('update jobs set worker_pid=123');self.assertEqual(self.selected(),[])
  self.db.execute("update jobs set worker_pid=NULL,output_record='{}'");self.assertEqual(self.selected(),[])
 def test_only_requested_ids_selected(self):self.add('two');self.assertEqual(self.selected(['two']),['two'])

 def audit_v4(self,failure,state='repair_required'):
  self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?)',('one','code','png',m.PREDECESSOR_V4,state,json.dumps({'failures':[failure]})))
 def glyph(self,field='html_actual_text_alignment'):
  self.db.execute('update jobs set output_record=?',(json.dumps({'code_sha256':'code','image_sha256':'png','source_format':'html',field:{'proof':'lineage'}}),))
 def test_unaffected_v4_failure_reused(self):self.audit_v4('source_coverage_failure');self.assertEqual(self.selected(),[])
 def test_native_v4_failure_not_retried_by_version_change(self):
  self.db.execute('update jobs set output_record=?',(json.dumps({'code_sha256':'code','image_sha256':'png','source_format':'drawio'}),));self.audit_v4('native actual failure');self.assertEqual(self.selected(),[])
 def test_glyph_and_layout_missing_boundary_receive_one_recheck(self):
  for field in ('html_actual_text_alignment','html_text_layout_v5'):
   self.db.execute('delete from auto_quality_audits_v1');self.glyph(field);self.audit_v4("'outside_page_pixel_audit'");self.assertEqual(self.selected(),['one']);self.audit(m.POLICY);self.assertEqual(self.selected(),[])
 def test_other_glyph_failures_not_retried(self):
  self.glyph();self.audit_v4('source proof failed');self.assertEqual(self.selected(),[])
 def test_unrelated_metadata_keyerror_not_reclassified_as_clip_failure(self):
  self.audit_v4("'outside_page_pixel_audit'");self.assertEqual(self.selected(),[])
 def test_abandoned_interface_failure_can_be_recovered_once(self):
  self.glyph();self.audit_v4("'outside_page_pixel_audit'");self.db.execute('insert into processing_outcomes_v2 values(?,?,?)',('one','abandoned',json.dumps({'code_sha256':'code','image_sha256':'png'})));self.assertEqual(self.selected(),['one']);self.audit(m.POLICY);self.assertEqual(self.selected(),[])
 def test_previous_stale_revision_is_not_a_quality_verdict(self):
  self.audit_v4('stale',state='stale_revision');self.assertEqual(self.selected(),['one'])

class Dispatch(unittest.TestCase):
 def test_owned_invalid_font_proof_never_falls_back(self):
  from unittest.mock import patch
  record={'source_format':'drawio','code_sha256':'actual','native_font_validation':{'audit':'conversion/auto_quality_font_repair_v1/id/hash/report.json','output_code_sha256':'wrong'}}
  failure={'supported':True,'ok':False,'failures':['bad-proof']}
  with patch('native_source_font_profile_v4.check_native_profile',return_value=failure) as strict,patch.object(m,'native_source_profile',side_effect=AssertionError('fallback called')):
   self.assertEqual(m.profile(record,'xml','source'),failure);strict.assert_called_once()
 def test_layout_lineage_has_priority_over_legacy_glyph(self):
  from unittest.mock import patch
  record={'source_format':'html','html_text_layout_v5':{'proof':'new'},'html_actual_text_alignment':{'proof':'old'}}
  with patch('auto_quality_html_text_layout_profile_v5.check_html_profile',return_value={'ok':True}) as newer,patch('auto_quality_html_glyph_profile_v3.check_html_profile',side_effect=AssertionError('legacy called')):
   self.assertEqual(m.profile(record,'xml','source',{'actual_clip_boxes':[]} ),{'ok':True});newer.assert_called_once()
 def test_canvas_uses_verified_font_baseline(self):
  from unittest.mock import patch
  before={'source_format':'drawio','native_font_validation':{'audit':'conversion/auto_quality_font_repair_v1/id/hash/report.json'}}
  current={'source_format':'drawio','auto_quality_canvas_repair':{'proof':'p'}}
  result={'supported':True,'ok':True,'evidence':{}}
  with patch.object(m,'source_baseline',return_value=(before,'before-xml')),patch('native_source_font_profile_v4.check_native_profile',return_value=result) as strict:
   r=m.profile(current,'current-xml','source',{'current':True});strict.assert_called_once_with(before,'before-xml','source',native_info=None);self.assertTrue(r['evidence']['canvas_only_transformation_independently_verified'])

if __name__=='__main__':unittest.main()
