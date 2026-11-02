"""Incremental author XML -> cold synchronized official source-replay audit. No PDF import."""
from pathlib import Path
import argparse,collections,concurrent.futures,datetime,fcntl,hashlib,io,json,os,signal,sqlite3,subprocess,sys,time,traceback,zipfile
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'author_native_source_replay_incremental_v1';OLD=P/'author_native_source_replay_v1';S=R/'conversion/scripts'
sys.path[:0]=[str(S),str(R/'scripts')]
from arxiv_author_native_assets_v1 import dependencies,sha
from arxiv_author_native_asset_package_v1 import package
from arxiv_author_native_synced_replay_v1 import Synced,POLICY,pixels
import arxiv_author_native_font_replay_v2 as font_storage
from arxiv_sourceonly_bulk_200_v1_1 import facts
from arxiv_bulk_official_xml_png_v1 import WAR
from PIL import Image
SOURCES=[P/n for n in ['new_bulk_200_v1','recent_ai_source_expansion_v2']]
NOW=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat();ENC=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True)
STOP=False;PIN_CACHE={}
def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)
def birth(pid):
 p=Path('/proc',str(pid),'stat')
 if not p.exists():return None
 f=p.read_text().split(') ',1)[1].split();return f[19] if f[0]!='Z' else None
def event(name,**data):
 line=(ENC({'at_utc':NOW(),'event':name,**data})+'\n').encode();fd=os.open(D/'events.jsonl',os.O_APPEND|os.O_CREAT|os.O_WRONLY,0o644)
 try:os.write(fd,line)
 finally:os.close(fd)
def db():
 c=sqlite3.connect(D/'once.sqlite',timeout=60);c.execute('pragma journal_mode=WAL');c.execute('create table if not exists cases(id text primary key,status text,record text,input_file text,pid integer,birth text,phase text)');c.execute('create table if not exists source_observations(id text,source text,primary key(id,source))');c.commit();return c
def pincheck(policy_path):
 policy=json.loads(Path(policy_path).read_text())
 for name,digest in policy['files_sha256'].items():
  p=Path(name);st=p.stat();key=(st.st_ino,st.st_size,st.st_mtime_ns)
  if PIN_CACHE.get(name)!=key:assert sha(p.read_bytes())==digest,'frozen_dependency_changed:'+name;PIN_CACHE[name]=key
 return policy
