import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tikz_closed_paint_pending_publication_v1 as p
class CASTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=sqlite3.connect(':memory:',isolation_level=None);self.db.execute('create table jobs(id text primary key,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)');self.db.execute('create table processing_outcomes_v2(id text primary key,category text,format text,source_code_hash text,source_image_hash text,status text,reason text,record text,updated_at text)');self.db.execute('create table stages(id text,state text,owner_pid integer,record text)');self.db.execute('create table harness_queue_v3(id text,state text,attempts integer,worker_pid integer)');self.db.execute('create table model_usage_events_v2(id text,event text,amount integer)');self.db.execute('create table auto_quality_dirty_v2(id text primary key,version integer,payload_version integer)');self.db.execute('create trigger dirty_payload after update of output_record on jobs begin insert into auto_quality_dirty_v2 values(new.id,1,1) on conflict(id) do update set version=version+1,payload_version=payload_version+1;end');self.db.execute('create trigger dirty_update after update on jobs begin insert into auto_quality_dirty_v2 values(new.id,1,0) on conflict(id) do update set version=version+1;end');self.original={'pair_sha256':'id','category':'scientific_diagram','format':'tikz','source':'provider','code_sha256':'source-code','image_sha256':'source-image'};self.manifest={'id':'id','source_format':'tikz','code_sha256':'source-code','image_sha256':'source-image'};self.db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)',('id','scientific_diagram','tikz','provider',json.dumps(self.original),'initial_conversion_deferred_v1','tikz',2,'before',None,'runtime',json.dumps(self.manifest),None));self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)',('id','scientific_diagram','tikz','source-code','source-image','pending','prior','budget-history','before'));self.db.execute('insert into stages values(?,?,?,?)',('id','deferred_recovery_tier',None,'unowned historical receipt'));self.db.execute('insert into model_usage_events_v2 values(?,?,?)',('id','historical-call',2));self.db.execute('insert into auto_quality_dirty_v2 values(?,?,?)',('id',5,7));self.record={'id':'id','source_pair_sha256':'id','source':'provider','category':'scientific_diagram','source_format':'tikz','source_record':self.original,'source_code_sha256':'source-code','source_image_sha256':'source-image','quality_state':'pending_fixture_private_tests_only','accepted':False,'model_calls':0};clean=self.root/'clean';clean.mkdir();payloads={'original_source':b'fixture-source','original_reference':b'fixture-reference','baseline_pdf':b'%PDF-fixture','projected_svg':b'<svg/>','code':b'<mxfile/>','image':b'fixture-native'};entries={}
  for name,raw in payloads.items():
   path=clean/name;path.write_bytes(raw);entries[name]={'file':'clean/'+name,'sha256':p.sha(raw)}
  self.original.update(code_sha256=entries['original_source']['sha256'],image_sha256=entries['original_reference']['sha256']);self.manifest.update(code_sha256=self.original['code_sha256'],image_sha256=self.original['image_sha256'],source_code='clean/original_source',reference_image='clean/original_reference');self.record.update(format='drawio',source_code_sha256=self.original['code_sha256'],source_image_sha256=self.original['image_sha256']);self.db.execute('update jobs set input_record=?,input_manifest=?',(json.dumps(self.original),json.dumps(self.manifest)));self.db.execute('update processing_outcomes_v2 set source_code_hash=?,source_image_hash=?',(self.original['code_sha256'],self.original['image_sha256']));self.db.execute('update auto_quality_dirty_v2 set version=5,payload_version=7')
  manifest={'version':p.bundle.VERSION,'id':'id','source_code_sha256':self.original['code_sha256'],'source_image_sha256':self.original['image_sha256'],'files':{k:entries[k] for k in ('original_source','original_reference','baseline_pdf','projected_svg')}};raw=p.canonical(manifest);(clean/'manifest.json').write_bytes(raw);self.record[p.bundle.FIELD]={'version':1,'file':'clean/manifest.json','sha256':p.sha(raw)}
  for field,name,digest in [('code_file','code','code_sha256'),('image_file','image','image_sha256'),('original_source_code','original_source','source_code_sha256'),('original_reference','original_reference','source_image_sha256'),('source_render_pdf','baseline_pdf','source_render_pdf_sha256'),('source_render_svg','projected_svg','source_render_svg_sha256')]:self.record[field]=entries[name]['file'];self.record[digest]=entries[name]['sha256']
  self.rf=self.root/'record.json';self.rf.write_bytes(p.canonical(self.record));self.qf=self.root/'quality.json';self.qf.write_text(json.dumps({'implementation_pins':{}}));self.files={str(self.rf):p.sha(self.rf.read_bytes()),str(self.qf):p.sha(self.qf.read_bytes()),**{str(self.root/e['file']):e['sha256'] for e in entries.values()},str(clean/'manifest.json'):p.sha(raw)};self.stub=patch.object(p,'file_preflight',return_value=self.files);self.stub.start();self.result={'id':'id','record':self.record};self.plan=p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root)
 def tearDown(self):self.stub.stop();self.db.close();self.tmp.cleanup()
 def dump(self):return list(self.db.iterdump())
 def test_rollback_default_preserves_every_row_and_budget(self):
  before=self.dump();r=p.publish_pending(self.db,self.plan);self.assertEqual(r['state'],'validated_rollback');self.assertEqual(self.dump(),before);self.assertFalse(r['accepted'])
 def test_private_apply_exactly_once_only_jobs_and_dirty_change(self):
  outcome=self.db.execute('select * from processing_outcomes_v2').fetchall();stage=self.db.execute('select * from stages').fetchall();calls=self.db.execute('select * from model_usage_events_v2').fetchall();r=p.publish_pending(self.db,self.plan,apply=True);self.assertTrue(r['published']);self.assertFalse(r['accepted']);self.assertEqual(self.db.execute('select attempts,worker_pid,state from jobs').fetchone(),(2,None,p.TARGET_STATE));self.assertEqual(self.db.execute('select * from processing_outcomes_v2').fetchall(),outcome);self.assertEqual(self.db.execute('select * from stages').fetchall(),stage);self.assertEqual(self.db.execute('select * from model_usage_events_v2').fetchall(),calls);self.assertEqual(self.db.execute('select version,payload_version from auto_quality_dirty_v2').fetchone(),(7,8));before=self.dump();again=p.publish_pending(self.db,self.plan,apply=True);self.assertTrue(again['already_published']);self.assertEqual(self.dump(),before)
 def test_foreign_job_lease_after_plan_not_overwritten(self):
  self.db.execute('update jobs set worker_pid=999 where id="id"');before=self.dump();r=p.publish_pending(self.db,self.plan,apply=True);self.assertFalse(r['published']);self.assertEqual(self.dump(),before)
 def test_stage_owner_or_queue_race_after_plan_rejected(self):
  for sql in ('update stages set state="running",owner_pid=999','insert into harness_queue_v3 values("id","running",2,999)'):
   base=self.db;self.db=sqlite3.connect(':memory:',isolation_level=None);base.backup(self.db)
   try:
    self.db.execute(sql);before=self.dump();r=p.publish_pending(self.db,self.plan,apply=True);self.assertFalse(r['published']);self.assertEqual(self.dump(),before)
   finally:self.db.close();self.db=base
 def test_source_history_or_outcome_race_is_full_row_CAS(self):
  for sql in ('insert into model_usage_events_v2 values("id","new-history",1)','update processing_outcomes_v2 set status="abandoned"','update stages set record="changed terminal receipt"'):
   base=self.db;self.db=sqlite3.connect(':memory:',isolation_level=None);base.backup(self.db)
   try:
    self.db.execute(sql);before=self.dump();r=p.publish_pending(self.db,self.plan,apply=True);self.assertFalse(r['published']);self.assertEqual(self.dump(),before)
   finally:self.db.close();self.db=base
 def test_full_schema_new_stage_even_without_rows_rejected(self):
  self.db.execute('create table new_stage(id text,state text)');r=p.publish_pending(self.db,self.plan,apply=True);self.assertFalse(r['published']);self.assertIn('schema',r['reason'])
 def test_unknown_non_id_owner_schema_is_not_ignored(self):
  self.db.execute('create table unknown_leases(task text,pid integer)')
  with self.assertRaisesRegex(ValueError,'unclassified tables'):p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root)
 def test_prepared_plan_cannot_overwrite_runnable_model_queue(self):
  self.db.execute('insert into harness_queue_v3 values("id","queued",2,null)')
  with self.assertRaisesRegex(ValueError,'queue'):p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root)
 def test_unrelated_initial_conversion_aggregate_progress_does_not_own_this_case(self):
  self.db.execute('create table initial_conversion_runs_v1(run_id text,stage text,quota int,claimed int,policy text,publish int,created_at text)');self.db.execute('insert into initial_conversion_runs_v1 values("other","native",10,0,"p",1,"before")');plan=p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root);self.db.execute('update initial_conversion_runs_v1 set claimed=1');r=p.publish_pending(self.db,plan,apply=True);self.assertTrue(r['published']);self.assertEqual(self.db.execute('select claimed from initial_conversion_runs_v1').fetchone()[0],1)
 def test_global_model_policy_is_still_bound(self):
  self.db.execute('create table model_policy_v1(key text,value text)');self.db.execute('insert into model_policy_v1 values("lifetime","2")');plan=p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root);self.db.execute('update model_policy_v1 set value="3"');r=p.publish_pending(self.db,plan,apply=True);self.assertFalse(r['published'])
 def test_prepared_publication_retains_logical_source_ownership(self):
  self.db.execute('update stages set state="prepared_waiting_publication"')
  with self.assertRaises(ValueError):p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root)
 def test_unknown_nonterminal_owner_is_not_treated_as_free(self):
  self.db.execute('update stages set state="new_stage_state",owner_pid=123')
  with self.assertRaisesRegex(ValueError,'unverified terminal owner'):p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root)
 def test_held_queue_history_is_preserved_byte_for_byte(self):
  self.db.execute('insert into harness_queue_v3 values("id","held_by_user_patch_only_policy",2,null)');plan=p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root);before=self.db.execute('select * from harness_queue_v3').fetchall();r=p.publish_pending(self.db,plan,apply=True);self.assertTrue(r['published']);self.assertEqual(self.db.execute('select * from harness_queue_v3').fetchall(),before)
 def test_plan_or_metadata_mutation_rejected(self):
  plan=copy.deepcopy(self.plan);plan['record']['model_calls']=1
  with self.assertRaisesRegex(ValueError,'damaged'):p.publish_pending(self.db,plan,apply=True)
  self.rf.write_bytes(b'changed')
  with self.assertRaises(ValueError):p.publish_pending(self.db,self.plan,apply=True)
 def test_failure_before_commit_rolls_back_entire_pending_pointer(self):
  outer=self
  class Fail:
   def __getattr__(self,n):return getattr(outer.db,n)
   def commit(self):raise sqlite3.OperationalError('injected commit failure')
  before=self.dump();r=p.publish_pending(Fail(),self.plan,apply=True);self.assertFalse(r['published']);self.assertEqual(self.dump(),before)
 def test_unknown_commit_result_is_recovered_by_exact_pending_pointer(self):
  outer=self
  class After:
   def __getattr__(self,n):return getattr(outer.db,n)
   def commit(self):outer.db.commit();raise sqlite3.OperationalError('injected lost receipt after commit')
  r=p.publish_pending(After(),self.plan,apply=True);self.assertTrue(r['published']);self.assertEqual(r['state'],'publication_commit_receipt_recovered');self.assertEqual(self.db.execute('select attempts from jobs').fetchone()[0],2)
 def test_nonbusy_SQL_error_is_not_retried(self):
  outer=self;calls=[]
  class Denied:
   def __getattr__(self,n):return getattr(outer.db,n)
   def execute(self,sql,*args):
    if sql=='begin immediate':calls.append(sql);raise sqlite3.OperationalError('permission denied')
    return outer.db.execute(sql,*args)
  r=p.publish_pending(Denied(),self.plan,apply=True);self.assertFalse(r['published']);self.assertEqual(len(calls),1);self.assertIn('permission denied',r['reason'])
 def test_foreign_published_or_publication_failed_owner_is_not_terminal_authority(self):
  for state in ('published','publication_failed'):
   self.db.execute('update stages set state=?,owner_pid=123',(state,))
   with self.assertRaisesRegex(ValueError,'unverified terminal owner'):p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root)
 def test_no_content_hash_or_fsync_is_called_in_the_writer_transaction(self):
  original=Path.read_bytes;witness=p.shared.file_witness;sync=p.os.fsync;outer=self
  def read(path):
   if outer.db.in_transaction:raise AssertionError('content read in SQL writer')
   return original(path)
  def hash_outside(*a,**kw):
   if outer.db.in_transaction:raise AssertionError('file_witness in SQL writer')
   return witness(*a,**kw)
  def sync_outside(fd):
   if outer.db.in_transaction:raise AssertionError('fsync in SQL writer')
   return sync(fd)
  with patch.object(Path,'read_bytes',read),patch.object(p.shared,'file_witness',side_effect=hash_outside),patch.object(p.os,'fsync',side_effect=sync_outside):r=p.publish_pending(self.db,self.plan,apply=True)
  self.assertTrue(r['published'])
 def alias_plan(self,ancestor=False):
  base=self.root/'conversion';base.mkdir(exist_ok=True);a=base/'a';b=base/'b';a.mkdir();b.mkdir();(a/'source.tex').write_bytes(b'fixture-source');(b/'source.tex').write_bytes(b'fixture-source');link=base/'alias'
  if ancestor:link.symlink_to(a,target_is_directory=True);logical='conversion/alias/source.tex'
  else:link.symlink_to(a/'source.tex');logical='conversion/alias'
  self.manifest['source_code']=logical;self.db.execute('update jobs set input_manifest=?',(json.dumps(self.manifest),));self.db.execute('update auto_quality_dirty_v2 set version=5,payload_version=7');plan=p.prepare_plan(self.db,self.result,self.qf,self.rf,root=self.root);return plan,link,(b if ancestor else b/'source.tex')
 def test_same_bytes_source_symlink_retarget_after_preparation_rejected(self):
  plan,link,target=self.alias_plan();link.unlink();link.symlink_to(target)
  with self.assertRaises(Exception):p.publish_pending(self.db,plan,apply=True)
  self.assertIsNone(self.db.execute('select output_record from jobs').fetchone()[0])
 def test_same_bytes_source_ancestor_retarget_during_admission_rejected(self):
  plan,link,target=self.alias_plan(True);outer=self
  class Retarget:
   def __getattr__(self,n):return getattr(outer.db,n)
   def execute(self,sql,*args):
    if sql=='begin immediate':link.unlink();link.symlink_to(target,target_is_directory=True)
    return outer.db.execute(sql,*args)
  r=p.publish_pending(Retarget(),plan,apply=True);self.assertFalse(r['published']);self.assertIsNone(self.db.execute('select output_record from jobs').fetchone()[0])
 def test_caller_writer_transaction_not_reused(self):
  self.db.execute('begin immediate')
  with self.assertRaisesRegex(ValueError,'owns its short'):p.publish_pending(self.db,self.plan,apply=True)
  self.db.rollback()
if __name__=='__main__':unittest.main()
