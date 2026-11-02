"""Private real SQLite fixtures only. No renderer, compiler or model imported."""
from pathlib import Path
import copy,hashlib,json,sqlite3,tempfile,unittest
from unittest.mock import patch
import visual_failure_route_guard_v1 as guard
sha=guard.sha
encode=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
class GuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.w=self.root/'conversion';self.w.mkdir();scripts=self.w/'scripts';scripts.mkdir();self.program=scripts/'route.py';self.program.write_text('frozen route source\n');wrapped=scripts/'auto_quality_html_repair_batch_v3.py';wrapped.write_text('EXCEPTION_REASON_SQL="(e.reason like \'%source_paint_object_missing%\')"\n');self.id='a'*64;self.qpolicy='bounded_deterministic_clip_canvas_and_native_quality_v4b:a8446927202f282d';self.old='source_execution_glyph_lineage_native_render_and_local_fidelity_v3:210bf4dbced804c5';self.sh=sha(b'source');self.si=sha(b'reference');self.ch=sha(b'xml');self.ih=sha(b'native');self.source={'pair_sha256':self.id,'source':'fixture','category':'scientific_diagram','format':'python','code_sha256':self.sh,'image_sha256':self.si};self.record={'id':self.id,'source_pair_sha256':self.id,'source':'fixture','category':'scientific_diagram','source_format':'python','format':'drawio','source_code_sha256':self.sh,'source_image_sha256':self.si,'code_sha256':self.ch,'image_sha256':self.ih,'conversion_method':'source_fixed','code_file':'clean/code.drawio','image_file':'clean/img.png','original_source_code':'clean/source.py','original_reference':'clean/ref.png'};self.input_manifest={'id':self.id,'source_format':'python','code_sha256':self.sh,'image_sha256':self.si,'width':100,'height':100,'source_code':'clean/source.py','reference_image':'clean/ref.png'};self.audit={'id':self.id,'policy':self.qpolicy,'input_code_sha256':self.ch,'input_image_sha256':self.ih,'source_code_sha256':self.sh,'source_image_sha256':self.si,'checks':{'structure':{'edges':0},'resources':{'files':4},'source':{'supported':True,'ok':True},'render':{'strict_outside_page_pixels':0},'text_paint':{'ok':True},'fonts':{'all_rendered_fonts_embedded':True},'visual':{'ok':False,'failures':['foreground_tile_p10_below_0.72']}},'failures':['raster_anomaly:foreground_tile_p10_below_0.72']}
  self.db=sqlite3.connect(self.w/'jobs.sqlite');self.addCleanup(self.db.close);self.db.execute('create table jobs(id text primary key,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)');self.db.execute('create table processing_outcomes_v2(id text primary key,category text,format text,source_code_hash text,source_image_hash text,status text,reason text,record text,updated_at text)');self.db.execute('create table auto_quality_audits_v1(id text,code_hash text,image_hash text,policy text,state text,record text,updated_at text,primary key(id,code_hash,image_hash,policy))');self.db.execute('create table auto_quality_exceptions_v1(id text,code_hash text,image_hash text,policy text,route text,state text,reason text,updated_at text)');self.db.execute('create table stage(id text,code_hash text,state text,owner_pid integer,record text,primary key(id,code_hash))')
  for t in ('harness_queue','harness_queue_v2','harness_queue_v3'):self.db.execute('create table '+t+'(id text primary key,state text,worker_pid integer,attempts integer,session text,error text)')
  self.db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(self.id,'scientific_diagram','python','fixture',encode(self.source),'needs_quality_repair','vector',2,'one',encode(self.record),None,encode(self.input_manifest),None));self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)',(self.id,'scientific_diagram','python',self.sh,self.si,'pending',None,None,'one'));self.save_audit();self.db.commit();self.owner={'pid':1234,'policy':self.qpolicy};self.owner_path=self.w/'auto_quality_owner.json';self.owner_path.write_text(encode(self.owner));self.model_path=self.w/'model_usage_policy_v2.json';self.model={'legacy_sdk_disabled':True,'automatic_model_case_selection_disabled':True,'model_calls_per_original_sample_lifetime_limit':2,'authorized_model_sample_ids':[]};self.model_path.write_text(encode(self.model));self.reservation_path=self.root/guard.RESERVATION;self.reservation_path.parent.mkdir(parents=True);self.reservation={'ids':[sha(('reserved'+str(i)).encode()) for i in range(16)]};self.reservation_path.write_text(encode(self.reservation));self.rule={'script':'route.py','formats':['python'],'table':'stage','revision_key':'code_hash','bindings':[],'base_query':"select 1 from jobs where format='python' and json_extract(output_record,'$.route_on')=1 and id=? limit 1",'selector_query':"select 1 from jobs where format='python' and json_extract(output_record,'$.route_on')=1 and id=? and not exists(select 1 from stage where stage.id=jobs.id) limit 1"};self.frozen={'id':self.id,'format':'python','source_code_sha256':self.sh,'source_image_sha256':self.si,'code_sha256':self.ch,'image_sha256':self.ih,'qa_policy':self.qpolicy,'audit_record_sha256':sha(encode(self.audit).encode()),'logical_visual_route_class':guard.CLASS,'routes':[{'script':'route.py','state':'not_applicable_by_actual_producer_SQL','actual_base_applicable':False,'actual_selector_eligible':False,'current_input_receipts':[]}]};self.expected={'python':1};self.report_path=self.root/guard.REPORT;self.report_path.parent.mkdir(parents=True,exist_ok=True);self.manifest_path=self.root/guard.MANIFEST;self.install_scope(wrapped);self.config=self.configure()
 def save_audit(self):self.db.execute('insert or replace into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',(self.id,self.ch,self.ih,self.audit['policy'],'repair_required',encode(self.audit),'one'))
 def install_scope(self,wrapped=None):
  wrapped=wrapped or self.w/'scripts/auto_quality_html_repair_batch_v3.py';pins={str(self.program):sha(self.program.read_bytes()),str(wrapped):sha(wrapped.read_bytes())};catalog={'active_quality_policy':self.qpolicy,'pins':pins,'static_routes':[self.rule]};self.report={'scope':131904,'active_owner':self.owner,'active_owner_sha256':sha(self.owner_path.read_bytes()),'route_catalog':catalog,'records':[self.frozen]};self.report_path.write_text(encode(self.report));item={k:self.frozen[k] for k in ('id','source_code_sha256','source_image_sha256','code_sha256','image_sha256','qa_policy','audit_record_sha256','logical_visual_route_class')};item['source_format']=self.frozen['format'];self.manifest={'full_scope':131904,'policy':self.qpolicy,'catalog_sha256':sha(guard.canonical(catalog)),'items':[item]};self.manifest_path.write_text(encode(self.manifest))
 def configure(self):
  with patch.multiple(guard,REPORT_SHA=sha(self.report_path.read_bytes()),MANIFEST_SHA=sha(self.manifest_path.read_bytes()),RESERVATION_SHA=sha(self.reservation_path.read_bytes()),EXPECTED_COUNTS=self.expected):
   cfg=guard.configuration(self.root)
  self.patch=patch.multiple(guard,REPORT_SHA=cfg['report']['sha256'],MANIFEST_SHA=cfg['manifest']['sha256'],RESERVATION_SHA=cfg['research_reservation']['sha256'],EXPECTED_COUNTS=self.expected);self.patch.start();self.addCleanup(self.patch.stop);return cfg
 def result(self):self.db.commit();return guard.capture(self.db,self.id,self.config)
 def assertRejected(self,needle=None):
  r=self.result();self.assertFalse(r['eligible'],r)
  if needle:self.assertIn(needle,r['reason'])
  return r
 def change_record(self,**fields):self.record.update(fields);self.db.execute('update jobs set output_record=? where id=?',(encode(self.record),self.id))
 def make_html(self):
  self.source.update(format='html',category='poster');self.record.update(source_format='html',category='poster');self.input_manifest['source_format']='html';self.frozen['format']='html';self.frozen['routes']=[{'script':'auto_quality_glyph_alignment_batch_v3c.py','state':'not_applicable_no_current_local_text_exception'},{'script':'auto_quality_html_text_layout_batch_v5a.py','state':'not_applicable_no_current_local_text_exception'},{'script':'auto_quality_html_repair_batch_v3.py','state':'not_applicable_current_source_inventory_passed_no_wrapped_source_exception'}];self.db.execute('update jobs set format="html",category="poster",input_record=?,output_record=?,input_manifest=? where id=?',(encode(self.source),encode(self.record),encode(self.input_manifest),self.id));self.db.execute('update processing_outcomes_v2 set format="html",category="poster" where id=?',(self.id,));self.db.commit();self.expected={'html':1};self.install_scope();self.config=self.configure()
 def test_real_capture_and_full_shape(self):
  before=list(self.db.iterdump());r=self.result();self.assertTrue(r['eligible'],r);self.assertEqual(len(r['item']),5);self.assertEqual(set(r['job']),set(guard.JOB_COLUMNS));self.assertEqual(r['full_snapshot']['tables']['stage']['rows'],[]);self.assertEqual(list(self.db.iterdump()),before);self.assertFalse(self.db.in_transaction);self.assertTrue(guard.revalidate(self.db,r,self.config)['eligible'])
 def test_outside_id(self):self.assertFalse(guard.capture(self.db,'b'*64,self.config)['eligible'])
 def test_report_or_manifest_change_refuses(self):
  self.report_path.write_text(self.report_path.read_text()+' ');self.assertRejected('inventory_identity_changed')
 def test_frozen_prerequisites_cannot_be_replaced_by_visual_only_flag(self):
  self.audit['checks']['source']['ok']=False;self.save_audit();self.frozen['audit_record_sha256']=sha(encode(self.audit).encode());self.install_scope();self.config=self.configure();self.assertRejected('source_not_passed')
 def test_strict_false_is_not_integer_zero(self):
  self.audit['checks']['render']['strict_outside_page_pixels']=False;self.save_audit();self.frozen['audit_record_sha256']=sha(encode(self.audit).encode());self.install_scope();self.config=self.configure();self.assertRejected('strict_outside_page_not_zero')
 def test_unknown_visual_failure_is_not_endstate(self):
  self.audit['checks']['visual']['failures']=['unknown_metric'];self.save_audit();self.frozen['audit_record_sha256']=sha(encode(self.audit).encode());self.install_scope();self.config=self.configure();self.assertRejected('not_bounded_visual_failure')
 def test_claim_token_changes_complete_context(self):
  self.db.execute('create table attempts(id text,state text,claim_token text)');self.db.execute('insert into attempts values(?,?,?)',(self.id,'finished','old'));context=self.result();self.assertTrue(context['eligible']);self.db.execute('update attempts set claim_token="new"');self.db.commit();self.assertFalse(guard.revalidate(self.db,context,self.config)['eligible'])
 def test_wrong_database(self):
  d=sqlite3.connect(':memory:');self.addCleanup(d.close);self.assertIn('wrong_canonical_database',guard.capture(d,self.id,self.config)['reason'])
 def test_qualified_and_abandoned_refused(self):
  for state in ('qualified','abandoned'):
   self.db.execute('update processing_outcomes_v2 set status=?',(state,));self.assertRejected('outcome_not_pending')
 def test_owner_zero_and_terminal_owner_refused(self):
  self.db.execute('insert into stage values(?,?,?,?,?)',(self.id,self.ch,'published',0,'{}'));self.assertRejected('residual_or_unknown_owner')
 def test_unknown_table_owner_and_active_state_refused(self):
  self.db.execute('create table unknown_owner(id text,state text,owner_pid integer)');self.db.execute('insert into unknown_owner values(?,?,?)',(self.id,'finished',987));self.assertRejected('residual_or_unknown_owner');self.db.execute('update unknown_owner set owner_pid=NULL,state="weird_running"');self.assertRejected('active_or_unknown_stage')
 def test_all_three_model_generations_protected(self):
  for table in ('harness_queue','harness_queue_v2','harness_queue_v3'):
   self.db.execute('insert into '+table+' values(?,?,?,?,?,?)',(self.id,'running',None,7,'keep','old'));self.assertRejected('active_or_unknown_stage');self.db.execute('delete from '+table)
 def test_nonrunning_model_pid_protected(self):
  self.db.execute('insert into harness_queue_v2 values(?,?,?,?,?,?)',(self.id,'attempt_finished',999,7,'keep','old'));self.assertRejected('residual_or_unknown_owner')
 def test_current_hash_and_source_hash_tamper(self):
  self.change_record(code_sha256='f'*64);self.assertRejected('candidate_code_hash_changed');self.change_record(code_sha256=self.ch,source_image_sha256='f'*64);self.assertRejected('original_image_hash_changed')
 def test_source_manifest_mismatch(self):
  self.input_manifest['code_sha256']='f'*64;self.db.execute('update jobs set input_manifest=?',(encode(self.input_manifest),));self.assertRejected('original_code_hash_changed')
 def test_current_route_becomes_applicable(self):self.change_record(route_on=True);self.assertRejected('deterministic_route_now_applicable')
 def test_new_same_key_terminal_receipt_stays_pending(self):
  self.db.execute('insert into stage values(?,?,?,?,?)',(self.id,self.ch,'no_change_required',None,'{}'));self.assertRejected('frozen_route_receipt_set_changed')
 def test_audit_hash_or_fonts_or_source_failure_refused(self):
  self.audit['checks']['fonts']['all_rendered_fonts_embedded']=False;self.save_audit();self.assertRejected('audit_changed')
 def test_successor_audit_cannot_hide_behind_old(self):
  self.audit['policy']=self.old;self.db.execute('delete from auto_quality_audits_v1');self.save_audit();self.frozen['qa_policy']=self.old;self.frozen['audit_record_sha256']=sha(encode(self.audit).encode());self.install_scope();self.config=self.configure();self.assertTrue(self.result()['eligible']);new=copy.deepcopy(self.audit);new['policy']=self.qpolicy;self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',(self.id,self.ch,self.ih,self.qpolicy,'repair_required',encode(new),'new'));self.assertRejected('successor_current_pair_audit')
 def test_accepted_audit_refused(self):
  self.db.execute('update auto_quality_audits_v1 set state="accepted"');self.assertRejected('audit_changed')
 def test_research_reserved(self):
  self.reservation['ids'][0]=self.id;self.reservation_path.write_text(encode(self.reservation));self.config=self.configure();self.assertRejected('reserved_deterministic_research')
 def test_model_allowlist(self):
  self.model['authorized_model_sample_ids']=[self.id];self.model_path.write_text(encode(self.model));self.config=self.configure();self.assertRejected('reserved_authorized_model_case')
 def test_owner_policy_and_modelpolicy_change_fail_closed(self):
  self.model_path.write_text(encode({**self.model,'new_gateway_enabled':True}));self.assertRejected('identity_changed');self.owner_path.write_text(encode({**self.owner,'pid':99}));self.assertRejected()
 def test_code_pin_change_and_config_forgery(self):
  forged=copy.deepcopy(self.config);forged['quality_policy']='forged';self.assertFalse(guard.capture(self.db,self.id,forged)['eligible']);self.program.write_text('different source');self.assertRejected('implementation_identity_changed')
 def test_new_schema_and_empty_id_table_invalidate_context(self):
  context=self.result();self.assertTrue(context['eligible']);self.db.execute('create table added_empty(id text primary key,state text)');self.db.commit();r=guard.revalidate(self.db,context,self.config);self.assertFalse(r['eligible']);self.assertIn('full_snapshot',r['reason']);self.assertIn('added_empty',r['full_snapshot']['tables'])
 def test_any_historical_row_mutation_invalidates_context(self):
  self.db.execute('insert into stage values(?,?,?,?,?)',(self.id,'e'*64,'finished',None,'old'));context=self.result();self.assertTrue(context['eligible']);self.db.execute('update stage set record="new"');self.db.commit();r=guard.revalidate(self.db,context,self.config);self.assertFalse(r['eligible']);self.assertIn('full_snapshot',r['reason'])
 def test_external_transaction_is_not_committed_or_rolled_back(self):
  self.db.execute('begin');self.assertTrue(guard.capture(self.db,self.id,self.config)['eligible']);self.assertTrue(self.db.in_transaction);self.db.rollback()
 def test_attached_and_temp_schema_fail_closed(self):
  self.db.execute("attach ':memory:' as other");self.assertRejected('attached_database');self.db.execute('detach other');self.db.execute('create temp table fake(x)');self.assertRejected('temporary_schema')
 def test_html_tile_only_is_eligible(self):self.make_html();self.assertTrue(self.result()['eligible'])
 def test_html_predecessor_policy_trigger_gap_is_not_closed(self):
  self.make_html();self.db.execute('insert into auto_quality_exceptions_v1 values(?,?,?,?,?,?,?,?)',(self.id,self.ch,self.ih,self.old,'source_geometry_or_harness','pending','raster_anomaly:local_text_line_ssim_below_0.55','one'));self.assertRejected('current_local_text_repair_or_trigger_gap')
 def test_html_wrapped_alias_is_reachable(self):
  self.make_html();self.db.execute('insert into auto_quality_exceptions_v1 values(?,?,?,?,?,?,?,?)',(self.id,self.ch,self.ih,self.old,'source_geometry_or_harness','pending','source_paint_object_missing','one'));self.assertRejected('current_wrapped_source_repair_available')
if __name__=='__main__':unittest.main(verbosity=2)