def authority(row):
 fields=['id','author_xml_sha256','image_sha256','pdf_sha256'];matches=[]
 for source in SOURCES:
  with sqlite3.connect((source/'once.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30) as c:r=c.execute("select record from pdfs where id=? and status='qualified_native_xml_png_pair'",(row['id'],)).fetchone()
  if r:
   actual=json.loads(r[0])
   if all(actual.get(k)==row.get(k) for k in fields):matches.append(str((source/'once.sqlite').relative_to(R)))
 assert matches,'source_manifest_does_not_match_official_once_authority'
 return matches
def init_baseline(c):
 old=json.loads((OLD/'published_source_replay_v2/manifest.json').read_text());assert sha((OLD/'published_source_replay_v2/source_replay_aligned.jsonl').read_bytes())=='8e1a635ec4532edebe8def1c333656efef0bb05ac2a19a807f5724684ef5b3fb'
 for row in map(json.loads,(OLD/'input_snapshot.jsonl').read_text().splitlines()):
  c.execute('insert or ignore into cases values(?,?,?,?,?,?,?)',(row['id'],'preserved_frozen_source_replay',ENC({'id':row['id'],'status':'preserved_frozen_source_replay','baseline_manifest':old['source_replay_file'],'source_reexecutions':0,'native_replays_added':0}),None,None,None,'frozen_baseline'))
 c.commit()
def discover(c):
 found={};snapshots=[]
 for source in SOURCES:
  path=source/'manifest.jsonl'
  if not path.exists():continue
  blob=path.read_bytes();rows=[json.loads(l) for l in blob.decode().splitlines() if l.strip()];snapshots.append({'file':str(path),'sha256':sha(blob),'rows':len(rows)})
  with sqlite3.connect((source/'once.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30) as authority_db:
   for row in rows:
    v=authority_db.execute("select record from pdfs where id=? and status='qualified_native_xml_png_pair'",(row['id'],)).fetchone()
    if not v:continue
    a=json.loads(v[0])
    if any(row.get(k)!=a.get(k) for k in ['author_xml_sha256','image_sha256','pdf_sha256']):event('manifest_authority_binding_pending',id=row['id'],manifest=str(path));continue
    item=found.setdefault(row['id'],row);item.setdefault('source_once_databases',[])
    dbname=str((source/'once.sqlite').relative_to(R))
    if dbname not in item['source_once_databases']:item['source_once_databases'].append(dbname)
    c.execute('insert or ignore into source_observations values(?,?)',(row['id'],dbname))
 added=0
 for ident,row in sorted(found.items()):
  if c.execute('select 1 from cases where id=?',(ident,)).fetchone():continue
  case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True);file=case/'input.json'
  if file.exists():assert json.loads(file.read_text())['author_xml_sha256']==row['author_xml_sha256'],'existing_input_binding_changed'
  else:
   with file.open('x') as f:f.write(ENC(row)+'\n')
  c.execute('insert into cases values(?,?,?,?,?,?,?)',(ident,'queued',ENC({'id':ident,'status':'queued','discovered_utc':NOW(),'input_sha256':sha(file.read_bytes())}),str(file),None,None,'incremental'));added+=1
 c.commit();event('discovery',raw_manifest_unique_candidates=len(found),new_queued=added,source_snapshots=snapshots);atomic(D/'latest_discovery.json',{'at_utc':NOW(),'raw_manifest_unique_candidates':len(found),'new_queued':added,'source_snapshots':snapshots});return found
def same_origin_padding(raw,fresh):
 a=Image.open(io.BytesIO(raw)).convert('RGBA');b=Image.open(io.BytesIO(fresh)).convert('RGBA');size=(max(a.width,b.width),max(a.height,b.height));aa=Image.new('RGBA',size,'white');bb=Image.new('RGBA',size,'white');aa.alpha_composite(a);bb.alpha_composite(b);equal=aa.tobytes()==bb.tobytes()
 return {'raw_size':list(a.size),'fresh_size':list(b.size),'same_origin_white_union_RGBA_exact':equal,'pixel_tolerance':0,'no_coordinate_or_pixel_fit':True} if equal and a.size!=b.size else None
def work_case(input_file,policy_path):
 signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('bounded_worker_alarm_170s')));signal.alarm(170);font_storage.D=D;row=json.loads(Path(input_file).read_text());case=Path(input_file).parent;record={'id':row['id'],'paper':row.get('paper'),'status':'typed_pending_author_native_source_replay','stage_seconds':{},'new_PDF_import_calls':0,'new_normal_calls':0,'new_models':0};renderer=None;began=time.monotonic()
 def measured(name,op):
  t=time.monotonic()
  try:return op()
  finally:record['stage_seconds'][name]=time.monotonic()-t
 try:
  policy=pincheck(policy_path);sources=authority(row);original=R/row['author_xml_file'];raw_png=R/row['image_file'];pdf=R/row['pdf_file'];xml=original.read_bytes();old_png=raw_png.read_bytes();assert sha(xml)==row['author_xml_sha256'] and sha(old_png)==row['image_sha256'] and sha(pdf.read_bytes())==row['pdf_sha256'],'original_payload_binding_changed'
  def asset_audit():
   with zipfile.ZipFile(WAR) as war:return dependencies(xml,original,pdf,war)
  dep=measured('bounded_model_and_asset_audit',asset_audit);assert len(dep['models'])==1,'multi_page_source_not_supported';structure=facts(xml.decode());assert structure['complexity_match'] and not structure['all_single_image_wrapper'],'noncomplex_or_whole_figure_wrapper'
  static={k:v for k,v in dep.items() if k not in {'models','asset_map'}};static['decoded_models']=len(dep['models']);static['original_author_XML_sha256']=sha(xml);staticfile=case/'static_asset_audit.json';atomic(staticfile,static)
  relative=any(a['status'] in {'author_adjacent_file','source_only_relative_asset_needs_portable_closure'} for a in dep['assets']);package_meta=None
  if dep['issues'] or relative:
   code,asset_map,package_meta=measured('standalone_exact_byte_resource_packaging',lambda:package(xml,dep,case/'standalone_asset_package'))
   with zipfile.ZipFile(WAR) as war:closed=dependencies(xml,code,code.parent/'no_original_source_directory.pdf',war)
   assert not closed['issues'],'package_only_resource_closure_failed'
   assert all(Path(p).is_relative_to(case) for p in asset_map.values()),'packaged_asset_map_references_original_source_directory'
  else:
   folder=case/'code';folder.mkdir(exist_ok=False);code=folder/'author.drawio';code.write_bytes(xml);asset_map=dep['asset_map']
  assert code.read_bytes()==xml,'author_XML_changed_during_packaging';folder=case/'synced_source_replay';renderer=measured('cold_full_Editor_start',lambda:Synced(asset_map));proof=measured('source_export_fonts_native_edit_exact_restore',lambda:renderer.replay(code.read_bytes(),folder))
  assert proof['ok'],'uniform_synced_official_edit_restore_failed';assert proof['source_XML_sha256']==sha(xml);assert proof['font_observations']['all_physical_font_bytes_pinned'],'actual_physical_font_asset_binding_pending'
  for f in proof['font_observations']['font_assets']:assert sha((R/f['file']).read_bytes())==f['sha256'],'actual_physical_font_file_changed'
  image=folder/'official.png';png=image.read_bytes();assert sha(png)==proof['source_official_PNG_sha256'];oldproof_file=R/row['render_edit_evidence'];oldproof=json.loads(oldproof_file.read_text());assert oldproof['edit_probe']['mutation_actual_PNG_changed'] and oldproof['edit_probe']['restored_actual_PNG_exact'],'raw_native_acceptance_proof_missing';equal=pixels(png)==pixels(old_png);padding=same_origin_padding(old_png,png);pairid=sha(ENC({'profile':'author_native_source_replay','author_XML_sha256':sha(xml),'code_sha256':sha(code.read_bytes()),'source_PNG_sha256':sha(png),'synced_protocol':POLICY}).encode())
  pair={'id':pairid,'raw_source_pair_id':row['id'],'raw_source_pair_ids':[row['id']],'source':'arxiv_author_native_drawio','paper':row.get('paper'),'profile':'author_native_source_replay','format':'drawio','source_format':'author_drawio_XML_embedded_in_PDF','category':'scientific_diagram','quality_state':'verified_under_declared_author_native_source_replay_contract','code_file':str(code.relative_to(R)),'code_sha256':sha(code.read_bytes()),'image_file':str(image.relative_to(R)),'image_sha256':sha(png),'source_code_sha256':sha(xml),'source_image_sha256':sha(png),'source_image_origin':'fresh_cold_source_only_official_drawio_full_Editor_Graph.getSvg_PNG_uniform_synced_protocol','original_author_XML':row['author_xml_file'],'original_author_XML_sha256':sha(xml),'paired_code_XML_bytes_equal_original_author_XML':True,'author_XML_original_file_unmodified':True,'auxiliary_preexisting_native_PNG':row['image_file'],'auxiliary_preexisting_native_PNG_sha256':sha(old_png),'fresh_RGBA_equals_preexisting_native_PNG':equal,'native_canvas_padding_equivalence':padding,'raw_native_PNG_difference_is_not_used_as_reference_substitution':True,'original_PDF_file':row['pdf_file'],'original_PDF_sha256':row['pdf_sha256'],'original_PDF_fidelity':'review_not_certified','provider_original_reference_aligned':False,'legacy_full8_qualified':False,'historical_author_OS_fonts_exact':False,'standalone_image_assets_complete':True,'standalone_font_portability_certified':False,'font_portability_state':'runtime_bound_current_actual_physical_faces_bundled; author font styles not rewritten','font_dependencies':proof['font_observations']['font_assets'],'actual_painted_Text_backend_nodes':proof['font_observations']['Text_nodes'],'actual_Unicode_characters':proof['font_observations']['Unicode_characters'],'source_once_databases':sources,'native_replay_proof':str((folder/'synced_replay_proof.json').relative_to(R)),'native_replay_proof_sha256':sha((folder/'synced_replay_proof.json').read_bytes()),'old_native_render_edit_proof':row['render_edit_evidence'],'old_native_render_edit_proof_sha256':sha(oldproof_file.read_bytes()),'asset_audit':str(staticfile.relative_to(R)),'asset_audit_sha256':sha(staticfile.read_bytes()),'asset_package':package_meta,'structural_complexity':structure,'drawing_object_counts_are_not_semantic_quality_labels':True,'whole_figure_wrapper':False,'new_PDF_import_calls':0,'new_normal_calls':0,'new_model_calls':0,'renderer_policy':POLICY,'audit_policy_id':policy['policy_id'],'audit_policy_file':str(Path(policy_path).relative_to(R)),'source_geometry_or_pixel_fitting':False,'official_WAR_sha256':sha(WAR.read_bytes())}
  assert sha(original.read_bytes())==row['author_xml_sha256'] and sha(raw_png.read_bytes())==row['image_sha256'] and sha(pdf.read_bytes())==row['pdf_sha256'],'old_source_payload_changed';pincheck(policy_path);record.update(status='verified_author_native_source_replay',pair=pair)
 except Exception as e:record.update(reason=type(e).__name__+':'+str(e)[:1600],traceback=traceback.format_exc()[-3500:])
 finally:
  if renderer:
   try:renderer.close()
   except Exception:pass
  signal.alarm(0);record['seconds']=time.monotonic()-began;record['finished_epoch']=time.time();record['finished_utc']=NOW();atomic(case/'record.json',record)
 print(ENC({'id':row['id'],'status':record['status'],'reason':record.get('reason'),'seconds':record['seconds']}),flush=True);return record
def bounded_run(input_file,policy_path):
 case=Path(input_file).parent;t=time.monotonic();command=[sys.executable,str(S/'arxiv_author_native_incremental_v1.py'),'--case',str(input_file),'--policy',str(policy_path)]
 with (case/'worker.log').open('ab') as log:
  p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=str(R/'env')),start_new_session=True)
  atomic(case/'worker_process.json',{'PID':p.pid,'birth':birth(p.pid),'parent_PID':os.getpid(),'parent_birth':birth(os.getpid()),'started_epoch':time.time(),'max_seconds':180,'command':command})
  try:p.wait(timeout=180)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   result={'id':case.name,'status':'typed_pending_worker_timeout_180s','reason':'bounded_cold_replay_worker_timeout; no automatic second attempt','seconds':time.monotonic()-t,'finished_epoch':time.time(),'stage_seconds':{},'new_PDF_import_calls':0,'new_models':0};atomic(case/'record.json',result)
 result=case/'record.json'
 if result.exists():return json.loads(result.read_text())
 value={'id':case.name,'status':'typed_pending_worker_exit_without_record','reason':'exit='+str(p.returncode),'seconds':time.monotonic()-t,'finished_epoch':time.time(),'stage_seconds':{},'new_PDF_import_calls':0,'new_models':0};atomic(result,value);return value
