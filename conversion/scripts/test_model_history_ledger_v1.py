import copy,json,tempfile,unittest,tarfile,sqlite3
from pathlib import Path
import model_history_ledger_v1 as h

ID='a'*64
IDENTITY=h.identity_for_ids([ID])
USAGE={'inputTokens':10,'outputTokens':20,'cacheReadTokens':30,'cacheWriteTokens':4,'totalTokens':64}


def event(kind,seq,data=None,session='s'):
 return {'params':{'sessionId':session,'event':{'type':kind,'seq':seq,'time':1000000000000+seq,'data':data or {}}}}


def fixture(usage=USAGE,retry=False):
 c=h.Collector();frames=[event('turn/start',1,{'turn':1}),event('step/start',2,{'turn':1,'step':1}),event('request/header',3)]
 if retry:frames.extend([event('llm/retry',4,{'turn':1,'step':1,'retry':1}),event('llm/retry-started',5,{'turn':1,'step':1,'retry':1})])
 frames.append(event('assistant/message',6,{'turn':1,'step':1,'message':{'id':'m','role':'assistant'},'usage':usage,'stream':[]}));c.add_events(map(json.dumps,frames),'/g/call/events.jsonl','/g',IDENTITY,call_group='/g/call');return c


class UsageTests(unittest.TestCase):
 def test_installed_dsh_input_already_excludes_cache(self):
  x=h.normalize_usage(USAGE);self.assertEqual([x[k] for k in h.TOKEN_FIELDS],[10,30,4,20]);self.assertEqual(x['known_token_sum'],64);self.assertFalse(x['usage_unknown'])
 def test_anthropic_cache_is_additive_and_thinking_not_added(self):
  x=h.normalize_usage({'input_tokens':10,'cache_read_input_tokens':30,'cache_creation_input_tokens':4,'output_tokens':20,'reasoning_tokens':8});self.assertEqual(x['known_token_sum'],64);self.assertEqual(x['output_including_reasoning'],20);self.assertEqual(x['reasoning_tokens'],8)
 def test_deepseek_prompt_hit_miss_and_reasoning(self):
  x=h.normalize_usage({'prompt_tokens':100,'prompt_cache_hit_tokens':80,'prompt_cache_miss_tokens':20,'completion_tokens':50,'completion_tokens_details':{'reasoning_tokens':30},'total_tokens':150});self.assertEqual(x['input_uncached'],20);self.assertEqual(x['cache_read'],80);self.assertEqual(x['known_token_sum'],150);self.assertEqual(x['output_including_reasoning'],50)
 def test_missing_or_inconsistent_usage_is_unknown(self):
  self.assertIn('usage_missing',h.normalize_usage(None)['issues']);bad=dict(USAGE,totalTokens=999);self.assertTrue(h.normalize_usage(bad)['usage_unknown'])


