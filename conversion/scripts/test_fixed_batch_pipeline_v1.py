import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('fixed_batch_pipeline_v1',Path(__file__).with_name('fixed_batch_pipeline_v1.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class PipelineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run=self.root/'release/fixed_batch_v1/test';self.run.mkdir(parents=True)
  self.db=sqlite3.connect(self.run/'status.sqlite');p.create_schema(self.db)
  for k,v in {'total':3,'full_scope':False,'policy':'test','finished':False}.items():p.meta(self.db,k,v)
  for seq in range(1,4):self.db.execute('insert into samples(seq,id,source) values(?,?,?)',(seq,'id'+str(seq),json.dumps({'code_sha256':'c','image_sha256':'i'})))
  self.db.commit()
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def result(self,seq,status='abandoned'):
  return {'seq':seq,'id':'id'+str(seq),'status':status,'reason':'test_failure','model_calls':0,**({'manifest':{'id':'id'+str(seq),'status':'qualified'}} if status=='qualified' else {})}
 def test_manifest_order_dispatch(self):
  self.assertEqual([p.claim(self.db,s)['seq'] for s in [1,2,3]],[1,2,3])
 def test_no_duplicate_dispatch(self):
  p.claim(self.db,1)
  with self.assertRaises(RuntimeError):p.claim(self.db,1)
 def test_finish_requires_matching_id(self):
  p.claim(self.db,1)
  with self.assertRaises(RuntimeError):p.finish(self.db,1,self.result(2))
 def test_finish_cannot_skip_claim(self):
  with self.assertRaises(RuntimeError):p.finish(self.db,1,self.result(1))
 def test_exactly_once_finish(self):
  p.claim(self.db,1);p.finish(self.db,1,self.result(1))
  with self.assertRaises(RuntimeError):p.finish(self.db,1,self.result(1))
 def test_failure_does_not_block_next(self):
  p.claim(self.db,1);p.finish(self.db,1,self.result(1));self.assertEqual(p.claim(self.db,2)['id'],'id2')
 def test_initial_screen_failed_is_not_success(self):
  p.claim(self.db,1);p.finish(self.db,1,self.result(1));self.assertEqual(self.db.execute('select status from samples where seq=1').fetchone(),('abandoned',))
 def test_all_results_ordered_after_out_of_order_finish(self):
  for seq in [1,2,3]:p.claim(self.db,seq)
  for seq in [3,1,2]:p.finish(self.db,seq,self.result(seq,'qualified' if seq==2 else 'abandoned'))
  with patch.object(p,'R',self.root):r=p.export(self.run,True)
  rows=[json.loads(x) for x in (self.run/'processed.jsonl').read_text().splitlines()]
  self.assertEqual([x['seq'] for x in rows],[1,2,3]);self.assertEqual(r['files']['qualified']['records'],1);self.assertEqual(r['files']['failed']['records'],2)
 def test_incomplete_cannot_export_final(self):
  with patch.object(p,'R',self.root):
   with self.assertRaises(RuntimeError):p.export(self.run,True)
 def test_status_distinguishes_pending_running_failed(self):
  p.claim(self.db,1);p.finish(self.db,1,self.result(1));p.claim(self.db,2)
  x=p.status(self.run);self.assertEqual(x['counts'],{'queued':1,'running':1,'abandoned':1});self.assertFalse(x['finished'])
 def test_input_manifest_scope_and_order(self):
  (self.root/'release/manifest.jsonl').write_text(''.join(json.dumps({'pair_sha256':str(i),'category':'poster','format':'html','code_sha256':'c','image_sha256':'i'})+'\n' for i in [3,1,2]))
  source=self.root/'release/manifest.jsonl';run=self.root/'new';digest=p.sha(source.read_bytes())
  with patch.object(p,'R',self.root),patch.object(p,'INPUT_SHA',digest):m=p.create_run(run,['3','2'])
  d=sqlite3.connect(run/'status.sqlite');self.assertEqual(d.execute('select id from samples order by seq').fetchall(),[('3',),('2',)]);d.close();self.assertEqual(m['total'],2)
 def test_changed_manifest_refused(self):
  (self.root/'release/manifest.jsonl').write_text('{}\n')
  with patch.object(p,'R',self.root):
   with self.assertRaises(ValueError):p.create_run(self.root/'new',['id'])
 def test_unknown_status_schema_refused(self):
  with self.assertRaises(sqlite3.IntegrityError):self.db.execute('update samples set status="accepted_without_checks" where seq=1')
 def test_attempts_cannot_exceed_one(self):
  with self.assertRaises(sqlite3.IntegrityError):self.db.execute('update samples set attempts=2 where seq=1')
 def artifact_result(self):
  dest=self.root/'clean/test';dest.mkdir(parents=True)
  m={'id':'id1','source_code_sha256':'c','source_image_sha256':'i'}
  for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('metadata_file','metadata_sha256')]:
   path=dest/field;path.write_bytes(field.encode());m[field]=str(path.relative_to(self.root));m[digest]=p.sha(path.read_bytes())
  self.db.execute('update samples set source=? where seq=1',(json.dumps({'code_sha256':m['source_code_sha256'],'image_sha256':m['source_image_sha256']}),));self.db.commit()
  r=self.result(1,'qualified');r['manifest']=m;p.claim(self.db,1);p.finish(self.db,1,r);return m
 def test_final_actual_payload_audit(self):
  self.artifact_result()
  with patch.object(p,'R',self.root):r=p.final_asset_audit(self.db)
  self.assertEqual(r['qualified_payloads_verified'],1);self.assertEqual(r['late_asset_failures'],0)
 def test_final_changed_payload_is_failed(self):
  m=self.artifact_result();(self.root/m['image_file']).write_bytes(b'changed')
  with patch.object(p,'R',self.root):r=p.final_asset_audit(self.db)
  self.assertEqual(r['late_asset_failures'],1);state,body=self.db.execute('select status,result from samples where seq=1').fetchone();self.assertEqual(state,'abandoned');self.assertIn('prior_qualified_manifest',json.loads(body))
if __name__=='__main__':unittest.main()
