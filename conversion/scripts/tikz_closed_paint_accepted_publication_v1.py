"""Independent closed-TikZ acceptance: full-context QA envelope and SQL-only CAS.

Default is a private/dry transaction. No watch, model call, source-rule waiver,
legacy QA4b policy reuse, or frozen-helper edit is exposed by this module.
"""
from __future__ import annotations
import datetime,hashlib,json,os,re,sqlite3,time,uuid
from pathlib import Path
import tikz_closed_paint_candidate_v1 as bundle
import tikz_closed_paint_pending_publication_v1 as pending

R=bundle.ROOT;W=R/'conversion';VERSION='independent_closed_TikZ_fullscope_acceptance_v1'
PENDING_SHA='55bb0f6d98449a2f69c6ecef18c29d3ecfb332992523ef201c49e625eb70833d'
ADAPTER_SHA='120f57fa87a3d040f94c81b4394e2f9ec4b5785def815088841efb6b32a6a20d'
CANDIDATE_SHA='1779897351e5f86bf5b321b7d016037aadf7f3b6c0ba2f63ea74e29a84fd79e9'
TRIGGERS={'auto_quality_dirty_v2_delete':'a66f4282faeb2b69e23c9758f953e7035638a9f7fdd611e0158486f7a6029c91','auto_quality_dirty_v2_insert':'40aaaa3e732525de8695afb49b6f90fdc94fc8978325c703d8247e9ef710e807','auto_quality_dirty_v2_payload':'d2481e9a54247072336d5d216888b0751756face8efc4bb38706e1d1f73e3f78','auto_quality_dirty_v2_update':'9c8b4b5a1a73230314afe14f1b802168a674ff79618d2b37a31332cf2c388959','retired_glyph_v3b_no_new_claims_v1':'790a4d67b34dc638288d39272aaaed15c56d4f24ac3b57ecc1cc2e402b544edd'}
CACHE_COLUMNS=('id','payload_version','trusted','manifest_record','metadata_sha256','updated_at')
sha=bundle.sha;canonical=bundle.canonical;require=bundle.require
LOADED_SHA=sha(Path(__file__).read_bytes());_SEAL=object()

def _fresh(db):
 require(not db.in_transaction and db.row_factory is None,'fresh default autocommit connection required');require(not db.execute('select 1 from sqlite_temp_master limit 1').fetchone(),'temporary schema is not allowed');require(all(r[1] in ('main','temp') for r in db.execute('pragma database_list')),'attached database is not allowed')

def _triggers(schema):
 actual={name:sha(sql.encode()) for kind,name,table,sql in schema['sqlite_master'] if kind=='trigger' and table=='jobs'};require(actual==TRIGGERS,'unreviewed jobs trigger definitions');require(not any(kind=='trigger' and table in ('processing_outcomes_v2','qualified_index_cache_v4') for kind,name,table,sql in schema['sqlite_master']),'unreviewed registry/cache trigger');require(tuple(x[1] for x in schema['tables'].get('qualified_index_cache_v4',{}).get('columns',[]))==CACHE_COLUMNS,'missing/unknown qualified cache schema')

def _frozen():
 import tikz_closed_paint_quality_adapter_v1 as adapter
 require(sha(Path(__file__).read_bytes())==LOADED_SHA,'acceptance module changed after import');require(sha(Path(pending.__file__).read_bytes())==PENDING_SHA,'frozen pending helper changed');require(sha(Path(bundle.__file__).read_bytes())==CANDIDATE_SHA,'frozen candidate helper changed');require(sha(Path(adapter.__file__).read_bytes())==ADAPTER_SHA,'frozen source adapter changed');return adapter

def capture(db,identifier,record=None):
 _fresh(db);db.execute('begin')
 try:
  schema=pending.schema_snapshot(db);_triggers(schema);scope=pending.scope_snapshot(db,identifier,schema);jobs=pending._dicts(scope,'jobs');require(len(jobs)==1 and jobs[0]['output_record'],'current pending candidate missing');current=json.loads(jobs[0]['output_record']);require(record is None or current==record,'current canonical candidate differs');require(current.get('conversion_method')==bundle.VERSION,'not the reviewed complete closed-TikZ candidate');pending.admission(scope,current);require(current['code_sha256'] and current['image_sha256'] and current['source_format']=='tikz','candidate/source identity incomplete');return {'schema':schema,'scope':scope},current
 finally:db.rollback()

