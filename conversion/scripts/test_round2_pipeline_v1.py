"""Pure finite selector/ledger/follower tests; no rendering, server or model API."""
import concurrent.futures,importlib.util,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
spec=importlib.util.spec_from_file_location('round2_pipeline_under_test',Path(__file__).with_name('round2_pipeline_v1.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class Pool:
 def __init__(self,*a,**kw):self.max_workers=kw['max_workers']
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def submit(self,fn,task):
  f=concurrent.futures.Future()
  try:f.set_result(fn(task))
  except BaseException as e:f.set_exception(e)
  return f

class Round2Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.universe=tempfile.TemporaryDirectory();cls.order=Path(cls.universe.name)/'input_order.jsonl'
  with cls.order.open('w') as f:
   for seq in range(1,131905):
    f.write(json.dumps({'seq':seq,'id':'id'+str(seq),'format':'html' if seq==2 else 'svg','category':'poster' if seq==2 else 'scientific_diagram','source_code_sha256':'code','source_image_sha256':'image'},separators=(',',':'))+'\n')
 @classmethod
 def tearDownClass(cls):cls.universe.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.first=self.root/'first';self.first.mkdir();(self.first/'input_order.jsonl').symlink_to(self.order)
  self.run=self.root/'release/round2_fixed_v1/test';self.run.parent.mkdir(parents=True)
  self.patches=[patch.object(p,'R',self.root),patch.object(p,'W',self.root/'conversion'),patch.object(p,'FIRST',self.first),patch.object(p.base,'R',self.root)]
  for x in self.patches:x.start()
  p.initialize(self.run);self.d=sqlite3.connect(self.run/'status.sqlite')
  self.failures=[self.failure(1),self.failure(2)]
  self.write_failed(self.failures)
 def tearDown(self):
  self.d.close()
  for x in reversed(self.patches):x.stop()
  self.tmp.cleanup()
 def failure(self,seq,status='abandoned'):
  return {'seq':seq,'id':'id'+str(seq),'status':status,'source_code_sha256':'code','source_image_sha256':'image','reason':'initial_screen_quality_failed','detail':['poster_object_coverage_mismatch' if seq==2 else 'source_coverage_failure: source_arrow_missing_attached_native_marker']}
 def write_failed(self,rows,final=False):
  (self.first/('failed.jsonl' if final else 'inprogress.failed.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
 def discover(self,ids=(),finished=False,live=True):
  with patch.object(p,'first_status',return_value={'finished':finished,'actual_upstream_live':live}):return p.discover(self.run,self.d,ids)
 def fake_execute(self,task):
  self.dispatched.append(task['id'])
  return {'id':task['id'],'seq':task['seq'],'source_code_sha256':'code','source_image_sha256':'image','status':'abandoned','reason':'expected_test_failure','model_calls':0,'case_cleanup_complete':True}
 def run_mocked(self,preflight=False,ids=(),upstream=None):
  self.dispatched=[];original=Path.read_text
  def read_text(path,*a,**kw):
   if str(path)=='/proc/self/stat':return '1 (python) '+' '.join(['S']+['1']*18+['123'])
   return original(path,*a,**kw)
  if upstream is None:upstream={'finished':True,'actual_upstream_live':False}
  states=list(upstream) if isinstance(upstream,list) else [upstream];calls=[]
  def next_status():
   calls.append(1)
   if len(calls)>20:raise RuntimeError('follower_did_not_finish_with_final_upstream')
   return states.pop(0) if len(states)>1 else states[0]
  with patch.object(p,'implementation',return_value={}),patch.object(p.base,'ensure_pins'),patch.object(p,'execute',side_effect=self.fake_execute),patch.object(p.concurrent.futures,'ProcessPoolExecutor',Pool),patch.object(Path,'read_text',read_text),patch.object(p,'first_status',side_effect=next_status),patch.object(p.time,'sleep'),patch.object(p,'merge_final',return_value={'test_merge_not_part_of_follower_test':True},create=True):
   return p.run_batch(self.run,workers=2,timeout=60,preflight=preflight,selected_ids=ids)
 def test_source_selector(self):self.assertEqual(p.route(self.failure(1),'svg'),['source'])
 def task(self,suffix):return {'id':'id1','seq':1,'source':{'code_sha256':'code','image_sha256':'image'},'work':str(self.root/'conversion/round2_fixed_v1'/suffix),'case_timeout_seconds':60}
 def test_case_timeout_is_failed_not_qualified(self):
  with patch('initial_conversion_process_v1.run',return_value={'cleanup_complete':True,'deadline_exceeded':True,'ok':False}):r=p.execute(self.task('timeout'))
  self.assertEqual(r['status'],'abandoned');self.assertEqual(r['reason'],'round2_whole_case_timeout');self.assertTrue(r['case_cleanup_complete'])
 def test_unclean_tree_halts_further_dispatch(self):
  with patch('initial_conversion_process_v1.run',return_value={'cleanup_complete':False,'deadline_exceeded':True,'ok':False}):r=p.execute(self.task('unclean'))
  self.assertTrue(r['infrastructure_failure']);self.assertEqual(r['reason'],'round2_cleanup_failed')
 def test_missing_process_result_is_typed_failure(self):
  with patch('initial_conversion_process_v1.run',return_value={'cleanup_complete':True,'ok':False}):r=p.execute(self.task('missing'))
  self.assertEqual(r['reason'],'round2_process_failed');self.assertEqual(r['model_calls'],0)
 def test_font_canvas_order(self):
  self.assertEqual(p.route({'detail':['Native content requires full tight canvas','actual_font_portability_requires_embedding']},'python'),['canvas','font'])
 def test_no_repair_for_uncovered_failure(self):self.assertEqual(p.route({'detail':['unsupported_source_graph_profile']},'tikz'),[])
 def test_discovery_unique_and_repeated_snapshot(self):
  self.write_failed(self.failures+[self.failures[0]]);r=self.discover();self.assertEqual(r['new_targets_added'],2);self.assertEqual(self.discover()['new_targets_added'],0)
  self.assertEqual(self.d.execute('select seq,id from samples order by seq').fetchall(),[(1,'id1'),(2,'id2')])
 def test_only_selected_ids_for_preflight_intake(self):
  self.assertEqual(self.discover(['id2'])['new_targets_added'],1);self.assertEqual(self.d.execute('select id from samples').fetchall(),[('id2',)])
 def test_source_hash_change_refused(self):
  r=self.failure(1);r['source_code_sha256']='wrong';self.write_failed([r])
  with self.assertRaises(RuntimeError):self.discover()
 def test_qualified_row_cannot_enter_failed_targets(self):
  self.write_failed([self.failure(1,'qualified')])
  with self.assertRaises(RuntimeError):self.discover()
 def test_wrong_upstream_sequence_refused(self):
  r=self.failure(1);r['seq']=99;self.write_failed([r])
  with self.assertRaises(RuntimeError):self.discover()
 def test_final_file_selected_only_after_finished(self):
  self.write_failed([self.failure(1)]);self.write_failed([self.failure(2)],True)
  self.assertEqual(self.discover()['new_targets_added'],1);self.assertEqual(self.discover(finished=True)['new_targets_added'],1)
 def test_failure_continues_and_upstream_final_exits(self):
  self.discover();self.write_failed(self.failures,True);r=self.run_mocked()
  self.assertTrue(r['finished']);self.assertEqual(self.dispatched,['id1','id2']);self.assertEqual(self.d.execute('select attempts from samples order by seq').fetchall(),[(1,),(1,)])
 def test_preflight_then_main_does_not_redispatch(self):
  self.discover();self.run_mocked(True,['id1']);self.assertEqual(self.dispatched,['id1']);self.write_failed(self.failures,True)
  r=self.run_mocked();self.assertTrue(r['finished']);self.assertEqual(self.dispatched,['id2'])
 def test_live_upstream_idle_then_new_final_targets(self):
  self.write_failed([]);self.discover();self.write_failed(self.failures,True)
  r=self.run_mocked(upstream=[{'finished':False,'actual_upstream_live':True},{'finished':True,'actual_upstream_live':False},{'finished':True,'actual_upstream_live':False},{'finished':True,'actual_upstream_live':False}])
  self.assertTrue(r['finished']);self.assertEqual(self.dispatched,['id1','id2'])
 def test_dead_unfinished_upstream_stops_without_false_completion(self):
  self.write_failed([]);self.discover();r=self.run_mocked(upstream={'finished':False,'actual_upstream_live':False})
  self.assertFalse(r['finished']);self.assertTrue((self.run/'infrastructure_stop.json').exists());self.assertEqual(self.dispatched,[])
 def test_already_running_requires_explicit_tree_cleanup(self):
  self.discover();p.base.claim(self.d,1)
  with self.assertRaises(RuntimeError):p.run_batch(self.run,workers=1,timeout=60)
if __name__=='__main__':unittest.main()
