"""Complete source-only SVG original-surface-contact scope with global identity and family closure.

Unknown static families remain in the applicable bulk population. Only the declared SOURCE Cairo surface-contact preprocessing may render.
No candidate/reference scores or failure reasons choose applicability/cohort.
"""
import argparse,collections,hashlib,importlib,json,sqlite3,sys
from compiler_typed_runtime_failure_v1 import is_infrastructure
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
SEED='svg_source_surface_unseen100_20261101_v1';SCOPE=26754
FRONTEND='compiler_svg_source_viewport_frontend_v1'
DEVELOPMENT=(R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl',R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl')
PREFLIGHT=R/'release/compiler_iterations/controls/svg_source_surface_controls_20261101_v1/case_preflight.json'
raw=lambda x:(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
sha=lambda b:hashlib.sha256(b).hexdigest()
def rows(path):
 with Path(path).open()as f:
  for line in f:
   if line.strip():yield json.loads(line)

def checked_original_code(locator,digest,data_root=R):
 root=Path(data_root).resolve(strict=True);p=(root/locator).resolve(strict=True)
 if not p.is_relative_to(root):raise ValueError('original_source_outside_registered_root')
 data=p.read_bytes()
 if sha(data)!=digest:raise ValueError('original_source_hash_changed')
 return data.decode('utf-8-sig')

def family(code):
 from compiler_svg_general_unseen_pool_v3 import family as source_xml_family
 return source_xml_family(code)

def identity_overlap(identifier,source,dev_ids,code_hashes,image_hashes):
 return identifier in dev_ids or source['code_sha256']in code_hashes or source['image_sha256']in image_hashes

def request_from_job(job,source,unit):
 canonical=json.loads(job[4])
 if canonical!=source or canonical.get('pair_sha256')!=job[0]:raise ValueError('worker_request_requires_complete_canonical_source')
 previous=json.loads(job[9])if job[9]else{}
 return dict(id=job[0],source=canonical,compiler_unit=unit,source_record_sha256=sha((job[9]or'').encode()),baseline_code_sha256=previous.get('code_sha256'),baseline_image_sha256=previous.get('image_sha256'))


def independent_components(records,development,codes,images,excluded):
 parents=list(range(len(records)));seen={}
 def find(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 for i,item in enumerate(records):
  for key in item['keys']:
   if key in seen:
    a,b=find(i),find(seen[key]);parents[max(a,b)]=min(a,b)
   else:seen[key]=i
 groups=collections.defaultdict(list)
 for i in range(len(records)):groups[find(i)].append(records[i])
 eligible=[];counts=collections.Counter()
 for members in groups.values():
  keys=set().union(*(x['keys']for x in members));pending=[x for x in members if x['pending']]
  contaminated=bool(keys&excluded)or any(identity_overlap(x['request']['id'],x['request']['source'],development,codes,images)for x in members)
  unknown=any(not x['known']for x in members);cluster='svg_source_surface_observed_source_component_v1:'+sha(raw(sorted(keys)));counts['observed_components']+=1
  if contaminated:counts['development_or_reserved_connected_components']+=1
  if unknown:counts['unknown_family_components']+=1
  for offset,item in enumerate(sorted(pending,key=lambda x:sha(raw([SEED,x['request']['id']])))):
   audit=item['audit'];audit.update(source_component=cluster,component_members=len(members))
   if contaminated:audit['disposition']='development_or_reserved_identity_family_or_provenance_overlap'
   elif unknown:audit['disposition']='population_unknown_family_component_not_independent'
   elif offset:audit['disposition']='duplicate_validation_source_component'
   else:
    audit['disposition']='eligible_fresh_complete_static_source_component';eligible.append({**item['request'],'audit_cluster':cluster,'cluster':cluster,'cluster_keys':sorted(keys|{cluster})})
 eligible.sort(key=lambda x:sha(raw([SEED,x['id']])));return eligible,dict(counts)

def supplementary_qualified(identifiers=None):
 """All authoritative QL versions plus controls, with five clean hashes checked."""
 from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
 from compiler_iteration_inventory_v1 import read_scope,check_manifest
 wanted=None if identifiers is None else set(identifiers);result=ledger_manifests(root=R,identifiers=wanted)
 for path in sorted((R/'release/compiler_iterations/controls').glob('*/qualified.jsonl')):
  result.extend(x for x in rows(path)if wanted is None or x['id']in wanted)
 source_scope,_=read_scope(R);cache={};verified=[]
 for row in result:
  if row['id']not in source_scope:continue
  try:check_manifest(R,row['id'],source_scope[row['id']],row,cache)
  except Exception as error:raise RuntimeError('infrastructure_qualified_ledger_asset_or_source_conflict:'+row['id']+':'+str(error))from error
  verified.append(row)
 return verified

def development_inputs():return list(DEVELOPMENT)+sorted((R/'release/compiler_iterations/development_seen_v1').glob('*.jsonl'))

def current_selected_exclusion_guard(selected):
 """Refresh global dev/registry aliases immediately before reservation."""
 import compiler_validation_cluster_audit_v1 as provenance
 inputs=development_inputs();items=[x for p in inputs for x in rows(p)];ids={x['id']for x in items};keys=set()
 for x in items:
  code=x.get('source_code_sha256')or x.get('code_sha256');image=x.get('source_image_sha256')or x.get('image_sha256')
  if code:keys.add('exact_original_code:'+code)
  if image:keys.add('exact_original_image:'+image)
  keys.update(x.get('cluster_keys')or [])
 with sqlite3.connect('file:'+str(R/'release/compiler_v1/validation_registry.sqlite')+'?mode=ro',uri=True,timeout=30)as d:
  d.execute('begin');reserved=set(d.execute('select kind,value from reservation_keys'))
 ids.update(v for k,v in reserved if k=='id')
 for kind,value in reserved:
  if kind=='code':keys.add('exact_original_code:'+value)
  elif kind=='image':keys.add('exact_original_image:'+value)
  elif kind in ('audit_cluster','hard_cluster'):keys.add(value)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as d:
  for id in sorted(ids):
   row=d.execute('select input_record,input_manifest from jobs where id=?',(id,)).fetchone()
   if not row:continue
   original=json.loads(row[0]);keys.update(('exact_original_code:'+original['code_sha256'],'exact_original_image:'+original['image_sha256']));keys.update(provenance.provenance(original,original['source']))
   if original['format']=='svg':
    try:
     manifest=json.loads(row[1]);data=(R/manifest['source_code']).read_bytes()
     if sha(data)!=original['code_sha256']:raise ValueError('development_source_hash_changed')
     f,_=family(data.decode('utf-8-sig'));keys.add(f)
    except ValueError:pass
 qualified_now={x['id']for x in supplementary_qualified(identifiers={x['id']for x in selected})}
 for x in selected:
  if x['id']in qualified_now:raise ValueError('selected_source_became_qualified_after_source_audit')
  if x['id']in ids or set(x['cluster_keys'])&keys:raise ValueError('selected_source_became_development_or_reserved_before_seal')
 return {'inputs':{str(p.absolute()):sha(p.read_bytes())for p in inputs},'global_development_reserved_ids':len(ids),'exclusion_keys':len(keys),'registry_sha256':sha(raw(sorted(reserved))),'selected_current_overlap':0,'source_only':True}

def prepare(output,inventory):
 import compiler_iteration_inventory_v1 as inventory_method
 import compiler_validation_cluster_audit_v1 as provenance
 import compiler_svg_source_viewport_iteration_program_v1 as program
 compiler=importlib.import_module(FRONTEND);config=compiler.configuration();unit=compiler.UNITS['svg']
 output=Path(output).resolve();inventory=Path(inventory).resolve(strict=True)
 if not output.is_relative_to((R/'release/compiler_iterations/source_pools').resolve()):raise ValueError('source_pool_outside_owner')
 controls=program.control_bundle(compiler);program.check_controls(controls)
 from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot as active_snapshot
 active=active_snapshot();active_ids=set(active['active'])
 full_scope,scope_info=inventory_method.read_scope(R);scope={i:x for i,x in full_scope.items()if x['format']=='svg'}
 if len(scope)!=SCOPE:raise ValueError('original_SVG_scope_not26754')
 info=json.loads((inventory/'summary.json').read_bytes());qualified=inventory/'qualified.jsonl'
 if info.get('accepted_integrity_errors')or sha(qualified.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('verified_qualified_inventory_changed')
 accepted={r['id']:r for r in rows(qualified)if r['id']in scope}
 for r in supplementary_qualified(identifiers=set(scope)):
  if r['id']in scope:accepted[r['id']]=r
 hashes={}
 for id,m in accepted.items():inventory_method.check_manifest(R,id,scope[id],m,hashes)
 dev_inputs=development_inputs();dev_rows=[x for p in dev_inputs for x in rows(p)];development={x['id']for x in dev_rows};development.update(x['id']for x in controls['positive_cases']);development.update(x['id']for x in controls['negative_cases'])
 typed_path=W/'compiler_tikz_free_paths_v1/development/typed_graph_inventory.json';typed=json.loads(typed_path.read_bytes());development.update(x['id']for x in typed['rows'])
 preflight=json.loads(PREFLIGHT.read_bytes());prior_normal={x['id']for x in preflight['cases']if x.get('normal_frontend_attempt')is True}
 if preflight.get('all_expected_outcomes')is not True:raise ValueError('exact_iteration_case_preflight_not_passed')
 development.update(prior_normal)
 with sqlite3.connect('file:'+str(R/'release/compiler_v1/validation_registry.sqlite')+'?mode=ro',uri=True,timeout=30)as d:
  d.execute('begin');registry_keys=set(d.execute('select kind,value from reservation_keys'))
 development.update(v for k,v in registry_keys if k=='id');codes={v for k,v in registry_keys if k=='code'};images={v for k,v in registry_keys if k=='image'};excluded={v for k,v in registry_keys if k in ('audit_cluster','hard_cluster')}
 for x in dev_rows:
  if x.get('source_code_sha256')or x.get('code_sha256'):codes.add(x.get('source_code_sha256')or x['code_sha256'])
  if x.get('source_image_sha256')or x.get('image_sha256'):images.add(x.get('source_image_sha256')or x['image_sha256'])
  excluded.update(x.get('cluster_keys')or [])
 db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);columns=('id','category','format','source','input_record','input_manifest');counters=collections.Counter();family_cache={}
 def load(id,code=False):
  row=db.execute('select '+','.join(columns)+' from jobs where id=?',(id,)).fetchone()
  if not row:raise ValueError('canonical_original_job_missing')
  job=dict(zip(columns,row));s=json.loads(job['input_record'])
  if (s['pair_sha256'],s['category'],s['format'],s['source'])!=(id,job['category'],job['format'],job['source']):raise ValueError('canonical_source_identity_changed')
  if id in scope and any(scope[id][k]!=s[k]for k in ('category','format','source','code_sha256','image_sha256')):raise ValueError('full_scope_original_identity_changed')
  text=None
  if code:
   manifest=json.loads(job['input_manifest']);text=checked_original_code(manifest['source_code'],s['code_sha256'])
  return job,s,text
 def parse(text):
  key=sha(text.encode())
  if key not in family_cache:
   try:family_cache[key]=(True,family(text))
   except Exception as e:family_cache[key]=(False,str(e)[:1000])
  ok,value=family_cache[key]
  if not ok:raise ValueError(value)
  return value
 try:
  for id in sorted(development):
   try:
    job,s,text=load(id,False);codes.add(s['code_sha256']);images.add(s['image_sha256']);excluded.update(provenance.provenance(s,s['source']));counters['global_dev_reserved_originals_loaded']+=1
    if job['format']=='svg':
     _,_,text=load(id,True);f,_=parse(text);excluded.add(f);counters['same_format_exclusion_complete_family_parsed']+=1
   except Exception as e:counters['exclusion_source_family_unknown:'+type(e).__name__]+=1
  output.mkdir(parents=True,exist_ok=False);audits=[];records=[];population=[]
  for id in sorted(scope,key=lambda i:sha(raw([SEED,i]))):
   audit={'id':id,'source_format':'svg','handler_applicable':False}
   try:
    job,s,text=load(id,True);support=compiler.static_support(job);
    if support.get('infrastructure_failure')is True:raise RuntimeError('infrastructure_source_only_support_runtime:'+str(support.get('reasons')))
    keys={'exact_original_code:'+s['code_sha256'],'exact_original_image:'+s['image_sha256']}|set(provenance.provenance(s,s['source']));known=False
    full_job=db.execute('select * from jobs where id=?',(id,)).fetchone();request=request_from_job(full_job,s,unit)
    try:f,evidence=parse(text);keys.add(f);known=True;audit.update(family=f,source_evidence=evidence)
    except Exception as e:audit['family_unknown_reason']=str(e)[:700]
    audit.update(source_code_sha256=s['code_sha256'],source_image_sha256=s['image_sha256'],handler_applicable=support['supported'])
    if id in accepted:audit['disposition']='already_qualified_preserved'
    elif not support['supported']:audit.update(disposition='pending_outside_frozen_frontend_source_profile',reason=support['reasons'])
    elif id in prior_normal:audit['disposition']='same_frontend_preflight_already_attempted_pending_next_repair'
    elif id in active_ids:audit['disposition']='deferred_birth_verified_active_conversion_overlap'
    else:audit['disposition']='source_component_inventory_pending';population.append(request)
    records.append(dict(audit=audit,request=request,keys=keys,known=known,pending=audit['disposition']=='source_component_inventory_pending'))
   except Exception as e:
    if is_infrastructure(exception=e):raise
    audit.update(disposition='pending_source_inventory_diagnosis',reason=str(e)[:1000])
   audits.append(audit)
  eligible,components=independent_components(records,development,codes,images,excluded);selected=eligible[:100]
  for seq,item in enumerate(selected,1):
   item['seq']=seq
  for x in audits:counters[x['disposition']]+=1
  for name,items in (('source_audit.jsonl',audits),('supported_population.jsonl',population),('selected.jsonl',selected),('preserved_qualified.jsonl',[accepted[i]for i in sorted(accepted)])):(output/name).write_bytes(b''.join(raw(x)for x in items))
  (output/'live_overlap_snapshot.json').write_bytes(raw(active))
  methods=[Path(__file__),W/'scripts/compiler_svg_general_unseen_pool_v3.py',Path(inventory_method.__file__),Path(provenance.__file__),W/'scripts/compiler_types_source_ir_v1.py',W/'scripts/compiler_typed_runtime_failure_v1.py',typed_path,PREFLIGHT,W/'scripts/compiler_mermaid_alpha_qualifications_v2.py',W/'scripts/compiler_mermaid_alpha_iteration_overlap_v2.py']+dev_inputs
  summary={'schema':'compiler_svg_source_viewport_unseen_source_pool_v1','seed':SEED,'scope':SCOPE,'full_scope_manifest':scope_info,'compiler_unit':unit,'frontend_module':FRONTEND,'frozen_implementation':config,'method_pins':{str(p.absolute()):sha(p.read_bytes())for p in methods},'controls_proof':controls['definition'],'source_only':True,'conversion_or_rendering':False,'source_only_recorded_Cairo_rendering':True,'model_calls':0,'development_inputs':{str(p):sha(p.read_bytes())for p in dev_inputs},'development_ids_all_formats':len(development),'global_two_development_inputs_included':True,'additional_typed_development':{'file':str(typed_path),'sha256':sha(typed_path.read_bytes())},'registry_keys_snapshot_sha256':sha(raw(sorted(registry_keys))),'registry_modified':False,'counters':{**dict(counters),'supported_remaining_population':len(population)},'source_component_counts':components,'eligible_observed_families':len(eligible),'selected':len(selected),'minimum100_met':len(selected)==100,'preserved_qualified':len(accepted),'preserved_clean_assets_verified':len(hashes),'preflight_normal_attempt_ids_excluded_from_repeat':sorted(prior_normal),'unknown_families_retained_in_bulk':True,'all_remaining_observed_families_selected':len(selected)==len(eligible),'limitations':['Conservative XML source families preserve role grammar, path arity, paint order, CSS and reference ownership; unknown family remains in bulk, never asserted independent.','All supported pending originals remain in bulk except an already executed normal preflight; selected B/C IDs and qualified controls will not be repeated.','Transitive family/code/image/provenance closure includes qualified and nonselected bridge sources. No score or prior failure selects applicability.','Observed static families do not prove hidden-generator independence.'],'files':{n:{'sha256':sha((output/n).read_bytes()),'bytes':(output/n).stat().st_size}for n in ('source_audit.jsonl','supported_population.jsonl','selected.jsonl','preserved_qualified.jsonl','live_overlap_snapshot.json')}}
  if compiler.configuration()!=config:raise ValueError('frozen_frontend_changed_during_source_audit')
  if len(audits)!=SCOPE:raise ValueError('incomplete_original_scope_audit')
  (output/'summary.json').write_bytes(raw(summary));print(json.dumps({k:v for k,v in summary.items()if k not in ('method_pins','frozen_implementation','development_inputs')},ensure_ascii=False),flush=True);return summary
 finally:db.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);a=p.parse_args();prepare(a.output,a.inventory)