def _immutable(path,raw):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():require(not path.is_symlink() and path.read_bytes()==raw,'immutable acceptance artifact conflict')
 else:
  with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.chmod(path,0o444)
 return {'file':str(path.relative_to(R)),'sha256':sha(raw),'bytes':len(raw)}

def _database_path(db):
 path=dict((name,path) for _,name,path in db.execute('pragma database_list')).get('main');require(path,'on-disk owned database required');path=Path(path).resolve();require(path==W/'jobs.sqlite' or path.is_relative_to(W/'prototype'),'unowned database');return path

def _source_quality(record,quality,quality_file,record_file):
 require(quality.get('version')=='independent_deterministic_candidate_quality_readonly_v1' and quality.get('ok') is True and quality.get('accepted') is False and quality.get('model_calls')==0 and quality.get('canonical_mutations')==0,'independent complete QA failed');require(quality['input_record_sha256']==sha(Path(record_file).read_bytes()) and quality['id']==record['id'] and quality['data_root']==str(R),'quality/record/source binding differs');require(quality['checks']['source']['supported'] and quality['checks']['source']['ok'] and quality['checks']['source']['evidence']['complete_source_coverage'] is True,'incomplete source profile');require(quality['checks']['source']['evidence']['candidate_code_sha256']==record['code_sha256'] and quality['checks']['source']['evidence']['clean_source_manifest']==record[bundle.FIELD],'quality current source manifest differs');require(quality['checks']['visual']['ok'] and quality['checks']['native_editing']['ok'],'visual/editing gate failed');require(quality['checks']['render']['code_sha256']==record['code_sha256'],'actual native render belongs to other XML');require(quality['quality_policy'].startswith(quality['version']+':'),'new independent quality policy required')


