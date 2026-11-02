"""Isolated full-revision/model ownership, bounded retry and immutable publication."""
import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tikz_execution_candidate_batch_v1 as b

POLICY='isolated-execution-policy'


def schema(db):
 db.execute('create table jobs(id text primary key,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)')
 for table in b.MODEL_TABLES:db.execute('create table '+table+'(id text primary key,state text,attempts integer,worker_pid integer,heartbeat text)')
 db.commit();b.init(db)


def add(db,id='case',state='needs_quality_repair',worker=None,model=None,old=None):
 old=old or {'id':id,'source_format':'tikz','source_code_sha256':'source-code','source_image_sha256':'source-image','code_sha256':'old-code','image_sha256':'old-image','code_file':'clean/case/old.drawio','image_file':'clean/case/old.png','source_render_pdf':'clean/case/source.pdf','source_render_svg':'clean/case/source.svg','edges':0}
 db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,'diagram','tikz','fixture','input-json',state,'tikz',7,'prior-time',json.dumps(old),'prior-error','manifest-json',worker))
 for table in b.MODEL_TABLES:db.execute('insert into '+table+' values(?,?,?,?,?)',(id,model or 'attempt_finished',5,987 if model=='running' else None,'prior-heart'))
 db.commit();return old


def get_claim(db,run='run-one',publish=False,retry=False):return b.claim(db,b.select_candidate(db,POLICY,run,publish,retry),POLICY,run,publish,retry,pid=123)


