"""Continue from preserved author XML after the common missing-MathJax error.

No PDF import/reimport. Existing failures and payloads remain immutable. New
versioned once claims cover cold source rendering, assets/fonts and edit/restore.
"""
from pathlib import Path
import argparse,concurrent.futures as cf,datetime,fcntl,hashlib,json,os,signal,sqlite3,subprocess,sys,time,zipfile
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts';D=P/'math_source_replay_v1'
sys.path.insert(0,str(S))
from arxiv_math_synced_renderer_v1 import MathSynced,POLICY
from arxiv_bulk_official_xml_png_math_v1 import WAR
from arxiv_author_native_assets_v1 import dependencies
from arxiv_author_native_asset_package_v1 import package
from priority_source_complexity_filter_v1 import native,classify
import arxiv_author_native_font_replay_v2 as fonts
from arxiv_sourceonly_bulk_200_v1_1 import facts
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.'+str(os.getpid())+'.tmp');q.write_text(json.dumps(x,ensure_ascii=True,indent=2)+'\n');os.replace(q,p)
def valuable(f):
 graph=(f['source_backed_logical_nodes']>=20 and f['connected_edges']>=15 and f['label_characters']>=200 and not f['directed_chain_only']) or (f['source_backed_logical_nodes']>=30 and f['label_characters']>=200) or (f['source_backed_logical_nodes']>=12 and f['connected_edges']>=12 and f['native_connected_groups']>=2 and f['label_characters']>=250)
 return graph or (f['native_vertices']>=60 and f['distinct_owner_labels']>=20 and f['label_characters']>=400 and f['image_objects']>=4)
def candidates():
 out={}
 for source in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
  db=P/source/'once.sqlite'
  with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
   for raw, in c.execute("select record from pdfs where status='technical_failure_review'"):
    row=json.loads(raw)
    if not row.get('author_xml_recovered') or 'MathJaxRender' not in row.get('reason',''):continue
    if not row.get('paper','')[:2].isdigit() or not 23<=int(row['paper'][:2])<=26:continue
    code=R/row['author_xml_file']
    if not code.exists() or sha(code)!=row['author_xml_sha256']:continue
    f=native(code.read_text());status,_=classify(f,'drawio',{})
    if status!='complex_candidate' or f['native_pages']!=1 or not valuable(f):continue
    out[row['id']]=dict(row,original_once_database=str(db.relative_to(R)),value_features=f)
 return out

def work(input_file):
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded_math_source_replay_170s')));signal.alarm(170)
 row=json.loads(input_file.read_text());case=input_file.parent;renderer=None;started=time.time();fonts.D=D
 record=dict(id=row['id'],status='pending_math_source_replay',at_utc=now(),new_PDF_import_calls=0,new_model_calls=0,old_failure_unchanged=True)
 try:
  with sqlite3.connect((R/row['original_once_database']).as_uri()+'?mode=ro',uri=True) as c:
   actual=json.loads(c.execute('select record from pdfs where id=?',(row['id'],)).fetchone()[0])
  for k in ['author_xml_sha256','pdf_sha256','reason']:assert actual[k]==row[k]
  original=R/row['author_xml_file'];pdf=R/row['pdf_file'];xml=original.read_bytes()
  assert sha(original)==row['author_xml_sha256'] and sha(pdf)==row['pdf_sha256']
  with zipfile.ZipFile(WAR) as war:dep=dependencies(xml,original,pdf,war)
  assert len(dep['models'])==1
  static={k:v for k,v in dep.items() if k not in ['models','asset_map']};put(case/'asset_audit.json',static)
  relative=any(a['status'] in ['author_adjacent_file','source_only_relative_asset_needs_portable_closure'] for a in dep['assets'])
  if dep['issues'] or relative:
   code,assets,meta=package(xml,dep,case/'standalone_asset_package')
   with zipfile.ZipFile(WAR) as war:closed=dependencies(xml,code,code.parent/'no_original_directory.pdf',war)
   assert not closed['issues'],'packaged_resource_closure_failed'
   assert all(Path(p).is_relative_to(case) for p in assets.values())
  else:
   folder=case/'code';folder.mkdir(exist_ok=False);code=folder/'author.drawio';code.write_bytes(xml);assets=dep['asset_map'];meta=None
  assert code.read_bytes()==xml
  renderer=MathSynced(assets);folder=case/'synced_source_replay';proof=renderer.replay(xml,folder)
  assert proof['ok'] and proof['font_observations']['all_physical_font_bytes_pinned']
  for f in proof['font_observations']['font_assets']:assert sha(R/f['file'])==f['sha256']
  assert sha(original)==row['author_xml_sha256'] and sha(pdf)==row['pdf_sha256']
  image=folder/'official.png';pid=hashlib.sha256((row['author_xml_sha256']+sha(image)+POLICY).encode()).hexdigest()
  pair=dict(id=pid,raw_source_pair_id=row['id'],raw_source_pair_ids=[row['id']],source='arxiv_author_native_drawio',paper=row['paper'],profile='author_native_source_replay',format='drawio',category='scientific_diagram',code_file=str(code.relative_to(R)),code_sha256=sha(code),image_file=str(image.relative_to(R)),image_sha256=sha(image),original_author_XML=row['author_xml_file'],original_author_XML_sha256=row['author_xml_sha256'],paired_code_XML_bytes_equal_original_author_XML=True,original_PDF_file=row['pdf_file'],original_PDF_sha256=row['pdf_sha256'],original_PDF_fidelity='review_not_certified',fresh_RGBA_equals_preexisting_native_PNG=False,quality_state='verified_under_versioned_official_math_source_replay_contract',native_replay_proof=str((folder/'synced_replay_proof.json').relative_to(R)),native_replay_proof_sha256=sha(folder/'synced_replay_proof.json'),source_once_databases=[row['original_once_database']],renderer_policy=POLICY,base_validation_thresholds_unchanged=True,repair_of_preserved_failure='missing_official_MathJax_initialization',prior_official_PDF_import_calls=actual['official_calls'],new_PDF_import_calls=0,new_model_calls=0,standalone_image_assets_complete=True,font_dependencies=proof['font_observations']['font_assets'],asset_package=meta,structural_complexity=facts(xml.decode()),drawing_object_counts_are_not_semantic_quality_labels=True,whole_figure_wrapper=False,official_WAR_sha256=sha(WAR))
  record.update(status='verified_math_author_native_source_replay',pair=pair)
 except Exception as e:record.update(reason=type(e).__name__+':'+str(e)[:1800])
 finally:
  if renderer:
   try:renderer.close()
   except Exception:pass
  signal.alarm(0);record.update(seconds=time.time()-started,finished_utc=now());put(case/'record.json',record)
 print(json.dumps(dict(id=row['id'],status=record['status'],reason=record.get('reason'))),flush=True)
 return record