def prepare(db,identifier,work):
 """Capture BEFORE QA, run unchanged root RO QA, compare AFTER, prepare files."""
 import deterministic_candidate_quality_ro_v1 as qa
 import qualified_index_v4 as index
 from auto_quality_common import resource_checks,require_rendered_text,image_quality
 from strict_canvas_gate import require_declared_page
 from PIL import Image
 adapter=_frozen();_fresh(db);database=_database_path(db);work=Path(work).absolute();require(work.is_relative_to(W/'prototype/tikz_closed_paint_accepted_v1'),'unowned acceptance evidence directory');work.mkdir(parents=True,exist_ok=False);before,record=capture(db,identifier);directory=bundle.clean_path(R,record['code_file']).parent;record_raw=canonical(record);record_desc=_immutable(directory/('pending_qa_input.'+sha(record_raw)+'.json'),record_raw);record_file=R/record_desc['file'];manifest=bundle.load_manifest(R,record);config=adapter.configuration(R);pins=dict(config['pins']);pins[str(Path(qa.__file__).absolute())]=sha(Path(qa.__file__).read_bytes());pins[str(Path(index.__file__).absolute())]=sha(Path(index.__file__).read_bytes());pins[str(Path(__file__).absolute())]=LOADED_SHA;pins[str(Path(pending.__file__).absolute())]=PENDING_SHA;pins.update(pending.SHARED_PINS);dependencies={p:v['sha256'] for p,v in json.loads(bundle.checked(R,manifest['files']['source_environment'])).items()};pins.update(dependencies);initial_files={str(R/record_desc['file']):record_desc['sha256']}
 for item in manifest['files'].values():initial_files[str(R/item['file'])]=item['sha256']
 for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_svg','source_render_svg_sha256')]:initial_files[str(R/record[field])]=record[digest]
 initial_files[str(R/record[bundle.FIELD]['file'])]=record[bundle.FIELD]['sha256'];pre_witnesses,_,durable=pending.logical_witnesses(R,record,manifest,before['scope'],initial_files,pins);pending.fsync_prepared(R,pre_witnesses,durable);require(capture(db,identifier,record)[0]==before,'context changed before QA; do not refresh expected scope')
 qa_work=W/'prototype/candidate_quality_ro_v1'/('closed_acceptance_'+uuid.uuid4().hex);quality=qa.verify(identifier,record_file,R,Path(adapter.__file__),qa_work,database=database);quality_file=Path(quality['evidence_file']);_source_quality(record,quality,quality_file,record_file);after,_=capture(db,identifier,record);require(after==before,'full source/stage/queue/history/schema changed during QA');pending.shared._check_identities(R,pre_witnesses);require(quality['implementation_pins'].items()<=pins.items(),'QA implementation differs from pre-QA pins');require(quality['checks']['source']['evidence']['required_software_dependencies']==dependencies,'source execution closure changed during QA')
 info_raw=(qa_work/'native_render.json').read_bytes();info=json.loads(info_raw);png=(qa_work/'fresh.png').read_bytes();require(sha(png)==quality['checks']['render']['image_sha256'],'current actual native PNG differs');require_declared_page(info,*quality['checks']['render']['canvas']);require_rendered_text((R/record['code_file']).read_text(),info);require(all(f.get('isCustomFont') for row in info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0),'actual font source portability failed');reference=(R/record['original_reference']).read_bytes();visual=image_quality(reference,png,record,info.get('actual_text_positions'));require(visual['ok'],'original global/local image gates do not replay')
 quality_desc=_immutable(directory/('validated_qa.'+sha(quality_file.read_bytes())+'.json'),quality_file.read_bytes());info_desc=_immutable(directory/('validated_native_info.'+sha(info_raw)+'.json'),info_raw);fresh_desc=_immutable(directory/('image.native.'+sha(png)+'.png'),png);stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();writer_policy=VERSION+':'+sha(canonical({p:h for p,h in pins.items() if p not in dependencies}))[:20];envelope={'version':VERSION,'id':identifier,'before_QA':before,'after_QA':after,'pending_record_sha256':sha(record_raw),'quality_report':quality_desc,'original_quality_report':str(quality_file.relative_to(R)),'original_quality_report_sha256':sha(quality_file.read_bytes()),'quality_policy':quality['quality_policy'],'source_profile_policy':quality['profile_policy'],'source_manifest':record[bundle.FIELD],'writer_policy':writer_policy,'qa_started_and_completed_with_same_full_context':True,'model_calls':0};envelope_raw=canonical(envelope);envelope_desc=_immutable(directory/('acceptance_context.'+sha(envelope_raw)+'.json'),envelope_raw)
 accepted={**record,'image_file':fresh_desc['file'],'image_sha256':fresh_desc['sha256'],'quality_state':'accepted_independent_deterministic_complete_source_and_native_quality_v1','automatic_quality_policy':quality['quality_policy'],'automatic_quality_audit':quality_desc['file'],'accepted_at_utc':stamp,'source_coverage_automatic':quality['checks']['source'],'render':info,'metrics':{**record.get('metrics',{}),'automatic_visual_quality':visual},'independent_quality_validation':{'version':quality['version'],'quality_policy':quality['quality_policy'],'profile_policy':quality['profile_policy'],'quality_report':quality_desc,'actual_native_info':info_desc,'full_context_envelope':envelope_desc,'writer_policy':writer_policy,'new_model_calls':0},'acceptance_publication_policy':writer_policy}
 resource_checks(R,accepted,(R/accepted['code_file']).read_text(),reference);compact,metadata_sha=index.manifest_row(accepted,R);metadata_file=R/compact['metadata_file'];metadata_raw=metadata_file.read_bytes();require(sha(metadata_raw)==metadata_sha and json.loads(metadata_raw)==accepted,'immutable accepted metadata differs');compact_raw=json.dumps(compact,ensure_ascii=False,separators=(',',':'));compact_desc=_immutable(directory/('qualified_manifest_row.'+sha(compact_raw.encode())+'.json'),compact_raw.encode());outcome={k:accepted[k] for k in ('id','source_pair_sha256','source_code_sha256','source_image_sha256','code_file','code_sha256','image_file','image_sha256','original_reference','original_source_code','automatic_quality_policy','automatic_quality_audit')};outcome.update(metadata_file=compact['metadata_file'],metadata_sha256=metadata_sha,acceptance_context=envelope_desc)
 files=dict(initial_files);files[str(quality_file)]=sha(quality_file.read_bytes());files[str(qa_work/'native_render.json')]=sha(info_raw);files[str(qa_work/'fresh.png')]=sha(png)
 for item in (quality_desc,info_desc,fresh_desc,envelope_desc,compact_desc):files[str(R/item['file'])]=item['sha256']
 files[str(metadata_file)]=metadata_sha;witnesses,clean,durable=pending.logical_witnesses(R,accepted,manifest,before['scope'],files,pins);clean=sorted(set(clean)|{str(Path(p).absolute()) for p in files if Path(p).resolve().is_relative_to(R/'clean')});pending.fsync_prepared(R,witnesses,durable);require(capture(db,identifier,record)[0]==before,'full context changed during metadata preparation');pending.shared._check_identities(R,pre_witnesses);doc={'version':VERSION,'id':identifier,'writer_policy':writer_policy,'writer_sha256':LOADED_SHA,'quality_policy':quality['quality_policy'],'quality_report':quality_desc,'pending_record':record,'pending_record_file':record_desc,'accepted_record':accepted,'accepted_metadata':{'file':compact['metadata_file'],'sha256':metadata_sha},'compact':compact,'compact_raw':compact_raw,'outcome_raw':json.dumps(outcome,sort_keys=True,separators=(',',':')),'context':before,'stamp':stamp,'pins':pins,'files':files,'file_witnesses':witnesses,'required_clean_logical_paths':clean,'source_manifest':record[bundle.FIELD],'full_context_envelope':envelope_desc,'created_at_utc':stamp,'accepted':False,'canonical_acceptance_performed':False,'model_calls':0};raw=canonical(doc);path=work/('acceptance_plan.'+sha(raw)+'.json');_immutable(path,raw);prepared=_make_prepared(doc,path,raw,witnesses);(work/'preparation_receipt.json').write_bytes(canonical(prepared['receipt']));return prepared


