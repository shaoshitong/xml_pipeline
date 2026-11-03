"""Official replay of previously unprocessed drawio files in preserved arXiv sources.

The graph once key prevents repeats. Archive membership, bytes, relative assets,
font pins and all original strict replay gates are required. No PDF import,
new download, model invocation or original-source modification is performed.
"""
from pathlib import Path,PurePosixPath
import argparse,concurrent.futures as cf,datetime,fcntl,hashlib,json,os,signal,sqlite3,subprocess,sys,tarfile,time,zipfile
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts';D=P/'direct_author_XML_source_replay_v1';BASE=P/'recent_ai_source_expansion_v2/papers'
sys.path.insert(0,str(S))
from arxiv_math_stable_export_renderer_v1 import MathSynced,POLICY as RENDER_POLICY
from arxiv_math_source_repair_v1 import put,native,classify,valuable
from arxiv_author_native_assets_v1 import dependencies
from arxiv_author_native_asset_package_v1 import package
from arxiv_bulk_official_xml_png_math_v1 import WAR
from inventory_arxiv_direct_author_XML_v1 import graphhash
import arxiv_author_native_font_replay_v2 as fonts
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
POLICY=RENDER_POLICY+'__official_archive_direct_author_XML_graph_once_v1'
def archive_file(t,source,root):
 relative=source.resolve().relative_to(root.resolve()).as_posix()
 members=[m for m in t.getmembers() if m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts and str(PurePosixPath(m.name))==relative]
 assert len(members)==1,'archive_member_missing_or_ambiguous:'+relative
 m=members[0];assert m.size<=64*1024**2,'archive_member_above64MiB'
 with t.extractfile(m) as stream:b=stream.read(m.size+1)
 assert len(b)==m.size and hashlib.sha256(b).hexdigest()==sha(source),'archive_member_bytes_mismatch:'+relative
 return dict(member=m.name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def connect():
 c=sqlite3.connect(D/'once.sqlite',timeout=60);c.execute('pragma journal_mode=WAL');c.execute('create table if not exists cases(id text primary key,status text,record text)');return c
def discover(c):
 subprocess.run([sys.executable,str(S/'inventory_arxiv_direct_author_XML_v1.py')],check=True,timeout=120)
 pending=[]
 snapshot=P/'author_XML_inventory_v1/inventory.json';data=snapshot.read_bytes();inventory=json.loads(data);f=D/'inventory_snapshots'/(hashlib.sha256(data).hexdigest()+'.json');f.parent.mkdir(exist_ok=True)
 if not f.exists():f.write_bytes(data)
 with sqlite3.connect((P/'recent_ai_source_expansion_v2/once.sqlite').as_uri()+'?mode=ro',uri=True) as original:
  for row in inventory['candidates']:
   if row['state']!='unseen_source_graph':continue
   ident=row['decoded_graph_sha256']
   if c.execute('select 1 from cases where id=?',(ident,)).fetchone():continue
   state=original.execute('select status,record from papers where id=?',(row['paper'],)).fetchone()
   if not state or state[0]!='source_completed':continue
   try:metadata=json.loads(state[1]).get('metadata',{});published=datetime.datetime.fromisoformat(metadata['publication_date'].replace('Z','+00:00')).date()
   except (ValueError,KeyError,TypeError) as error:
    pending.append(dict(file=row['file'],reason='publication_metadata_unverified:'+str(error)));continue
   if not datetime.date(2023,1,1)<=published<=datetime.date(2026,11,2) or not set(metadata.get('categories',[])) & {'cs.AI','cs.CL','cs.CV','cs.LG'}:continue
   assert metadata['versioned_id']==row['paper']
   row.update(paper_metadata=metadata,original_paper_record_SHA256=hashlib.sha256(state[1].encode()).hexdigest())
   folder=BASE/row['paper'];receipt=folder/'source_receipt.json';archive=folder/'source.archive'
   if not receipt.exists() or not archive.exists():continue
   receipt_data=json.loads(receipt.read_text());assert receipt_data['url']=='https://arxiv.org/src/'+row['paper']
   row.update(id=ident,source_archive=str(archive.relative_to(R)),source_archive_SHA256=receipt_data['sha256'],source_receipt=str(receipt.relative_to(R)),source_receipt_SHA256=sha(receipt),inventory_snapshot=str(f.relative_to(R)),inventory_snapshot_SHA256=sha(f))
   case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True);put(case/'input.json',row);c.execute('insert into cases values(?,?,?)',(ident,'queued',json.dumps(dict(id=ident,status='queued'))))
 c.commit();put(D/'discovery_pending.json',pending)
