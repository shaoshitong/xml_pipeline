"""Read-only admission for the frozen finite visual-only no-route cohort.

Never invokes a producer, source compiler, browser, renderer, model or writer.
The report is discovery evidence; actual source identity, audit and all current
route selectors are checked again. Every id table (including empty sets) forms
one CAS snapshot. Unknown, changed or owned data stays pending.
"""
from pathlib import Path
import ast,copy,hashlib,json,math,os,re,sqlite3,stat
ROOT=Path('/backup/shaoshitong/img2code_20261029')
REPORT='conversion/prototype/visual_only_scope_ro_v1/visual_only_fullscope_program_routes_ro_v2.json'
REPORT_SHA='28d0316c290ec551d6ffb9851c6dcb32f2d1a608af2b62c9845e89d963288d34'
MANIFEST='conversion/prototype/visual_only_scope_ro_v1/visual_only_current_manifest_v2.json'
MANIFEST_SHA='3c0d0190181def37d4180db9f8aa9e772e5117e9825d9e89069797dff863e06e'
RESERVATION='conversion/prototype/svg_marker_composition_v2/research_cohort_manifest.json'
RESERVATION_SHA='85ae48fc00597c3d86e7d5db2b52d5234050d7d0b4b87f3fe43c4f4a79943bb8'
CLASS='current_visual_catalog_routes_terminal_or_inapplicable'
EXPECTED_COUNTS={'python':1358,'svg':356,'tikz':6,'drawio':1,'html':9}
POLICY='frozen_visual_failure_no_current_route_readonly_guard_v1'
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
REGISTRY_COLUMNS=('id','category','format','source_code_hash','source_image_hash','status','reason','record','updated_at')
IDLE={'rendered','needs_quality_repair','harness_review_pending','harness_rendered','needs_fallback'}
FAILURES={'global_fidelity_below_0.90','foreground_tile_p10_below_0.72','foreground_coverage_below_0.90','local_text_line_ssim_below_0.55'}
_CACHE={}
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
def _identity(path):
 p=Path(path);s=p.stat();require(stat.S_ISREG(s.st_mode),'not_regular_frozen_file:'+str(p));return {'resolve':str(p.resolve(strict=True)),'dev':s.st_dev,'ino':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}
def _read(path,expected=None):
 p=Path(path);require(not p.is_symlink(),'frozen_file_symlink_forbidden:'+str(p));before=_identity(p);raw=p.read_bytes();require(_identity(p)==before,'frozen_file_changed_while_reading:'+str(p));require(expected is None or sha(raw)==expected,'frozen_file_sha_changed:'+str(p));return raw,before
def _json(raw):
 result=json.loads(raw);canonical(result);return result

