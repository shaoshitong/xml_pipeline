"""Short-transaction registry-only outcomes for fresh finite visual failures.

A current-source guard and existing real PNG/native evidence are checked before
independent registration/fidelity recomputation. Hashes/fsync are outside the
SQL writer lock. This module never renders, calls a model, changes a job/queue,
or claims intrinsic source inexpressibility. Default is a read-only dry run.
"""
from pathlib import Path
import copy,datetime,hashlib,importlib,json,math,os,re,secrets,sqlite3,stat,sys,time,uuid
import program_terminal_outcomes_v2 as shared
import visual_failure_route_guard_v1 as guard
import visual_failure_certificate_v1 as collector
import visual_failure_clip_evidence_v1 as clip_evidence
import visual_failure_finite_v1 as supervisor
from bounded_sqlite_transaction_v1 import BusyBudget
ROOT=guard.ROOT
POLICY='current_verified_program_visual_failure_registry_only_terminal_v1'
DIRECTORY=Path('conversion/visual_failure_terminal_outcomes_v1')
PRIVATE=Path('conversion/prototype/visual_failure_terminal_private_v1')
PREPARATIONS=Path('conversion/prototype/visual_failure_terminal_preparations_v1')
MARKER='visual_failure_terminal_outcome_v1'
SCHEMA='visual_failure_terminal_plan_v1'
INDEPENDENT_SCHEMA='independent_original_image_and_real_native_png_fidelity_v1'
REGISTRY_COLUMNS=('category','format','source_code_hash','source_image_hash','status','reason','record','updated_at')
FROZEN={'visual_failure_certificate_v1.py':'6b57c6077c167ea731f1fbea4b9b6e0240c6264cdce95d8c386c7df644fdce4c','visual_failure_route_guard_v1.py':'fd33e9d73933547d5a23939f091387c0da02ad40a2ff41545d16f122ef3c059a','visual_failure_clip_evidence_v1.py':'577f1d8c1da1d37aeb875bbed939befa94d14257f6b13bda2f306039748361b1','visual_failure_finite_v1.py':'78f4f366e19f9716dcc6a3beb719ada9662d321ac80264d8ff04e0cca0542518','initial_conversion_process_v1.py':'45d6097a9349c9ce0ff6b2de7384900445fe75aaa1ff8a3c5e48c743d216b736'}
_SEAL=object();sha=shared.sha;require=shared.require;canonical=shared.canonical
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def configuration(root=ROOT,private_root=None):
 root=Path(root).resolve(strict=True);scripts=root/'conversion/scripts'
 if str(scripts) not in sys.path:sys.path.insert(0,str(scripts))
 c=collector.configuration(root);pins=dict(c['pins'])
 for name,expected in FROZEN.items():require(sha((scripts/name).read_bytes())==expected,'frozen_dependency_changed:'+name);pins[str((scripts/name).resolve())]=expected
 for module in (sys.modules[__name__],shared,sys.modules[BusyBudget.__module__]):pins[str(Path(module.__file__).resolve())]=sha(Path(module.__file__).read_bytes())
 destination=root
 if private_root is not None:
  destination=Path(private_root).resolve();require(destination.is_relative_to(root/PRIVATE) and destination!=root/PRIVATE,'private_validation_namespace_required');destination.mkdir(parents=True,exist_ok=True)
 return {'root':str(root),'decision_root':str(destination),'private_validation_only':destination!=root,'policy':POLICY,'guard':c['guard'],'collector':c,'pins':pins,'qa_policy':c['qa_policy'],'writer_begin_seconds':180,'writer_commit_seconds':30}

def _config_signature(config):return canonical(config)
def ensure_pins(config):
 for path,expected in config['pins'].items():require(sha(Path(path).read_bytes())==expected,'pinned_implementation_changed:'+path)
 guard._checked_config(config['guard'])
def _locator(root,path):
 root=Path(root).resolve();p=Path(path);p=p if p.is_absolute() else root/p;require(p.resolve(strict=True).is_relative_to(root),'file_outside_data_root');return p

