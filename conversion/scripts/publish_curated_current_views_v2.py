"""Immutable current curation snapshot; pure source/asset/hash bookkeeping.

Never runs conversion, QA, rendering, network requests, models, or job writers.
The only mutable publication is current.json after every immutable file passes.
"""
from pathlib import Path
import collections,concurrent.futures,datetime,hashlib,json,os,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';RUN=R/'clean/complexity_curation_20261102T054553Z_v1';BASE=RUN/'published_v1'
sys.path.insert(0,str(W/'scripts'))
from compiler_iteration_inventory_v1 import check_manifest
from compiler_mermaid_alpha_qualifications_v2 import find_qualified
FIELDS=[('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]
STAMP=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');OUT=RUN/('published_current_'+STAMP+'_v2')
raw=lambda x:(json.dumps(x,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode()
compact=lambda x:(json.dumps(x,ensure_ascii=True,sort_keys=True)+'\n').encode()
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def require(x,reason):
 if not x:raise ValueError(reason)
def clean(name):
 p=Path(name);p=p if p.is_absolute()else R/p;p=p.resolve(strict=True)
 require(p.is_file()and p.is_relative_to((R/'clean').resolve()),'asset_not_actual_clean_file:'+str(p));return p
def digest(p):
 h=hashlib.sha256();before=p.stat()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 after=p.stat();require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'asset_changed_during_hash:'+str(p));return h.hexdigest()
def asset(name,expected=None,field=None):
 p=clean(name);h=digest(p)
 if expected:require(h==expected,'asset_hash_mismatch:'+str(p))
 return dict(field=field,file=str(p.relative_to(R)),absolute_file=str(p),sha256=h,bytes=p.stat().st_size)
def loadlines(p):return [json.loads(l)for l in p.open()if l.strip()]
def write(name,rows=None,value=None):
 p=OUT/name;blob=raw(value)if value is not None else b''.join(compact(r)for r in rows)
 with p.open('xb')as f:f.write(blob)
 return dict(file=str(p.relative_to(R)),sha256=sha(blob),bytes=len(blob),**({'rows':len(rows)}if rows is not None else{}))
def source_snapshot(ids):
 result={};db=sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)
 try:
  db.execute('pragma query_only=ON');db.execute('begin');values=sorted(ids)
  for start in range(0,len(values),500):
   chunk=values[start:start+500]
   for ident,body in db.execute('select id,input_record from jobs where id in ('+','.join('?'for _ in chunk)+')',chunk):result[ident]=json.loads(body)
 finally:db.close()
 require(set(result)==set(ids),'canonical_original_source_missing');return result
def source_key(q):return tuple(q[k]for k in('source','source_format','category','source_code_sha256','source_image_sha256'))
def audit_pair(q,s,view):
 require(q['status']=='qualified'and q['format']=='drawio'and q['id']==q['source_pair_sha256']==s['pair_sha256'],'qualified_pair_ID_or_status_mismatch')
 require(source_key(q)==(s['source'],s['format'],s['category'],s['code_sha256'],s['image_sha256']),'qualified_pair_original_source_identity_mismatch:'+q['id'])
 rows=[asset(q[f],q[h],f)for f,h in FIELDS]
 metadata=json.loads(clean(q['metadata_file']).read_bytes())
 for k in('id','source_pair_sha256','source','category','source_format','source_code_sha256','source_image_sha256','code_sha256','image_sha256'):require(metadata[k]==q[k],'accepted_metadata_identity_mismatch:'+q['id']+':'+k)
 check_manifest(R,q['id'],s,q,{})
 return dict(id=q['id'],view=view,source=q['source'],source_code_sha256=q['source_code_sha256'],source_image_sha256=q['source_image_sha256'],ok=True,errors=[],audited_assets=rows,QA_rerun=False)

def native_snapshot():
 # Two coherent RO snapshots; repeated inherited rows are aliases, not new pairs.
 ledgers=[];by_pdf={};at=now()
 for label in('new_bulk_200_v1','recent_ai_source_expansion_v2'):
  path=R/'clean/arxiv_research_figures_v1'/label/'once.sqlite'
  with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)as db:
   db.execute('pragma query_only=ON');db.execute('begin');records=db.execute("select id,record from pdfs where status='qualified_native_xml_png_pair' order by id").fetchall()
  ledgers.append(dict(file=str(path.relative_to(R)),qualified_rows=len(records),query="select id,record from pdfs where status='qualified_native_xml_png_pair' order by id",read_only=True))
  for ident,body in records:
   r=json.loads(body);require(r['id']==ident==r['pdf_sha256'],'native_original_PDF_ID_mismatch')
   alias=dict(ledger=str(path.relative_to(R)),record_json_sha256=sha(body.encode()),imported_history=r.get('imported_history',False))
   if ident in by_pdf:
    prev=by_pdf[ident]['record'];require(all(prev[k]==r[k]for k in('pdf_sha256','author_xml_sha256','image_sha256')),'conflicting_native_PDF_recovery');by_pdf[ident]['ledger_aliases'].append(alias)
   else:by_pdf[ident]=dict(record=r,ledger_aliases=[alias])
 groups={};audits=[]
 for ident,item in sorted(by_pdf.items()):
  r=item['record'];require(r['original_PDF_fidelity']=='review_not_certified'and r['author_XML_unmodified']is True and r['frozen_author_XML_hash_unchanged']is True and r['source_provenance']=='PDF_native_embedded_author_XML','native_recovery_contract_changed')
  require(r['assets_complete']is True and not r.get('custom_PDF_geometry_converter')and r.get('external_models')==0,'native_recovery_unclosed_or_wrong_route')
  code=asset(r['author_xml_file'],r['author_xml_sha256'],'author_editable_XML');image=asset(r['image_file'],r['image_sha256'],'official_render_PNG');pdf=asset(r['pdf_file'],r['pdf_sha256'],'original_source_PDF')
  ep=clean(r['render_edit_evidence']);e=json.loads(ep.read_bytes());proof=asset(ep,field='existing_native_render_edit_proof')
  cp=ep.parent/'record.json';original=json.loads(cp.read_bytes());require(all(original[k]==r[k]for k in('id','pdf_sha256','author_xml_sha256','image_sha256')),'native_case_record_not_original_once_result')
  metadata=asset(cp,field='original_native_case_record')
  require(e['png_sha256']==r['image_sha256']and e['official_generator']=='Graph.getSvg from pinned full Editor','native_proof_official_PNG_not_bound')
  require(all(e['edit_probe'].get(k)is True for k in('geometry_and_label_mutation_changes_xml','restore_xml_exact','mutation_SVG_changed','mutation_actual_PNG_changed','restored_actual_PNG_exact')),'existing_native_edit_restore_proof_incomplete')
  require(e['resource_font_closure'].get('all_images_decode_completed')is True and not e['resource_font_closure'].get('failed'),'existing_native_image_load_proof_incomplete')
  additional=[]
  for filename in('official.svg','mutated.svg','restored.svg','mutated.png','restored.png','source.pdf','source_pdf_reference.png','pdf_alignment_review.json'):
   p=ep.parent/filename;require(p.is_file(),'existing_native_proof_asset_missing:'+str(p));additional.append(asset(p,field='existing_proof_'+filename))
  require(next(a['sha256']for a in additional if a['field']=='existing_proof_source.pdf')==r['pdf_sha256'],'native_source_PDF_copy_changed')
  audit=dict(id=ident,view='native_recovery_candidate',required_native_assets=[code,image,pdf,proof,metadata],additional_existing_proof_assets=additional,ok=True,new_QA=False)
  audits.append(audit);key=(r['author_xml_sha256'],r['image_sha256'])
  alias=dict(original_PDF_id=ident,paper=r['paper'],source_PDF=pdf,original_native_record=metadata,native_render_edit_proof=proof,existing_program_proof=e,additional_existing_proof_assets=additional,ledger_aliases=item['ledger_aliases'])
  if key not in groups:
   groups[key]=dict(id=ident,status='native_recovery_candidate',qualified=False,source='arxiv_official_builtin_native_recovery',format='drawio',source_format='pdf',code_file=code['file'],code_sha256=code['sha256'],image_file=image['file'],image_sha256=image['sha256'],source_provenance=r['source_provenance'],upstream_pipeline_status=r['status'],original_PDF_fidelity='review_not_certified',independent_full8_QA_passed=False,provider_reference_qualified=False,full8_font_portability_certified=False,original_PDF_aliases=[],structure_from_original_native_XML=r['structure'],new_conversion_or_QA_or_model_calls=0)
  groups[key]['original_PDF_aliases'].append(alias)
 return list(groups.values()),audits,dict(snapshot_started_at_utc=at,snapshot_completed_at_utc=now(),ledgers=ledgers,ledger_qualified_rows=sum(x['qualified_rows']for x in ledgers),unique_source_PDFs=len(by_pdf),unique_native_XML_PNG_pairs=len(groups),same_PDF_ledger_alias_rows=sum(x['qualified_rows']for x in ledgers)-len(by_pdf),same_native_XML_PNG_pair_PDF_aliases=len(by_pdf)-len(groups))

def main():
 summary0=json.loads((BASE/'summary.json').read_bytes());basefile=BASE/'paired_priority_complex.jsonl'
 require(digest(basefile)==summary0['files']['paired_priority_complex.jsonl']['sha256'],'published_baseline_index_changed')
 mainrows=loadlines(basefile);require(len(mainrows)==771,'baseline_count_changed')
 hp=R/'clean/html_flex_paragraph_development_v1/c147987817d2e46985d2ba59d2f265db4646735ccb210e34d417b3bf2293bc0b/b141e36589e819a6a1197679dc1f3970fcae91a3068fb5a80edfd998a85c11b7/qualified_manifest.json';html=json.loads(hp.read_bytes())
 svgpath=R/'clean/priority_svg_source_image_panels_20261102_v1/qualified_combined3_snapshot_v1.jsonl';svg=loadlines(svgpath)
 newmain=[html]+[q for q in svg if q['id'].startswith('1e37ecbe')];review=[q for q in svg if not q['id'].startswith('1e37ecbe')]
 require(len(newmain)==2 and len(review)==2,'new_profile_manifest_scope_changed')
 # Confirm new complexity/source classification in the frozen source curation.
 wanted={q['id']for q in newmain};curation={}
 with (RUN/'priority_sources/complex_candidate.jsonl').open('rb')as f:
  for line in f:
   if any(i.encode()in line for i in wanted):
    r=json.loads(line)
    if r['id']in wanted:curation[r['id']]=r
   if set(curation)==wanted:break
 require(set(curation)==wanted,'new_main_source_not_frozen_complex_candidate')
 for q in newmain:
  r=curation[q['id']];require(r['status']=='complex_candidate'and r['code_sha256_manifest']==q['source_code_sha256']and r['image_sha256_manifest']==q['source_image_sha256'],'new_main_source_complexity_identity_changed')
  mainrows.append({**q,'curation':dict(selection='priority_source_complex_candidate',source_status='complex_candidate',source_features=r['features'],source_reasons=r['reasons'],source_provenance=r.get('provenance'),reference_kind=r.get('reference_kind'),current_required_asset_hashes_verified=True,scientific_merit_individually_certified=False,new_conversion_or_QA_or_model_calls=0)})
 classmap={r['id']:r for r in loadlines(R/'clean/priority_svg_asset_panel_source_pool_20261102_v1/source_audit.jsonl')}
 review=[{**q,'curation':dict(selection='qualified_priority_structure_review',source_status=classmap[q['id']]['curation_status'],source_features=classmap[q['id']]['curation_features'],source_provenance=classmap[q['id']]['source_metadata'],not_promoted_to_complex=True)}for q in review]
 require(all(q['curation']['source_status']=='structure_review'for q in review),'review_source_was_promoted')
 allrows=mainrows+review;ids=[q['id']for q in allrows];require(len(ids)==len(set(ids))==775,'duplicate_paired_ID')
 keys=[source_key(q)for q in allrows];require(len(keys)==len(set(keys)),'duplicate_original_source_pair')
 sources=source_snapshot(ids)
 for q in newmain+review:require(find_qualified(q['id'],sources[q['id']],R)is not None,'new_pair_not_globally_published')
 tasks=[(q,sources[q['id']],'paired_priority_complex')for q in mainrows]+[(q,sources[q['id']],'new_qualified_structure_review')for q in review]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:audits=list(pool.map(lambda x:audit_pair(*x),tasks))
 require(source_snapshot(ids)==sources,'original_source_identity_changed_during_hash_audit')
 native,naudit,nsnapshot=native_snapshot()
 # Pending queue remains immutable, represented by an exact-ID removal overlay.
 target=BASE/'complex_conversion_targets.jsonl';th=hashlib.sha256();found=set();n=0
 with target.open('rb')as f:
  for line in f:
   th.update(line);n+=bool(line.strip())
   for i in wanted:
    if i.encode()in line and json.loads(line)['id']==i:found.add(i)
 require(th.hexdigest()==summary0['files']['complex_conversion_targets.jsonl']['sha256']and n==27150 and found==wanted,'baseline_pending_overlay_identity_changed')
 OUT.mkdir(parents=True,exist_ok=False)
 files={'paired_priority_complex':write('paired_priority_complex.jsonl',rows=sorted(mainrows,key=lambda q:q['id'])),'new_qualified_structure_review':write('qualified_structure_review_additions.jsonl',rows=sorted(review,key=lambda q:q['id'])),'native_recovery_candidates':write('native_recovery_candidates.jsonl',rows=sorted(native,key=lambda q:q['id'])),'required_paired_asset_hash_audit':write('required_paired_asset_hash_audit.jsonl',rows=audits),'required_native_asset_hash_audit':write('required_native_asset_hash_audit.jsonl',rows=naudit)}
 inherited={}
 for name in('paired_auxiliary_rich_graphs.jsonl','qualified_priority_value_review.jsonl'):
  expected=summary0['files'][name];require(digest(BASE/name)==expected['sha256'],'inherited_index_changed');inherited[name]=dict(file=str((BASE/name).relative_to(R)),**expected,payload_assets_reaudited_in_this_snapshot=False)
 out=dict(schema='curated_current_original_reference_snapshot_v2',at_utc=now(),root=str(OUT),snapshot_scope='Frozen published_v1 baseline plus explicitly published HTML b141 and SVG 1e; SVG be58/74d0 remain review additions. arXiv native recovery is a separate candidate profile.',paired_priority_complex=773,paired_priority_by_source=dict(collections.Counter(q['source']for q in mainrows)),paired_priority_by_format=dict(collections.Counter(q['source_format']for q in mainrows)),new_primary_ids=sorted(wanted),new_qualified_structure_review=2,source_complex_candidates=summary0['priority_source_complex_candidates'],source_rows_screened=summary0['source_rows_screened'],pending_complex_targets=27148,pending_target_overlay=dict(base_file=str(target.relative_to(R)),base_sha256=th.hexdigest(),base_rows=n,exclude_exact_qualified_ids=sorted(wanted),rows_after_filter=n-len(wanted)),native_recovery=nsnapshot,native_recovery_candidate_count=len(native),native_recovery_original_PDF_fidelity='review_not_certified',native_recovery_counts_in_main_primary=False,chart_new_profile_pairs_imported=0,chart_original_vs_replay_profiles='Published separately by the chart-profile owner; no new Chart pair imported into this reference profile.',required_paired_asset_audit=dict(pairs_checked=len(audits),required_asset_hashes_checked=sum(len(a['audited_assets'])for a in audits),failed_pairs=0,fields=[x[0]for x in FIELDS]),required_native_asset_audit=dict(original_PDF_records_checked=len(naudit),required_asset_hashes_checked=sum(len(a['required_native_assets'])for a in naudit),additional_existing_proof_asset_hashes_checked=sum(len(a['additional_existing_proof_assets'])for a in naudit),failed_records=0),input_baseline=dict(file=str(basefile.relative_to(R)),sha256=digest(basefile),rows=771),input_new_HTML_manifest=asset(hp),input_new_SVG_manifests=asset(svgpath),files=files,inherited_frozen_views=inherited,qualification_scope='Existing recorded qualifications are preserved; new pairs already have independent full QA. This publication only rechecks source identities and current clean asset hashes.',RAP_provenance='Reconstructed template render and editable HTML; original poster remains auxiliary.',new_conversions=0,new_QA_calls=0,new_models=0,canonical_mutations=0,old_immutable_publication_modified=False,goal_complete=False)
 files['summary']=write('summary.json',value=out)
 # A full hashed inventory avoids a circular summary/report hash dependency.
 inventory=write('hash_inventory.json',value=dict(schema='curated_current_file_hash_inventory_v2',files=files,producer_sha256=sha(Path(__file__).read_bytes())))
 current=RUN/'current.json';previous=None
 if current.exists():previous=write('previous_current_snapshot.json',value=json.loads(current.read_bytes()))
 pointer=dict(schema='curated_current_pointer_v2',at_utc=now(),snapshot=str(OUT.relative_to(R)),summary=files['summary'],hash_inventory=inventory,views={k:v for k,v in files.items()if k in('paired_priority_complex','new_qualified_structure_review','native_recovery_candidates')},paired_priority_complex=773,new_qualified_structure_review=2,native_recovery_candidate_count=len(native),native_recovery_unique_source_PDFs=nsnapshot['unique_source_PDFs'],native_recovery_original_PDF_fidelity='review_not_certified',previous_current_snapshot=previous)
 tmp=current.with_name(current.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(raw(pointer));os.replace(tmp,current)
 for p in OUT.iterdir():
  if p.is_file():os.chmod(p,0o444)
 require(digest(basefile)==summary0['files']['paired_priority_complex.jsonl']['sha256'],'original_baseline_changed')
 print(json.dumps(dict(current_pointer=dict(file=str(current),sha256=digest(current)),summary=files['summary'],hash_inventory=inventory,paired_priority_complex=773,new_qualified_structure_review=2,native_recovery_candidate_count=len(native),native_recovery_snapshot=nsnapshot,required_paired_asset_hashes_checked=out['required_paired_asset_audit']['required_asset_hashes_checked'],required_native_asset_hashes_checked=out['required_native_asset_audit']['required_asset_hashes_checked'],additional_native_proof_asset_hashes_checked=out['required_native_asset_audit']['additional_existing_proof_asset_hashes_checked'],files=files,new_conversions=0,new_QA=0,models=0,canonical_mutations=0),ensure_ascii=True))

if __name__=='__main__':main()
