import json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import tikz_execution_parallel_supervisor_v1 as m
from test_tikz_execution_candidate_batch_v1 import schema,add


def fixture(db,identifier):
 old=add(db,identifier);db.execute('create table if not exists processing_outcomes_v2(id primary key,status)');db.execute('insert into processing_outcomes_v2 values(?,?)',(identifier,'pending'));db.commit();return old


def unsupported(current,policy,files,publish):
 time.sleep(.15);return None,None,{'id':current['id'],'policy':policy,'state':'unsupported_source','error':'Unsupported synthetic semantic fixture','accepted':False,'previous_candidate_retained':True}

class Admission(unittest.TestCase):
 def setUp(self):self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close);schema(self.db);fixture(self.db,'one')
 def test_only_pending_outcomes_selected(self):
  fixture(self.db,'abandoned');self.db.execute("update processing_outcomes_v2 set status='abandoned' where id='abandoned'");self.db.commit();self.assertEqual(m.shortlist(self.db,'policy','run',False),['one'])
 def test_model_owner_blocks_even_without_running_label(self):
  self.db.execute("update harness_queue_v3 set worker_pid=9 where id='one'");self.db.commit();self.assertEqual(m.shortlist(self.db,'policy','run',False),[])
 def test_same_policy_terminal_never_replayed(self):
  selection=m.selection(self.db,'policy','one');claim=m.base.claim(self.db,selection,'policy','one',pid=12);m.base.finish(self.db,claim,{'state':'unsupported_source','accepted':False});self.assertEqual(m.shortlist(self.db,'policy','two',False),[])
 def test_other_actor_running_claim_never_taken(self):
  selection=m.selection(self.db,'policy','one');self.assertIsNotNone(m.base.claim(self.db,selection,'policy','one',pid=12));self.assertIsNone(m.selection(self.db,'policy','two'))
 def test_validated_dry_run_publish_requires_explicit_mode(self):
  selection=m.selection(self.db,'policy','one');claim=m.base.claim(self.db,selection,'policy','one',pid=12);m.base.finish(self.db,claim,{'accepted':False},{'synthetic':True});self.assertEqual(m.shortlist(self.db,'policy','two',False),[]);self.assertEqual(m.shortlist(self.db,'policy','two',True),['one'])
 def test_outcome_change_after_claim_restores_without_generate(self):
  prior=m.base.snapshot(self.db,'one');claim=m.base.claim(self.db,m.selection(self.db,'policy','one'),'policy','one',pid=12);self.db.execute("update processing_outcomes_v2 set status='abandoned'");self.db.commit();called=[]
  stage,_,_=m.generate_one(self.db,claim,'policy',{},False,lambda *a:called.append(a));self.assertEqual(stage,'cancelled_registered_outcome');self.assertFalse(called);self.assertEqual(m.base.snapshot(self.db,'one'),prior)
 def test_outcome_changes_during_generation_cancel_new_pointer(self):
  prior=m.base.snapshot(self.db,'one');claim=m.base.claim(self.db,m.selection(self.db,'policy','one'),'policy','one',pid=12)
  def generator(*args):self.db.execute("update processing_outcomes_v2 set status='abandoned'");self.db.commit();return None,{'candidate':True},{'accepted':False}
  with patch.object(m.base,'ensure_implementation'):
   stage,_,_=m.generate_one(self.db,claim,'policy',{},False,generator)
  self.assertEqual(stage,'cancelled_registered_outcome');self.assertEqual(m.base.snapshot(self.db,'one'),prior);self.assertEqual(self.db.execute('select status from processing_outcomes_v2').fetchone()[0],'abandoned')
 def test_late_model_owner_preserved(self):
  prior=m.base.snapshot(self.db,'one');claim=m.base.claim(self.db,m.selection(self.db,'policy','one'),'policy','one',pid=12)
  def generator(*args):self.db.execute('update harness_queue_v3 set worker_pid=99');self.db.commit();return None,{'candidate':True},{'accepted':False}
  with patch.object(m.base,'ensure_implementation'):
   stage,_,_=m.generate_one(self.db,claim,'policy',{},False,generator)
  self.assertEqual(stage,'deferred_model_running');self.assertEqual(m.base.snapshot(self.db,'one'),prior);self.assertEqual(self.db.execute('select worker_pid from harness_queue_v3').fetchone()[0],99)

class Parallel(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.path=self.root/'jobs.sqlite';db=sqlite3.connect(self.path);schema(db)
  for identifier in ('one','two','three'):fixture(db,identifier)
  self.before=m.canonical_snapshot(db,['one','two','three']);db.close()
 def run_pool(self,**kwargs):
  with patch.object(m.base,'ensure_implementation'),patch.object(m.base,'W',self.root):return m.run_workers(self.path,'policy',{},workers=2,limit=2,generator=unsupported,**kwargs)
 def test_two_workers_total_limit_is_two_not_four(self):
  result=self.run_pool();self.assertEqual(result['total_claims'],2);self.assertEqual(result['observed_max_active'],2);self.assertTrue(all(code==0 for code in result['worker_exits'].values()));db=sqlite3.connect(self.path);self.assertEqual(m.canonical_snapshot(db,['one','two','three']),self.before);self.assertEqual(db.execute('select count(*) from '+m.base.TABLE).fetchone()[0],2);self.assertEqual(db.execute('select count(distinct claim_token) from '+m.base.TABLE).fetchone()[0],2);db.close()
 def test_existing_original_actor_and_two_extras_never_share_case(self):
  db=sqlite3.connect(self.path);existing=m.base.claim(db,m.selection(db,'policy','original_watch'),'policy','original_watch',pid=999);owned=m.base.snapshot(db,existing['id']);db.close()
  result=self.run_pool();self.assertEqual(result['total_claims'],2);db=sqlite3.connect(self.path);self.assertEqual(m.base.snapshot(db,existing['id']),owned);self.assertEqual(db.execute('select count(*) from '+m.base.TABLE).fetchone()[0],3);self.assertEqual(db.execute("select count(*) from "+m.base.TABLE+" where state='running'").fetchone()[0],1);db.close()
 def test_second_same_policy_run_processes_only_remaining_revision(self):
  self.run_pool();result=self.run_pool();self.assertEqual(result['total_claims'],1)
 def test_existing_drain_does_not_claim(self):
  control=self.root/'control.json';control.write_text('{"drain":true}');result=self.run_pool(control=control);self.assertEqual(result['total_claims'],0);self.assertTrue(result['drained'])
 def test_invalid_workers_and_unbounded_finite_mode_rejected(self):
  with self.assertRaises(ValueError):m.run_workers(self.path,'policy',{},workers=3)
  with self.assertRaises(ValueError):m.run_workers(self.path,'policy',{},workers=2,limit=0,watch=False)
 def test_production_requires_exact_receipt_before_touching_database(self):
  with patch.object(m.base,'W',self.root):
   with self.assertRaises(FileNotFoundError):m.production_preflight('policy',2)
 def test_only_this_supervisor_lock_name_is_new(self):
  source=Path(m.__file__).read_text();self.assertNotIn("/'tikz_execution_candidate_watch_v1_owner.json'",source);self.assertNotIn("/'tikz_execution_candidate_v1_owner.json'",source)

if __name__=='__main__':unittest.main()