def _read_owned(root,path,expected=None,immutable=False):
 root=Path(root).resolve();p=Path(path);p=p if p.is_absolute() else root/p;require(p.is_relative_to(root) and '..' not in p.parts,'invalid_owned_locator');relative=p.relative_to(root);directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fd=None
 try:
  for part in relative.parts[:-1]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=child
  fd=os.open(relative.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory);a=os.fstat(fd);require(stat.S_ISREG(a.st_mode),'owned_artifact_not_regular');require(not immutable or a.st_mode&0o222==0,'owned_artifact_not_immutable');parts=[]
  while True:
   part=os.read(fd,1048576)
   if not part:break
   parts.append(part)
  b=os.fstat(fd);require(shared._stat_tuple(a)==shared._stat_tuple(b),'owned_artifact_changed_during_read')
 finally:
  if fd is not None:os.close(fd)
  os.close(directory)
 raw=b''.join(parts);require(expected is None or sha(raw)==expected,'owned_artifact_sha_mismatch:'+str(p));return raw,p

def _entry(path,raw):return {'file':str(path),'sha256':sha(raw)}
def _doc(root,descriptor,immutable=False):
 require(isinstance(descriptor,dict) and digest(descriptor.get('sha256')),'invalid_file_descriptor');raw,p=_read_owned(root,descriptor['file'],descriptor['sha256'],immutable);doc=json.loads(raw);canonical(doc);return doc,raw,p

def _canonical_snapshot(snapshot):
 # Physical B-tree root page allocation is not logical schema. All object SQL,
 # schema cookie, every column and every same-ID raw row (including empty sets)
 # remain in the CAS; this also supports a genuine isolated private DB clone.
 result=copy.deepcopy(snapshot);result['schema']=[row[:3]+row[4:] for row in result['schema']];return result

def _snapshot(db,identifier):return _canonical_snapshot(guard._snapshot(db,identifier))
def _registry(db,identifier):return db.execute('select '+','.join(REGISTRY_COLUMNS)+' from processing_outcomes_v2 where id=?',(identifier,)).fetchone()
def _capture(db,identifier,config,context=None):
 ensure_pins(config);current=guard.revalidate(db,context,config['guard']) if context is not None else guard.capture(db,identifier,config['guard']);require(current.get('eligible') is True,'current_route_or_owner_guard_refused:'+str(current.get('reason')));return current

def _completed_births(state,report):
 from initial_conversion_process_v1 import identity,same_birth
 for execution in (state['outer_execution'],report['execution']):
  require(execution.get('ok') is True and execution.get('cleanup_complete') is True and execution.get('deadline_exceeded') is False and execution.get('returncode')==0,'evidence_process_not_successfully_closed');require(not execution.get('tracking_errors') and not execution.get('foreign_children_not_touched'),'evidence_process_tracking_not_closed')
  records=execution.get('tracked_processes');require(isinstance(records,list) and records,'missing_actual_process_birth_evidence')
  for record in records:require(not same_birth(record,identity(record['pid'])),'evidence_case_process_birth_still_live')

