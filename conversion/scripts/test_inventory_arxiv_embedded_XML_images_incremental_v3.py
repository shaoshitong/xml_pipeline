from pathlib import Path
import sqlite3,tempfile,unittest,contextlib,io,json
from unittest.mock import patch
import inventory_arxiv_embedded_XML_images_incremental_v3 as scanner
from inventory_arxiv_embedded_XML_images_incremental_v3 import schema,scan_source
class IncrementalDiscoveryTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.c=sqlite3.connect(':memory:',uri=True);schema(self.c)
 def test_seed_path_never_read_and_completed_paper_never_rescanned(self):
  old=self.root/'old.png';old.write_bytes(b'old');new=self.root/'new.svg';new.write_bytes(b'new')
  self.c.execute('insert into files values(?,?,?,?)',(str(old),'checked','{}','frozen_v2'));seen=[]
  def probe(p):seen.append(p.name);return dict(file=str(p),kind='SVG_native_XML_marker')
  self.assertEqual(scan_source(self.c,'paper',self.root,probe),1);self.assertEqual(seen,['new.svg'])
  self.assertEqual(scan_source(self.c,'paper',self.root,lambda p:self.fail('already scanned')),0)
 def test_interruption_keeps_paper_resumable_and_prior_paths_unique(self):
  (self.root/'a.png').write_bytes(b'a');(self.root/'b.png').write_bytes(b'b')
  def broken(p):
   if p.name=='b.png':raise OSError('temporary read failure')
   return None
  with self.assertRaises(OSError):scan_source(self.c,'paper',self.root,broken)
  self.assertIsNone(self.c.execute('select status from papers where id="paper"').fetchone())
  seen=[];scan_source(self.c,'paper',self.root,lambda p:seen.append(p.name));self.assertEqual(seen,['b.png']);self.assertEqual(self.c.execute('select count(*) from files').fetchone()[0],2)
 def test_read_only_frozen_URI_seed_is_idempotent(self):
  frozen=self.root/'frozen';frozen.mkdir();db=frozen/'files.sqlite';f=sqlite3.connect(db);f.execute('create table files(path text primary key,status text,details text)');f.execute('insert into files values(?,?,?)',('old.png','marker',json.dumps(dict(file='old.png',kind='PNG_native_XML_marker'))));f.commit();f.close()
  (frozen/'inventory.json').write_text(json.dumps(dict(scan_complete=True,directory_walk_complete=True,states={'marker':1})))
  (frozen/'launch.json').write_text(json.dumps(dict(at_utc='2026-11-03T11:00:00+00:00')));before=db.read_bytes()
  with patch.object(scanner,'F',frozen),patch.object(scanner,'R',self.root):scanner.seed(self.c);scanner.seed(self.c)
  self.assertEqual(self.c.execute('select count(*) from files').fetchone()[0],1);self.assertEqual(db.read_bytes(),before)
 def test_missing_source_not_marked_complete(self):
  self.assertIsNone(scan_source(self.c,'paper',self.root/'missing'));self.assertEqual(self.c.execute('select count(*) from papers').fetchone()[0],0)
 def test_queued_or_failed_papers_prevent_complete_claim(self):
  self.c.execute('insert into papers values(?,?,?,?)',('new','queued',None,'{}'))
  with patch.object(scanner,'D',self.root),contextlib.redirect_stdout(io.StringIO()):scanner.publish(self.c)
  self.assertFalse(json.loads((self.root/'inventory.json').read_text())['scan_complete'])
  self.c.execute("update papers set status='pending_io_error'")
  with patch.object(scanner,'D',self.root),contextlib.redirect_stdout(io.StringIO()):scanner.publish(self.c)
  self.assertFalse(json.loads((self.root/'inventory.json').read_text())['scan_complete'])
  self.c.execute("update papers set status='scanned'")
  with patch.object(scanner,'D',self.root),contextlib.redirect_stdout(io.StringIO()):scanner.publish(self.c)
  self.assertTrue(json.loads((self.root/'inventory.json').read_text())['scan_complete'])
 def test_symlink_cannot_escape_source(self):
  outside=self.root/'outer.png';outside.write_bytes(b'a');inside=self.root/'source';inside.mkdir();(inside/'link.png').symlink_to(outside)
  with self.assertRaises(ValueError):scan_source(self.c,'paper',inside,lambda p:self.fail('escaping read'))
if __name__=='__main__':unittest.main()
