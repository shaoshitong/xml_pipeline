import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import glyph_archive_metadata_compat_v3 as compat

class Tests(unittest.TestCase):
    def fixture(self,root):
        root=Path(root);clean=root/'clean/case';clean.mkdir(parents=True);archive=root/compat.OWNER/'case/baseline_archive';archive.mkdir(parents=True);harness=root/'conversion/harness_sessions/old/baseline';harness.mkdir(parents=True)
        blobs={'diagram.drawio':b'<mxfile/>','image.png':b'PNG','source.html':b'HTML','reference.png':b'REF'}
        for name,blob in blobs.items():(clean/name).write_bytes(blob)
        record={'id':'case','code_file':'clean/case/diagram.drawio','code_sha256':compat.sha(blobs['diagram.drawio']),'image_file':'clean/case/image.png','image_sha256':compat.sha(blobs['image.png']),'original_source_code':'clean/case/source.html','source_code_sha256':compat.sha(blobs['source.html']),'original_reference':'clean/case/reference.png','source_image_sha256':compat.sha(blobs['reference.png']),'previous_candidate_archive':str(archive.relative_to(root))}
        previous={**record,'previous_candidate_archive':str(harness.relative_to(root))};harness_record=copy.deepcopy(previous);harness_record.pop('previous_candidate_archive',None);(harness/'conversion.json').write_text(json.dumps(harness_record));(harness/'diagram.drawio').write_bytes(blobs['diagram.drawio']);p=archive.parent/'previous_record.json';p.write_text(json.dumps(previous));link={'version':3,'output_code_sha256':record['code_sha256'],'output_image_sha256':record['image_sha256'],'previous_record':str(p.relative_to(root)),'previous_record_sha256':compat.sha(p.read_bytes())};proof={'files':{'previous_record':{'file':link['previous_record'],'sha256':link['previous_record_sha256']}}};p=archive.parent/'proof.json';p.write_text(json.dumps(proof));link.update(proof=str(p.relative_to(root)),proof_sha256=compat.sha(p.read_bytes()));record[compat.FIELD]=link
        raw=json.dumps(record);(clean/'conversion.json').write_text(raw);db=sqlite3.connect(':memory:');db.execute('create table jobs(id text,state text,output_record text,worker_pid int,error text,updated_at text,input_record text,input_manifest text)');db.execute('insert into jobs values(?,?,?,?,?,?,?,?)',('case','needs_quality_repair',raw,None,'same-error','same-time','same-input','same-manifest'));db.execute('create table harness_queue_v3(id text,state text,attempts int,priority int,worker_pid int)');db.execute('insert into harness_queue_v3 values(?,?,?,?,?)',('case','held_for_source_v5',3,42,None));db.commit();return db,record,raw
    def test_metadata_only_restores_harness_lineage_and_preserves_all_other_fields(self):
        with tempfile.TemporaryDirectory() as root:
            db,old,raw=self.fixture(root);queue=db.execute('select * from harness_queue_v3').fetchall();snapshot=db.execute('select '+compat.COLUMNS+' from jobs').fetchone();result=compat.repair_one(db,'case',root,resolver=lambda r:None);self.assertEqual(result['state'],'repaired_archive_metadata_only');new=json.loads(db.execute('select output_record from jobs').fetchone()[0]);self.assertEqual(new['previous_candidate_archive'],'conversion/harness_sessions/old/baseline');self.assertEqual(new['glyph_alignment_prior_pair_archive'],old['previous_candidate_archive']);self.assertEqual(queue,db.execute('select * from harness_queue_v3').fetchall());self.assertEqual(snapshot[:1]+snapshot[2:],(db.execute('select '+compat.COLUMNS+' from jobs').fetchone())[:1]+(db.execute('select '+compat.COLUMNS+' from jobs').fetchone())[2:]);self.assertEqual(new[compat.FIELD],old[compat.FIELD]);self.assertEqual(json.loads((Path(root)/'clean/case/conversion.json').read_text()),new)
    def test_busy_paid_and_accepted_jobs_are_not_touched(self):
        for statement in ["update jobs set worker_pid=123","update jobs set state='accepted'","update harness_queue_v3 set state='running',worker_pid=777"]:
            with tempfile.TemporaryDirectory() as root:
                db,old,raw=self.fixture(root);db.execute(statement);db.commit();before=db.execute('select * from jobs').fetchall();queue=db.execute('select * from harness_queue_v3').fetchall();self.assertEqual(compat.repair_one(db,'case',root,resolver=lambda r:None)['state'],'skipped_busy_or_nonidle');self.assertEqual(before,db.execute('select * from jobs').fetchall());self.assertEqual(queue,db.execute('select * from harness_queue_v3').fetchall())
    def test_changed_hash_or_source_identity_cannot_be_migrated(self):
        for damage in ('payload','proof','source_identity','stale_revision'):
            with tempfile.TemporaryDirectory() as root:
                db,old,raw=self.fixture(root);root=Path(root)
                if damage=='payload':(root/old['code_file']).write_bytes(b'damage')
                elif damage=='proof':(root/old[compat.FIELD]['proof']).write_bytes(b'damage')
                else:
                    old=copy.deepcopy(old)
                    if damage=='source_identity':old['source_code_sha256']='other-source'
                    else:old[compat.FIELD]['output_code_sha256']='stale-code'
                    db.execute('update jobs set output_record=?',(json.dumps(old),));db.commit()
                with self.assertRaises(AssertionError):compat.repair_one(db,'case',root,resolver=lambda r:None)
    def test_actual_harness_resolver_failure_keeps_metadata_and_queue(self):
        with tempfile.TemporaryDirectory() as root:
            db,old,raw=self.fixture(root)
            def failure(r):raise AssertionError('Still incompatible source lineage')
            with self.assertRaises(AssertionError):compat.repair_one(db,'case',root,resolver=failure)
            self.assertEqual(db.execute('select output_record from jobs').fetchone()[0],raw);self.assertEqual((Path(root)/'clean/case/conversion.json').read_text(),raw)

class ActualHarnessApiTests(unittest.TestCase):
    def test_real_resolve_freeze_validate_contract_after_metadata_migration(self):
        from importlib.util import find_spec
        if find_spec('pyarrow') is None:self.skipTest('Actual runtime API test runs on HKUST3')
        import harness_source_provenance as provenance
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);db,old,raw=Tests().fixture(root)
            with patch.object(provenance,'R',root):
                with self.assertRaises(AssertionError):provenance.resolve(old)
                new=compat.proposed_record(old,root);resolved,xml,origin=provenance.resolve(new)
                self.assertEqual(compat.sha(xml),new['code_sha256']);self.assertEqual(resolved['id'],new['id'])
                work=root/'conversion/harness_sessions/new';work.mkdir(parents=True)
                proof=provenance.freeze(new,work);checked=provenance.validate_frozen(proof)
                self.assertEqual(checked['source_code_sha256'],new['source_code_sha256']);self.assertEqual(checked['source_image_sha256'],new['source_image_sha256'])

if __name__=='__main__':unittest.main()
