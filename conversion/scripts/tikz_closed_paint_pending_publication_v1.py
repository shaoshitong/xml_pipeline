"""Short-transaction pending pointer publication; no acceptance or budget writes.

All expensive source/browser/QA work happens before plan preparation. Inside
BEGIN IMMEDIATE only exact schema/ID-row/file/pin CAS and a jobs pointer update
run. No claims, new tables, watch loop, producer, queue updates or ledger reset.
"""
import datetime,hashlib,json,os,re,sqlite3,time
from pathlib import Path
import tikz_closed_paint_candidate_v1 as bundle
import program_terminal_outcomes_v2 as shared

R=bundle.ROOT;W=R/'conversion';VERSION='closed_tikz_candidate_pending_fullschema_CAS_v1'
sha=bundle.sha;canonical=bundle.canonical;require=bundle.require
LOADED_SHA256=sha(Path(__file__).read_bytes())
SHARED_PINS={str(Path(m.__file__).absolute()):sha(Path(m.__file__).read_bytes()) for m in (shared,shared.frozen)}
JOBS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
OUTCOME=('id','category','format','source_code_hash','source_image_hash','status','reason','record','updated_at')
QUEUES=('harness_queue','harness_queue_v2','harness_queue_v3')
GLOBALS={'auto_quality_inventory_meta_v2','initial_conversion_runs_v1','model_policy_v1','sqlite_sequence'}
IDLE={'queued','tikz_source_rendered','initial_conversion_deferred_v1','needs_fallback','rendered','needs_quality_repair','harness_review_pending','harness_rendered'}
INITIAL_STAGE_COLUMNS=('id','stage','source_code_hash','source_image_hash','stage_input_hash','state','owner_pid','owner_start_ticks','claim_token','policy','record','updated_at')
INITIAL_RECOVERY_COLUMNS=('id','stage','source_code_hash','source_image_hash','stage_input_hash','reason','record','updated_at')
INITIAL_POLICY='bounded_offline_initial_tikz_v1b:e73bc05db8e1a1b13637'
TARGET_STATE='needs_quality_repair';TARGET_ROUTE='tikz_closed_paint_projection_candidate_v1';TARGET_ERROR='Pending deterministic closed-paint/source-projection candidate; independent complete-source quality policy required'


def _safe(name):require(re.fullmatch('[A-Za-z0-9_]+',name) is not None,'unreviewed SQL identifier');return '"'+name+'"'
def _value(x):return {'BLOB_SHA256':sha(x),'bytes':len(x)} if isinstance(x,bytes) else x

def schema_snapshot(db):
 rows=db.execute("select type,name,tbl_name,sql from sqlite_master where name not like 'sqlite_stat%' order by type,name").fetchall();tables={}
 for kind,name,table,sql in rows:
  if kind!='table':continue
  q=_safe(name);cols=[list(x) for x in db.execute('pragma table_xinfo('+q+')')];tables[name]={'columns':cols,'foreign_keys':[list(x) for x in db.execute('pragma foreign_key_list('+q+')')]}
 require(tuple(x[1] for x in tables['jobs']['columns'])==JOBS,'unknown full jobs schema');require(tuple(x[1] for x in tables['processing_outcomes_v2']['columns'])==OUTCOME,'unknown full outcomes schema');unknown=[t for t,v in tables.items() if 'id' not in [c[1] for c in v['columns']] and t not in GLOBALS];require(not unknown,'unclassified tables without per-source id: '+','.join(unknown))
 return {'sqlite_master':[list(x) for x in rows],'tables':tables,'user_version':db.execute('pragma user_version').fetchone()[0],'application_id':db.execute('pragma application_id').fetchone()[0],'schema_version':db.execute('pragma schema_version').fetchone()[0]}

def scope_snapshot(db,identifier,schema):
 result={}
 for name,info in schema['tables'].items():
  cols=[x[1] for x in info['columns']];query='select * from '+_safe(name);args=()
  if 'id' in cols:query+=' where id=?';args=(identifier,)
  else:
   if name in ('auto_quality_inventory_meta_v2','initial_conversion_runs_v1'):
    result[name]={'columns':cols,'rows':[],'row_scope':'non_case_aggregate; full schema bound; whole aggregate protected before/after our writer transaction'};continue
  rows=[[_value(v) for v in r] for r in db.execute(query,args)];rows.sort(key=canonical);result[name]={'columns':cols,'rows':rows}
 return result

