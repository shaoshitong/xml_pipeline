#!/usr/bin/env python3
"""Bounded, read-only final metadata audit. Does not assert final visual QA.
Only fixed JSON reports, supervisor metadata and canonical metadata JSONL are
read. No media/data code, processes, catalog writes, or goal tools are touched.
"""
import argparse,collections,datetime,hashlib,json,os,tempfile,time
from pathlib import Path
STAGES=(('curate_pairs.py','summary.json'),('curate_archives.py','archive_summary.json'),('curate_derived.py','derived_summary.json'),('curate_native_sources.py','native_sources_summary.json'),('finalize_catalog.py','catalog_summary.json'),('audit_provenance_qc.py','provenance_qc.json'),('audit_catalog_content.py','content_audit.json'))
RUNS=('priority','bulk','rap','extra','omni_i2c')
ALLOWED_CATEGORIES={'poster','scientific_diagram','chart'}
GOOD={'complete','already_complete'}


def timestamp(value):
 try:
  parsed=datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return parsed.replace(tzinfo=datetime.timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
 except (ValueError,TypeError):return None

def iso(value):return datetime.datetime.fromtimestamp(value,datetime.timezone.utc).isoformat()

def audit(root,seconds=30,max_json_bytes=128*1024**2,max_manifest_bytes=1024**3,log_bytes=8*1024**2):
 root=root.resolve();started=time.monotonic();deadline=started+seconds;checks={};read_issues=[];bounds=[]
 def check(name,ok,detail=None,pending=False):
  checks[name]={'status':'pass' if ok else ('pending' if pending else 'fail')}
  if detail is not None:checks[name]['detail']=detail
 def read(path,default=None):
  try:
   if time.monotonic()>deadline:bounds.append('time_budget');return default
   if path.stat().st_size>max_json_bytes:bounds.append(str(path.relative_to(root))+':json_byte_limit');return default
   return json.loads(path.read_text())
  except (OSError,ValueError) as exc:read_issues.append({'file':str(path.relative_to(root)),'error_type':type(exc).__name__});return default
 def mtime(path):
  try:return path.stat().st_mtime
  except OSError:return None
 owner=read(root/'supervisor/owner.json',{});status=read(root/'supervisor/status.json',{});done=read(root/'collection_done.json',{})
 generation=timestamp(owner.get('started_at'));pid=owner.get('pid');generation_known=generation is not None and pid is not None
 status_current=bool(generation_known and status.get('supervisor_pid')==pid and (timestamp(status.get('time')) or 0)>=generation-2)
 done_time=timestamp(done.get('finished_at'));done_mtime=mtime(root/'collection_done.json')
 done_current=bool(generation_known and done.get('status')=='complete' and done_time is not None and done_time>=generation-2 and done_mtime is not None and done_mtime>=generation-2)
 pending=not done_current
 check('generation_anchor',generation_known,{'supervisor_pid':pid,'started_at':owner.get('started_at')},pending=True)
 check('collection_done_current_generation',done_current,{'present':bool(done),'status':done.get('status'),'finished_at':done.get('finished_at'),'historical_or_absent':not done_current},pending=True)
 if status_current and status.get('status') in {'curation_failed','stalled','needs_attention'}:check('supervisor_state',False,{'status':status.get('status'),'stage':status.get('script') or status.get('stage')})
 else:check('supervisor_state',True,{'current_generation':status_current,'status':status.get('status'),'stage':status.get('script') or status.get('stage')})
 events=[];log_truncated=False
 path=root/'supervisor/progress.jsonl'
 try:
  length=path.stat().st_size;log_truncated=length>log_bytes
  with path.open('rb') as stream:
   stream.seek(max(0,length-log_bytes));data=stream.read(log_bytes)
  lines=data.splitlines()
  if log_truncated and lines:lines=lines[1:]
  for line in lines:
   try:event=json.loads(line)
   except ValueError:continue
   if event.get('supervisor_pid')==pid and (timestamp(event.get('time')) or 0)>=(generation or float('inf'))-2:events.append(event)
 except OSError:pass
 stage_info=[];reports={};stage_current={};previous_finish=None
 for script,report_name in STAGES:
  path=root/'reports'/report_name;report=read(path,{});reports[report_name]=report
  start_events=[x for x in events if x.get('script')==script and x.get('status') in ('curation_started','curation_started_after_incremental_run')]
  verified_events=[x for x in events if x.get('script')==script and x.get('status')=='curation_verified']
  event_start=timestamp(start_events[-1]['time']) if start_events else None;event_verified=timestamp(verified_events[-1]['time']) if verified_events else None
  payload_start=timestamp(report.get('started_at') or report.get('created_at'));finish=timestamp(report.get('finished_at'));modified=mtime(path)
  boundary=event_start if event_start is not None else generation
  fresh=bool(generation_known and boundary is not None and payload_start is not None and finish is not None and modified is not None and payload_start>=boundary-2 and finish>=payload_start-2 and modified>=boundary-2)
  ordered=previous_finish is None or (payload_start is not None and payload_start>=previous_finish-2)
  if event_verified is not None:fresh=fresh and event_verified>=(event_start or generation)-2 and finish<=event_verified+2
  if done_current:fresh=fresh and finish is not None and finish<=done_time+2 and modified<=done_mtime+2
  current=fresh and ordered;stage_current[report_name]=current
  if current:previous_finish=finish
  evidence={'script':script,'report':'reports/'+report_name,'started_at':report.get('started_at') or report.get('created_at'),'finished_at':report.get('finished_at'),'current_generation':current,'journal_start_present':event_start is not None,'journal_verified_present':event_verified is not None,'freshness_basis':'current-supervisor journal plus report times' if event_start is not None else 'owner start plus ordered report times; journal start unavailable'}
  stage_info.append(evidence);check('stage:'+script,current,evidence,pending=pending or bool(log_truncated and not start_events))
  if current:
   errors={key:value.get('error') for key,value in report.get('sources',{}).items() if isinstance(value,dict) and value.get('error')}
   check('source_errors:'+script,not errors,errors)
   if script=='curate_native_sources.py':check('native_source_pages_processed',report.get('processed_all_eligible_pages') is True,{'accepted_pairs':report.get('accepted_pairs'),'render_rejected':report.get('render_rejected'),'note':'Rejected pages may remain auxiliary; no zero-render-rejections gate.'})
 all_stages_current=all(stage_current.values())
 check('seven_stage_reports_current_generation',all_stages_current,pending=pending)
 download_rows=[];all_ready=True
 for name in RUNS:
  folder=root if name=='priority' else root/'runs'/name
  inventory=read(folder/'download_inventory.json',None);manifest=read(folder/'download_manifest.json',None);failures=read(folder/'download_failures.json',None)
  if not isinstance(inventory,list) or not isinstance(manifest,dict) or not isinstance(failures,list):
   download_rows.append({'run':name,'ready':False,'reason':'metadata_absent_or_unreadable'});all_ready=False;continue
  def key(record,repo=None,revision=None):return (record.get('repo_id') or repo,record.get('path'),record.get('revision') or revision)
  expected={key(task,repo.get('repo_id'),repo.get('revision')):task for repo in inventory for task in repo.get('files',[])}
  files=manifest.get('files',[]);good={key(x) for x in files if x.get('status') in GOOD};manifest_keys={key(x) for x in files}
  ready=bool(expected and manifest.get('finished') and not failures and all(x.get('status') in GOOD for x in files) and good==set(expected) and manifest_keys==set(expected) and len(files)==len(expected))
  all_ready&=ready;download_rows.append({'run':name,'ready':ready,'planned_unique_keys':len(expected),'manifest_files':len(files),'complete_unique_keys':len(good),'finished':manifest.get('finished',False),'failures':len(failures),'metadata_only':True})
 check('all_five_download_runs_ready',all_ready,download_rows,pending=pending)
 templates=read(root/'raw/jgraph--drawio-templates/source_manifest.json',{});extra=read(root/'reports/extra_assets.json',{})
 aux={'official_templates':bool(templates.get('finished') and not templates.get('failed_files')),'extra_assets':bool(len(extra.get('assets',[]))==2 and all(x.get('status')=='complete' and x.get('archive_integrity_checked') for x in extra.get('assets',[])))}
 check('existing_auxiliary_download_gates',all(aux.values()),aux,pending=pending)
 catalog=reports.get('catalog_summary.json',{});provenance=reports.get('provenance_qc.json',{});content=reports.get('content_audit.json',{})
 canonical={};hashes={};catalog_current=stage_current.get('catalog_summary.json',False)
 if catalog_current:
  groups=catalog.get('groups',{});invalid={kind:groups.get(kind,{}).get('invalid_locators') for kind in ('provided','derived')}
  check('catalog_invalid_locators_zero',all(value==0 for value in invalid.values()),invalid)
  category_bad={kind:{key:value for key,value in groups.get(kind,{}).get('categories',{}).items() if key not in ALLOWED_CATEGORIES and value} for kind in ('provided','derived')}
  check('catalog_categories_only_requested_three',not any(category_bad.values()),category_bad)
  for kind,folder in [('provided','clean'),('derived','derived')]:
   path=root/folder/'manifest.jsonl';stats={'rows':0,'categories':collections.Counter(),'image_provenance':collections.Counter(),'code_provenance':collections.Counter(),'pairing':collections.Counter(),'code_execution_checked':collections.Counter(),'provenance_separation_errors':0,'missing_detailed_provenance':0};digest=hashlib.sha256();read_bytes=0;valid=True
   try:
    if path.stat().st_size>max_manifest_bytes:bounds.append(folder+'/manifest.jsonl:manifest_byte_limit');valid=False
    else:
     with path.open('rb') as stream:
      while True:
       if time.monotonic()>deadline:bounds.append('time_budget_during_'+folder);valid=False;break
       line=stream.readline(2*1024**2+1)
       if not line:break
       if len(line)>2*1024**2:bounds.append(folder+'/manifest.jsonl:line_limit');valid=False;break
       digest.update(line);read_bytes+=len(line)
       if not line.strip():continue
       row=json.loads(line);stats['rows']+=1;category=row.get('category','missing');stats['categories'][category]+=1
       image_prov=row.get('image_provenance') or row.get('provenance') or 'missing';code_prov=row.get('gold_code_provenance') or row.get('code_provenance') or row.get('provenance') or 'missing';pairing=row.get('pairing','missing')
       stats['image_provenance'][image_prov]+=1;stats['code_provenance'][code_prov]+=1;stats['pairing'][pairing]+=1;stats['code_execution_checked'][str(bool(row.get('code_execution_checked')))]+=1
       if image_prov=='missing' or code_prov=='missing':stats['missing_detailed_provenance']+=1
       alignment='rendered_from_selected_code' if kind=='derived' else 'provider_declared_pairing_not_independently_rendered'
       bad=row.get('catalog_kind')!=kind or row.get('alignment_verification')!=alignment
       if kind=='provided':bad=bad or pairing.startswith('derived_from_') or image_prov in {'rendered_from_source_svg','rendered_from_selected_native_drawio'}
       else:bad=bad or not pairing.startswith('derived_from_') or image_prov not in {'rendered_from_source_svg','rendered_from_selected_native_drawio'}
       stats['provenance_separation_errors']+=bool(bad)
   except (OSError,ValueError) as exc:valid=False;read_issues.append({'file':folder+'/manifest.jsonl','error_type':type(exc).__name__})
   stats={key:dict(value) if isinstance(value,collections.Counter) else value for key,value in stats.items()};stats.update({'metadata_scan_complete':valid,'bytes_read':read_bytes});canonical[kind]=stats
   if valid:
    hashes[folder]=digest.hexdigest();check('canonical_rows_match_catalog:'+kind,stats['rows']==groups.get(kind,{}).get('pairs'),{'rows':stats['rows'],'catalog_pairs':groups.get(kind,{}).get('pairs')})
    check('canonical_categories_match_catalog:'+kind,stats['categories']==groups.get(kind,{}).get('categories',{}),stats['categories'])
    check('canonical_categories_allowed:'+kind,not any(key not in ALLOWED_CATEGORIES for key in stats['categories']),stats['categories'])
    check('provided_derived_provenance_separated:'+kind,stats['provenance_separation_errors']==0,{'bad_rows':stats['provenance_separation_errors'],'missing_detailed_provenance_warning_rows':stats['missing_detailed_provenance']})
   else:check('canonical_metadata_scan:'+kind,False,{'reason':'bounded_or_unreadable'},pending=True)
 else:check('canonical_metadata_current',False,{'action':'Old canonical manifests/counts were not read as current because current-generation catalog stage is not established.'},pending=True)
 if stage_current.get('provenance_qc.json'):
  check('provenance_critical_issues_zero',provenance.get('ok') is True and not provenance.get('critical_issues'),{'ok':provenance.get('ok'),'critical_issues':provenance.get('critical_issues'), 'noncritical_issue_counts':provenance.get('issues',{}),'note':'Noncritical warnings, including unknown licenses, do not fail this audit.'})
  if catalog_current:
   for kind in ('provided','derived'):check('provenance_count_matches_catalog:'+kind,provenance.get('groups',{}).get(kind,{}).get('rows')==catalog.get('groups',{}).get(kind,{}).get('pairs'))
 else:check('provenance_report_current',False,pending=True)
 if stage_current.get('content_audit.json'):
  check('content_audit_zero_errors',content.get('ok') is True and content.get('errors')==0 and not content.get('manifest_changes_during_audit'),{'ok':content.get('ok'),'errors':content.get('errors'),'manifest_changes_during_audit':content.get('manifest_changes_during_audit',[])})
  if catalog_current:
   expected_total=0
   for kind,folder in [('provided','clean'),('derived','derived')]:
    count=catalog.get('groups',{}).get(kind,{}).get('pairs');expected_total+=count or 0
    check('content_checked_matches_catalog:'+kind,content.get('groups',{}).get(folder,{}).get('checked')==count and content.get('groups',{}).get(folder,{}).get('errors')==0,{'checked':content.get('groups',{}).get(folder,{}).get('checked'),'catalog_pairs':count})
    if folder in hashes:check('content_input_manifest_sha_matches_current:'+kind,content.get('input_manifest_sha256',{}).get(folder)==hashes[folder],{'current_sha256':hashes[folder],'content_audit_sha256':content.get('input_manifest_sha256',{}).get(folder)})
   check('content_total_checked_matches_catalog',content.get('checked_pairs')==expected_total,{'checked_pairs':content.get('checked_pairs'),'catalog_sum':expected_total})
 else:check('content_report_current',False,pending=True)
 if done_current:
  check('collection_done_root_matches',Path(done.get('root','/missing')).resolve()==root)
  check('collection_done_all_original_download_gates_true',bool(done.get('additional_download_gates')) and all(done['additional_download_gates'].values()))
  if all_stages_current:
   expected_provenance={key:provenance.get(key) for key in ('ok','critical_issues','issues','cross_kind')}
   bindings={'catalogs':done.get('catalogs')==catalog.get('groups'),'content_hash_audit':done.get('content_hash_audit')==content,'provenance_audit':done.get('provenance_audit')==expected_provenance,'pair_sources':done.get('pair_sources')==reports['summary.json'].get('sources',{}),'archive_sources':done.get('archive_sources')==reports['archive_summary.json'].get('sources',{}),'archive_paired_image_code':done.get('archive_paired_image_code')==reports['archive_summary.json'].get('paired_image_code'),'derived_pairs':done.get('derived_pairs')==reports['derived_summary.json'].get('derived_pairs'),'native_source_pages_accepted':done.get('native_source_pages_accepted')==reports['native_sources_summary.json'].get('accepted_pairs')}
   check('collection_done_matches_seven_stage_snapshots',all(bindings.values()),bindings)
 failures=[key for key,value in checks.items() if value['status']=='fail'];waiting=[key for key,value in checks.items() if value['status']=='pending']
 outcome='needs_attention' if failures else ('pending' if waiting or bounds else 'metadata_pass')
 return {'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':outcome,'metadata_acceptance_pass':outcome=='metadata_pass','collection_or_goal_completion_claim':False,'manual_final_visual_qa':{'status':'not_evaluated_by_this_metadata_tool','automatic_completion_claim':False,'note':'Final visual QA remains a separate human/interactive review. Passing hashes/metadata does not establish semantic alignment or authorize an automatic final-completion claim.'},'generation':{'supervisor_pid':pid,'started_at':owner.get('started_at'),'current_status':status.get('status') if status_current else 'unconfirmed_or_historical','current_stage':status.get('script') if status_current else None},'seven_stage_reports':stage_info,'checks':checks,'failed_checks':failures,'pending_checks':waiting,'canonical_current_metadata':canonical,'canonical_current_manifest_sha256':hashes,'metadata_read_issues':read_issues,'bounded_inspection_limits':bounds,'journal_tail_truncated':log_truncated,'seconds':round(time.monotonic()-started,3),'notes':['No source media or dataset program was opened/executed. Only fixed reports and canonical metadata JSONL were read.','Reports do not carry a dedicated generation UUID; same-generation evidence uses current supervisor owner/journal, payload times, file mtimes and snapshot/count/hash bindings.','Provided and derived remain separate. Cross-kind overlaps and noncritical license/provenance warnings are reported by existing provenance QC and are not new zero-warning gates.']}


def self_test():
 with tempfile.TemporaryDirectory(prefix='final-metadata-fixture-') as directory:
  root=Path(directory);(root/'supervisor').mkdir();(root/'reports').mkdir();base=time.time()-300;pid=123
  def write(relative,data,when=None):
   path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data));
   if when is not None:os.utime(path,(when,when))
  write('supervisor/owner.json',{'pid':pid,'started_at':iso(base)});write('supervisor/status.json',{'supervisor_pid':pid,'time':iso(base+1),'status':'curating','script':'curate_pairs.py'})
  initial=audit(root);assert initial['status']=='pending' and not initial['canonical_current_metadata']
  for run in RUNS:
   prefix='' if run=='priority' else 'runs/'+run+'/'
   task={'repo_id':'owner/'+run,'revision':'fixed','path':'README.md','expected_size':1}
   write(prefix+'download_inventory.json',[{'repo_id':task['repo_id'],'revision':'fixed','files':[task]}]);write(prefix+'download_manifest.json',{'finished':True,'files':[{**task,'status':'complete'}]});write(prefix+'download_failures.json',[])
  write('raw/jgraph--drawio-templates/source_manifest.json',{'finished':True,'failed_files':[]});write('reports/extra_assets.json',{'assets':[{'status':'complete','archive_integrity_checked':True}]*2})
  rows={'clean':{'catalog_kind':'provided','alignment_verification':'provider_declared_pairing_not_independently_rendered','category':'chart','image_provenance':'dataset_provided_image','gold_code_provenance':'dataset_provided_code','pairing':'provided_image_and_code','code_execution_checked':False},'derived':{'catalog_kind':'derived','alignment_verification':'rendered_from_selected_code','category':'scientific_diagram','image_provenance':'rendered_from_selected_native_drawio','code_provenance':'official_repository_native_drawio_author_unverified','pairing':'derived_from_native_drawio','code_execution_checked':True}}
  hashes={}
  for folder,row in rows.items():
   path=root/folder/'manifest.jsonl';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(row)+'\n');hashes[folder]=hashlib.sha256(path.read_bytes()).hexdigest();os.utime(path,(base+82,base+82))
  groups={kind:{'pairs':1,'invalid_locators':0,'categories':{rows[folder]['category']:1}} for kind,folder in [('provided','clean'),('derived','derived')]}
  reports={'summary.json':{'sources':{},'paired_image_code':1},'archive_summary.json':{'sources':{},'paired_image_code':0},'derived_summary.json':{'sources':{},'derived_pairs':1},'native_sources_summary.json':{'sources':{},'accepted_pairs':1,'processed_all_eligible_pages':True,'render_rejected':6},'catalog_summary.json':{'groups':groups},'provenance_qc.json':{'ok':True,'critical_issues':{},'issues':{'license_unknown_or_unverified':2},'groups':{'provided':{'rows':1},'derived':{'rows':1}},'cross_kind':{}},'content_audit.json':{'ok':True,'errors':0,'checked_pairs':2,'groups':{'clean':{'checked':1,'errors':0},'derived':{'checked':1,'errors':0}},'input_manifest_sha256':hashes}}
  journal=[]
  for index,(script,name) in enumerate(STAGES):
   start=base+10+index*20;finish=start+10;reports[name].update({'started_at':iso(start),'finished_at':iso(finish)});write('reports/'+name,reports[name],finish)
   journal.extend([{'supervisor_pid':pid,'time':iso(start),'status':'curation_started','script':script},{'supervisor_pid':pid,'time':iso(finish+1),'status':'curation_verified','script':script}])
  (root/'supervisor/progress.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in journal))
  done={'status':'complete','root':str(root),'finished_at':iso(base+180),'additional_download_gates':{'priority_downloads':True,'official_templates':True,'extra_assets':True},'catalogs':groups,'content_hash_audit':reports['content_audit.json'],'provenance_audit':{key:reports['provenance_qc.json'].get(key) for key in ('ok','critical_issues','issues','cross_kind')},'pair_sources':{},'archive_sources':{},'archive_paired_image_code':0,'derived_pairs':1,'native_source_pages_accepted':1}
  write('collection_done.json',done,base+180);write('supervisor/status.json',{'supervisor_pid':pid,'time':iso(base+181),'status':'complete'})
  passed=audit(root);assert passed['status']=='metadata_pass',passed;assert not passed['collection_or_goal_completion_claim']
  manifest=root/'clean/manifest.jsonl';old=manifest.read_bytes();manifest.write_bytes(old+b'\n');os.utime(manifest,(base+83,base+83));bad=audit(root);assert bad['status']=='needs_attention' and 'content_input_manifest_sha_matches_current:provided' in bad['failed_checks'];manifest.write_bytes(old)
  write('supervisor/owner.json',{'pid':pid+1,'started_at':iso(base+200)});write('supervisor/status.json',{'supervisor_pid':pid+1,'time':iso(base+201),'status':'curating','script':'curate_pairs.py'});stale=audit(root);assert stale['status']=='pending' and not stale['canonical_current_metadata']
 print(json.dumps({'self_test':'passed','fixtures':['live pipeline pending does not use old catalog','same-generation seven stages + done bindings','all download metadata ready','canonical SHA + counts/category/provenance checks','noncritical license warnings do not block','native rejected auxiliary pages do not block','hash mismatch detected','old-generation done/catalog not current','visual/goal completion never asserted']}))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path);parser.add_argument('--seconds',type=int,default=30);parser.add_argument('--max-json-bytes',type=int,default=128*1024**2);parser.add_argument('--max-manifest-bytes',type=int,default=1024**3);parser.add_argument('--journal-tail-bytes',type=int,default=8*1024**2);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
 if args.self_test:self_test()
 elif args.root:print(json.dumps(audit(args.root,args.seconds,args.max_json_bytes,args.max_manifest_bytes,args.journal_tail_bytes),ensure_ascii=False),flush=True)
 else:parser.error('--root required')