def configuration(root=ROOT):
 root=Path(root).resolve(strict=True);raw,ri=_read(root/REPORT,REPORT_SHA);report=_json(raw);mr,mi=_read(root/MANIFEST,MANIFEST_SHA);manifest=_json(mr);require(report['scope']==manifest['full_scope']==131904,'unknown_full_scope');require(report['active_owner']['policy']==manifest['policy']==report['route_catalog']['active_quality_policy'],'frozen_policy_mismatch');require(manifest['catalog_sha256']==sha(canonical(report['route_catalog'])),'manifest_catalog_sha_mismatch')
 records={r['id']:r for r in report['records']};require(len(records)==len(report['records'])==len(manifest['items']),'duplicate_or_missing_report_items');targets={};counts={}
 for item in manifest['items']:
  identifier=item['id'];require(digest(identifier) and identifier in records,'invalid_manifest_identifier');record=records[identifier]
  require(all(item.get(k)==record.get(k) for k in ('source_code_sha256','source_image_sha256','code_sha256','image_sha256','qa_policy','audit_record_sha256')),'manifest_report_revision_mismatch');require(item['source_format']==record['format'],'manifest_format_mismatch')
  require(item['logical_visual_route_class']==record['logical_visual_route_class'],'manifest_route_class_mismatch')
  if item['logical_visual_route_class']==CLASS:
   targets[identifier]=record;counts[record['format']]=counts.get(record['format'],0)+1
 require(counts==EXPECTED_COUNTS,'unknown_finite_target_cohort')
 pins=dict(report['route_catalog']['pins']);pins[str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes());identities={}
 for path,expected in pins.items():
  require(digest(expected),'invalid_source_pin');_,identities[path]=_read(path,expected)
 rr,rid=_read(root/RESERVATION,RESERVATION_SHA);reserved=_json(rr);require(len(reserved['ids'])==len(set(reserved['ids']))==16,'unknown_research_reservation')
 pr,pid=_read(root/'conversion/model_usage_policy_v2.json');model=_json(pr);require(model.get('legacy_sdk_disabled') is True and model.get('automatic_model_case_selection_disabled') is True and model.get('model_calls_per_original_sample_lifetime_limit')==2,'model_policy_not_bounded_or_legacy_enabled');allow=model.get('authorized_model_sample_ids');require(isinstance(allow,list) and len(allow)==len(set(allow))<=16 and all(digest(x) for x in allow),'invalid_model_allowlist')
 oraw,oid=_read(root/'conversion/auto_quality_owner.json');owner=_json(oraw);require(sha(oraw)==report['active_owner_sha256'] and owner['policy']==manifest['policy'],'active_quality_owner_changed')
 wrapped=root/'conversion/scripts/auto_quality_html_repair_batch_v3.py';wrapped_sha=pins.get(str(wrapped));require(wrapped_sha is not None,'missing_wrapped_source_pin');tree=ast.parse(wrapped.read_text());values=[n.value.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str) and any(isinstance(t,ast.Name) and t.id=='EXCEPTION_REASON_SQL' for t in n.targets)];require(len(values)==1,'unknown_wrapped_source_exception_predicate')
 config={'policy':POLICY,'database':'conversion/jobs.sqlite','root':str(root),'quality_policy':owner['policy'],'report':{'file':REPORT,'sha256':REPORT_SHA},'manifest':{'file':MANIFEST,'sha256':MANIFEST_SHA},'target_count':len(targets),'target_counts':counts,'pins':pins,'pin_identities':identities,'owner':{'file':'conversion/auto_quality_owner.json','sha256':sha(oraw),'identity':oid},'model_policy':{'file':'conversion/model_usage_policy_v2.json','sha256':sha(pr),'identity':pid},'research_reservation':{'file':RESERVATION,'sha256':RESERVATION_SHA,'identity':rid},'frozen_inputs':{REPORT:ri,MANIFEST:mi},'html_wrapped_predicate':values[0]}
 key=(str(root),REPORT_SHA,MANIFEST_SHA);_CACHE[key]={'config':copy.deepcopy(config),'targets':targets,'static_routes':report['route_catalog']['static_routes'],'reserved':set(reserved['ids']),'authorized':set(allow)};return config

def _checked_config(config):
 require(isinstance(config,dict) and config.get('policy')==POLICY,'unknown_guard_configuration');key=(config.get('root'),REPORT_SHA,MANIFEST_SHA)
 if key not in _CACHE:configuration(config['root'])
 cached=_CACHE[key];require(canonical(config)==canonical(cached['config']),'guard_configuration_changed')
 for path,identity in config['pin_identities'].items():require(_identity(path)==identity,'frozen_implementation_identity_changed:'+path)
 for name in ('owner','model_policy','research_reservation'):
  entry=config[name];path=Path(config['root'])/entry['file'];require(_identity(path)==entry['identity'],'guard_input_identity_changed:'+name)
  # These small authority files are rehashed; hot source files use their frozen
  # crypto-verified full inode/size/mtime/ctime/resolve identity from startup.
  require(sha(path.read_bytes())==entry['sha256'],'guard_authority_sha_changed:'+name)
 for relative,identity in config['frozen_inputs'].items():require(_identity(Path(config['root'])/relative)==identity,'frozen_inventory_identity_changed')
 return cached

