"""Repair only proven random-gradient export failures under unchanged exact gates.

No PDF import/model invocation; old records, source XML, SVG and PNG stay read-only.
Namespace normalization is used only to diagnose old failures, never to accept
new output: the original strict replay implementation still decides proof.ok.
"""
from pathlib import Path
import argparse,concurrent.futures as cf,fcntl,hashlib,json,os,re,signal,sqlite3,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts';D=P/'stable_export_source_replay_v1';OLD=P/'math_viewport_source_replay_v1'
sys.path.insert(0,str(S))
import arxiv_math_source_repair_v1 as core
from arxiv_math_stable_export_renderer_v1 import MathSynced,POLICY
core.D=D;core.MathSynced=MathSynced;core.POLICY=POLICY
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def connect():
 c=sqlite3.connect(D/'once.sqlite',timeout=60);c.execute('pragma journal_mode=WAL');c.execute('create table if not exists cases(id text primary key,status text,record text)');return c
def namespace_only(a,b):
 def diagnose(s):return re.sub(r'drawio-svg-[A-Za-z0-9_-]{20}(?=-gradient-)','drawio-svg-DIAGNOSIS-ONLY',re.sub(r'ge-svg-[A-Za-z0-9_-]+','ge-svg-OFFICIAL-EXPORT-ID',s))
 return diagnose(a)==diagnose(b) and a!=b
def discover(c):
 with sqlite3.connect((OLD/'once.sqlite').as_uri()+'?mode=ro',uri=True) as old:ids=[r[0] for r in old.execute("select id from cases where status like 'pending%'")]
 for ident in ids:
  if c.execute('select 1 from cases where id=?',(ident,)).fetchone():continue
  oldcase=OLD/'cases'/ident;folder=oldcase/'synced_source_replay';proof=folder/'synced_replay_proof.json'
  if not proof.exists():continue
  p=json.loads(proof.read_text());gates=['normalized_model_exact_restore','mutation_normalized_model_changed','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact']
  if p.get('ok') or not all(p.get(k) for k in gates) or p.get('restored_SVG_namespace_canonical_exact'):continue
  if p.get('source_geometry_topology_style_inventory_sha256')!=p.get('restored_geometry_topology_style_inventory_sha256') or not p.get('font_observations',{}).get('all_physical_font_bytes_pinned') or p.get('blocked') or p.get('missing'):continue
  if not namespace_only((folder/'official.svg').read_text(),(folder/'restored.svg').read_text()):continue
  row=json.loads((oldcase/'input.json').read_text());prior=[proof,oldcase/'record.json',folder/'official.svg',folder/'restored.svg',folder/'official.png',folder/'restored.png']
  prior += [R/row[k] for k in ['previous_validation_proof','previous_validation_record'] if row.get(k)]
  row['readonly_prior_files']={str(f.relative_to(R)):sha(f) for f in prior}
  row.update(previous_validation_proof=str(proof.relative_to(R)),previous_validation_proof_sha256=sha(proof))
  case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True);core.put(case/'input.json',row)
  c.execute('insert into cases values(?,?,?)',(ident,'queued',json.dumps(dict(id=ident,status='queued'))))
 c.commit()
def work(file):
 row=json.loads(file.read_text());pins=json.loads((D/'policy.json').read_text())['files_sha256']
 for n,h in dict(pins,**row['readonly_prior_files']).items():assert sha(R/n)==h,'read_only_input_or_recipe_changed:'+n
 result=core.work(file)
 try:
  for n,h in dict(pins,**row['readonly_prior_files']).items():assert sha(R/n)==h,'read_only_input_or_recipe_changed:'+n
 except Exception as e:result.pop('pair',None);result.update(status='pending_stable_export_input_changed',reason=str(e))
 result.update(old_failed_outputs_unchanged=True,existing_acceptance_comparator_unchanged=True,new_PDF_import_calls=0,new_model_calls=0)
 if result.get('pair'):result['pair'].update(repair_of_preserved_failure='official_random_gradient_export_namespace',previous_validation_proof=row['previous_validation_proof'],previous_validation_proof_sha256=row['previous_validation_proof_sha256'],old_failed_outputs_unchanged=True)
 core.put(file.parent/'record.json',result);return result
def bounded(file):
 with connect() as c:assert c.execute("update cases set status='attempt_started' where id=? and status='queued'",(file.parent.name,)).rowcount==1
 with (file.parent/'worker.log').open('ab') as log:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',str(file)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:child.wait(timeout=185)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 p=file.parent/'record.json';return json.loads(p.read_text()) if p.exists() else dict(id=file.parent.name,status='pending_stable_export_worker_exit',exit=child.returncode,new_PDF_import_calls=0)
def run():
 D.mkdir(exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 test=P/'stable_export_protocol_selftest_v1/results.json';t=json.loads(test.read_text());assert not t['random_export_ids']['ok'] and t['stable_export_ids']['ok']
 policy=D/'policy.json'
 if not policy.exists():
  files=[Path(__file__),S/'arxiv_math_stable_export_renderer_v1.py',S/'arxiv_math_uniform_viewport_renderer_v1.py',S/'arxiv_math_source_repair_v1.py',S/'arxiv_math_synced_renderer_v1.py',S/'arxiv_bulk_official_xml_png_math_v1.py',S/'arxiv_author_native_synced_replay_v1.py']
  core.put(policy,dict(policy=POLICY,files_sha256={str(f.relative_to(R)):sha(f) for f in files},selftest_SHA256=sha(test),new_PDF_import_calls=0,old_failed_outputs_read_only=True))
 c=connect()
 while True:
  for ident, in c.execute("select id from cases where status='attempt_started'").fetchall():
   p=D/'cases'/ident/'record.json'
   if p.exists():
    r=json.loads(p.read_text());c.execute('update cases set status=?,record=? where id=?',(r['status'],json.dumps(r),ident))
  c.commit();discover(c);files=[D/'cases'/r[0]/'input.json' for r in c.execute("select id from cases where status='queued' order by id")]
  with cf.ThreadPoolExecutor(max_workers=2) as pool:
   for r in pool.map(bounded,files):c.execute('update cases set status=?,record=? where id=?',(r['status'],json.dumps(r),r['id']));c.commit();core.publish(c)
  core.publish(c);time.sleep(60)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',type=Path);a=p.parse_args();work(a.case) if a.case else run()
