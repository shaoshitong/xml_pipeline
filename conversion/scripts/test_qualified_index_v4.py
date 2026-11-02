import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
import qualified_index_v4 as m

class Index(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for folder in ('conversion','release','clean/pair'): (self.root/folder).mkdir(parents=True)
  self.db=sqlite3.connect(self.root/'conversion/jobs.sqlite');self.addCleanup(self.db.close)
  self.db.executescript('''create table jobs(id primary key,state,output_record,input_record);create table auto_quality_dirty_v2(id primary key,payload_version);
   create trigger payload after update of output_record on jobs begin update auto_quality_dirty_v2 set payload_version=payload_version+1 where id=NEW.id;end;''')
  self.identifier=m.sha(b'original-pair');self.r={'id':self.identifier,'source_pair_sha256':self.identifier,'source':'example','category':'poster','source_format':'html','format':'drawio','automatic_quality_policy':'fixed-test:v4','automatic_quality_audit':'conversion/audit.json'}
  for key,digest,name,data in [('code_file','code_sha256','diagram.drawio',b'XML'),('image_file','image_sha256','image.png',b'PNG'),('original_reference','source_image_sha256','source.png',b'ORIGINAL PNG'),('original_source_code','source_code_sha256','source.html',b'ORIGINAL HTML')]:
   p=self.root/'clean/pair'/name;p.write_bytes(data);self.r[key]=str(p.relative_to(self.root));self.r[digest]=m.sha(data)
  self.original={'category':'poster','source':'example','format':'html','code_sha256':self.r['source_code_sha256'],'image_sha256':self.r['source_image_sha256']}
  self.db.execute('insert into jobs values(?,?,?,?)',(self.identifier,'accepted',json.dumps(self.r),json.dumps(self.original)))
  self.db.execute('insert into auto_quality_dirty_v2 values(?,1)',(self.identifier,));self.db.commit()
 def export(self):return m.export(self.root)
 def rows(self):return [json.loads(x) for x in (self.root/'release/qualified_drawio_manifest.inprogress.jsonl').read_text().splitlines()]
 def test_exact_clean_payload_and_metadata_hash(self):
  summary=self.export();self.assertEqual(summary['qualified_records'],1)
  row=self.rows()[0];p=self.root/row['metadata_file'];self.assertTrue(p.is_relative_to(self.root/'clean'));self.assertEqual(m.sha(p.read_bytes()),row['metadata_sha256']);self.assertEqual(json.loads(p.read_bytes()),self.r)
  self.assertEqual(self.export()['refreshed_full_records'],0)
 def test_unvalidated_legacy_excluded(self):
  r=dict(self.r);r.pop('automatic_quality_policy');self.db.execute('update jobs set output_record=?',(json.dumps(r),));self.db.commit()
  s=self.export();self.assertEqual((s['qualified_records'],s['legacy_unvalidated_excluded']),(0,1));self.assertEqual(self.rows(),[])
 def test_metadata_only_change_gets_new_immutable_pointer(self):
  self.export();old=self.rows()[0];self.r['render']={'new':'proof'};self.db.execute('update jobs set output_record=?',(json.dumps(self.r),));self.db.commit()
  s=self.export();self.assertEqual(s['refreshed_full_records'],1);new=self.rows()[0];self.assertNotEqual(old['metadata_sha256'],new['metadata_sha256']);self.assertTrue((self.root/old['metadata_file']).exists());self.assertEqual(json.loads((self.root/new['metadata_file']).read_bytes()),self.r)
 def test_current_pair_hash_corruption_rejects(self):
  (self.root/self.r['code_file']).write_bytes(b'changed')
  with self.assertRaises(ValueError):self.export()
 def test_clean_symlink_escape_rejects(self):
  target=self.root/'outside';target.write_bytes(b'XML');path=self.root/self.r['code_file'];path.unlink();path.symlink_to(target)
  with self.assertRaises(ValueError):self.export()
 def test_immutable_metadata_corruption_rejects(self):
  _,digest=m.manifest_row(self.r,self.root);p=self.root/'clean/pair'/('accepted_metadata.'+digest[:24]+'.json');p.write_bytes(b'changed')
  with self.assertRaises(AssertionError):self.export()
 def test_mismatched_authoritative_source_rejects(self):
  bad={**self.original,'image_sha256':m.sha(b'wrong')};self.db.execute('update jobs set input_record=?',(json.dumps(bad),));self.db.commit()
  with self.assertRaises(AssertionError):self.export()
 def test_original_dataset_category_format_not_rewritten(self):
  for key in ('source','category','format'):
   bad={**self.original,key:'wrong'};self.db.execute('update jobs set input_record=?',(json.dumps(bad),));self.db.commit()
   with self.assertRaises(AssertionError):self.export()
 def test_publication_cache_rolls_back_with_job_transaction(self):
  self.db.execute('begin');m.cache_publication(self.db,self.r,self.root);self.db.rollback()
  self.assertFalse(self.db.execute("select 1 from sqlite_master where name=?",(m.TABLE,)).fetchone())
 def test_publication_requires_real_source_and_policy(self):
  self.db.execute('begin');bad=dict(self.r);bad.pop('automatic_quality_policy')
  with self.assertRaises(AssertionError):m.cache_publication(self.db,bad,self.root)
  self.db.rollback()
 def test_journal_missing_fails_closed(self):
  self.db.execute('delete from auto_quality_dirty_v2');self.db.commit()
  with self.assertRaises(AssertionError):self.export()
 def test_nonaccepted_cached_pair_is_excluded(self):
  self.export();self.db.execute("update jobs set state='needs_quality_repair'");self.db.commit();self.assertEqual(self.export()['qualified_records'],0)

if __name__=='__main__':unittest.main()