def _dicts(scope,table):
 s=scope.get(table);return [dict(zip(s['columns'],r)) for r in s['rows']] if s else []
def initial_deferred_owner(scope,row,record):
 require(tuple(scope['initial_conversion_stage_attempts_v1']['columns'])==INITIAL_STAGE_COLUMNS and tuple(scope.get('initial_conversion_recovery_v1',{}).get('columns',[]))==INITIAL_RECOVERY_COLUMNS,'unknown initial terminal receipt schemas')
 key=[record['id'],'native',record['source_code_sha256'],record['source_image_sha256'],row.get('stage_input_hash')];require([row.get(k) for k in INITIAL_STAGE_COLUMNS[:5]]==key and row.get('state')=='deferred_recovery_tier' and row.get('policy')==INITIAL_POLICY,'not an admitted initial native deferred terminal')
 require(type(row.get('owner_pid')) is int and row['owner_pid']>0 and type(row.get('owner_start_ticks')) is int and row['owner_start_ticks']>0 and re.fullmatch('[0-9a-f]{32}',row.get('claim_token') or ''),'incomplete historical initial owner identity')
 recoveries=[r for r in _dicts(scope,'initial_conversion_recovery_v1') if [r.get(k) for k in INITIAL_RECOVERY_COLUMNS[:5]]==key];require(len(recoveries)==1,'missing/ambiguous matching initial recovery receipt');recovery=recoveries[0];doc=json.loads(recovery['record']);claim=doc.get('claim') or {};result=doc.get('result') or {};terminal=json.loads(row['record']);require(claim.get('key')==key and claim.get('id')==record['id'] and claim.get('stage')=='native' and claim.get('policy')==row['policy'] and claim.get('pid')==row['owner_pid'] and claim.get('pid_start_ticks')==row['owner_start_ticks'] and claim.get('token')==row['claim_token'],'recovery nonce/source/stage/owner does not match terminal row');require(canonical(result)==canonical(terminal) and result.get('state')=='deferred_recovery_tier' and result.get('ok') is False and result.get('published') is False and result.get('accepted') is False and result.get('model_calls')==0 and result.get('larger_or_recovery_tier_required') is True and result.get('reason')==recovery['reason'],'not a committed nonpublished deferred result; prepared/unknown commits retain ownership')
 require((result.get('id'),result.get('stage'),result.get('code_sha256'),result.get('image_sha256'),result.get('stage_input_hash'))==tuple(key),'terminal result source key differs');require(not any(x in str(result.get('reason','')).lower() for x in ('prepared','publication','commit')),'prepared or unknown publication result cannot be terminal idle')
 executions=_dicts(scope,'tikz_renders');require(len(executions)==1,'original execution receipt missing/ambiguous');execution=executions[0];actual=[execution.get(k) for k in scope['tikz_renders']['columns']];require(claim.get('prior_execution')==actual and execution.get('state')=='tikz_source_rendered' and execution.get('error') is None,'original execution receipt changed since the exact native lease');compiled=json.loads(execution['record']);require(compiled.get('id')==record['id'] and compiled.get('source')==record['source'] and compiled.get('source_code_sha256')==record['source_code_sha256'] and compiled.get('pdf_sha256')==key[4] and compiled.get('compile_returncode')==0 and compiled.get('pages')==1,'original source compilation/input PDF differs')
 prior=claim.get('prior_snapshot');owned=claim.get('owned_snapshot');require(isinstance(prior,list) and isinstance(owned,list) and len(prior)==len(owned)==len(JOBS),'missing complete original claim snapshots');prior=dict(zip(JOBS,prior));owned=dict(zip(JOBS,owned));require(prior['id']==owned['id']==record['id'] and prior['worker_pid'] is None and owned['worker_pid']==row['owner_pid'] and prior['output_record'] is None and owned['output_record'] is None and prior['input_record']==owned['input_record'] and json.loads(prior['input_record'])==record['source_record'],'terminal claim lost source/prior logical ownership');require(owned['attempts']==prior['attempts']+1 and owned['state']=='initial_tikz_native_v1b_running','unreviewed original native lease transition');require(doc.get('work')=='conversion/initial_conversion_supervisor_v1/'+record['id']+'/native/'+key[4]+'/'+row['claim_token'],'unowned initial recovery work locator')
 return {'historical_receipt_not_live_lease':True,'key':key,'nonce':row['claim_token'],'original_execution_pdf':{'file':compiled['pdf_file'],'sha256':key[4]}}

