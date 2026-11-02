"""Exhaustive source-only TikZ inventory and fresh structural-family cohort.

All dataset bytes stay on HKUST. No source rendering, conversion, model calls,
canonical writes or reservations occur here. Old and current development and
reserved identities exclude ID/code/image/observed source family/provenance.
Every still-pending frontend-supported original is retained for the bulk pass.
"""
import argparse,collections,hashlib,importlib,json,sqlite3,sys
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
SEED='hkust-tikz-pdftex2025-v2-source-only-unseen-20261101-round3'
SCOPE=40746
FRONTEND='compiler_tikz_poppler_source_v2'
CONTROLS=R/'release/compiler_iterations/controls/tikz_pdftex2025_v2_controls_20261101_v1/proof.json'

def raw(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def rows(path):
 with Path(path).open() as f:
  for line in f:
   if line.strip():yield json.loads(line)

def family(code):
 import compiler_types_source_ir_v1 as ir
 import compiler_validation_dot_ir_v2 as iso
 import tikz_literal_graph as parser
 # Parse the entire declared grammar first. Unknown macros/math/paint remain
 # explicitly unknown; no node/edge statements are dropped to obtain a family.
 unit,graph,evidence=ir.tikz(code,parser)
 if unit!='tikz_literal_named_graph_inventory_v1':
  raise ValueError('source_family_requires_complete_static_named_graph')
 # Merge numeric geometry, styles and literal-program spelling conservatively.
 # Endpoint/anchor graph, routes and arrow roles remain the actual typed IR.
 # This intentionally over-merges variants, rather than claiming fresh numeric
 # or color variations as an independent source structure.
 graph.nodes['ROOT']['signature']=sha(raw(['tikz_complete_static_named_endpoint_family_v1']))
 return 'tikz_observed_typed_source_family_v1:'+iso.invariant(graph),evidence

def identity_overlap(identifier,source,dev_ids,code_hashes,image_hashes):
 return identifier in dev_ids or source['code_sha256'] in code_hashes or source['image_sha256'] in image_hashes

def extract_hashes(row):
 code=row.get('source_code_sha256') or row.get('code_sha256')
 image=row.get('source_image_sha256') or row.get('image_sha256')
 return code,image

def prepare(output,inventory):
 import compiler_validation_cluster_audit_v1 as provenance
 import compiler_tikz_iteration_program_v1 as program
 compiler=importlib.import_module(FRONTEND);unit=compiler.UNITS['tikz'];config=compiler.configuration()
 output=Path(output).resolve();inventory=Path(inventory).resolve(strict=True)
 if not output.is_relative_to((R/'release/compiler_iterations/source_pools').resolve()):raise ValueError('source_pool_outside_owned_remote_root')
 controls=program.control_bundle(compiler);program.check_controls(controls)
 scope_path=R/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl';scope={r['id']:r for r in rows(scope_path) if r['format']=='tikz'}
 if len(scope)!=SCOPE:raise ValueError('TikZ_original_scope_changed')
 summary=json.loads((inventory/'summary.json').read_bytes());accepted_path=inventory/'qualified.jsonl'
 if sha(accepted_path.read_bytes())!=summary['files']['qualified.jsonl']['sha256']:raise ValueError('accepted_inventory_asset_changed')
 accepted={r['id'] for r in rows(accepted_path)};accepted.update(r['id'] for r in rows(Path(controls['qualified_manifest']['file'])))
 dev_path=R/'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl';dev_rows=list(rows(dev_path));development={r['id'] for r in dev_rows};development.update(r['id'] for r in controls['positive_cases'])
 # All previously consumed TikZ development sources, including failed cases,
 # exclude their IDs and the original code/image/family/provenance aliases.
 typed_dev_path=W/'compiler_tikz_free_paths_v1/development/typed_graph_inventory.json'
 typed_dev=json.loads(typed_dev_path.read_bytes());development.update(r['id'] for r in typed_dev['rows'])
 registry=R/'release/compiler_v1/validation_registry.sqlite'
 with sqlite3.connect('file:'+str(registry)+'?mode=ro',uri=True) as db:
  db.execute('begin');registry_keys=set(db.execute('select kind,value from reservation_keys'))
 development.update(v for k,v in registry_keys if k=='id')
 excluded_codes={v for k,v in registry_keys if k=='code'};excluded_images={v for k,v in registry_keys if k=='image'}
 reserved_cluster_keys={v for k,v in registry_keys if k in ('audit_cluster','hard_cluster')}
 for r in dev_rows:
  c,i=extract_hashes(r)
  if c:excluded_codes.add(c)
  if i:excluded_images.add(i)
 excluded_families=set();excluded_provenance=set();counters=collections.Counter();columns=('id','category','format','source','input_record','input_manifest')
 db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 def load(identifier,with_code=False):
  item=db.execute('select '+','.join(columns)+' from jobs where id=?',(identifier,)).fetchone()
  if not item:raise ValueError('source_job_missing')
  j=dict(zip(columns,item));source=json.loads(j['input_record'])
  if source['pair_sha256']!=identifier or source['format']!=j['format'] or source['category']!=j['category'] or source['source']!=j['source']:raise ValueError('original_job_source_identity_mismatch')
  code=None
  if with_code:
   manifest=json.loads(j['input_manifest']);data=(R/manifest['source_code']).read_bytes()
   if sha(data)!=source['code_sha256']:raise ValueError('original_source_code_hash_changed')
   code=data.decode('utf-8-sig')
  return j,source,code
 try:
  # Cross-format hashes and explicit documents/templates also exclude duplicates.
  # Only same-format source text is parsed into a TikZ structural family.
  for identifier in sorted(development):
   try:
    j,source,code=load(identifier,identifier in scope);excluded_codes.add(source['code_sha256']);excluded_images.add(source['image_sha256']);excluded_provenance.update(provenance.provenance(source,source['source']));counters['global_development_or_reserved_identity_loaded']+=1
    if identifier in scope:
     f,_=family(code);excluded_families.add(f);counters['same_format_exclusion_source_family_parsed']+=1
   except Exception as error:counters['exclusion_source_read_or_parse:'+type(error).__name__]+=1
  output.mkdir(parents=True,exist_ok=False);eligible=[];chosen_families=set();chosen_provenance=set();chosen_codes=set();chosen_images=set()
  ordered=sorted((i for i in scope if i not in accepted),key=lambda i:sha(raw([SEED,i])))
  with (output/'supported_population.jsonl').open('wb') as population,(output/'source_audit.jsonl').open('wb') as audit:
   for identifier in ordered:
    item={'id':identifier,'source_format':'tikz'}
    try:
     job,source,code=load(identifier,True)
     for field,key in [('source_code_sha256','code_sha256'),('source_image_sha256','image_sha256')]:
      if scope[identifier].get(field)!=source[key]:raise ValueError('initial_scope_source_digest_changed')
     support=compiler.static_support(job)
     if not support['supported']:item.update(disposition='pending_unsupported_in_this_frontend_version',reason=support['reasons'])
     else:
      population.write(raw({'id':identifier,'source':source,'compiler_unit':unit}));counters['supported_remaining_population']+=1
      f,evidence=family(code);keys=set(provenance.provenance(source,source['source']));item.update(family=f,source_evidence=evidence)
      if identity_overlap(identifier,source,development,excluded_codes,excluded_images):item['disposition']='development_or_reserved_identity_overlap'
      elif f in excluded_families or f in reserved_cluster_keys or keys & (excluded_provenance|reserved_cluster_keys):item['disposition']='development_or_reserved_family_provenance_overlap'
      elif f in chosen_families or keys & chosen_provenance or source['code_sha256'] in chosen_codes or source['image_sha256'] in chosen_images:item['disposition']='duplicate_validation_family_provenance_or_identity'
      else:
       item['disposition']='eligible_fresh_observed_source_family';chosen_families.add(f);chosen_provenance.update(keys);chosen_codes.add(source['code_sha256']);chosen_images.add(source['image_sha256']);eligible.append({'id':identifier,'source':source,'compiler_unit':unit,'audit_cluster':f,'cluster':f,'cluster_keys':sorted({f}|keys)})
    except Exception as error:item.update(disposition='pending_source_family_inventory_diagnosis',reason=str(error)[:700])
    counters[item['disposition']]+=1;audit.write(raw(item))
  selected=eligible[:100]
  for seq,item in enumerate(selected,1):
   item['seq']=seq;baseline=db.execute('select output_record from jobs where id=?',(item['id'],)).fetchone()[0];record=json.loads(baseline) if baseline else {};item.update(source_record_sha256=sha((baseline or '').encode()),baseline_code_sha256=record.get('code_sha256'),baseline_image_sha256=record.get('image_sha256'))
  (output/'selected.jsonl').write_bytes(b''.join(raw(x) for x in selected));methods=[Path(__file__),W/'scripts/compiler_types_source_ir_v1.py',W/'scripts/tikz_literal_graph.py',W/'scripts/tikz_connectivity.py',W/'scripts/compiler_validation_dot_ir_v2.py',W/'scripts/compiler_validation_cluster_audit_v1.py']
  info={'schema':'compiler_tikz_unseen_source_pool_v1','seed':SEED,'scope':SCOPE,'compiler_unit':unit,'frontend_module':FRONTEND,'frozen_implementation':config,'method_pins':{str(p.resolve()):sha(p.read_bytes()) for p in methods},'controls_proof':controls['definition'],'source_only':True,'conversion_or_rendering':False,'model_calls':0,'development_ids_all_formats':len(development),'excluded_same_format_families':len(excluded_families),'eligible_observed_families':len(eligible),'selected':len(selected),'minimum100_met':len(selected)>=100,'all_remaining_observed_families_selected':len(selected)==len(eligible),'excluded_accepted':len(accepted&set(scope)),'counters':dict(counters),'registry_modified':False,'registry_keys_snapshot_sha256':sha(raw(sorted(registry_keys))),'development_input_sha256':sha(dev_path.read_bytes()),'scope_index_sha256':sha(scope_path.read_bytes()),'limitations':['Source graph invariant collisions conservatively merge families; hidden generator independence is not proven.','Unparseable source-family syntax remains visible in the audit and still belongs to the applicable frozen frontend population; conversion has independent full source/native QA.','All original supported remaining sources are in bulk population, including development/reserved families; already qualified controls and selected B/C IDs are excluded from duplicate mass attempts.'],'files':{n:{'sha256':sha((output/n).read_bytes()),'bytes':(output/n).stat().st_size} for n in ('source_audit.jsonl','selected.jsonl','supported_population.jsonl')}}
  info['additional_development_inventory']={'file':str(typed_dev_path),'sha256':sha(typed_dev_path.read_bytes()),'ids':len(typed_dev['rows'])}
  if compiler.configuration()!=config:raise ValueError('frontend_changed_during_source_inventory')
  (output/'summary.json').write_bytes(raw(info));print(json.dumps({k:v for k,v in info.items() if k not in ('frozen_implementation','method_pins')},ensure_ascii=False),flush=True);return info
 finally:db.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);a=p.parse_args();prepare(a.output,a.inventory)
