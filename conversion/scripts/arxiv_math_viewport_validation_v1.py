"""Continue failed source validation with uniform editor view state.

Original PDF once records, author XML, failed proofs and baseline outputs are
read-only. Only prior geometric-identical validation failures are eligible. The
same strict model/SVG/PNG restoration gates apply under a new pinned protocol.
"""
from pathlib import Path
import argparse,concurrent.futures as cf,fcntl,hashlib,json,os,signal,sqlite3,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts';D=P/'math_viewport_source_replay_v1';OLD=P/'math_source_replay_v1'
sys.path.insert(0,str(S))
import arxiv_math_source_repair_v1 as core
from arxiv_math_uniform_viewport_renderer_v1 import MathSynced,POLICY
core.D=D;core.MathSynced=MathSynced;core.POLICY=POLICY
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def connection():
 c=sqlite3.connect(D/'once.sqlite',timeout=60);c.execute('pragma journal_mode=WAL');c.execute('create table if not exists cases(id text primary key,status text,record text)');return c

def discover(c):
 added=0
 with sqlite3.connect((OLD/'once.sqlite').as_uri()+'?mode=ro',uri=True) as old:
  ids=[x[0] for x in old.execute("select id from cases where status='pending_math_source_replay'")]
 for ident in ids:
  if c.execute('select 1 from cases where id=?',(ident,)).fetchone():continue
  oldcase=OLD/'cases'/ident;proof=oldcase/'synced_source_replay/synced_replay_proof.json'
  if not proof.exists():continue
  p=json.loads(proof.read_text())
  if p.get('ok') or not p.get('font_observations',{}).get('all_physical_font_bytes_pinned'):continue
  if p.get('source_geometry_topology_style_inventory_sha256')!=p.get('restored_geometry_topology_style_inventory_sha256'):continue
  if p.get('blocked') or p.get('missing'):continue
  row=json.loads((oldcase/'input.json').read_text());row.update(previous_validation_proof=str(proof.relative_to(R)),previous_validation_proof_sha256=sha(proof),previous_validation_record=str((oldcase/'record.json').relative_to(R)),previous_validation_record_sha256=sha(oldcase/'record.json'))
  case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True);core.put(case/'input.json',row)
  c.execute('insert into cases values(?,?,?)',(ident,'queued',json.dumps(dict(id=ident,status='queued'))));added+=1
 c.commit();return added

def work(file):
 row=json.loads(file.read_text())
 pins=json.loads((D/'policy.json').read_text())['files_sha256']
 for name,digest in pins.items():assert sha(R/name)==digest,'validation_source_pin_changed:'+name
 for key in ['previous_validation_proof','previous_validation_record']:assert sha(R/row[key])==row[key+'_sha256']
 result=core.work(file)
 try:
  for name,digest in pins.items():assert sha(R/name)==digest,'validation_source_pin_changed:'+name
  for key in ['previous_validation_proof','previous_validation_record']:assert sha(R/row[key])==row[key+'_sha256']
 except Exception as error:
  result.pop('pair',None);result.update(status='pending_viewport_validation_input_changed',reason=str(error))
 result.update(continued_failed_source_validation_only=True,previous_source_geometry_was_identical=True,original_failed_outputs_unchanged=True,new_PDF_import_calls=0,new_model_calls=0)
 if result.get('pair'):
  result['pair'].update(previous_validation_proof=row['previous_validation_proof'],previous_validation_proof_sha256=row['previous_validation_proof_sha256'],viewport_policy=POLICY,old_PDF_conversion_not_repeated=True,repair_of_preserved_failure='non_uniform_editor_viewport_during_strict_restore')
 core.put(file.parent/'record.json',result);return result

def bounded(file):
 with connection() as c:
  changed=c.execute("update cases set status='attempt_started' where id=? and status='queued'",(file.parent.name,)).rowcount
  assert changed==1,'validation_once_claim_not_available'
 with (file.parent/'worker.log').open('ab') as log:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',str(file)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:child.wait(timeout=185)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 result=file.parent/'record.json'
 return json.loads(result.read_text()) if result.exists() else dict(id=file.parent.name,status='pending_viewport_validation_worker_exit',exit=child.returncode,new_PDF_import_calls=0)

def run():
 D.mkdir(exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 test=P/'math_viewport_protocol_selftest_v1/results.json';t=json.loads(test.read_text());assert not t['baseline']['ok'] and t['uniform_viewport']['ok']
 fresh=P/'math_uniform_viewport_probe_v1';probe=json.loads((fresh/'selection.json').read_text());assert json.loads((fresh/'cases'/probe['id']/'record.json').read_text())['status']=='verified_math_author_native_source_replay'
 policy=D/'policy.json'
 if not policy.exists():
  files=[Path(__file__),S/'arxiv_math_uniform_viewport_renderer_v1.py',S/'arxiv_math_source_repair_v1.py',S/'arxiv_math_synced_renderer_v1.py',S/'arxiv_bulk_official_xml_png_math_v1.py',S/'arxiv_author_native_synced_replay_v1.py']
  core.put(policy,dict(policy=POLICY,files_sha256={str(f.relative_to(R)):sha(f) for f in files},synthetic_test_sha256=sha(test),fresh_source_probe=probe['id'],new_PDF_import_calls=0,old_validation_outputs_preserved=True))
 c=connection()
 while True:
  for ident, in c.execute("select id from cases where status='attempt_started'").fetchall():
   path=D/'cases'/ident/'record.json'
   if path.exists():
    r=json.loads(path.read_text());c.execute('update cases set status=?,record=? where id=?',(r['status'],json.dumps(r),ident))
  c.commit();discover(c)
  files=[D/'cases'/ident/'input.json' for ident, in c.execute("select id from cases where status='queued' order by id")]
  with cf.ThreadPoolExecutor(max_workers=2) as pool:
   for result in pool.map(bounded,files):
    c.execute('update cases set status=?,record=? where id=?',(result['status'],json.dumps(result),result['id']));c.commit();core.publish(c)
  core.publish(c);time.sleep(60)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',type=Path);a=p.parse_args();work(a.case) if a.case else run()