def admission(scope,record):
 jobs=_dicts(scope,'jobs');require(len(jobs)==1,'missing/duplicate source job');job=jobs[0];original=json.loads(job['input_record']);manifest=json.loads(job['input_manifest']);out=_dicts(scope,'processing_outcomes_v2');require(len(out)==1 and out[0]['status']=='pending','original scope not pending');out=out[0];require(job['state'] in IDLE and job['worker_pid'] is None,'job currently owned/not an admitted idle state');require(job['id']==record['id']==record['source_pair_sha256']==original['pair_sha256']==manifest['id'],'pair identity differs');require(job['category']==original['category']==record['category']==out['category'] and job['category'] in ('scientific_diagram','poster'),'outside requested source category');require(job['format']==original['format']==record['source_format']==manifest['source_format']==out['format']=='tikz','source format changed');require(job['source']==record['source']==original['source'] and record['source_record']==original,'source dataset or full input record changed');require((out['source_code_hash'],out['source_image_hash'])==(record['source_code_sha256'],record['source_image_sha256'])==(original['code_sha256'],original['image_sha256'])==(manifest['code_sha256'],manifest['image_sha256']),'source code/image hashes changed');require(record.get('accepted') is False and record['quality_state'].startswith('pending_') and not record.get('automatic_quality_policy') and record.get('model_calls')==0,'candidate must remain unaccepted and model-free')
 require(job['output_record'] is None or json.loads(job['output_record'])==record,'different existing candidate lineage is outside this initial source-only publisher')
 for table,block in scope.items():
  for row in _dicts(scope,table):
   state=str(row.get('state',''));pid=row.get('worker_pid');owner=row.get('owner_pid')
   if table in QUEUES:
    require(pid is None and (state.startswith('held_') or state in ('done','failed','abandoned','budget_exhausted','complete','completed','cancelled','unsupported_source')),'model queue live/runnable/unclassified: '+table+':'+state)
   elif table!='jobs' and 'state' in row:
    require(not (state in ('running','claimed','processing','leased','in_progress','prepared_waiting_publication','waiting_publication') or state.endswith(('_producing','_repairing','_converting','_rendering'))),'active source stage owner: '+table+':'+state)
    require(pid is None,'non-null source-stage worker: '+table)
    if owner is not None:
     require(table=='initial_conversion_stage_attempts_v1','unverified terminal owner on table '+table+':'+state);initial_deferred_owner(scope,row,record)
 return job