def _effective_files(case_file,config):
 root=Path(config['root']);case_path=Path(case_file);case_path=case_path if case_path.is_absolute() else root/case_path;prefix=root/supervisor.BASE/'finite_runs';require(case_path.is_relative_to(prefix) and case_path.name=='case_result.json' and case_path.parent.parent.name=='cases','outside_finite_case_result_namespace');identifier=case_path.parent.name;require(digest(identifier),'invalid_case_id');run=case_path.parent.parent.parent;require(re.fullmatch('[0-9a-f]{32}',run.name),'invalid_finite_run_uuid');case_raw,_=_read_owned(root,case_path,immutable=True);case=json.loads(case_raw);require(canonical(case)==case_raw,'noncanonical_immutable_case_result');state_raw,state_path=_read_owned(root,case_path.parent/'state.json');state=json.loads(state_raw);request_raw,request_path=_read_owned(root,case_path.parent/'request.json',immutable=True);request=json.loads(request_raw);manifest_raw,manifest_path=_read_owned(root,run/'manifest.json',immutable=True);manifest=json.loads(manifest_raw)
 require(case['id']==state['id']==request['id']==identifier,'case_state_request_identity_mismatch');require(case['effective_proposal'] is True and case['raw_collector_proposal'] is True and case['inner_cleanup_complete'] is True and case['accepted'] is False and case['terminal_publication_authorized'] is False,'not_effective_nonpublishing_visual_case');require(case['state']=='fresh_visual_failure_evidence_proposal' and type(case['model_api_calls']) is int and case['model_api_calls']==0 and case['canonical_mutations']==0,'wrong_case_effect_or_api_contract');require(state['case_result_sha256']==sha(case_raw) and state['attempts_this_run']==1 and state['fatal'] is False and state['matching_live_owned_births']==[],'unclosed_finite_state_or_multiple_attempts');require(all(state.get(key)==value for key,value in case.items()),'final_state_differs_from_immutable_case')
 require(manifest['schema']==supervisor.POLICY and manifest['count']==1730 and manifest['full_scope']==131904 and manifest['format_counts']==supervisor.EXPECTED and manifest['workers']==4 and manifest['case_total_deadline_seconds']==360 and manifest['canonical_writer'] is False and manifest['watch'] is False and manifest['api_calls']==0,'unknown_finite_manifest');require(manifest['source_manifest_sha256']==guard.MANIFEST_SHA and manifest['source_report_sha256']==guard.REPORT_SHA,'finite_source_scope_changed');require(request['root']==str(root) and Path(request['run'])==run and Path(request['manifest_file'])==manifest_path and request['manifest_sha256']==sha(manifest_raw) and request['policy']==supervisor.POLICY and request['deadline_seconds']==360,'finite_request_not_bound_to_manifest');items=[r for r in manifest['items'] if r['id']==identifier];require(len(items)==1,'case_not_unique_in_fixed_manifest')
 keymap={'supervisor':'visual_failure_finite_v1.py','collector':'visual_failure_certificate_v1.py','guard':'visual_failure_route_guard_v1.py','clip_evidence':'visual_failure_clip_evidence_v1.py','process':'initial_conversion_process_v1.py'}
 for key,name in keymap.items():require(manifest['implementation'][key]==FROZEN[name],'finite_author_mismatch:'+name)
 files={str(case_path):{'sha256':sha(case_raw),'bytes':len(case_raw)},str(state_path):{'sha256':sha(state_raw),'bytes':len(state_raw)},str(request_path):{'sha256':sha(request_raw),'bytes':len(request_raw)},str(manifest_path):{'sha256':sha(manifest_raw),'bytes':len(manifest_raw)}}
 for name in ('visual_failure_finite_v1.py','visual_failure_certificate_v1.py','visual_failure_route_guard_v1.py','visual_failure_clip_evidence_v1.py'):
  raw,p=_read_owned(root,run/'implementation'/name,FROZEN[name],immutable=True);files[str(p)]={'sha256':sha(raw),'bytes':len(raw)}
 certificate_raw,certificate_path=_read_owned(root,case['report'],case['report_file_sha256']);require(certificate_path==case_path.parent/'collector_attempt/report.json','case_report_not_owned');certificate=json.loads(certificate_raw);require(canonical(certificate)==certificate_raw,'fresh_certificate_not_canonical');body=copy.deepcopy(certificate);cert_hash=body.pop('certificate_sha256');require(sha(canonical(body))==cert_hash==case['certificate_sha256'],'fresh_certificate_body_digest_mismatch');require(certificate['schema']==collector.SCHEMA and certificate['proposal'] is True and certificate['accepted'] is False and certificate['source_semantically_unsupported'] is False and certificate['native_editing']['state']=='not_reached' and certificate['native_editing']['ok'] is None and certificate['models_called']==0 and certificate['canonical_mutations']==0,'not_fresh_visual_only_failure_certificate');require(certificate['id']==identifier and certificate['qa_policy']==config['qa_policy'],'fresh_certificate_identity_or_policy_changed');_completed_births(state,certificate)
 fresh_clip=clip_evidence.inspect(certificate,root,certificate_path.parent);require(fresh_clip['complete'] is True and case['clip_dependency_evidence']['complete'] is True,'incomplete_supervisor_or_current_CLIP_closure');require(canonical(fresh_clip)==canonical(case['clip_dependency_evidence']),'CLIP_posthash_closure_changed_after_supervisor');require(supervisor.effective_decision(certificate,fresh_clip)[0] is True,'supervisor_effective_decision_not_reproducible')
 # Every retained per-case artifact, not just the top-level JSON links, is
 # crypto-bound. No symlink/unknown subtree is silently skipped.
 count=0
 for parent,dirs,names in os.walk(case_path.parent,followlinks=False):
  require(not any((Path(parent)/name).is_symlink() for name in dirs),'symlink_case_evidence_directory')
  for name in names:
   p=Path(parent)/name;raw,_=_read_owned(root,p);files[str(p)]={'sha256':sha(raw),'bytes':len(raw)};count+=1;require(count<=10000,'case_evidence_inventory_bound_exceeded')
 for entry in fresh_clip['files']:
  p=root/entry['file'];raw,_=_read_owned(root,p,entry['sha256']);files[str(p)]={'sha256':sha(raw),'bytes':len(raw)}
 files[str(certificate_path)]={'sha256':sha(certificate_raw),'bytes':len(certificate_raw)}
 return {'id':identifier,'case':case,'state':state,'manifest':manifest,'request':request,'report':certificate,'files':files,'fresh_certificate':{**_entry(certificate_path,certificate_raw),'certificate_sha256':cert_hash},'effective_case':_entry(case_path,case_raw),'supervisor_state':_entry(state_path,state_raw),'supervisor_request':_entry(request_path,request_raw),'supervisor_manifest':_entry(manifest_path,manifest_raw)}

