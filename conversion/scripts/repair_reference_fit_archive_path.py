import json,sqlite3,hashlib,shutil
from native_worker import R,W,now
from durable_sqlite import begin,commit
from harness_source_provenance import resolve
ID='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641';D=sqlite3.connect(W/'jobs.sqlite',timeout=2);state,raw=D.execute('select state,output_record from jobs where id=?',(ID,)).fetchone();r=json.loads(raw);assert state=='accepted';old=(R/r['previous_candidate_archive']).resolve();assert old.is_relative_to(W/'mermaid_reference_fit'/ID);before=json.loads((old/'conversion.json').read_text())
assert hashlib.sha256((old/'diagram.drawio').read_bytes()).hexdigest()==before['code_sha256'];assert hashlib.sha256((old/'image.png').read_bytes()).hexdigest()==before['image_sha256']
dest=W/'harness_sessions'/('reference_fit_accepted_archive_'+ID)/'baseline';dest.mkdir(parents=True,exist_ok=True)
for name in ['conversion.json','diagram.drawio','image.png']:
 p=dest/name
 if p.exists():assert p.read_bytes()==(old/name).read_bytes()
 else:shutil.copyfile(old/name,p)
r['previous_candidate_archive']=str(dest.relative_to(R));resolved,xml,origin=resolve(r);assert resolved==r and hashlib.sha256(xml).hexdigest()==r['code_sha256']
begin(D);assert D.execute('select state,output_record from jobs where id=?',(ID,)).fetchone()==(state,raw);p=(R/r['code_file']).parent/'conversion.json';tmp=p.with_suffix('.archivepath.tmp');tmp.write_text(json.dumps(r,indent=2));tmp.replace(p);D.execute('update jobs set output_record=?,updated_at=? where id=?',(json.dumps(r),now(),ID));commit(D)
report={'at':now(),'id':ID,'old_archive_retained':str(old.relative_to(R)),'new_archive':str(dest.relative_to(R)),'archive_file_bytes_identical':True,'native_xml_png_unchanged':True,'source_provenance_resolver_pass':True};(W/'reference_fit_archive_path_repair.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