def _columns(db,table):return [row[1] for row in db.execute('pragma main.table_info('+table+')')]
def _snapshot(db,identifier):
 require(db.row_factory is None,'default_sqlite_row_factory_required');require(all(row[1] in ('main','temp') for row in db.execute('pragma database_list')),'attached_database_forbidden');require(not db.execute('select 1 from sqlite_temp_master limit 1').fetchone(),'temporary_schema_forbidden')
 schema=[list(row) for row in db.execute("select type,name,tbl_name,rootpage,sql from main.sqlite_master where name not like 'sqlite_%' order by type,name")];tables={}
 for kind,name,*_ in schema:
  if kind!='table':continue
  require(re.fullmatch('[A-Za-z0-9_]+',name),'unknown_table_identifier');info=db.execute('pragma main.table_info('+name+')').fetchall();columns=[r[1] for r in info];require(all(re.fullmatch('[A-Za-z0-9_]+',col) for col in columns),'unknown_column_identifier')
  if 'id' not in columns:continue
  order=[r[1] for r in sorted(info,key=lambda row:row[5]) if r[5]] or columns
  rows=[list(row) for row in db.execute('select * from main.'+name+' where id=? order by '+','.join(order),(identifier,))];canonical(rows);tables[name]={'columns':columns,'rows':rows}
 return {'schema_version':db.execute('pragma main.schema_version').fetchone()[0],'schema':schema,'tables':tables}
def _rows(snapshot,table):
 v=snapshot['tables'].get(table);return [] if v is None else [dict(zip(v['columns'],row)) for row in v['rows']]
def _one(snapshot,table):
 rows=_rows(snapshot,table);require(len(rows)==1,'missing_exact_'+table+'_row');return rows[0]
def _owners(snapshot):
 for table,value in snapshot['tables'].items():
  for row in _rows(snapshot,table):
   for field,val in row.items():
    if field in ('owner_pid','worker_pid','pid') or field.endswith(('_owner_pid','_worker_pid')):require(val is None,'residual_or_unknown_owner:'+table+':'+field)
   state=row.get('state')
   if state is not None:
    require(isinstance(state,str),'untyped_stage_state:'+table);text=state.lower();require(text not in ('running','producing','repairing','converting','rendering','claimed') and not text.endswith(('_running','_producing','_repairing','_converting','_rendering')),'active_or_unknown_stage:'+table)

def _scope(snapshot,frozen):
 job=_one(snapshot,'jobs');require(tuple(job)==JOB_COLUMNS,'unknown_full_jobs_schema');outcome=_one(snapshot,'processing_outcomes_v2');require(tuple(outcome)==REGISTRY_COLUMNS,'unknown_full_registry_schema');require(job['state'] in IDLE and job['worker_pid'] is None,'job_not_idle');require(outcome['status']=='pending','outcome_not_pending');record=_json(job['output_record']);source=_json(job['input_record']);manifest=_json(job['input_manifest']);identifier=frozen['id'];fmt=frozen['format'];require(fmt in EXPECTED_COUNTS and job['format']==fmt==outcome['format']==source['format']==record['source_format']==manifest['source_format'],'original_format_mismatch');require(job['category'] in ('poster','scientific_diagram') and job['category']==outcome['category']==source['category']==record['category'],'original_category_mismatch');require(job['source']==source['source']==record['source'],'original_dataset_mismatch');require(job['id']==outcome['id']==source['pair_sha256']==record['id']==record['source_pair_sha256']==manifest['id']==identifier,'original_pair_identity_mismatch');require(record['format']=='drawio','candidate_not_native_drawio')
 for name in ('code','image'):
  old=frozen['source_'+name+'_sha256'];current=frozen[name+'_sha256'];require(digest(old) and digest(current),'invalid_frozen_pair_digests');require(outcome['source_'+name+'_hash']==source[name+'_sha256']==record['source_'+name+'_sha256']==manifest[name+'_sha256']==old,'current_original_'+name+'_hash_changed');require(record[name+'_sha256']==current,'current_candidate_'+name+'_hash_changed')
 require(all(type(manifest.get(k)) is int and manifest[k]>0 for k in ('width','height')),'unknown_original_dimensions');return job,record,source,manifest,outcome