def _independent(config,bundle,context):
 qa=importlib.import_module('auto_quality_batch_v4b');root=Path(config['root']);r=context['record'];report=bundle['report'];fresh=report['fresh_qa'];require(not fresh['observer_errors'] and not fresh['blocked_mutation_attempts'] and not fresh['qa_returned_out'],'fresh_observation_not_a_closed_negative');ob=fresh['observations'];require(len(ob)==1,'primary_render_not_unique');ob=ob[0];request,_,_=_doc(root,report['evidence_files']['request']);q=fresh['report'];collector.classify(q,ob,request)
 for field,descriptor in report['evidence_files'].items():
  _doc(root,descriptor)  # exact hash and well-formed JSON, never boolean trust.
 child,_,_=_doc(root,report['evidence_files']['child_result']);audit,_,_=_doc(root,report['evidence_files']['frozen_qa_audit']);require(canonical(child)==canonical(fresh) and canonical(audit)==canonical(q),'child_or_QA_audit_not_exact')
 require(tuple(request['item'])==(r['id'],context['job']['state'],context['job']['output_record'],context['job']['input_record'],context['job']['route']),'fresh_request_job_record_not_current');require(request['record']==r,'fresh_request_output_metadata_changed');require(report['current_four_hashes']=={k:r[k] for k in ('source_code_sha256','source_image_sha256','code_sha256','image_sha256')},'fresh_certificate_four_hashes_not_current')
 png,png_path=_read_owned(root,ob['png']['file'],ob['png']['sha256']);native_raw,native_path=_read_owned(root,ob['native_info']['file'],ob['native_info']['sha256']);info=json.loads(native_raw);xml=qa.checked(root,r['code_file'],r['code_sha256']).decode();reference=qa.checked(root,r['original_reference'],r['source_image_sha256']);qa.checked(root,r['image_file'],r['image_sha256']);qa.checked(root,r['original_source_code'],r['source_code_sha256']);registered,registration=qa.registration_record(copy.deepcopy(r),reference,xml);resources=qa.resource_checks(root,registered,xml,reference);structure=qa.structure_checks(xml);text=qa.require_rendered_text(xml,info);qa.require_declared_page(info,*ob['canvas']);require(info['selected_image']=='declared_first_page' and info['output_size']==ob['canvas'] and info['content_outside_declared_canvas'] is False,'actual_native_page_not_declared')
 boundary=info['outside_page_pixel_audit'];require(type(boundary['nonwhite_outside_pixels']) is int and boundary['nonwhite_outside_pixels']==0 and boundary['white_threshold']==255 and boundary['audit_always_performed'] is True and boundary['minimum_probe_margin']==32 and info['probe_includes_actual_dom_paint_bounds'] is True,'missing_actual_unconditional_strict_paint_audit');offset=boundary['offset'];padded=boundary['padded_native_render_size'];require(all(type(n) is int for n in offset+padded) and len(offset)==len(padded)==2 and min(offset)>=32 and padded[0]>=ob['canvas'][0]+offset[0]+32 and padded[1]>=ob['canvas'][1]+offset[1]+32,'strict_probe_does_not_cover_full_original_page')
 from PIL import Image
 import io
 require(list(Image.open(io.BytesIO(png)).size)==ob['canvas'],'real_PNG_canvas_changed');usage=[f for row in info['actual_platform_font_usage'] for f in row['fonts'] if f['glyphCount']>0];require(not text['expected_text_objects'] or usage,'missing_actual_font_usage');require(all(f['isCustomFont'] is True for f in usage),'actual_font_not_custom');glyphs=sum(f['glyphCount'] for f in usage);require(glyphs==q['checks']['fonts']['actual_custom_font_glyphs'],'actual_font_glyph_count_not_bound');require(resources==q['checks']['resources'] and structure==q['checks']['structure'] and text==q['checks']['text_paint'],'fresh_resources_structure_or_text_checks_changed')
 metric=qa.image_quality(reference,png,registered,info['actual_text_positions']);require(metric['ok'] is False and metric['failures'] and set(metric['failures'])<=collector.VISUAL_FAILURES,'independent_visual_now_passes_or_unknown_failure');require(canonical(metric)==canonical(q['checks']['visual']),'independent_visual_recompute_differs_from_frozen_QA');require(q['failures']==['raster_anomaly: '+','.join(metric['failures'])] and 'native_editing' not in q['checks'],'not_sole_raster_or_editing_misrepresented')
 paths={r[k]:r[h] for k,h in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]}
 for p in resources['verified_files']:paths.setdefault(p,None)
 for key,h in [('source_code','code_sha256'),('reference_image','image_sha256')]:paths[context['input_manifest'][key]]=context['input_manifest'][h]
 # Current registered proof dependencies may include hard-coded sibling files.
 # Capture bounded proof directories as well as their logical aliases.
 proof_paths={}
 def visit(value):
  if isinstance(value,dict):
   for v in value.values():visit(v)
  elif isinstance(value,list):
   for v in value:visit(v)
  elif isinstance(value,str) and 0<len(value)<4096 and '\0' not in value:
   try:
    p=_locator(root,value)
    if p.is_file():proof_paths[str(p)]=None
   except (OSError,ValueError):pass
 if registration:
  visit(registration)
  parents={Path(p).parent for p in proof_paths if Path(p).is_relative_to(root/'conversion')}
  for parent in parents:
   for p in parent.rglob('*'):
    if p.is_file():proof_paths[str(p)]=None;require(len(proof_paths)<=2000,'registration_proof_inventory_bound_exceeded')
 paths.update(proof_paths)
 evidence={'schema':INDEPENDENT_SCHEMA,'id':r['id'],'four_hashes':{k:r[k] for k in ('source_code_sha256','source_image_sha256','code_sha256','image_sha256')},'actual_png':{'file':str(png_path),'sha256':sha(png)},'actual_native_info':{'file':str(native_path),'sha256':sha(native_raw)},'metrics':metric,'registration':registration,'resources':resources,'structure':structure,'text_paint':text,'actual_custom_font_glyphs':glyphs,'strict_outside_page_pixels':0,'source_verified_by_fresh_frozen_QA':q['checks']['source'],'native_editing':{'state':'not_reached','ok':None},'no_renderer_or_model_invoked':True}
 return metric,paths,evidence

