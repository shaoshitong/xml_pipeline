import copy,json,sqlite3,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import svg_failure_closure_v1 as m

class PureTests(unittest.TestCase):
 def setUp(self):
  self.fresh={'supported':False,'ok':False,'failures':[{'reason':'unidentified_svg_connectors_require_semantic_profile'}]}
  self.scene={'supported':False,'ok':False,'failures':[{'reason':'closed_path_requires_an_explicit_role_or_basic_geometry_proof','id':'p'}]}
  self.dom={'sceneCapture':{'completeOfflineSource':True}}
 def decision(self,**kwargs):return m.closure_decision(kwargs.get('fresh',self.fresh),kwargs.get('scene',self.scene),kwargs.get('dom',self.dom),kwargs.get('routes',[]),kwargs.get('blockers',[]))
 def test_verified_source_failure_without_routes_proposes(self):self.assertTrue(self.decision()['proposal'])
 def test_fresh_source_success_never_accepts_or_terminates(self):self.assertFalse(self.decision(fresh={'ok':True})['proposal'])
 def test_supported_graph_geometry_failure_not_laundered_by_closed_scene_rule(self):
  fresh={'supported':True,'ok':False,'failures':[{'reason':'source_text_position_changed'}]};self.assertFalse(self.decision(fresh=fresh)['proposal'])
 def test_any_unattempted_font_canvas_marker_route_defers(self):
  for script in ('font.py','canvas.py','marker.py'):
   self.assertFalse(self.decision(routes=[{'script':script,'state':'available_unattempted'}])['proposal'])
 def test_legacy_unbound_stage_defers(self):self.assertFalse(self.decision(routes=[{'state':'blocked','reason':'legacy'}])['proposal'])
 def test_metadata_or_runtime_failure_defers(self):
  x=copy.deepcopy(self.fresh);x['failures']=[{'reason':'source_profile_validation_error','error':'KeyError'}];self.assertFalse(self.decision(fresh=x)['proposal'])
 def test_external_source_resource_never_complete(self):self.assertFalse(self.decision(dom={'sceneCapture':{'completeOfflineSource':False}})['proposal'])
 def test_new_bounded_scene_rule_source_supported_defers(self):
  self.assertFalse(self.decision(scene={'supported':True,'ok':False,'failures':[{'reason':'source_paint_object_missing'}]})['proposal'])
 def test_nested_capture_parse_error_not_semantic_terminal(self):
  x=copy.deepcopy(self.scene);x['failures'].append({'reason':'unresolved_source_feature','issue':{'reason':'scene_source_path_parse_failed','error':'bad parser'}});self.assertFalse(self.decision(scene=x)['proposal'])
 def test_actual_contour_error_bound_failure_is_not_a_validator_error(self):
  scene={'supported':False,'ok':False,'failures':[{'reason':'generic_svg_arc_requires_actual_contour_error_bound'}]};self.assertTrue(self.decision(scene=scene)['proposal'])
 def test_owner_or_metadata_blocker_defers(self):self.assertFalse(self.decision(blockers=['font_source_scan_missing'])['proposal'])
 def test_missing_or_wrong_source_group_metadata_not_treated_as_route_inapplicability(self):
  r={'conversion_method':'svg_element_native_stencils_editable_text_and_connectors_v1','svg_conversion':{'counts':{'node_groups':0}}};self.assertTrue(m.conversion_metadata_blockers(r,{'nodes':{'real':'node'}}));self.assertEqual(m.conversion_metadata_blockers(r,{'nodes':{}}),[])
 def test_known_v2_version_field_gap_defers(self):
  r={'conversion_method':'svg_element_native_stencils_editable_text_and_connectors_v2','svg_conversion':{'counts':{'node_groups':0}}};self.assertIn('known_converter_missing_version_required_by_production_font_route',m.conversion_metadata_blockers(r,{'nodes':{}}))
 def test_actual_sql_stage_guard_removes_only_target(self):
  sql="select j.id,j.output_record from jobs j where j.format='svg' and exists(select 1 from prior x where x.id=j.id) and not exists(select 1 from stage s where s.id=j.id and s.h=json_extract(j.output_record,'$.code_sha256')) order by j.id limit 1"
  base,guards=m.strip_stage_guard(sql,'stage');self.assertIn('from prior',base);self.assertNotIn('from stage',base);self.assertEqual(len(guards),1);self.assertEqual(m.per_id_query(base).count('?'),1)
 def test_legacy_not_in_guard(self):
  sql="select id,state from jobs where format='svg' and id not in (select id from old) order by id limit 1";base,_=m.strip_stage_guard(sql,'old');self.assertNotIn('not in',base);self.assertIn('and id=?',m.per_id_query(base))
 def test_ambiguous_or_changed_selector_fails_closed(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.py';p.write_text("a=\"select id from jobs where format='svg'\"\nb=\"select id from jobs where format='python'\"")
   with self.assertRaises(ValueError):m.literal_selector(p)

class IntegratedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'clean').mkdir();self.db=sqlite3.connect(':memory:')
  self.db.executescript('''create table jobs(id,format,state,worker_pid,input_record,output_record,input_manifest,updated_at);create table processing_outcomes_v2(id,category,format,source_code_hash,source_image_hash,status);create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at);create table stage(id,input_code_sha256,state,record,updated_at);''')
  data={'code_file':b'<mxfile><diagram><mxGraphModel><root/></mxGraphModel></diagram></mxfile>','image_file':b'png','original_source_code':b'<svg><path d="M0 0L2 0L1 1Z"/></svg>','original_reference':b'reference'}
  self.record={'id':'a','source_pair_sha256':'a','source_format':'svg','source_code_sha256':m.sha(data['original_source_code']),'source_image_sha256':m.sha(data['original_reference']),'code_sha256':m.sha(data['code_file']),'image_sha256':m.sha(data['image_file']),'svg_conversion':{'converter_version':'svg_native_v6'}}
  for k,v in data.items():
   p=self.root/'clean'/k;p.write_bytes(v);self.record[k]=str(p.relative_to(self.root))
  inp={'code_sha256':self.record['source_code_sha256'],'image_sha256':self.record['source_image_sha256']};self.raw=json.dumps(self.record)
  self.db.execute('insert into jobs values(?,?,?,?,?,?,?,?)',('a','svg','needs_quality_repair',None,json.dumps(inp),self.raw,'{}','t'))
  self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?)',('a','scientific_diagram','svg',inp['code_sha256'],inp['image_sha256'],'pending'))
  audit={'source_code_sha256':inp['code_sha256'],'source_image_sha256':inp['image_sha256'],'checks':{'source':{'supported':False,'ok':False,'failures':[{'reason':'unidentified_svg_connectors_require_semantic_profile'}]}},'failures':['source_profile_not_implemented']}
  self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',('a',self.record['code_sha256'],self.record['image_sha256'],'old-frozen','repair_required',json.dumps(audit),'t'))
  pin=self.root/'pinned.py';pin.write_text('frozen=1');self.config={'root':str(self.root),'policy':'qa4b-frozen','pins':{str(pin):m.sha(pin.read_bytes())},'routes':[],'catalog_sha256':'catalog','research':{'production_route':False,'status':'frozen'}}
  owner=self.root/'owner.json';owner.write_text(json.dumps({'policy':'qa4b-frozen'}));self.config['owner_policy_path']=str(owner)
  self.resource=types.SimpleNamespace(resource_checks=lambda *args:{'verified_files':[]})
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def capture(self,r,xml):
  dom={'objects':[{'id':str(n)} for n in range(80)],'issues':[{'reason':'filter','id':str(n)} for n in range(160)]}
  scene=copy.deepcopy(dom);scene['sceneCapture']={'completeOfflineSource':True,'recordId':'a','recordCodeSha256':r['code_sha256'],'sourceCodeSha256':r['source_code_sha256'],'sourceImageSha256':r['source_image_sha256']}
  return {'fresh_source_checker':{'supported':False,'ok':False,'failures':[{'reason':'unidentified_svg_connectors_require_semantic_profile'}]},'scene_checker':{'supported':False,'ok':False,'failures':[{'reason':'closed_path_requires_an_explicit_role_or_basic_geometry_proof'}]},'base_dom':dom,'scene_dom':scene,'full_uncertain_object_ids':list(range(80)),'full_base_issues':dom['issues'],'full_scene_issues':scene['issues'],'full_scene_additional_issues':[]}
 def prepare(self):
  self.db.commit()
  with patch.dict('sys.modules',{'auto_quality_common':self.resource}):return m.prepare(self.db,'a',self.config,self.root/'new',self.capture)
 def test_complete_sidecars_not_old_20_30_previews_and_no_db_mutation(self):
  changes=self.db.total_changes;plan=self.prepare();self.assertTrue(plan['proposal']);self.assertEqual(self.db.total_changes,changes);self.assertEqual(plan['full_uncertain_objects'],80);self.assertEqual(plan['full_source_issue_count'],160);self.assertEqual(len(json.loads((self.root/'new/base_dom.json').read_text())['objects']),80);self.assertTrue(m.revalidate(self.db,plan,self.config)['current'])
 def test_sidecar_changed_rejected(self):
  p=self.prepare();(self.root/'new/scene_dom.json').write_text('{}');self.assertFalse(m.revalidate(self.db,p,self.config)['current'])
 def test_plan_decision_corrupted_rejected(self):
  p=self.prepare();p['code_sha256']='fake';self.assertFalse(m.revalidate(self.db,p,self.config)['current'])
 def test_new_current_job_revision_or_registry_state_rejected(self):
  p=self.prepare();self.db.execute("update processing_outcomes_v2 set status='qualified'");self.assertFalse(m.revalidate(self.db,p,self.config)['current'])
 def test_pin_changed_rejected(self):
  p=self.prepare();Path(next(iter(self.config['pins']))).write_text('changed');self.assertFalse(m.revalidate(self.db,p,self.config)['current'])
 def test_active_QA_source_policy_changed_rejected(self):
  p=self.prepare();Path(self.config['owner_policy_path']).write_text(json.dumps({'policy':'new-unproved-source-policy'}));self.assertFalse(m.revalidate(self.db,p,self.config)['current'])
 def test_resource_changed_rejected(self):
  p=self.prepare();(self.root/'clean/original_source_code').write_bytes(b'changed');self.assertFalse(m.revalidate(self.db,p,self.config)['current'])
 def test_fresh_end_snapshot_observes_other_connection_publication(self):
  self.db.commit();path=self.root/'live.sqlite';filedb=sqlite3.connect(path,timeout=1);self.db.backup(filedb);other=sqlite3.connect(path,timeout=1)
  def capture(r,xml):
   other.execute("update jobs set updated_at='new revision observation'");other.commit();return self.capture(r,xml)
  try:
   with patch.dict('sys.modules',{'auto_quality_common':self.resource}):p=m.prepare(filedb,'a',self.config,self.root/'new',capture)
   self.assertFalse(p['proposal']);self.assertIn('snapshot changed',p['error']);self.assertFalse(filedb.in_transaction)
  finally:other.close();filedb.close()
 def test_revalidate_preserves_writer_owned_transaction(self):
  p=self.prepare();self.db.execute('BEGIN IMMEDIATE');self.assertTrue(m.revalidate(self.db,p,self.config)['current']);self.assertTrue(self.db.in_transaction)
 def test_owner_rejected_before_capture(self):
  self.db.execute('update jobs set worker_pid=123');p=self.prepare();self.assertFalse(p['proposal']);self.assertNotIn('source_object_count',p)
 def test_historical_other_pair_does_not_admit(self):
  self.db.execute("update auto_quality_audits_v1 set code_hash='other'");self.assertFalse(self.prepare()['proposal'])
 def test_current_metadata_format_mismatch_rejected(self):
  r=dict(self.record,source_format='html');self.db.execute('update jobs set output_record=?',(json.dumps(r),));self.assertFalse(self.prepare()['proposal'])
 def test_exact_source_current_audit_identity_required(self):
  self.db.execute("update auto_quality_audits_v1 set record=?",(json.dumps({'source_code_sha256':'other','checks':{'source':{'ok':False,'failures':['x']}}}),));self.assertFalse(self.prepare()['proposal'])
 def test_route_current_stage_not_id_only(self):
  rule={'script':'marker.py','table':'stage','revision_key':'input_code_sha256','base_query':"select 1 from jobs where id=?",'selector_query':"select 1 from jobs j where id=? and not exists(select 1 from stage s where s.id=j.id and s.input_code_sha256=json_extract(j.output_record,'$.code_sha256'))"};config=dict(self.config,routes=[rule]);self.assertEqual(m.route_verdicts(self.db,'a',self.record,config)[0]['state'],'available_unattempted');self.db.execute('insert into stage values(?,?,?,?,?)',('a','historical','no_additional_vee','{}','t'));self.assertEqual(m.route_verdicts(self.db,'a',self.record,config)[0]['state'],'available_unattempted');self.db.execute('insert into stage values(?,?,?,?,?)',('a',self.record['code_sha256'],'no_additional_vee','{}','t'));self.assertEqual(m.route_verdicts(self.db,'a',self.record,config)[0]['state'],'exhausted_terminal')

if __name__=='__main__':unittest.main()