def bounded(file):
 with sqlite3.connect(D/'once.sqlite') as c:
  changed=c.execute("update cases set status='attempt_started',record=? where id=? and status='queued'",(json.dumps(dict(id=file.parent.name,status='attempt_started',at_utc=now())),file.parent.name)).rowcount
  if changed!=1:
   old=c.execute('select record from cases where id=?',(file.parent.name,)).fetchone()
   assert old,'missing_once_case'
   return json.loads(old[0])
 with (file.parent/'worker.log').open('ab') as log:
  p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',str(file)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:p.wait(timeout=185)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10)
 result=file.parent/'record.json'
 return json.loads(result.read_text()) if result.exists() else dict(id=file.parent.name,status='pending_math_worker_exit',exit=p.returncode,new_PDF_import_calls=0)
def publish(c):
 rows=[json.loads(r[0]) for r in c.execute('select record from cases')];pairs=[r['pair'] for r in rows if r.get('pair')]
 path=D/'author_native_math_source_replay.jsonl';tmp=path.with_suffix('.tmp');tmp.write_text(''.join(json.dumps(r,ensure_ascii=True,sort_keys=True)+'\n' for r in pairs));os.replace(tmp,path)
 put(D/'summary.json',dict(at_utc=now(),states=dict(c.execute('select status,count(*) from cases group by status')),source_replay_verified=len(pairs),new_PDF_import_calls=0,new_model_calls=0,goal_complete=False))
def run():
 D.mkdir(exist_ok=True);lock=(D/'repair.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 test=json.loads((D/'procedure_selftest_runtime_svg_options_v3/synced_replay_proof.json').read_text());assert test['ok']
 with sqlite3.connect(D/'once.sqlite') as c:
  c.execute('create table if not exists cases(id text primary key,status text,record text)')
  while True:
   # A bounded child may finish after its controller exits. Recover its saved
   # terminal record without repeating the source replay or its PDF import.
   for ident, in c.execute("select id from cases where status='attempt_started'").fetchall():
    receipt=D/'cases'/ident/'record.json'
    if receipt.exists():
     result=json.loads(receipt.read_text());c.execute('update cases set status=?,record=? where id=?',(result['status'],json.dumps(result),ident))
   c.commit()
   pending=[]
   for ident,row in candidates().items():
    if c.execute('select 1 from cases where id=?',(ident,)).fetchone():continue
    folder=D/'cases'/ident;folder.mkdir(parents=True,exist_ok=True);file=folder/'input.json';put(file,row)
    c.execute('insert into cases values(?,?,?)',(ident,'queued',json.dumps(dict(id=ident,status='queued',at_utc=now()))));c.commit()
   pending=[D/'cases'/ident/'input.json' for ident, in c.execute("select id from cases where status='queued' order by id")]
   with cf.ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(bounded,pending):
     c.execute('update cases set status=?,record=? where id=?',(result['status'],json.dumps(result),result['id']));c.commit();publish(c)
   publish(c);time.sleep(60)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',type=Path);a=p.parse_args();work(a.case) if a.case else run()