def _save_evidence(path,raw):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb') as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return {'file':str(path),'sha256':sha(raw),'bytes':len(raw)}

def _fsync(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

def _outcome(plan,receipt):
 reason='current_verified_program_visual_gate_failure: '+','.join(plan['visual_failures']);names=('id','source_code_sha256','source_image_sha256','code_sha256','image_sha256','reason_code','reason_detail','visual_failures','qa_policy','fresh_certificate','effective_case','independent_visual','native_editing','source_semantically_unsupported');evidence={k:copy.deepcopy(plan[k]) for k in names};evidence.update(accepted=False,abandonment_is_not_conversion_success=True,deterministic_recovery_permitted=True,new_model_calls=0,scope='Current frozen verified program and current revision only; not intrinsic drawio impossibility.');evidence[MARKER]={'policy':POLICY,'decision':receipt,'commit_nonce':receipt['commit_nonce'],'active_quality_policy':plan['qa_policy'],'prior_registry_snapshot_sha256':plan['registry_snapshot_sha256']};return reason,canonical(evidence).decode()

def _write_decision(root,receipt,payload):
 require(sha(payload)==receipt['sha256'],'decision_digest_mismatch');relative=Path(receipt['file']);require(relative==DIRECTORY/relative.parent.name/('decision.'+receipt['sha256']+'.json') and digest(relative.parent.name),'invalid_decision_locator');directory=os.open(Path(root).resolve(),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fd=None;tmp='.'+relative.name+'.'+secrets.token_hex(16)+'.tmp'
 try:
  for name in relative.parts[:-1]:
   try:os.mkdir(name,0o755,dir_fd=directory)
   except FileExistsError:pass
   child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.fsync(directory);os.fsync(child);os.close(directory);directory=child
  fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory);remaining=memoryview(payload)
  while remaining:
   n=os.write(fd,remaining);require(n>0,'short_decision_write');remaining=remaining[n:]
  os.fsync(fd);os.fchmod(fd,0o444);os.fsync(fd);os.close(fd);fd=None
  try:os.link(tmp,relative.name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
  except FileExistsError:
   stored,_=_read_owned(root,relative,receipt['sha256'],True);require(stored==payload,'immutable_decision_conflict')
  os.fsync(directory)
 finally:
  if fd is not None:os.close(fd)
  try:os.unlink(tmp,dir_fd=directory);os.fsync(directory)
  except FileNotFoundError:pass
  os.close(directory)

def prepare_decision(source_db,effective_case,config,publish=False):
 require(type(publish) is bool and not source_db.in_transaction,'fresh_source_connection_and_explicit_publish_required');started=time.monotonic();ensure_pins(config);bundle=_effective_files(effective_case,config);context=_capture(source_db,bundle['id'],config);metric,resources,recomputed=_independent(config,bundle,context);root=Path(config['root']);decision_root=Path(config['decision_root']);proof_path=decision_root/PREPARATIONS/bundle['id']/uuid.uuid4().hex/'independent_visual.json';independent=_save_evidence(proof_path,canonical(recomputed));files=copy.deepcopy(bundle['files']);files[str(proof_path)]={'sha256':independent['sha256'],'bytes':independent['bytes']};all_witnesses={p:shared.file_witness(root,p,info['sha256']) for p,info in files.items()}
 for p,expected in resources.items():all_witnesses[str(p)]=shared.file_witness(root,p,expected)
 for p,expected in config['pins'].items():all_witnesses[p]=shared.file_witness(root,p,expected)
 for name in ('owner','model_policy','research_reservation'):
  entry=config['guard'][name];p=root/entry['file'];all_witnesses[str(p)]=shared.file_witness(root,p,entry['sha256'])
 resolved={v['identity']['resolve']:v['sha256'] for v in all_witnesses.values()}
 for value in (context['record'],context['source'],context['input_manifest'],recomputed.get('registration')):
  for logical,expected in shared._logical_aliases(value,root,resolved).items():all_witnesses.setdefault(logical,shared.file_witness(root,logical,expected))
 for p in files:_fsync(p)
 for p in {str(Path(p).parent) for p in files}:_fsync(p)
 final=_capture(source_db,bundle['id'],config,context);shared._check_identities(root,all_witnesses);snapshot=_canonical_snapshot(final['full_snapshot']);registry=tuple(final['outcome'][k] for k in REGISTRY_COLUMNS);r=final['record'];plan={'schema':SCHEMA,'id':r['id'],'category':r['category'],'source_format':r['source_format'],**{k:r[k] for k in ('source_code_sha256','source_image_sha256','code_sha256','image_sha256')},'qa_policy':config['qa_policy'],'visual_failures':metric['failures'],'fresh_certificate':bundle['fresh_certificate'],'effective_case':bundle['effective_case'],'supervisor_state':bundle['supervisor_state'],'supervisor_request':bundle['supervisor_request'],'supervisor_manifest':bundle['supervisor_manifest'],'independent_visual':metric,'independent_visual_evidence':independent,'native_editing':{'state':'not_reached','ok':None},'source_semantically_unsupported':False,'reason_code':'current_program_visual_gate_failure','reason_detail':'Current frozen program failed original-image visual gates: '+','.join(metric['failures']),'scope_identity':final['scope_identity'],'registry_snapshot_sha256':sha(canonical(list(registry))),'files':files,'pins':config['pins'],'route_verdicts':final['route_verdicts']};nonce=secrets.token_hex(16);stamp=now();document={'version':1,'id':r['id'],'created_at':stamp,'writer_policy':POLICY,'writer_sha256':sha(Path(__file__).read_bytes()),'collector_sha256':FROZEN['visual_failure_certificate_v1.py'],'supervisor_sha256':FROZEN['visual_failure_finite_v1.py'],'guard_sha256':FROZEN['visual_failure_route_guard_v1.py'],'clip_evidence_sha256':FROZEN['visual_failure_clip_evidence_v1.py'],'data_root':str(root),'decision_root':str(decision_root),'private_validation_only':config['private_validation_only'],'plan':plan,'plan_sha256':sha(canonical(plan)),'prior_outcome':dict(zip(REGISTRY_COLUMNS,registry)),'complete_database_cas_snapshot':snapshot,'guard_full_database_cas_snapshot':final['full_snapshot'],'file_witnesses':all_witnesses,'reviewed_config':config,'commit_nonce':nonce,'accepted':False,'deterministic_recovery_permitted':True,'abandonment_is_not_conversion_success':True,'new_model_calls':0,'source_semantically_unsupported':False,'native_editing':{'state':'not_reached','ok':None}};payload=canonical(document);receipt={'file':str(DIRECTORY/r['id']/('decision.'+sha(payload)+'.json')),'sha256':sha(payload),'plan_sha256':document['plan_sha256'],'commit_nonce':nonce,'created_at':stamp};reason,raw=_outcome(plan,receipt);expected=tuple(list(registry[:4])+['abandoned',reason,raw,stamp])
 if publish:
  _write_decision(decision_root,receipt,payload);stored,p=_read_owned(decision_root,receipt['file'],receipt['sha256'],True);require(stored==payload,'decision_durable_readback_failed');all_witnesses={**all_witnesses,'decision:'+receipt['sha256']:shared.file_witness(decision_root,p,receipt['sha256'])}
 return {'_seal':_SEAL,'id':r['id'],'plan':plan,'document':document,'snapshot':snapshot,'registry':registry,'expected':expected,'witnesses':all_witnesses,'receipt':receipt,'publish':publish,'config_signature':_config_signature(config),'preparation_seconds':time.monotonic()-started}

def _destination(db,config):
 rows=[r for r in db.execute('pragma database_list') if r[1]=='main'];require(len(rows)==1 and rows[0][2],'real_registry_database_required');path=Path(rows[0][2]).resolve();expected=(Path(config['decision_root'])/'conversion/jobs.sqlite').resolve();require(path==expected,'wrong_registry_database_destination')
 if config['private_validation_only']:require(path!=(Path(config['root'])/'conversion/jobs.sqlite').resolve(),'private_validation_cannot_target_canonical_DB');require(path.stat().st_ino!=(Path(config['root'])/'conversion/jobs.sqlite').stat().st_ino or path.stat().st_dev!=(Path(config['root'])/'conversion/jobs.sqlite').stat().st_dev,'private_validation_DB_is_canonical_hardlink')

def apply_prepared(db,prepared,config):
 require(prepared.get('_seal') is _SEAL and not db.in_transaction and db.row_factory is None,'fresh_connection_and_owned_preparation_required');_destination(db,config);base={'id':prepared['id'],'policy':POLICY,'applied':False,'accepted':False,'decision':prepared['receipt'],'private_validation_only':config['private_validation_only'],'preparation_seconds':prepared['preparation_seconds']};acquired=None;committing=False;updated=False
 try:
  guard._owners(prepared['snapshot']);require(_config_signature(config)==prepared['config_signature'],'configuration_changed_after_preparation')
  if prepared['publish']:
   begin=BusyBudget(config.get('writer_begin_seconds',180),5);begin.begin(db)
  else:db.execute('begin')
  acquired=time.monotonic();require(_snapshot(db,prepared['id'])==prepared['snapshot'],'complete_database_CAS_changed');shared._check_identities(config['root'],prepared['witnesses'])
  if not prepared['publish']:
   db.rollback();return {**base,'state':'dry_run_current','would_apply':True,'writer_lock_held_seconds':0.0}
  changed=db.total_changes;reason,raw,stamp=prepared['expected'][5:8];where=' and '.join(name+' is ?' for name in REGISTRY_COLUMNS);cursor=db.execute('update processing_outcomes_v2 set status="abandoned",reason=?,record=?,updated_at=? where id=? and '+where,(reason,raw,stamp,prepared['id'],*prepared['registry']));cursor.fetchall();require(cursor.rowcount==1 and db.total_changes-changed==1,'registry_CAS_or_trigger_side_effect_refused');updated=True;require(_registry(db,prepared['id'])==prepared['expected'],'registry_after_update_not_exact');shared._check_identities(config['root'],prepared['witnesses']);committing=True;end=BusyBudget(config.get('writer_commit_seconds',30),5);end.commit(db);return {**base,'state':'abandoned','applied':True,'commit_nonce':prepared['receipt']['commit_nonce'],'writer_lock_held_seconds':time.monotonic()-acquired,'begin_diagnostics':begin.diagnostics(),'commit_diagnostics':end.diagnostics(),'jobs_queues_source_and_history_unchanged':True}
 except BaseException as error:
  active=db.in_transaction
  if active:db.rollback()
  if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
  recovered=False
  if committing and updated and not active:
   try:recovered=_registry(db,prepared['id'])==prepared['expected']
   except sqlite3.Error:pass
  return {**base,'state':'abandoned' if recovered else 'commit_outcome_unknown' if committing and updated and not active else 'failed_rolled_back','applied':recovered,'commit_receipt_recovered':recovered,'error':repr(error),'may_have_committed':bool(committing and updated and not active and not recovered),'writer_lock_held_seconds':time.monotonic()-acquired if acquired is not None else 0.0}

def apply(db,effective_case,config,publish=False,source_db=None):
 require(type(publish) is bool and not db.in_transaction,'explicit_publish_and_fresh_connection_required');_destination(db,config);prior=_registry(db,Path(effective_case).parent.name)
 if prior and prior[4]!='pending':return {'id':Path(effective_case).parent.name,'state':'preserved_'+prior[4],'applied':False,'accepted':False}
 try:prepared=prepare_decision(source_db or db,effective_case,config,publish)
 except (ValueError,OSError,KeyError,TypeError,AssertionError,sqlite3.Error) as error:return {'id':Path(effective_case).parent.name,'state':'preparation_refused','applied':False,'accepted':False,'error':repr(error),'no_writer_transaction_opened':True}
 return apply_prepared(db,prepared,config)

def clone_private_database(prepared,config):
 """Validation helper: reproduce the complete logical same-ID state privately.

 No canonical DB writes, no lease recovery, no altered live guard. The source
 preparation was obtained through the real canonical RO guard. Only an explicit
 private root may receive these rows; production receipts remain disallowed by
 the strict reader's default private=False contract.
 """
 require(config['private_validation_only'] is True and prepared.get('_seal') is _SEAL,'explicit_private_preparation_required');path=Path(config['decision_root'])/'conversion/jobs.sqlite';path.parent.mkdir(parents=True,exist_ok=True);require(not path.exists(),'new_private_database_required');db=sqlite3.connect(path,timeout=0);snapshot=prepared['snapshot']
 try:
  db.execute('pragma foreign_keys=off')
  for kind,name,table,sql in snapshot['schema']:
   if kind=='table':require(sql and 'virtual table' not in sql.lower(),'unsupported_private_schema_clone');db.execute(sql)
  for name,value in snapshot['tables'].items():
   for row in value['rows']:db.execute('insert into '+name+'('+','.join(value['columns'])+') values('+','.join('?' for _ in row)+')',row)
  for kind,name,table,sql in snapshot['schema']:
   if kind!='table' and sql:db.execute(sql)
  db.commit();db.execute('pragma schema_version='+str(snapshot['schema_version']));require(_snapshot(db,prepared['id'])==snapshot,'private_clone_not_exact_logical_snapshot');return db
 except BaseException:db.close();raise