def _make_prepared(doc,path,raw,witnesses):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
 fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 witnesses=dict(witnesses);witnesses[str(Path(path).absolute())]=pending.shared.file_witness(R,str(path),sha(raw));return {'_seal':_SEAL,'document':doc,'witnesses':witnesses,'receipt':{'file':str(Path(path).relative_to(R)),'sha256':sha(raw),'writer_policy':doc['writer_policy'],'quality_policy':doc['quality_policy'],'id':doc['id'],'accepted':False}}

def load_prepared(db,path,expected_sha):
 """Rehydrate only an explicitly reviewed immutable plan; no new QA context."""
 _frozen();_fresh(db);path=Path(path).absolute();require(path.is_relative_to(W/'prototype/tikz_closed_paint_accepted_v1') and re.fullmatch('[0-9a-f]{64}',expected_sha or ''),'owned plan and reviewed SHA required');raw=path.read_bytes();require(sha(raw)==expected_sha,'reviewed acceptance plan differs');doc=json.loads(raw);require(canonical(doc)==raw and doc['version']==VERSION and doc['writer_sha256']==LOADED_SHA and doc['accepted'] is False,'stale/noncanonical acceptance document');already=_accepted_current(db,doc)
 if not already:require(capture(db,doc['id'],doc['pending_record'])[0]==doc['context'],'full pre-QA context no longer current')
 for p,h in {**doc['pins'],**doc['files']}.items():require(p in doc['file_witnesses'] and doc['file_witnesses'][p]['sha256']==h,'plan witness closure incomplete')
 fresh={p:pending.shared.file_witness(R,p,w['sha256']) for p,w in doc['file_witnesses'].items()};require(fresh==doc['file_witnesses'],'logical data/software identities changed');require(_accepted_current(db,doc) if already else capture(db,doc['id'],doc['pending_record'])[0]==doc['context'],'context changed during crypto readback');return _make_prepared(doc,path,raw,fresh)


def _accepted_current(db,doc):
 row=db.execute('select state,output_record,worker_pid from jobs where id=?',(doc['id'],)).fetchone();registry=db.execute('select status,record from processing_outcomes_v2 where id=?',(doc['id'],)).fetchone();cache=db.execute('select payload_version,trusted,manifest_record,metadata_sha256 from qualified_index_cache_v4 where id=?',(doc['id'],)).fetchone();version=db.execute('select payload_version from auto_quality_dirty_v2 where id=?',(doc['id'],)).fetchone();return bool(row==('accepted',canonical(doc['accepted_record']).decode(),None) and registry==('qualified',doc['outcome_raw']) and cache and version and cache==(version[0],1,doc['compact_raw'],doc['accepted_metadata']['sha256']))