def work(file):
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded_native_XML_replay_170s')));signal.alarm(170)
 row=json.loads(file.read_text());case=file.parent;renderer=None;started=time.monotonic();result=dict(id=row['id'],paper=row['paper'],status='pending_direct_author_XML_replay',new_PDF_import_calls=0,new_model_calls=0,at_utc=now());fonts.D=D
 try:
  policy=json.loads((D/'policy.json').read_text());pins=policy['files_SHA256'];assert sha(WAR)==policy['WAR_SHA256']
  with sqlite3.connect((P/'recent_ai_source_expansion_v2/once.sqlite').as_uri()+'?mode=ro',uri=True) as original:
   status,raw=original.execute('select status,record from papers where id=?',(row['paper'],)).fetchone();assert status=='source_completed' and hashlib.sha256(raw.encode()).hexdigest()==row['original_paper_record_SHA256']
  for n,h in pins.items():assert sha(R/n)==h,'recipe_changed:'+n
  author=R/row['file'];archive=R/row['source_archive'];receipt=R/row['source_receipt'];root=BASE/row['paper']/'source';xml=author.read_bytes()
  assert sha(author)==row['sha256'] and graphhash(xml)==row['decoded_graph_sha256'];assert sha(archive)==row['source_archive_SHA256'] and sha(receipt)==row['source_receipt_SHA256'];assert sha(R/row['inventory_snapshot'])==row['inventory_snapshot_SHA256']
  f=native(xml.decode('utf-8-sig'));kind,_=classify(f,'drawio',{});assert kind=='complex_candidate' and f['native_pages']==1 and valuable(f),'value_policy_not_met'
  with zipfile.ZipFile(WAR) as war:dep=dependencies(xml,author,author,war)
  provenance=[]
  with tarfile.open(archive) as t:
   provenance.append(archive_file(t,author,root))
   for asset in set(dep['asset_map'].values()):provenance.append(archive_file(t,Path(asset),root))
  put(case/'asset_audit.json',{k:v for k,v in dep.items() if k not in ['models','asset_map']});put(case/'archive_membership.json',dict(archive=row['source_archive'],SHA256=row['source_archive_SHA256'],members=provenance))
  relative=any(a['status'] in ['author_adjacent_file','source_only_relative_asset_needs_portable_closure'] for a in dep['assets'])
  if dep['issues'] or relative:
   code,assets,meta=package(xml,dep,case/'standalone_asset_package')
   with zipfile.ZipFile(WAR) as war:closed=dependencies(xml,code,code,war)
   assert not closed['issues'],'packaged_resource_closure_failed'
  else:
   (case/'code').mkdir(exist_ok=False);code=case/'code'/author.name;code.write_bytes(xml);assets=dep['asset_map'];meta=None
  assert code.read_bytes()==xml
  renderer=MathSynced(assets);out=case/'synced_source_replay';proof=renderer.replay(xml,out)
  assert proof['ok'] and proof['font_observations']['all_physical_font_bytes_pinned'],'strict_replay_or_fonts_failed'
  for font in proof['font_observations']['font_assets']:assert sha(R/font['file'])==font['sha256']
  for n,h in pins.items():assert sha(R/n)==h,'recipe_changed:'+n
  assert sha(author)==row['sha256'] and sha(archive)==row['source_archive_SHA256'] and sha(receipt)==row['source_receipt_SHA256']
  image=out/'official.png';pair=dict(id=hashlib.sha256((row['sha256']+sha(image)+POLICY).encode()).hexdigest(),raw_source_pair_id=row['id'],raw_source_pair_ids=[row['id']],source='arxiv_direct_author_drawio',paper=row['paper'],paper_metadata=row['paper_metadata'],profile='author_native_source_replay',format='drawio',category='scientific_diagram',code_file=str(code.relative_to(R)),code_sha256=sha(code),image_file=str(image.relative_to(R)),image_sha256=sha(image),original_author_XML=row['file'],original_author_XML_sha256=row['sha256'],paired_code_XML_bytes_equal_original_author_XML=True,original_PDF_file=None,original_PDF_sha256=None,original_PDF_fidelity='not_assessed_direct_author_source',actual_paper_PDF_figure_usage='not_certified',source_archive_file=row['source_archive'],source_archive_sha256=row['source_archive_SHA256'],source_receipt_file=row['source_receipt'],source_receipt_sha256=row['source_receipt_SHA256'],archive_membership_proof=str((case/'archive_membership.json').relative_to(R)),archive_membership_proof_sha256=sha(case/'archive_membership.json'),source_origin_kind='official_arxiv_archive_native_XML',native_replay_proof=str((out/'synced_replay_proof.json').relative_to(R)),native_replay_proof_sha256=sha(out/'synced_replay_proof.json'),source_once_databases=[str((D/'once.sqlite').relative_to(R))],renderer_policy=POLICY,base_validation_thresholds_unchanged=True,new_PDF_import_calls=0,new_model_calls=0,new_source_downloads=0,original_source_payloads_unchanged=True,standalone_image_assets_complete=True,asset_package=meta,font_dependencies=proof['font_observations']['font_assets'],whole_figure_wrapper=False,official_WAR_sha256=sha(WAR),fresh_RGBA_equals_preexisting_native_PNG=False)
  result.update(status='verified_direct_author_XML_source_replay',pair=pair)
 except Exception as e:result.update(reason=type(e).__name__+':'+str(e)[:1800])
 finally:
  if renderer:
   try:renderer.close()
   except Exception:pass
  signal.alarm(0);result.update(seconds=time.monotonic()-started,finished_utc=now());put(case/'record.json',result)
 return result