def _audit(snapshot,frozen,config):
 options=[x for x in _rows(snapshot,'auto_quality_audits_v1') if (x['code_hash'],x['image_hash'])==(frozen['code_sha256'],frozen['image_sha256']) and x['state']!='stale_revision'];same=[x for x in options if x['policy']==frozen['qa_policy']];require(len(same)==1,'missing_frozen_current_pair_audit');row=same[0];require(row['state']=='repair_required' and sha(row['record'].encode())==frozen['audit_record_sha256'],'current_pair_audit_changed');q=_json(row['record']);require(q['id']==frozen['id'] and q['policy']==frozen['qa_policy'],'audit_scope_mismatch');require((q['input_code_sha256'],q['input_image_sha256'],q['source_code_sha256'],q['source_image_sha256'])==tuple(frozen[k] for k in ('code_sha256','image_sha256','source_code_sha256','source_image_sha256')),'audit_pair_hash_mismatch')
 rank={config['quality_policy']:3,'bounded_deterministic_font_text_layout_and_native_quality_v4:d2f5d9ada102865c':2,'source_execution_glyph_lineage_native_render_and_local_fidelity_v3:210bf4dbced804c5':1};require(frozen['qa_policy'] in rank,'unknown_predecessor_family');require(not any(rank.get(x['policy'],0)>rank[frozen['qa_policy']] for x in options),'new_successor_current_pair_audit_requires_new_scope');require(not any(x['state']=='accepted' for x in options),'already_accepted_current_pair_audit')
 checks=q['checks'];require(all(isinstance(checks.get(k),dict) for k in ('structure','resources','source','render','text_paint','fonts','visual')),'missing_complete_prerequisite_checks');require(checks['source'].get('supported') is True and checks['source'].get('ok') is True,'source_not_passed');require(type(checks['render'].get('strict_outside_page_pixels')) is int and checks['render']['strict_outside_page_pixels']==0,'strict_outside_page_not_zero');require(checks['fonts'].get('all_rendered_fonts_embedded') is True,'physical_fonts_not_embedded');visual=checks['visual'];require(visual.get('ok') is False and isinstance(visual.get('failures'),list) and visual['failures'] and set(visual['failures'])<=FAILURES,'not_bounded_visual_failure');require(q.get('failures') and all(isinstance(f,str) and f.startswith('raster_anomaly:') for f in q['failures']),'not_visual_only_observed_failure');return q

def _receipt_rows(snapshot,rule,frozen):
 rows=_rows(snapshot,rule['table']);key=rule['revision_key']
 if key:rows=[r for r in rows if r.get(key)==frozen['code_sha256']]
 if rows and 'image_hash' in rows[0]:rows=[r for r in rows if r['image_hash']==frozen['image_sha256']]
 return sorted(sha(canonical(r)) for r in rows)
def _routes(db,snapshot,frozen,record,cached,config):
 verdicts=[];rules={r['script']:r for r in cached['static_routes'] if frozen['format'] in r['formats']}
 for before in frozen['routes']:
  name=before['script'];verdict={'script':name,'frozen_state':before['state']}
  if name in rules:
   rule=rules[name];require('catalog_error' not in rule,'unknown_frozen_route_selector:'+name);require(before.get('actual_base_applicable') is False and before.get('actual_selector_eligible') is False,'nontrivial_terminal_rule_requires_separate_review:'+name)
   params=[*rule['bindings'],frozen['id']];base=bool(db.execute(rule['base_query'],params).fetchone());selected=bool(db.execute(rule['selector_query'],params).fetchone());require(not base and not selected,'deterministic_route_now_applicable:'+name);expected=sorted(x['row_sha256'] for x in before.get('current_input_receipts',[]));require(_receipt_rows(snapshot,rule,frozen)==expected,'frozen_route_receipt_set_changed:'+name);verdict.update(base_applicable=False,selector_eligible=False,state='unchanged_actual_SQL_not_applicable')
  elif name in ('auto_quality_glyph_alignment_batch_v3c.py','auto_quality_html_text_layout_batch_v5a.py'):
   # The target HTML8 has no local-text exception in ANY policy. This stronger
   # condition rejects the known QA4b/QA3 trigger gap, rather than hiding it.
   require(before['state']=='not_applicable_no_current_local_text_exception','unknown_frozen_html_trigger_state');require(not db.execute("select 1 from auto_quality_exceptions_v1 where id=? and code_hash=? and image_hash=? and state='pending' and reason like '%local_text_line_ssim%' limit 1",(frozen['id'],frozen['code_sha256'],frozen['image_sha256'])).fetchone(),'current_local_text_repair_or_trigger_gap_available');verdict['state']='no_current_local_text_exception_any_policy'
  elif name=='auto_quality_html_repair_batch_v3.py':
   require(before['state']=='not_applicable_current_source_inventory_passed_no_wrapped_source_exception','unknown_frozen_wrapped_trigger_state');sql="select 1 from auto_quality_exceptions_v1 e where e.id=? and e.code_hash=? and e.image_hash=? and e.state='pending' and e.route in ('source_geometry_or_harness','source_profile_extension') and "+config['html_wrapped_predicate']+' limit 1';require(not db.execute(sql,(frozen['id'],frozen['code_sha256'],frozen['image_sha256'])).fetchone(),'current_wrapped_source_repair_available');verdict['state']='no_current_wrapped_source_exception'
  elif name=='tikz_execution_candidate_batch_v1.py':
   eligible=(record.get('source_format')=='tikz' and all(record.get(k) for k in ('code_sha256','image_sha256','source_code_sha256','source_image_sha256','source_render_pdf','source_render_svg')) and not record.get('edges') and not record.get('native_page_padding') and not record.get('native_canvas_contract'));require(before['state']=='not_applicable_existing_semantic_edges_or_canvas_lineage' and not eligible,'pgf_source_execution_route_now_applicable_or_unknown');verdict['state']='unchanged_frozen_PGF_eligible_record_false'
  elif name=='native_source_font_profile_v4.py':require(frozen['format']=='drawio' and before['state']=='not_applicable_source_fixed_original_geometry_and_custom_fonts_already_passed','unknown_native_source_route');verdict['state']='no_registered_original_drawio_geometry_fitter_custom_fonts_passed'
  else:raise ValueError('unrecognized_frozen_route:'+name)
  verdicts.append(verdict)
 require(len(verdicts)==len(frozen['routes']) and verdicts,'incomplete_frozen_route_recheck');return verdicts