class HistoryTests(unittest.TestCase):
 def save(self,c,db,jobs=None):return h.persist(db,c,h.reconcile(c),jobs or {ID:{'state':'needs_quality_repair'}})
 def test_export_and_persistent_event_mirrors_count_one(self):
  c=fixture();data=c.serialize();c.merge(data)
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';summary,_=self.save(c,db);row=h.lookup_sample_budget(ID,db);self.assertEqual(summary['confirmed_response_calls'],1);self.assertEqual(row['conservative_budget_used'],1);self.assertEqual(row['tokens']['input_uncached'],10)
 def test_call_aggregate_is_checksum_not_another_call(self):
  c=fixture();c.add_meta('/g/call/call.json',{'usage':USAGE},'/g',IDENTITY);r=h.reconcile(c);self.assertEqual(len(r['responses']),1);self.assertTrue(r['aggregate_checks'][0]['usage_matches_responses'])
 def test_actual_retry_keeps_unknown_failed_attempt(self):
  c=fixture(retry=True)
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.save(c,db);row=h.lookup_sample_budget(ID,db);self.assertEqual(row['confirmed_calls'],1);self.assertEqual(row['unknown_reservations'],1);self.assertEqual(row['remaining_calls'],0)
 def test_scheduled_retry_without_started_is_not_extra_send(self):
  c=h.Collector();frames=[event('step/start',1,{'turn':1,'step':1}),event('request/context',2),event('llm/retry',3,{'turn':1,'step':1,'retry':1})];c.add_events(map(json.dumps,frames),'f','/g',IDENTITY);r=h.reconcile(c);self.assertEqual(len(r['requests']),1);self.assertEqual(r['retry_started'],0)
 def test_proven_blocked_prompt_not_charged_or_reserved(self):
  c=h.Collector();c.register_identity('/g',IDENTITY);c.prompts=[{'artifact':'/g/round1_generate/prompt.txt','call_group':'/g/round1_generate','group':'/g','mtime':1}];c.blocked=[{'group':'/g','session_id':'round1_generate-uuid','kind':'blocked_prompt','time':2}]
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';summary,_=self.save(c,db);row=h.lookup_sample_budget(ID,db);self.assertEqual(row['confirmed_calls'],0);self.assertEqual(row['unknown_reservations'],0);self.assertEqual(summary['proven_blocked_local_requests'],1)
 def test_aggregate_only_locks_unknown_multiplicity(self):
  c=h.Collector();c.add_meta('/g/call/call.json',{'usage':USAGE},'/g',IDENTITY)
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.save(c,db);row=h.lookup_sample_budget(ID,db);self.assertTrue(row['unknown_usage']);self.assertFalse(row['eligible_for_new_call']);self.assertEqual(row['unknown_reservations'],1)
 def test_prompt_with_null_session_aggregate_reservation(self):
  c=fixture();c.add_meta('/g/call/call.json',{'usage':dict(USAGE,inputTokens=999)},'/g',IDENTITY);c.prompts=[{'artifact':'/g/another/prompt.txt','call_group':'/g/another','group':'/g','mtime':1}];c.blocked=[{'group':'/g','session_id':None,'kind':'blocked_fetch','time':2}]
  r=h.reconcile(c);self.assertEqual(len(r['responses']),1);self.assertEqual(sum(q['status']=='unresolved' for q in r['requests'].values()),2)
 def test_archive_appledouble_is_not_sdk_event_stream(self):
  good=tarfile.TarInfo('sdk_home/sessions/project/session/session.v4.jsonl.zstd');good.type=tarfile.REGTYPE
  bad=tarfile.TarInfo('sdk_home/sessions/project/session/._session.v4.jsonl.zstd');bad.type=tarfile.REGTYPE
  self.assertTrue(h.is_sdk_session_member(good));self.assertFalse(h.is_sdk_session_member(bad))
 def test_recovered_same_bytes_clears_only_artifact_read_uncertainty(self):
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';c=fixture();c.artifacts=[{'artifact':'bad.tar.gz','sha256':'x','size':10,'stable':True,'errors':['parser_error'],'group':'/g'}];c.problems=[{'reason':'artifact_read_failed','artifact':'bad.tar.gz','group':'/g'}];self.save(c,db);self.assertEqual(h.lookup_sample_budget(ID,db)['unknown_reservations'],1)
   c=fixture();c.artifacts=[{'artifact':'bad.tar.gz','sha256':'x','size':10,'stable':True,'errors':[],'group':'/g'}];self.save(c,db);self.assertEqual(h.lookup_sample_budget(ID,db)['unknown_reservations'],0)
 def test_replacement_bytes_do_not_clear_unknown_lost_history(self):
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';c=fixture();c.artifacts=[{'artifact':'bad.tar.gz','sha256':'x','size':10,'stable':True,'errors':['parser_error'],'group':'/g'}];c.problems=[{'reason':'artifact_read_failed','artifact':'bad.tar.gz','group':'/g'}];self.save(c,db)
   c=fixture();c.artifacts=[{'artifact':'bad.tar.gz','sha256':'changed','size':10,'stable':True,'errors':[],'group':'/g'}];self.save(c,db);self.assertEqual(h.lookup_sample_budget(ID,db)['unknown_reservations'],1)
 def test_corrupt_history_is_not_zero_budget(self):
  c=h.Collector();c.register_identity('/g',IDENTITY);c.problems=[{'reason':'artifact_read_failed','group':'/g','artifact':'f'}]
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.save(c,db);row=h.lookup_sample_budget(ID,db);self.assertEqual(row['unknown_reservations'],1);self.assertGreaterEqual(row['conservative_budget_used'],2);self.assertFalse(row['coverage_complete_for_id'])
 def test_reimport_is_idempotent_and_never_forgets_removed_raw_history(self):
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.save(fixture(),db);a=h.lookup_sample_budget(ID,db);self.save(fixture(),db);b=h.lookup_sample_budget(ID,db);self.assertEqual(a['tokens'],b['tokens']);self.assertEqual(b['confirmed_calls'],1);self.save(h.Collector(),db);c=h.lookup_sample_budget(ID,db);self.assertEqual(c['confirmed_calls'],1);self.assertEqual(c['tokens'],a['tokens'])
 def test_late_usage_resolves_unknown_response_same_identity(self):
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.save(fixture(None),db);self.assertEqual(h.lookup_sample_budget(ID,db)['unknown_reservations'],1);self.save(fixture(),db);row=h.lookup_sample_budget(ID,db);self.assertEqual(row['confirmed_calls'],1);self.assertEqual(row['unknown_reservations'],0)
 def test_missing_ledger_and_unknown_id_fail_closed(self):
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.assertFalse(h.lookup_sample_budget(ID,db)['eligible_for_new_call']);self.save(fixture(),db);row=h.lookup_sample_budget('unknown',db);self.assertFalse(row['coverage_complete_for_id']);self.assertEqual(row['conservative_budget_used'],2)
 def test_trusted_qualified_is_never_eligible(self):
  with tempfile.TemporaryDirectory() as p:
   db=Path(p)/'ledger.sqlite';self.save(fixture(),db,{ID:{'state':'accepted','qualified':True,'processing_outcome':'qualified'}});self.assertFalse(h.lookup_sample_budget(ID,db)['eligible_for_new_call'])
 def test_current_qa_policy_suffix_and_revision_binding(self):
  with tempfile.TemporaryDirectory() as p:
   root=Path(p);(root/'conversion').mkdir();db=sqlite3.connect(root/'conversion/jobs.sqlite');db.executescript('create table jobs(id,state,error,input_record,output_record);create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at);');db.execute('insert into jobs values(?,?,?,?,?)',(ID,'needs_quality_repair','',json.dumps({'image_sha256':'sourceimg','code_sha256':'sourcecode'}),json.dumps({'quality_state':'needs_repair','code_sha256':'currentcode','image_sha256':'currentimg'})));policy='source_execution_glyph_lineage_native_render_and_local_fidelity_v3:hash';db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',(ID,'currentcode','currentimg',policy,'repair_required',json.dumps({'failures':['geometry']}),'at'));db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',(ID,'oldercode','currentimg',policy,'repair_required',json.dumps({'failures':['old']}),'at'));db.commit();db.close();row=h.load_jobs(root)[ID];self.assertEqual(len(row['same_revision_failed_qa']),1);self.assertTrue(row['same_revision_failed_qa'][0]['current_v3_policy'])


if __name__=='__main__':unittest.main()