def apply_prepared(db,prepared,*,apply=False,canonical_authorized=False,admission_timeout=5):
 """SQL+identity only while locked; never hash/read/compile/render source here."""
 require(prepared.get('_seal') is _SEAL,'unverified prepared acceptance');_fresh(db);doc=prepared['document'];database=_database_path(db);require(not apply or database!=W/'jobs.sqlite' or canonical_authorized,'canonical acceptance requires explicit reviewed authorization');_frozen();pending.shared._check_identities(R,prepared['witnesses']);previous_busy=db.execute('pragma busy_timeout').fetchone()[0];db.execute('pragma busy_timeout=0');deadline=time.monotonic()+admission_timeout;began=None;committing=False;updated=False
 try:
  while True:
   try:db.execute('begin immediate');began=time.monotonic();break
   except sqlite3.OperationalError as exc:
    if not any(x in str(exc).lower() for x in ('locked','busy')):raise
    if time.monotonic()>=deadline:return {'state':'admission_deferred','accepted':False,'applied':False,'no_work_regenerated':True}
    time.sleep(min(.05,max(0,deadline-time.monotonic())))
  if _accepted_current(db,doc):db.rollback();return {'state':'already_accepted_exact_tuple','accepted':True,'applied':False,'database_mutations':0}
  require(pending.schema_snapshot(db)==doc['context']['schema'],'full schema changed');scope=pending.scope_snapshot(db,doc['id'],doc['context']['schema']);require(scope==doc['context']['scope'],'full source/stage/queue/history context changed since BEFORE QA');pending.admission(scope,doc['pending_record']);_triggers(doc['context']['schema']);pending.shared._check_identities(R,prepared['witnesses'])
  for logical in doc['required_clean_logical_paths']:require(Path(pending.shared.file_identity(R,logical)['resolve']).is_relative_to(R/'clean'),'final metadata/payload clean membership changed')
  aggregates={t:db.execute('select * from '+pending._safe(t)).fetchall() for t in ('initial_conversion_runs_v1','auto_quality_inventory_meta_v2') if t in doc['context']['schema']['tables']};before_job=pending._dicts(scope,'jobs')[0];before_registry=pending._dicts(scope,'processing_outcomes_v2')[0];db.execute('update jobs set state="accepted",output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?',(canonical(doc['accepted_record']).decode(),doc['stamp'],doc['id']));require(db.execute('select changes()').fetchone()[0]==1,'accepted job update missed source');after_job_scope=pending.scope_snapshot(db,doc['id'],doc['context']['schema']);pending._dirty_expected(scope['auto_quality_dirty_v2'],after_job_scope['auto_quality_dirty_v2']);version=db.execute('select payload_version from auto_quality_dirty_v2 where id=?',(doc['id'],)).fetchone();require(version is not None,'missing real payload journal');db.execute('update processing_outcomes_v2 set status="qualified",reason=NULL,record=?,updated_at=? where id=?',(doc['outcome_raw'],doc['stamp'],doc['id']));require(db.execute('select changes()').fetchone()[0]==1,'qualified source registry update missed source');db.execute('insert or replace into qualified_index_cache_v4(id,payload_version,trusted,manifest_record,metadata_sha256,updated_at) values(?,?,?,?,?,?)',(doc['id'],version[0],1,doc['compact_raw'],doc['accepted_metadata']['sha256'],doc['stamp']));after=pending.scope_snapshot(db,doc['id'],doc['context']['schema']);allowed={'jobs','processing_outcomes_v2','qualified_index_cache_v4','auto_quality_dirty_v2'};require({k:v for k,v in after.items() if k not in allowed}=={k:v for k,v in scope.items() if k not in allowed},'source/model/queue/stage/history side effects refused');require(all(db.execute('select * from '+pending._safe(t)).fetchall()==rows for t,rows in aggregates.items()),'global aggregate changed by acceptance');newjob=pending._dicts(after,'jobs')[0];require({k for k in newjob if newjob[k]!=before_job[k]}<={'state','output_record','error','updated_at'},'source/attempts/route/owner changed by acceptance');newreg=pending._dicts(after,'processing_outcomes_v2')[0];require({k for k in newreg if newreg[k]!=before_registry[k]}<={'status','reason','record','updated_at'},'original registry source changed');require(_accepted_current(db,doc),'accepted job/qualified registry/current-version trusted cache tuple differs');pending.shared._check_identities(R,prepared['witnesses']);updated=True;committing=True
  if apply:db.commit()
  else:db.rollback()
  return {'state':'accepted' if apply else 'validated_acceptance_rollback','accepted':bool(apply),'applied':bool(apply),'writer_policy':doc['writer_policy'],'automatic_quality_policy':doc['quality_policy'],'payload_version':version[0],'transaction_seconds':time.monotonic()-began,'source_attempts_model_queue_stage_history_unchanged':True,'receipt':prepared['receipt']}
 except Exception as exc:
  active=db.in_transaction
  if active:db.rollback()
  if committing and updated and not active and apply and _accepted_current(db,doc):return {'state':'accepted_commit_receipt_recovered','accepted':True,'applied':True,'receipt':prepared['receipt']}
  return {'state':'stale_or_failed_closed','accepted':False,'applied':False,'reason':repr(exc),'transaction_seconds':time.monotonic()-began if began else 0}
 finally:db.execute('pragma busy_timeout='+str(previous_busy))