def publish(c,phase,started):
 records=[json.loads(r[0]) for r in c.execute("select record from cases where status not in ('queued','running','preserved_frozen_source_replay')")];groups=collections.defaultdict(list)
 for r in records:
  if r.get('pair'):groups[(r['pair']['code_sha256'],r['pair']['image_sha256'])].append(r['pair'])
 pairs=[]
 for group in groups.values():
  p=dict(group[0]);p['raw_source_pair_ids']=sorted({r['raw_source_pair_id'] for r in group});p['raw_source_provenance']=[{k:r.get(k) for k in ['raw_source_pair_id','paper','source_once_databases','original_author_XML','original_author_XML_sha256','auxiliary_preexisting_native_PNG','auxiliary_preexisting_native_PNG_sha256','original_PDF_file','original_PDF_sha256','native_replay_proof','native_replay_proof_sha256','old_native_render_edit_proof','old_native_render_edit_proof_sha256','asset_audit','asset_audit_sha256']} for r in sorted(group,key=lambda r:r['raw_source_pair_id'])];p['source_once_databases']=sorted({s for r in group for s in r['source_once_databases']});pairs.append(p)
 path=D/'author_native_source_replay.jsonl';tmp=path.with_suffix('.tmp');tmp.write_text(''.join(ENC(p)+'\n' for p in sorted(pairs,key=lambda r:r['id'])));os.replace(tmp,path);states=dict(c.execute('select status,count(*) from cases group by status'));failures=collections.Counter(r.get('reason','').split(':',2)[0]+':'+r.get('reason','').split(':',2)[1] if ':' in r.get('reason','') else r.get('reason','unknown') for r in records if not r.get('pair'));stage=collections.defaultdict(list)
 for r in records:
  for name,seconds in r.get('stage_seconds',{}).items():stage[name].append(seconds)
 recent=sorted(records,key=lambda r:r.get('finished_epoch',0))[-50:];span=max((r.get('finished_epoch',0) for r in recent),default=0)-min((r.get('finished_epoch',0)-r.get('seconds',0) for r in recent),default=0);success=sum(bool(r.get('pair')) for r in records);rate=success/max(1,len(records));analysis=[]
 if len(records)>=10 and rate<.5:analysis.append({'cause':'low_native_replay_pass_rate','failure_families':failures.most_common(5),'action':'typed failures are once-only; source/asset/font context retained for a versioned common repair, no model/import retry'})
 summary={'at_utc':NOW(),'phase':phase,'states':states,'new_raw_candidates_finished':len(records),'new_raw_source_replays_verified':success,'unique_new_pairs':len(pairs),'merged_raw_backlinks':sum(len(p['raw_source_pair_ids']) for p in pairs),'file':str(path),'sha256':sha(path.read_bytes()),'profile':'author_native_source_replay','old_frozen_pairs':25,'old_frozen_raw_candidates':26,'old_frozen_manifest_unchanged':True,'elapsed_controller_seconds':time.monotonic()-started,'rolling_last50_cases_per_minute':len(recent)/max(1,span)*60,'qualified_fraction':rate,'stage_seconds':{name:{'count':len(v),'total_worker_seconds':sum(v),'mean_seconds':sum(v)/len(v)} for name,v in stage.items()},'failure_families':failures.most_common(12),'common_cause_analysis':analysis,'new_PDF_import_calls':0,'new_models':0,'legacy_full8_or_original_PDF_claimed':False,'runtime_bound_fonts':True,'all_payloads_HKUST':True};atomic(D/'summary.json',summary);return summary