class StateTests(unittest.TestCase):
 def test_broader_batch_and_publish_require_this_exact_smoke_policy(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(b,'W',Path(temp)):
   b.require_bounded_smoke(POLICY,False,1,3)
   with self.assertRaises(FileNotFoundError):b.require_bounded_smoke(POLICY,True,1,1)
   receipt={'ok':True,'published':False,'accepted':0,'summary':{'policy':POLICY},'all_selected_job_snapshots_exactly_restored':True,'all_model_queue_rows_unchanged':True,'all_source_and_native_pair_hashes_unchanged':True,'source_profile_v3_api_tests':{'relocated_actual_proof_bundle_passed':True},'state_and_rollback_tests':{'ok':True}};(Path(temp)/'tikz_execution_candidate_v1_smoke.json').write_text(json.dumps(receipt));b.require_bounded_smoke(POLICY,True,2,100)
   with self.assertRaises(ValueError):b.require_bounded_smoke(POLICY+'-changed',True,1,1)
 def test_idle_selection_excludes_accepted_busy_and_running_model(self):
  d=sqlite3.connect(':memory:');schema(d);add(d,'accepted',state='accepted');add(d,'busy',worker=99);add(d,'paid',model='running');add(d,'eligible');self.assertEqual(b.select_candidate(d,POLICY,'one')[0],'eligible')
 def test_every_snapshot_column_is_compared_and_swapped(self):
  for column in b.SNAPSHOT_COLUMNS.split(','):
   with self.subTest(column=column):
    d=sqlite3.connect(':memory:');schema(d);add(d);selection=b.select_candidate(d,POLICY,'one');value=8 if column=='attempts' else 888 if column=='worker_pid' else 'changed';d.execute('update jobs set '+column+'=?',(value,));d.commit();self.assertIsNone(b.claim(d,selection,POLICY,'one',pid=123))
 def test_all_legacy_and_current_running_models_block_claim(self):
  for table in b.MODEL_TABLES:
   d=sqlite3.connect(':memory:');schema(d);add(d);selection=b.select_candidate(d,POLICY,'one');d.execute('update '+table+' set state="running"');d.commit();self.assertIsNone(b.claim(d,selection,POLICY,'one',pid=123))
 def test_only_one_competing_owner_claims(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'jobs.sqlite';a=sqlite3.connect(path);schema(a);add(a);c=sqlite3.connect(path);x=b.select_candidate(a,POLICY,'one');y=b.select_candidate(c,POLICY,'two');self.assertIsNotNone(b.claim(a,x,POLICY,'one',pid=111));self.assertIsNone(b.claim(c,y,POLICY,'two',pid=222))
 def test_failure_and_dryrun_restore_exact_job_and_all_model_history(self):
  for success in (False,True):
   d=sqlite3.connect(':memory:');schema(d);add(d,state='harness_review_pending');prior=b.snapshot(d,'case');queues={t:d.execute('select * from '+t).fetchall() for t in b.MODEL_TABLES};c=get_claim(d);stage=b.finish(d,c,{'state':'unsupported_source','accepted':False},{'candidate':True} if success else None);self.assertEqual(stage,'validated_dry_run' if success else 'unsupported_source');self.assertEqual(b.snapshot(d,'case'),prior);self.assertEqual({t:d.execute('select * from '+t).fetchall() for t in b.MODEL_TABLES},queues);self.assertIsNone(b.select_candidate(d,POLICY,'run-two'))
 def test_retry_is_explicit_bounded_and_never_twice_per_run(self):
  d=sqlite3.connect(':memory:');schema(d);add(d);c=get_claim(d);b.finish(d,c,{'state':'unsupported_source','accepted':False});self.assertIsNone(b.select_candidate(d,POLICY,'run-one',retry_failed=True));self.assertIsNone(b.select_candidate(d,POLICY,'run-two'));self.assertIsNotNone(b.select_candidate(d,POLICY,'run-two',retry_failed=True));c=get_claim(d,'run-two',retry=True);b.finish(d,c,{'state':'unsupported_source','accepted':False});self.assertIsNone(b.select_candidate(d,POLICY,'run-three',retry_failed=True));self.assertIsNotNone(b.select_candidate(d,POLICY+'-new','run-three'))
 def test_validated_dryrun_may_publish_only_explicit_later_run(self):
  d=sqlite3.connect(':memory:');schema(d);add(d);c=get_claim(d);b.finish(d,c,{'accepted':False},{'candidate':True});self.assertIsNone(b.select_candidate(d,POLICY,'run-one',publish=True));self.assertIsNotNone(b.select_candidate(d,POLICY,'run-two',publish=True))
 def test_model_started_during_generation_is_never_touched(self):
  d=sqlite3.connect(':memory:');schema(d);add(d);prior=b.snapshot(d,'case');c=get_claim(d,publish=True);d.execute('update harness_queue_v3 set state="running",worker_pid=888');d.commit();called=[];self.assertEqual(b.finish(d,c,{'accepted':False},{},publish=True,artifact_writer=lambda *a:called.append(a)),'deferred_model_running');self.assertFalse(called);self.assertEqual(b.snapshot(d,'case'),prior);self.assertEqual(d.execute('select state,worker_pid,attempts from harness_queue_v3').fetchone(),('running',888,5))
 def test_stolen_job_or_table_claim_never_overwritten(self):
  for table in (False,True):
   d=sqlite3.connect(':memory:');schema(d);add(d);c=get_claim(d,publish=True)
   if table:d.execute('update '+b.TABLE+' set owner_pid=999,claim_token="new-token"')
   else:d.execute('update jobs set state="accepted",output_record="new revision",worker_pid=null')
   d.commit();prior=b.snapshot(d,'case');rows=d.execute('select * from '+b.TABLE).fetchall();called=[];self.assertEqual(b.finish(d,c,{'accepted':False},{},publish=True,artifact_writer=lambda *a:called.append(a)),'stale_revision_or_ownership');self.assertFalse(called);self.assertEqual(b.snapshot(d,'case'),prior)
   if table:self.assertEqual(rows,d.execute('select * from '+b.TABLE).fetchall())
 def test_success_is_pending_candidate_and_preserves_queue_attempts(self):
  d=sqlite3.connect(':memory:');schema(d);add(d);c=get_claim(d,publish=True);new={'code_sha256':'new-code','image_sha256':'new-image'};self.assertEqual(b.finish(d,c,{'accepted':False},new,publish=True,artifact_writer=lambda *a:None),'published_candidate');self.assertEqual(b.snapshot(d,'case')[0],'needs_quality_repair');self.assertEqual(json.loads(b.snapshot(d,'case')[1]),new)
  for t in b.MODEL_TABLES:self.assertEqual(d.execute('select state,attempts,heartbeat from '+t).fetchone()[:2],('held_for_quality_v3',5))
 def test_writer_failure_rolls_back_then_prior_job_can_be_restored(self):
  d=sqlite3.connect(':memory:');schema(d);add(d);prior=b.snapshot(d,'case');c=get_claim(d,publish=True);owned=b.snapshot(d,'case')
  def failed(*a):raise OSError('synthetic staged FS failure')
  with self.assertRaises(OSError):b.finish(d,c,{'accepted':False},{},publish=True,artifact_writer=failed)
  self.assertEqual(b.snapshot(d,'case'),owned);b.finish(d,c,{'state':'publication_failed','accepted':False});self.assertEqual(b.snapshot(d,'case'),prior)
 def test_dead_owner_recovery_is_explicit_and_safe(self):
  d=sqlite3.connect(':memory:');schema(d);add(d);prior=b.snapshot(d,'case');get_claim(d)
  with patch.object(b.os,'kill',side_effect=ProcessLookupError):self.assertEqual(b.recover_dead(d),[{'id':'case','stage':'recovered_abandoned'}])
  self.assertEqual(b.snapshot(d,'case'),prior)


class PublicationTests(unittest.TestCase):
 def fixture(self,root):
  case=root/'clean/case';case.mkdir(parents=True);blobs={'old.drawio':b'old-native-xml','old.png':b'old-native-png','source.tex':b'unchanged-source','ref.png':b'unchanged-reference','source.svg':b'source-svg','source.pdf':b'source-pdf'}
  for name,blob in blobs.items():(case/name).write_bytes(blob)
  old={'id':'case','source_pair_sha256':'case','previous_candidate_archive':'conversion/harness_sessions/legacy/baseline','source_format':'tikz','code_file':'clean/case/old.drawio','code_sha256':b.sha(blobs['old.drawio']),'image_file':'clean/case/old.png','image_sha256':b.sha(blobs['old.png']),'original_source_code':'clean/case/source.tex','source_code_sha256':b.sha(blobs['source.tex']),'original_reference':'clean/case/ref.png','source_image_sha256':b.sha(blobs['ref.png']),'source_render_svg':'clean/case/source.svg','source_render_svg_sha256':b.sha(blobs['source.svg']),'source_render_pdf':'clean/case/source.pdf','source_render_pdf_sha256':b.sha(blobs['source.pdf']),'edges':0}
  target=case/'execution_v3/version';target.mkdir(parents=True);(target/'diagram.drawio').write_bytes(b'new-native-xml');(target/'image.png').write_bytes(b'new-native-png');archive=target/'prior_pair';archive.mkdir();(archive/'conversion.json').write_text(json.dumps(old));(archive/'diagram.drawio').write_bytes(blobs['old.drawio']);(archive/'image.png').write_bytes(blobs['old.png']);(case/'conversion.json').write_text(json.dumps(old));out={**old,'code_file':str((target/'diagram.drawio').relative_to(root)),'image_file':str((target/'image.png').relative_to(root)),'code_sha256':b.sha(b'new-native-xml'),'image_sha256':b.sha(b'new-native-png'),'execution_prior_pair_archive':str(archive.relative_to(root)),'quality_state':'pending_automatic_quality_v3_recheck','tikz_execution_source_v3':{'files':{}}};(target/'conversion.json').write_text(json.dumps(out));d=sqlite3.connect(':memory:');schema(d);add(d,old=old);current=get_claim(d,publish=True);report={'accepted':False,'candidate_checks_passed':True,'policy':POLICY};return d,old,out,current,report
 def test_staged_clean_version_preserves_old_pair_and_metadata(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(b,'R',Path(temp)):
   root=Path(temp);d,old,out,c,report=self.fixture(root);self.assertEqual(b.finish(d,c,report,out,publish=True),'published_candidate');self.assertEqual((root/old['code_file']).read_bytes(),b'old-native-xml');self.assertEqual((root/old['image_file']).read_bytes(),b'old-native-png');self.assertEqual(json.loads((root/old['code_file']).parent.joinpath('conversion.json').read_text()),old);self.assertEqual(json.loads(b.snapshot(d,'case')[1]),out)
 def test_changed_source_image_or_native_pair_blocks_pointer_swap(self):
  for key in ('original_source_code','original_reference','code_file','image_file'):
   with self.subTest(key=key),tempfile.TemporaryDirectory() as temp,patch.object(b,'R',Path(temp)):
    root=Path(temp);d,old,out,c,report=self.fixture(root);(root/old[key]).write_bytes(b'changed');owned=b.snapshot(d,'case')
    with self.assertRaises(ValueError):b.finish(d,c,report,out,publish=True)
    self.assertEqual(b.snapshot(d,'case'),owned);self.assertEqual(json.loads((root/old['code_file']).parent.joinpath('conversion.json').read_text()),old)


if __name__=='__main__':unittest.main()