def bounded(file):
 with connect() as c:assert c.execute("update cases set status='attempt_started' where id=? and status='queued'",(file.parent.name,)).rowcount==1
 with (file.parent/'worker.log').open('ab') as log:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',str(file)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:child.wait(timeout=185)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 p=file.parent/'record.json';return json.loads(p.read_text()) if p.exists() else dict(id=file.parent.name,status='pending_direct_XML_worker_exit',exit=child.returncode,new_PDF_import_calls=0)
def publish(c):
 rows=[json.loads(r[0]) for r in c.execute('select record from cases')];pairs=[r['pair'] for r in rows if r.get('pair')];path=D/'author_native_source_replay.jsonl';tmp=path.with_suffix('.tmp');tmp.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in pairs));os.replace(tmp,path);put(D/'summary.json',dict(at_utc=now(),states=dict(c.execute('select status,count(*) from cases group by status')),verified=len(pairs),new_PDF_import_calls=0,new_model_calls=0,new_source_downloads=0,goal_complete=False))
def run(watch):
 D.mkdir(exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 test=P/'stable_export_protocol_selftest_v1/results.json';assert json.loads(test.read_text())['stable_export_ids']['ok']
 if not (D/'policy.json').exists():
  names=['arxiv_direct_author_XML_replay_v1.py','arxiv_math_stable_export_renderer_v1.py','arxiv_math_uniform_viewport_renderer_v1.py','arxiv_math_synced_renderer_v1.py','arxiv_author_native_synced_replay_v1.py','arxiv_bulk_official_xml_png_math_v1.py','arxiv_author_native_assets_v1.py','arxiv_author_native_asset_package_v1.py','inventory_arxiv_direct_author_XML_v1.py','arxiv_math_source_repair_v1.py','priority_source_complexity_filter_v1.py','arxiv_author_native_font_replay_v2.py']
  put(D/'policy.json',dict(policy=POLICY,files_SHA256={str((S/n).relative_to(R)):sha(S/n) for n in names},WAR_SHA256=sha(WAR),new_PDF_import_calls=0,source_XML_bytes_unchanged=True))
 c=connect()
 while True:
  for i, in c.execute("select id from cases where status='attempt_started'").fetchall():
   f=D/'cases'/i/'record.json'
   if f.exists():
    r=json.loads(f.read_text());c.execute('update cases set status=?,record=? where id=?',(r['status'],json.dumps(r),i))
  c.commit();discover(c);files=[D/'cases'/r[0]/'input.json' for r in c.execute("select id from cases where status='queued' order by id")]
  with cf.ThreadPoolExecutor(max_workers=2) as pool:
   for r in pool.map(bounded,files):c.execute('update cases set status=?,record=? where id=?',(r['status'],json.dumps(r),r['id']));c.commit();publish(c)
  publish(c)
  if not watch:break
  time.sleep(300)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',type=Path);p.add_argument('--watch',action='store_true');a=p.parse_args();work(a.case) if a.case else run(a.watch)
