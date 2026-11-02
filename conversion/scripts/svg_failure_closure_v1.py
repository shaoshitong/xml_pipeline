"""Failure-only, read-only direct-SVG evidence and finite-program closure plans.

No publication, DB mutation, model, native rerender, or success equivalence.
Existing source checker runs unchanged; its full captured DOM is retained before
its historical early return/truncation. A second, frozen additive scene capture
records roles, complete path topology, marker/use/ancestor/style/viewport facts.
Only a source-role/feature failure plus an exhausted production route catalogue
can yield a proposal. The catalogue is extracted from actual producer SQL, not
the old whole-triangle research reservation. Uncertain admission stays pending.
"""
from __future__ import annotations
import ast,copy,datetime,hashlib,json,re,sqlite3,sys,time
from pathlib import Path

SCHEMA='svg_failure_only_finite_program_closure_v1'
IDLE=('rendered','needs_quality_repair','harness_review_pending','harness_rendered')
# script, stage table, revision key (None denotes unsafe legacy id-only ledger)
ROUTES=(
 ('svg_batch_v2.py',None,None),
 ('svg_v3_repair_batch.py','svg_v3_repairs',None),
 ('svg_v5_repair_batch.py','svg_v5_repairs',None),
 ('svg_v6_repair_batch.py','svg_v6_repairs',None),
 ('svg_v7_repair_batch.py','svg_v6_repairs',None),
 ('native_font_embedding_batch.py','native_font_embeddings','input_code_sha256'),
 ('native_font_embedding_v2_batch.py','native_font_embeddings_v2','input_code_sha256'),
 ('native_font_embedding_v3_batch.py','native_font_embeddings_v3','input_code_sha256'),
 ('native_font_embedding_v4_batch.py','native_font_embeddings_v4','input_code_sha256'),
 ('nonhtml_canvas_font_batch.py','nonhtml_canvas_font_repairs','input_code_sha256'),
 ('svg_fullname_font_batch.py','svg_fullname_font_repairs','input_code_sha256'),
 ('svg_fullname_font_batch_v2.py','svg_fullname_font_repairs_v2','input_code_sha256'),
 ('source_vee_batch.py','source_vee_scan','input_code_sha256'),
 ('auto_quality_font_repair.py','auto_quality_font_repairs_v2','input_hash'),
)
TERMINAL_STAGE_STATES={'published','published_pending_batch_qa','published_candidate','retained_prior_candidate','no_additional_vee','no_change_required','no_safe_improvement','no_matching_incremental_changes'}
RUNTIME_WORDS=('timeout','timed out','keyerror','filenotfound','missing file','no such file','browser has been closed','target closed','connection closed','out of memory','database is locked','canvas exceeds','8192','validation_error','assertionerror')
SEMANTIC_REASONS={
 'closed_path_requires_an_explicit_role_or_basic_geometry_proof',
 'open_source_path_requires_plot_or_relation_profile','thin_closed_paint_may_encode_an_untyped_connector',
 'generic_svg_arc_requires_actual_contour_error_bound','nonuniform_or_shear_stroke_not_in_base_mapping',
 'non_scaling_stroke_not_in_base_mapping','nonzero_dash_offset_not_in_base_mapping',
 'nondefault_source_internal_paint_order_not_in_mapping','material_source_native_miter_limit_difference',
 'rgba_alpha_not_in_base_native_paint_mapping','gradient_stop_rgba_alpha_not_in_base_mapping',
 'source_text_stroke_not_in_native_text_mapping','source_text_fill_alpha_not_in_native_text_mapping',
 'source_text_advance_css_requires_separate_profile','group_opacity_compositing_not_proven',
 'ancestor_blend_compositing_not_proven','source_use_instance_mapping_not_proven',
 'source_relations_require_bound_graph_and_native_marker_profile','unresolved_source_feature',
 'unmapped_source_viewport_background','unmapped_source_viewport_background_image',
 'unmapped_source_viewport_css_border','material_source_viewport_clipping_needs_an_explicit_mapping',
 'cubic_ellipse_contour_error_bound_exceeds_quarter_pixel','original_image_transform_aspect_or_type_unproven',
}
sha=lambda b:hashlib.sha256(b).hexdigest()
LOADED_MODULE_SHA256=sha(Path(__file__).read_bytes())
canonical=lambda x:(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def table_exists(db,table):return db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone() is not None
def literal_selector(path):
 """Read, never execute, the producer's actual admission SQL literal."""
 options=[]
 for node in ast.walk(ast.parse(path.read_text())):
  if not isinstance(node,ast.Constant) or not isinstance(node.value,str):continue
  value=node.value.strip()
  if not re.match(r'^select\b',value,re.I) or not re.search(r'\bfrom\s+jobs\b',value,re.I) or not re.search(r'\bwhere\b',value,re.I):continue
  if ('format' in value or 'route="svg_v2"' in value or "q.route='deterministic_font_embedding'" in value):options.append(value)
 require(len(options)==1,'ambiguous/missing actual selector: '+path.name)
 return options[0]
def strip_stage_guard(sql,table):
 if not table:return sql,[]
 removals=[]
 pattern=re.compile(r'\band\s+(?:not\s+exists\s*\(|(?:\w+\.)?id\s+not\s+in\s*\()',re.I)
 for match in pattern.finditer(sql):
  opening=sql.find('(',match.start());depth=0;quote=None;end=None
  for index in range(opening,len(sql)):
   ch=sql[index]
   if quote:
    if ch==quote:quote=None
   elif ch in "'\"":quote=ch
   elif ch=='(':depth+=1
   elif ch==')':
    depth-=1
    if depth==0:end=index+1;break
  if end and re.search(r'\b'+re.escape(table)+r'\b',sql[opening:end]):removals.append((match.start(),end,sql[match.start():end]))
 require(len(removals)==1,'missing/ambiguous stage guard '+str(table))
 for start,end,_ in reversed(removals):sql=sql[:start]+sql[end:]
 return sql,[entry[2] for entry in removals]
def per_id_query(selector):
 """Keep source WHERE/JOIN clauses exactly; project one constant for this ID."""
 from_match=re.search(r'\bfrom\s+jobs\b',selector,re.I);require(from_match is not None,'selector lacks jobs')
 tail=selector[from_match.start():];tail=re.split(r'\border\s+by\b|\blimit\s+\d+',tail,1,flags=re.I)[0].strip()
 alias_match=re.match(r'from\s+jobs\s+(\w+)',tail,re.I);alias=alias_match.group(1) if alias_match else None
 if alias and alias.lower() in ('where','join','left','inner'):alias=None
 return 'select 1 '+tail+' and '+(alias+'.' if alias else '')+'id=? limit 1'
def configuration(root):
 require(sha(Path(__file__).read_bytes())==LOADED_MODULE_SHA256,'collector changed after import')
 root=Path(root).resolve();work=root/'conversion';scripts=work/'scripts'
 if str(scripts) not in sys.path:sys.path.insert(0,str(scripts))
 prototype=work/'prototype'
 if str(prototype) not in sys.path:sys.path.append(str(prototype))
 import auto_quality_batch_v4b as qa
 owner=json.loads((work/'auto_quality_owner.json').read_text());require(owner['policy']==qa.POLICY,'active QA owner/pinned module policy differ')
 qa.ensure_pinned();pins={str((Path(k) if Path(k).is_absolute() else scripts/k).resolve()):v for k,v in qa.IMPLEMENTATION.items()}
 routes=[]
 for script,table,key in ROUTES:
  p=scripts/script;selector=literal_selector(p);base,guards=strip_stage_guard(selector,table)
  routes.append({'script':script,'table':table,'revision_key':key,'selector_sql':selector,'selector_query':per_id_query(selector),'base_query':per_id_query(base),'removed_stage_guards':guards,'selector_literal_sha256':sha(selector.encode())})
  pins[str(p)]=sha(p.read_bytes())
 # The bounded canvas worker builds its SQL dynamically. This exact same-ID,
 # same-pair projection preserves its trigger route and stage guard; no claim.
 canvas="select 1 from jobs j where j.state in ('rendered','needs_quality_repair','harness_review_pending') and j.worker_pid is null and exists(select 1 from auto_quality_exceptions_v1 e where e.id=j.id and e.route='deterministic_canvas_repair' and e.state='pending' and e.code_hash=json_extract(j.output_record,'$.code_sha256') and e.image_hash=json_extract(j.output_record,'$.image_sha256'))"
 routes.append({'script':'auto_quality_canvas_repair.py','table':'auto_quality_canvas_repairs_v1','revision_key':'code_hash','selector_sql':canvas,'base_query':per_id_query(canvas),'selector_query':per_id_query(canvas+" and not exists(select 1 from auto_quality_canvas_repairs_v1 t where t.id=j.id and t.code_hash=json_extract(j.output_record,'$.code_sha256') and t.image_hash=json_extract(j.output_record,'$.image_sha256'))"),'removed_stage_guards':[],'selector_projection':'same-ID actual canvas worker trigger, exact current pair, stage guard'})
 for name in ('svg_failure_closure_v1.py','svg_convert_v5.py','svg_convert_v6.py','svg_original_assets.py','svg_source_coverage.py','svg_fullname_fonts.py','scan_svg_fullnames.py','source_vee_incremental.py','portable_native_fonts_v2.py','native_padding_proof.py','repair_svg_fullname_font.py','repair_svg_fullname_font_v2.py','repair_source_vee_incremental.py','repair_nonhtml_canvas_font.py'):
  p=scripts/name;require(p.is_file(),'missing route/capture helper: '+name);pins[str(p)]=sha(p.read_bytes())
 handoff=work/'prototype/svg_source_profile_scope_v1/frozen_source_marker_handoff_v1.json';frozen=json.loads(handoff.read_text())
 require(frozen.get('status')=='frozen_research_handoff_not_production_candidate_worker','SVG research is not frozen')
 for name in ('auto_quality_svg_closed_scene_v1.py','svg_source_scene_dom_v1.py','svg_dom_source_scene_v1.js'):
  p=prototype/name;expected=frozen['implementation_sha256'].get(str(p));require(expected and sha(p.read_bytes())==expected,'frozen scene extractor/checker differs');pins[str(p)]=expected
 pins[str(handoff)]=sha(handoff.read_bytes())
 policy_path=work/'model_usage_policy_v2.json';pins[str(policy_path)]=sha(policy_path.read_bytes())
 research=[]
 for relative in ('prototype/svg_source_profile_scope_v1/closed_scene_cohort_v1/cohort_report.json','prototype/svg_source_profile_scope_v1/triangle_marker_bound_family_cohort_v1/triangle_rule_report.json','prototype/svg_source_profile_scope_v1/triangle_marker_bound_family_cohort_v1/triangle_native_smoke_report.json'):
  p=work/relative
  if p.exists():pins[str(p)]=sha(p.read_bytes());research.append({'file':str(p),'sha256':pins[str(p)]})
 require(len(research)==3,'missing bounded SVG research freeze receipts')
 result={'root':str(root),'policy':qa.POLICY,'owner_policy_path':str(work/'auto_quality_owner.json'),'evidence_root':str(work/'prototype/svg_failure_closure_v1'),'pins':pins,'routes':routes,'research':{'production_route':False,'status':'frozen_no_production_marker_or_closed_scene_producer','authority':'parent task explicitly freezes SVG research; pinned bounded cohort and native-smoke receipts','evidence':research}}
 result['catalog_sha256']=sha(canonical({'policy':result['policy'],'pins':pins,'routes':routes,'research':result['research']}));return result
def snapshot(db,identifier):
 result={}
 for table, in db.execute("select name from sqlite_master where type='table' order by name"):
  if not re.fullmatch('[A-Za-z0-9_]+',table):continue
  columns=[r[1] for r in db.execute('pragma table_info('+table+')')]
  if 'id' not in columns:continue
  values=db.execute('select * from '+table+' where id=?',(identifier,)).fetchall()
  if not values:continue
  result[table]={'columns':columns,'count':len(values),'rows_sha256':sha(canonical(sorted((list(x) for x in values),key=lambda v:canonical(v))))}
 return result
def ensure_pins(config):
 for p,h in config['pins'].items():require(sha(Path(p).read_bytes())==h,'pinned program/resource changed: '+p)
 require(config['research']['production_route'] is False,'research must not masquerade as completed production route')
 if config.get('owner_policy_path'):require(json.loads(Path(config['owner_policy_path']).read_text()).get('policy')==config['policy'],'active QA source policy changed')
def busy_rows(db,identifier):
 found=[]
 for table, in db.execute("select name from sqlite_master where type='table'"):
  if not re.fullmatch('[A-Za-z0-9_]+',table):continue
  columns=[r[1] for r in db.execute('pragma table_info('+table+')')]
  if not {'id','state'}<=set(columns):continue
  for row in db.execute('select * from '+table+' where id=?',(identifier,)):
   x=dict(zip(columns,row));state=str(x.get('state',''))
   if state=='running' or any(state.endswith(suffix) for suffix in ('_producing','_repairing','_converting','_rendering')):found.append({'table':table,'state':state,'owner_pid':x.get('owner_pid') or x.get('worker_pid')})
 return found
def current_audit(db,identifier,record):
 options=[]
 for ch,ih,policy,state,raw,stamp in db.execute('select code_hash,image_hash,policy,state,record,updated_at from auto_quality_audits_v1 where id=?',(identifier,)):
  if (ch,ih)!=(record['code_sha256'],record['image_sha256']) or state!='repair_required':continue
  a=json.loads(raw);source=(a.get('checks') or {}).get('source') or {}
  if source.get('ok') is not False or not source.get('failures'):continue
  require((a.get('source_code_sha256'),a.get('source_image_sha256'))==(record['source_code_sha256'],record['source_image_sha256']),'historical source audit identity differs')
  options.append({'policy':policy,'updated_at':stamp,'record_sha256':sha(raw.encode()),'source':source,'failures':a.get('failures')})
 require(options,'no exact-current-pair source failure audit');return max(options,key=lambda x:x['updated_at'])
def route_verdicts(db,identifier,record,config):
 verdicts=[]
 for rule in config['routes']:
  item={k:rule[k] for k in ('script','table','revision_key')};table=rule['table'];key=rule['revision_key']
  try:
   base=bool(db.execute(rule['base_query'],(identifier,)).fetchone());eligible=bool(db.execute(rule['selector_query'],(identifier,)).fetchone())
   item.update(base_applicable=base,actual_selector_eligible=eligible)
   if not base:item.update(state='not_applicable',reason='actual_pinned_producer_SQL_prerequisites_false')
   elif eligible:item.update(state='available_unattempted',reason='actual_pinned_producer_SQL_selects_this_current_revision')
   elif not table or not table_exists(db,table):item.update(state='blocked',reason='applicable_route_has_no_stage_schema')
   elif key is None:item.update(state='blocked',reason='legacy_id_only_stage_is_not_a_current_revision_terminal_receipt')
   else:
    columns=[r[1] for r in db.execute('pragma table_info('+table+')')];q='select * from '+table+' where id=? and '+key+'=?';args=[identifier,record['code_sha256']]
    if 'image_hash' in columns:q+=' and image_hash=?';args.append(record['image_sha256'])
    receipts=[dict(zip(columns,x)) for x in db.execute(q,args)]
    item['stage_receipts']=[{'state':x.get('state'),'updated_at':x.get('updated_at'),'row_sha256':sha(canonical(x))} for x in receipts]
    terminal=bool(receipts) and all(x.get('state') in TERMINAL_STAGE_STATES and not any(word in str(x.get('record','')).lower() for word in RUNTIME_WORDS) for x in receipts)
    item.update(state='exhausted_terminal' if terminal else 'blocked',reason='exact_current_revision_terminal_receipt' if terminal else 'missing_running_runtime_or_unclassified_current_revision_receipt')
  except (sqlite3.Error,ValueError) as error:item.update(state='blocked',reason='route_selector_or_schema_not_proven',error=repr(error))
  verdicts.append(item)
 return verdicts
def source_reasons(result):return {x.get('reason') if isinstance(x,dict) else str(x) for x in result.get('failures',[])}
def validation_or_capture_reason(reason):
 value=str(reason)
 return value.endswith(('_validation_error','_admission_error','_parse_failed','_expansion_failed','_capture_failed')) or value in {'source_computed_style_metadata_missing','source_viewport_css_paint_not_captured'}
def conversion_metadata_blockers(record,base_dom):
 method=str(record.get('conversion_method',''));stats=record.get('svg_conversion') or {};groups=(stats.get('counts') or {}).get('node_groups');actual=len(base_dom.get('nodes',{}));result=[]
 if method.startswith('svg_element_native'):
  if groups is None or groups!=actual:result.append('source_node_group_metadata_missing_or_differs_from_fresh_source')
  if method=='svg_element_native_stencils_editable_text_and_connectors_v1' and actual:result.append('legacy_v1_named_graph_has_known_background_order_migration')
  if method in ('svg_element_native_stencils_editable_text_and_connectors_v2','svg_element_native_graphviz_arrows_and_edge_labels_v3') and not stats.get('converter_version'):result.append('known_converter_missing_version_required_by_production_font_route')
 return result
def nested_evidence_errors(value):
 if isinstance(value,dict):
  if value.get('error') or any(token in str(value.get('reason','')).lower() for token in ('validation_error','parse_failed','expansion_failed','capture_failed')):return True
  return any(nested_evidence_errors(v) for v in value.values())
 if isinstance(value,list):return any(nested_evidence_errors(v) for v in value)
 return False
def closure_decision(fresh,scene,dom,routes,blockers):
 reasons=[]
 if fresh.get('ok'):reasons.append('fresh_source_profile_passes_no_failure_termination')
 if fresh.get('supported') is not False and 'unsupported_fresh_source_features' not in source_reasons(fresh):reasons.append('ordinary_candidate_coverage_error_is_not_source_construct_unsupported')
 if any(validation_or_capture_reason(x) for x in source_reasons(fresh)):reasons.append('source_validator_runtime_or_metadata_error')
 if dom.get('sceneCapture',{}).get('completeOfflineSource') is not True:reasons.append('source_capture_not_complete_offline')
 if scene.get('supported') or not scene.get('failures'):reasons.append('bounded_scene_rule_supports_source_or_no_complete_construct_failure')
 semantic=source_reasons(scene)&SEMANTIC_REASONS
 if not semantic:reasons.append('no_allowlisted_current_program_source_role_or_feature_failure')
 if any(validation_or_capture_reason(x) for x in source_reasons(scene)):reasons.append('scene_capture_or_validation_or_metadata_error')
 if nested_evidence_errors(scene) or nested_evidence_errors(dom.get('sceneIssues',[])):reasons.append('nested_scene_capture_or_validation_error')
 if any(x.get('state') not in ('not_applicable','exhausted_terminal') for x in routes):reasons.append('applicable_production_route_not_exhausted')
 reasons+=list(blockers)
 return {'proposal':not reasons,'reason':'current_frozen_program_source_role_or_feature_unverifiable_all_production_routes_exhausted' if not reasons else 'retain_pending','deferred_reasons':sorted(set(reasons)),'source_construct_classes':sorted(semantic),'scope':'current finite verified program; never claims drawio is intrinsically incapable'}
def capture_failure(record,xml):
 import auto_quality_source_vector_v2 as prior
 import auto_quality_svg_closed_scene_v1 as closed
 import svg_source_scene_dom_v1 as scene_module
 captured=[];original=prior._capture
 def retain(*args,**kwargs):
  dom,served=original(*args,**kwargs);captured.append(copy.deepcopy(dom));return dom,served
 prior._capture=retain
 try:fresh=prior.check_vector_profile(record,xml)
 finally:prior._capture=original
 require(len(captured)==1,'fresh frozen source checker did not perform exactly one complete capture')
 try:
  scene=closed.capture_closed_scene(record);admission=closed.check_scene_coverage(scene,xml)
 finally:scene_module.close_worker_runtime()
 # Record the full rejected object inventory using the frozen predicate, rather
 # than its old uncertain[:30] preview. This does not change its verdict.
 uncertain=[]
 for obj in captured[0].get('objects',[]):
  marker=obj.get('edge') or obj.get('markerOwner') or any(obj.get(k,'none')!='none' for k in ('markerStart','markerEnd'))
  shape=obj.get('type')=='shape';b=obj.get('bbox',{});thin=shape and max(b.get('w',0),b.get('h',0))/max(.01,min(b.get('w',0),b.get('h',0)))>12 and min(b.get('w',0),b.get('h',0))<4
  if marker or shape and obj.get('tag') not in ('rect','circle','ellipse') or thin:uncertain.append(obj['id'])
 return {'fresh_source_checker':fresh,'base_dom':captured[0],'scene_dom':scene,'scene_checker':admission,'full_uncertain_object_ids':uncertain,'full_base_issues':captured[0].get('issues',[]),'full_scene_issues':scene.get('issues',[]),'full_scene_additional_issues':scene.get('sceneIssues',[])}
def prepare(db,identifier,config,work,capture=capture_failure):
 """Write one new failure sidecar and optional proposal; never apply anything."""
 require(not db.in_transaction,'prepare requires an autocommit read-only connection')
 ensure_pins(config);root=Path(config['root']).resolve();folder=Path(work).resolve()
 require(folder.is_relative_to(Path(config.get('evidence_root',root)).resolve()),'evidence path outside isolated prototype root')
 folder.mkdir(parents=True,exist_ok=False);started=time.monotonic()
 report={'schema':SCHEMA,'id':identifier,'at':now(),'catalog_sha256':config['catalog_sha256'],'policy':config['policy'],'read_only':True,'accepted':False,'models_called':0,'proposal':False}
 files={}
 def save(name,data):
  p=folder/name;p.write_bytes(data);files[str(p)]={'sha256':sha(data),'bytes':len(data)}
 try:
  db.execute('BEGIN')
  before=snapshot(db,identifier);row=db.execute('select format,state,worker_pid,input_record,output_record,input_manifest from jobs where id=?',(identifier,)).fetchone();require(row is not None,'unknown id')
  fmt,state,owner,inp,raw,manifest=row;require(fmt=='svg' and state in IDLE and owner is None and raw,'source not an idle completed direct SVG candidate')
  r=json.loads(raw);src=json.loads(inp);outcome=db.execute('select category,format,source_code_hash,source_image_hash,status from processing_outcomes_v2 where id=?',(identifier,)).fetchone()
  require(outcome and outcome[1]=='svg' and outcome[4]=='pending','source outcome not pending SVG')
  require(r.get('source_format')=='svg' and src.get('format','svg')=='svg','current metadata/source format is not the authoritative direct SVG format')
  require((r['id'],r['source_pair_sha256'])==(identifier,identifier),'current output sourcepair mismatch')
  require((r['source_code_sha256'],r['source_image_sha256'])==(src['code_sha256'],src['image_sha256'])==outcome[2:4],'source/code/reference/registry identity mismatch')
  require(not busy_rows(db,identifier),'active or unresolved stage/model owner')
  historical=current_audit(db,identifier,r);routes=route_verdicts(db,identifier,r,config)
  for loc,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
   path=(root/r[loc]).resolve();require(path.is_relative_to(root/'clean'),'resource outside clean: '+loc);data=path.read_bytes();require(sha(data)==r[digest],'current payload hash differs: '+loc);files[str(path)]={'sha256':r[digest],'bytes':len(data)}
  xml=(root/r['code_file']).read_text();reference=(root/r['original_reference']).read_bytes()
  from auto_quality_common import resource_checks
  resource_proof=resource_checks(root,r,xml,reference)
  for rel in resource_proof.get('verified_files',[]):
   path=(root/rel).resolve();require(path.is_relative_to(root/'clean'),'verified shared resource outside clean');data=path.read_bytes();files[str(path)]={'sha256':sha(data),'bytes':len(data)}
  save('current.drawio',xml.encode());save('original_source.svg',(root/r['original_source_code']).read_bytes());save('current_record.json',raw.encode());save('input_record.json',inp.encode())
  db.rollback() # Release the coherent admission snapshot before browser work.
  captured=capture(r,xml)
  for key,value in captured.items():save(key+'.json',canonical(value))
  blockers=conversion_metadata_blockers(r,captured['base_dom'])
  # Missing source-font discovery is a recoverable pipeline metadata issue.
  converter=(r.get('svg_conversion') or {}).get('converter_version')
  if converter in ('svg_native_v2_group_paint_order','svg_native_v3_group_paint_order_and_native_arrows') and not r.get('native_source_font_repair') and (r.get('native_font_validation') or {}).get('output_code_sha256')==r['code_sha256']:
   if not table_exists(db,'svg_fullname_font_sources'):blockers.append('font_fullname_source_scan_schema_missing')
   else:
    font=db.execute('select source_sha256,error from svg_fullname_font_sources where id=?',(identifier,)).fetchone()
    if not font or font[0]!=r['source_code_sha256'] or font[1]:blockers.append('font_fullname_source_scan_missing_stale_or_error')
  decision=closure_decision(captured['fresh_source_checker'],captured['scene_checker'],captured['scene_dom'],routes,blockers)
  report.update(decision,source_code_sha256=r['source_code_sha256'],source_image_sha256=r['source_image_sha256'],code_sha256=r['code_sha256'],image_sha256=r['image_sha256'],input_record_sha256=sha(inp.encode()),output_record_sha256=sha(raw.encode()),historical_exact_current_pair_failure=historical,route_verdicts=routes,research_reservation_replaced=config['research'],resources=resource_proof,source_object_count=len(captured['base_dom'].get('objects',[])),scene_object_count=len(captured['scene_dom'].get('objects',[])),full_uncertain_objects=len(captured['full_uncertain_object_ids']),full_source_issue_count=len(captured['full_base_issues']),full_scene_issue_count=len(captured['full_scene_issues'])+len(captured['full_scene_additional_issues']),snapshot=before,files=files,pins=config['pins'])
  ensure_pins(config)
  db.execute('BEGIN') # A fresh coherent snapshot, never the old read view.
  require(snapshot(db,identifier)==before,'current full table snapshot changed during fresh capture')
  for p,v in files.items():require(sha(Path(p).read_bytes())==v['sha256'],'source/resource/sidecar changed after fresh capture: '+p)
  db.rollback()
 except Exception as exc:
  if db.in_transaction:db.rollback()
  report.update(proposal=False,reason='retain_pending',deferred_reasons=['evidence_or_snapshot_or_resource_not_complete'],error=repr(exc))
 report['seconds']=round(time.monotonic()-started,3);report['evidence_directory']=str(folder)
 report['certificate_sha256']=sha(canonical(report));(folder/'report.json').write_bytes(canonical(report));return report
def revalidate(db,plan,config,check_files=True):
 """Read-only immediate pre-writer CAS check. Does not claim or publish."""
 try:
  require(plan.get('schema')==SCHEMA and plan.get('proposal') is True,'not a closure proposal')
  body={k:v for k,v in plan.items() if k!='certificate_sha256'};require(sha(canonical(body))==plan.get('certificate_sha256'),'closure certificate damaged or edited')
  require(plan.get('catalog_sha256')==config['catalog_sha256'],'different route catalogue')
  ensure_pins(config);require(plan.get('pins')==config['pins'],'proposal pin set changed')
  require(snapshot(db,plan['id'])==plan['snapshot'],'full job/outcome/QA/stage/queue snapshot stale')
  if check_files:
   for p,x in plan['files'].items():require(sha(Path(p).read_bytes())==x['sha256'],'source/resource/evidence changed: '+p)
  folder=Path(plan['evidence_directory']);fresh=json.loads((folder/'fresh_source_checker.json').read_text());scene=json.loads((folder/'scene_checker.json').read_text());dom=json.loads((folder/'scene_dom.json').read_text())
  require(all(str(folder/name) in plan['files'] for name in ('current.drawio','original_source.svg','fresh_source_checker.json','scene_checker.json','scene_dom.json')),'incomplete evidence inventory')
  r=json.loads(db.execute('select output_record from jobs where id=?',(plan['id'],)).fetchone()[0]);capture=dom.get('sceneCapture',{})
  require((capture.get('recordId'),capture.get('recordCodeSha256'),capture.get('sourceCodeSha256'),capture.get('sourceImageSha256'))==(plan['id'],r['code_sha256'],r['source_code_sha256'],r['source_image_sha256']),'scene evidence identity differs')
  routes=route_verdicts(db,plan['id'],r,config);require(routes==plan['route_verdicts'],'production route applicability changed')
  require(closure_decision(fresh,scene,dom,routes,[])['proposal'],'saved source or routes no longer prove closure')
  return {'current':True,'id':plan['id']}
 except Exception as exc:return {'current':False,'id':plan.get('id'),'reason':repr(exc)}