def capture(db,identifier,config):
 result={'eligible':False,'reason':'not_checked','id':identifier,'route_verdicts':[]};own=False
 try:
  cached=_checked_config(config);database=[row for row in db.execute('pragma database_list') if row[1]=='main'];require(len(database)==1 and database[0][2] and Path(database[0][2]).resolve()==(Path(config['root'])/config['database']).resolve(),'wrong_canonical_database');require(digest(identifier) and identifier in cached['targets'],'outside_frozen_finite_no_route_cohort');require(identifier not in cached['reserved'],'reserved_deterministic_research');require(identifier not in cached['authorized'],'reserved_authorized_model_case');frozen=cached['targets'][identifier]
  if not db.in_transaction:db.execute('begin');own=True
  snapshot=_snapshot(db,identifier);result.update(full_snapshot=snapshot,snapshot=snapshot);_owners(snapshot);job,record,source,manifest,outcome=_scope(snapshot,frozen);audit=_audit(snapshot,frozen,config);verdicts=_routes(db,snapshot,frozen,record,cached,config);require(_snapshot(db,identifier)==snapshot,'snapshot_changed_during_read');_checked_config(config)
  item=(identifier,job['state'],job['output_record'],job['input_record'],job['route']);scope={k:frozen[k] for k in ('id','format','source_code_sha256','source_image_sha256','code_sha256','image_sha256','qa_policy','audit_record_sha256')};scope['quality_policy']=config['quality_policy'];result.update(eligible=True,reason='current_exact_visual_failure_all_frozen_routes_still_inapplicable',route_verdicts=verdicts,job=job,record=record,source=source,input_manifest=manifest,outcome=outcome,item=item,scope_identity=scope,configuration_sha256=sha(canonical(config)),audit=audit,snapshot_sha256=sha(canonical(snapshot)),accepted=False,abandonment_proposal=False)
 except (Exception,) as error:result.update(eligible=False,reason=str(error),error_type=type(error).__name__)
 finally:
  if own and db.in_transaction:db.rollback()
 return result

def revalidate(db,context,config):
 if not isinstance(context,dict) or context.get('eligible') is not True:return {'eligible':False,'reason':'unverified_context'}
 current=capture(db,context.get('id'),config)
 if not current['eligible']:return current
 fields=('full_snapshot','scope_identity','configuration_sha256','route_verdicts','item','snapshot_sha256')
 for key in fields:
  if canonical(current.get(key))!=canonical(context.get(key)):return {**current,'eligible':False,'reason':'complete_context_CAS_changed:'+key}
 return current