def controller(pilot,policy_path):
 global STOP
 D.mkdir(parents=True,exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);pincheck(policy_path);c=db();init_baseline(c);discover(c)
 for ident,record,pid,stamp in c.execute("select id,record,pid,birth from cases where status='running'").fetchall():
  if birth(pid)==stamp:raise RuntimeError('prior_controller_still_live:'+ident)
  receipt=D/'cases'/ident/'worker_process.json'
  if receipt.exists():
   w=json.loads(receipt.read_text())
   if birth(w['PID'])==w['birth']:raise RuntimeError('prior_bounded_worker_still_live:'+ident)
  file=D/'cases'/ident/'record.json';r=json.loads(file.read_text()) if file.exists() else {'id':ident,'status':'typed_pending_interrupted_cold_replay_not_repeated','reason':'prior audit claim interrupted; no silent second replay','seconds':0,'stage_seconds':{},'finished_epoch':time.time()};c.execute('update cases set status=?,record=? where id=?',(r['status'],ENC(r),ident))
 c.commit();began=time.monotonic();phase='pilot2' if pilot else 'incremental';pilot_ids=None
 if pilot:
  seed='arxiv-native-synced-replay-incremental-unseen2-v1-20261102';available=[(ident,json.loads(Path(file).read_text())) for ident,file in c.execute("select id,input_file from cases where status='queued'")];old_author={r['author_xml_sha256'] for r in map(json.loads,(OLD/'input_snapshot.jsonl').read_text().splitlines())};selected=sorted([(i,r) for i,r in available if r['author_xml_sha256'] not in old_author],key=lambda a:sha((seed+'|'+a[0]).encode()));chosen=[];papers=set()
  for ident,row in selected:
   if row.get('paper') not in papers:chosen.append(ident);papers.add(row.get('paper'))
   if len(chosen)==2:break
  assert len(chosen)==2;pilot_ids=set(chosen);atomic(D/'pilot_selection.json',{'seed':seed,'ids':chosen,'different_author_XML_from_old26':True,'different_papers':True,'selection_before_new_render_or_score':True})
 def stop(signum,frame):
  global STOP
  STOP=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);event('collector_started',pid=os.getpid(),birth=birth(os.getpid()),phase=phase,workers=2);last_discovery=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
  active={}
  while True:
   if not pilot and time.monotonic()-last_discovery>=30:discover(c);last_discovery=time.monotonic()
   if not STOP:
    queued=list(c.execute("select id,input_file from cases where status='queued' order by id"))
    for ident,file in queued:
     if len(active)>=2:break
     if pilot and ident not in pilot_ids:continue
     marker=Path(file).parent/'audit_attempt_started.json'
     if marker.exists():r={'id':ident,'status':'typed_pending_prior_attempt_not_repeated','reason':'once marker already exists without terminal record','seconds':0,'stage_seconds':{},'finished_epoch':time.time()};c.execute('update cases set status=?,record=? where id=?',(r['status'],ENC(r),ident));c.commit();continue
     with marker.open('x') as f:f.write(ENC({'at_utc':NOW(),'policy':str(policy_path),'controller_pid':os.getpid(),'controller_birth':birth(os.getpid()),'max_worker_seconds':180})+'\n')
     c.execute('update cases set status=?,pid=?,birth=?,phase=? where id=?',('running',os.getpid(),birth(os.getpid()),phase,ident));c.commit();active[executor.submit(bounded_run,file,policy_path)]=ident
   completed,_=concurrent.futures.wait(active,timeout=10,return_when=concurrent.futures.FIRST_COMPLETED) if active else (set(),None)
   for future in completed:
    ident=active.pop(future)
    try:r=future.result()
    except Exception as e:r={'id':ident,'status':'typed_pending_controller_worker_exception','reason':type(e).__name__+':'+str(e),'seconds':0,'stage_seconds':{},'finished_epoch':time.time()}
    c.execute('update cases set status=?,record=?,pid=NULL,birth=NULL where id=?',(r['status'],ENC(r),ident));c.commit();event('case_finished',id=ident,status=r['status'],seconds=r['seconds'],reason=r.get('reason'))
   summary=publish(c,phase,began)
   if pilot and not active and all(c.execute('select status from cases where id=?',(i,)).fetchone()[0]!='queued' for i in pilot_ids):
    pilot_records=[json.loads(c.execute('select record from cases where id=?',(i,)).fetchone()[0]) for i in sorted(pilot_ids)];atomic(D/'pilot_results.json',{'ok':all(r.get('pair') for r in pilot_records),'records':pilot_records,'summary':summary});break
   if STOP and not active:break
   if not active:time.sleep(10)
 pincheck(policy_path);publish(c,phase+'_stopped',began);c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case');p.add_argument('--policy',required=True);p.add_argument('--pilot',action='store_true');p.add_argument('--daemon',action='store_true');args=p.parse_args()
 if args.case:work_case(args.case,args.policy)
 else:controller(args.pilot,Path(args.policy))