def stat_pin(path):
 s=Path(path).stat();return [s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

def file_preflight(result,quality,root,quality_file,record_file):
 root=Path(root);record=result['record'];require(result.get('accepted') is False and result.get('published') is False and result.get('staging_only') is True,'not an immutable pending proposal');require(Path(record_file).read_bytes()==canonical(record),'candidate metadata bytes differ');manifest=bundle.load_manifest(root,record,bundle.checked(root,{'file':record['code_file'],'sha256':record['code_sha256']}).decode());require(quality.get('version')=='independent_deterministic_candidate_quality_readonly_v1' and quality.get('ok') is True and quality.get('accepted') is False and quality.get('canonical_mutations')==0 and quality['id']==record['id'],'missing independent complete source/native QA');require(quality['data_root']==str(root.resolve()) and quality['input_record_sha256']==sha(Path(record_file).read_bytes()),'quality candidate metadata binding differs');source=quality['checks']['source'];require(source.get('supported') is True and source.get('ok') is True and source.get('evidence',{}).get('complete_source_coverage') is True,'partial source proof cannot publish a candidate');require(quality['checks']['render']['code_sha256']==record['code_sha256'] and quality['checks']['render']['image_sha256']==record['image_sha256'],'fresh strict native pair differs');require(quality['checks']['native_editing'].get('ok') is True and quality['checks']['visual'].get('ok') is True,'native editing or original-image quality failed');import tikz_closed_paint_quality_adapter_v1 as adapter
 cfg=adapter.configuration(root);require(quality['profile_policy']==cfg['policy']==record['candidate_quality_adapter']['policy'] and source['evidence']['current_program_policy']==cfg['policy'],'unknown or stale complete-source adapter policy')
 for p,h in cfg['pins'].items():require(quality['implementation_pins'].get(p)==h,'quality report omits/changes required complete-source program pin')
 dependencies=source['evidence'].get('required_software_dependencies');expected_dependencies={p:v['sha256'] for p,v in json.loads(bundle.checked(root,manifest['files']['source_environment'])).items()};require(dependencies==expected_dependencies and dependencies,'complete original source software dependency closure missing/differs')
 for p,h in dependencies.items():require(p in cfg['environment'] and cfg['environment'][p]['sha256']==h and sha(Path(p).read_bytes())==h,'recorded source software changed/missing')
 require(source['evidence']['candidate_code_sha256']==record['code_sha256'] and source['evidence']['clean_source_manifest']==record[bundle.FIELD],'source QA evidence belongs to another candidate manifest')
 files={}
 for locator,entry in result['publish_files'].items():
  blob=bundle.checked(root,{'file':locator,'sha256':entry['sha256'],'bytes':entry['bytes']});files[str(root/locator)]=entry['sha256']
 files[str(Path(quality_file).absolute())]=sha(Path(quality_file).read_bytes());files[str(Path(record_file).absolute())]=sha(Path(record_file).read_bytes());return files

def logical_witnesses(root,record,manifest,scope,files,pins):
 root=Path(root).absolute();expected={**pins,**files};durable=set(files);required_clean=set(str(root/item['file']) for item in manifest['files'].values());required_clean.update(str(root/record[k]) for k in ('code_file','image_file','original_source_code','original_reference','source_render_pdf','source_render_svg'));required_clean.add(str(root/record[bundle.FIELD]['file']))
 job=_dicts(scope,'jobs')[0];inputs=json.loads(job['input_manifest']);authorities=[job,json.loads(job['input_record']),inputs,record,manifest];
 for key,digest in [('source_code','code_sha256'),('reference_image','image_sha256')]:
  rel=Path(inputs[key]);require(not rel.is_absolute() and '..' not in rel.parts,'invalid authoritative source locator');path=root/rel;require(path.resolve(strict=True).is_relative_to(root.resolve()),'authoritative source outside registered root');expected[str(path)]=inputs[digest];durable.add(str(path))
 for row in _dicts(scope,'initial_conversion_stage_attempts_v1'):
  if row.get('owner_pid') is not None:
   proof=initial_deferred_owner(scope,row,record);item=proof['original_execution_pdf'];path=root/item['file'];require(path.resolve(strict=True).is_relative_to(root.resolve()/'conversion'),'original execution PDF outside owned conversion root');expected[str(path)]=item['sha256'];durable.add(str(path))
 witnesses={p:shared.file_witness(root,p,h) for p,h in sorted(expected.items())};resolved={w['identity']['resolve']:w['sha256'] for w in witnesses.values()}
 for authority in authorities:
  for p,h in shared._logical_aliases(authority,root,resolved).items():
   if p not in witnesses:witnesses[p]=shared.file_witness(root,p,h)
 for p in required_clean:
  require(p in witnesses and Path(witnesses[p]['identity']['resolve']).is_relative_to(root.resolve()/'clean'),'required logical payload resolves outside clean')
 return witnesses,sorted(required_clean),sorted(durable)

def fsync_prepared(root,witnesses,durable):
 # Only owned data/evidence is newly staged. Installed software needs no fsync.
 root=Path(root).resolve();directories=set()
 for key in durable:
  witness=witnesses[key];path=Path(witness['identity']['logical']);resolved=Path(witness['identity']['resolve'])
  if not resolved.is_relative_to(root):continue
  fd=os.open(path,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
  if resolved.is_relative_to(root/'clean'):
   for parent in resolved.parents:
    if parent==root:break
    directories.add(parent)
 for directory in sorted(directories,key=lambda p:len(p.parts),reverse=True):
  fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 shared._check_identities(root,witnesses)

def prepare_plan(db,result,quality_file,record_file,root=R):
 require(not db.in_transaction,'prepare requires RO autocommit');require(sha(Path(__file__).read_bytes())==LOADED_SHA256,'publisher changed after import');quality=json.loads(Path(quality_file).read_text());files=file_preflight(result,quality,root,quality_file,record_file);pins=dict(quality['implementation_pins']);dependencies=quality.get('checks',{}).get('source',{}).get('evidence',{}).get('required_software_dependencies',{})
 for p,h in dependencies.items():require(p not in pins or pins[p]==h,'conflicting source software pin');pins[p]=h
 pins[str(Path(__file__).absolute())]=LOADED_SHA256
 for p,h in SHARED_PINS.items():require(sha(Path(p).read_bytes())==h,'shared witness implementation changed');pins[p]=h
 for path,digest in pins.items():require(sha(Path(path).read_bytes())==digest,'pinned candidate/quality program changed')
 db.execute('begin')
 try:schema=schema_snapshot(db);scope=scope_snapshot(db,result['id'],schema);job=admission(scope,result['record'])
 finally:db.rollback()
 manifest=bundle.load_manifest(root,result['record']);witnesses,required_clean,durable=logical_witnesses(root,result['record'],manifest,scope,files,pins);fsync_prepared(root,witnesses,durable)
 db.execute('begin')
 try:require(schema_snapshot(db)==schema and scope_snapshot(db,result['id'],schema)==scope,'complete source context changed during cryptographic preparation')
 finally:db.rollback()
 plan={'version':VERSION,'id':result['id'],'record':result['record'],'record_file':str(Path(record_file).absolute()),'record_raw_sha256':sha(Path(record_file).read_bytes()),'quality_file':str(Path(quality_file).absolute()),'quality_sha256':sha(Path(quality_file).read_bytes()),'schema':schema,'scope':scope,'files':files,'pins':pins,'file_witnesses':witnesses,'required_clean_logical_paths':required_clean,'root':str(Path(root).absolute()),'pending_state':TARGET_STATE,'pending_route':TARGET_ROUTE,'pending_error':TARGET_ERROR,'source_pair_unchanged':True,'accepted':False,'model_budget_reset':False,'outcomes_and_queues_untouched':True,'prior_output_record_sha256':sha(job['output_record'].encode()) if job['output_record'] else None,'prepared_at':datetime.datetime.now(datetime.timezone.utc).isoformat()};plan['plan_sha256']=sha(canonical(plan));return plan

def _idempotent(db,plan):
 row=db.execute('select input_record,output_record,state,route,worker_pid from jobs where id=?',(plan['id'],)).fetchone();out=db.execute('select status,source_code_hash,source_image_hash from processing_outcomes_v2 where id=?',(plan['id'],)).fetchone();return bool(row and row[1]==canonical(plan['record']).decode() and row[2:]==(TARGET_STATE,TARGET_ROUTE,None) and out==('pending',plan['record']['source_code_sha256'],plan['record']['source_image_sha256']) and json.loads(row[0])==plan['record']['source_record'])

def _dirty_expected(before,after):
 if before is None:return after is None
 require(before['columns']==after['columns']==['id','version','payload_version'],'unknown dirty trigger schema');a=before['rows'];b=after['rows'];require(len(b)==1,'dirty trigger did not create/update exactly one source row')
 require(b[0]==([a[0][0],a[0][1]+2,a[0][2]+1] if a else [b[0][0],2,1]),'dirty payload/update trigger effects differ')

def publish_pending(db,plan,*,apply=False,canonical_authorized=False,admission_timeout=5):
 """A one-shot CAS; default rolls back. Never performs browser/engine work."""
 require(not db.in_transaction,'publisher owns its short transaction');require(plan['version']==VERSION and plan['accepted'] is False and not plan['model_budget_reset'],'not a pending publication plan');require(sha(canonical({k:v for k,v in plan.items() if k!='plan_sha256'}))==plan['plan_sha256'],'plan damaged');require(sha(Path(__file__).read_bytes())==LOADED_SHA256,'publisher module changed after import');database=dict((name,path) for seq,name,path in db.execute('pragma database_list')).get('main','');path=Path(database).resolve() if database else None;require(not path or path==W/'jobs.sqlite' or path.is_relative_to(W/'prototype'),'publication database outside private/canonical owned scope');require(not apply or path!=W/'jobs.sqlite' or canonical_authorized,'canonical pending publication requires explicit reviewed authorization');quality=json.loads(Path(plan['quality_file']).read_text());require(sha(Path(plan['quality_file']).read_bytes())==plan['quality_sha256'] and sha(Path(plan['record_file']).read_bytes())==plan['record_raw_sha256'],'quality/metadata proposal changed');synthetic={'record':plan['record'],'id':plan['id'],'accepted':False,'published':False,'staging_only':True,'publish_files':{str(Path(p).relative_to(plan['root'])):{'sha256':h,'bytes':Path(p).stat().st_size} for p,h in plan['files'].items() if Path(p).is_relative_to(Path(plan['root'])/'clean')}};rechecked=file_preflight(synthetic,quality,plan['root'],plan['quality_file'],plan['record_file']);require(rechecked==plan['files'],'candidate publication file closure changed');expected_pins={**quality['implementation_pins'],**quality.get('checks',{}).get('source',{}).get('evidence',{}).get('required_software_dependencies',{}),str(Path(__file__).absolute()):LOADED_SHA256,**SHARED_PINS};require(plan['pins']==expected_pins,'plan dropped/changed required quality pins');require(plan.get('file_witnesses'),'missing logical filesystem witness closure');manifest=bundle.load_manifest(plan['root'],plan['record']);fresh_witnesses,fresh_clean,_=logical_witnesses(plan['root'],plan['record'],manifest,plan['scope'],plan['files'],plan['pins']);require(fresh_witnesses==plan['file_witnesses'] and fresh_clean==plan['required_clean_logical_paths'],'logical file/alias witness closure changed');shared._check_identities(plan['root'],plan['file_witnesses'])
 deadline=time.monotonic()+admission_timeout;previous_busy=db.execute('pragma busy_timeout').fetchone()[0];db.execute('pragma busy_timeout=0');began=None
 try:
  while True:
   try:db.execute('begin immediate');began=time.monotonic();break
   except sqlite3.OperationalError as exc:
    if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():raise
    if time.monotonic()>=deadline:return {'state':'admission_deferred','published':False,'accepted':False,'reason':'bounded_SQL_writer_busy','no_work_regenerated':True}
    time.sleep(min(.05,max(0,deadline-time.monotonic())))
  if _idempotent(db,plan):db.rollback();return {'state':'already_published_pointer_only','published':False,'already_published':True,'accepted':False,'database_mutations':0}
  require(schema_snapshot(db)==plan['schema'],'full database schema changed');current=scope_snapshot(db,plan['id'],plan['schema']);require(current==plan['scope'],'source/job/outcome/stage-owner/queue/history snapshot changed');job=admission(current,plan['record'])
  shared._check_identities(plan['root'],plan['file_witnesses'])
  for logical in plan['required_clean_logical_paths']:require(Path(shared.file_identity(plan['root'],logical)['resolve']).is_relative_to(Path(plan['root']).resolve()/'clean'),'required logical clean membership changed')
  aggregate_before={t:db.execute('select * from '+_safe(t)).fetchall() for t in ('initial_conversion_runs_v1','auto_quality_inventory_meta_v2') if t in plan['schema']['tables']};stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();db.execute('update jobs set output_record=?,state=?,route=?,error=?,updated_at=? where id=?',(canonical(plan['record']).decode(),TARGET_STATE,TARGET_ROUTE,TARGET_ERROR,stamp,plan['id']));require(db.execute('select changes()').fetchone()[0]==1,'pending pointer update missed source');after=scope_snapshot(db,plan['id'],plan['schema']);require(all(db.execute('select * from '+_safe(t)).fetchall()==rows for t,rows in aggregate_before.items()),'publisher changed unrelated global quota/cache metadata');before_other={k:v for k,v in current.items() if k not in ('jobs','auto_quality_dirty_v2')};after_other={k:v for k,v in after.items() if k not in ('jobs','auto_quality_dirty_v2')};require(before_other==after_other,'unexpected source/outcome/stage/queue/history side effects');_dirty_expected(current.get('auto_quality_dirty_v2'),after.get('auto_quality_dirty_v2'));newjob=_dicts(after,'jobs')[0];changed={k for k in newjob if newjob[k]!=job[k]};require(changed<= {'output_record','state','route','error','updated_at'},'publisher changed budgets/source/owner');require(newjob['attempts']==job['attempts'] and newjob['worker_pid'] is None,'attempts or owner changed');seconds=time.monotonic()-began
  shared._check_identities(plan['root'],plan['file_witnesses'])
  if apply:db.commit()
  else:db.rollback()
  return {'state':'published_pending_candidate' if apply else 'validated_rollback','published':bool(apply),'accepted':False,'changed_job_fields':sorted(changed),'outcomes_queues_stage_history_unchanged':True,'model_budget_reset':False,'transaction_seconds':seconds,'record_sha256':plan['record_raw_sha256']}
 except Exception as exc:
  if db.in_transaction:db.rollback()
  elif apply and _idempotent(db,plan):return {'state':'publication_commit_receipt_recovered','published':True,'accepted':False,'outcomes_queues_stage_history_unchanged':True,'model_budget_reset':False,'reason':repr(exc)}
  return {'state':'stale_or_failed_closed','published':False,'accepted':False,'reason':repr(exc),'transaction_seconds':time.monotonic()-began if began else 0}
 finally:db.execute('pragma busy_timeout='+str(previous_busy))
