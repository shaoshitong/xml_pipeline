"""Full canonical source and baseline snapshots before reservation/dispatch."""
from pathlib import Path
import hashlib,json,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
POLICY='author_native_drawio_full_canonical_source_and_baseline_request_contract_v2'
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda v:json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
FIELDS=('source_record_sha256','baseline_code_sha256','baseline_image_sha256')
def require(ok,reason):
 if not ok:raise ValueError(reason)
def check_rows(rows,db,expected_unit=None):
 seen=set();snapshots=[];claims=[]
 for row in rows:
  ident=row.get('id');require(isinstance(ident,str)and ident not in seen,'request_duplicate_or_missing_id');seen.add(ident)
  item=db.execute('select input_record,output_record,category,format,source,worker_pid,state,updated_at from jobs where id=?',(ident,)).fetchone();require(item is not None,'request_original_missing:'+ident);original_text,existing_text,category,fmt,provider,worker,state,updated=item;original=json.loads(original_text);require(isinstance(original,dict),'canonical_source_not_object:'+ident)
  require(row.get('source')==original,'request_full_canonical_source_mismatch:'+ident)
  require((original.get('pair_sha256'),original.get('category'),original.get('format'),original.get('source'))==(ident,category,fmt,provider),'request_canonical_source_identity_conflict:'+ident)
  require(fmt=='drawio'and category in ('scientific_diagram','poster'),'request_outside_authoritative_author_native_drawio_scope:'+ident)
  require(all(k in row for k in FIELDS),'request_baseline_snapshot_field_missing:'+ident)
  require(row['source_record_sha256']==sha((existing_text or'').encode()),'request_existing_output_record_snapshot_changed:'+ident)
  existing=json.loads(existing_text)if existing_text else{};require(isinstance(existing,dict),'canonical_existing_record_not_object:'+ident)
  require(row['baseline_code_sha256']==existing.get('code_sha256')and row['baseline_image_sha256']==existing.get('image_sha256'),'request_existing_candidate_baseline_changed:'+ident)
  from compiler_plantuml_engine_canonical_claim_v1 import diagnose
  claims.append({'id':ident,**diagnose({'worker_pid':worker,'state':state,'updated_at':updated})})
  if expected_unit is not None:require(row.get('compiler_unit')==expected_unit,'request_wrong_compiler_unit:'+ident)
  import drawio_author_version_frontend_v2 as frontend
  db.row_factory=__import__('sqlite3').Row
  full=dict(db.execute('select*from jobs where id=?',(ident,)).fetchone());db.row_factory=None
  support=frontend.static_support(full)
  require(support['supported']and row.get('source_capture_snapshot')==support.get('source_capture_snapshot'),'request_complete_author_source_capture_changed:'+ident)
  snapshots.append({'id':ident,'canonical_input_record_sha256':sha(original_text.encode()),'existing_output_record_sha256':row['source_record_sha256'],'baseline_code_sha256':row['baseline_code_sha256'],'baseline_image_sha256':row['baseline_image_sha256'],'complete_source_capture_sha256':sha(raw(row['source_capture_snapshot']))})
 return {'rows':len(rows),'ids_sha256':sha(raw(sorted(seen))),'snapshot_sha256':sha(raw(sorted(snapshots,key=lambda x:x['id']))),'complete_canonical_source_objects_exact':True,'complete_existing_output_record_hashes_exact':True,'baseline_code_and_image_snapshots_exact':True,'canonical_claims_readonly':claims,'deferred_live_or_uncertain_ids':[r['id']for r in claims if not r['conversion_allowed']],'stale_claim_ids':[r['id']for r in claims if r['status'].startswith('stale_')],'nonnull_claim_is_not_automatic_whole_pool_failure':True}
def validate(rows,database=W/'jobs.sqlite',expected_unit=None):
 with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True,timeout=30)as db:
  db.execute('pragma query_only=ON');db.execute('begin');result=check_rows(list(rows),db,expected_unit)
 return {'ok':True,'policy':POLICY,**result,'read_only_database':str(database),'validator_sha256':sha(Path(__file__).read_bytes())}
def validate_pool(pool,database=W/'jobs.sqlite',expected_unit=None):
 pool=Path(pool);assets={};data={}
 for name in ('selected.jsonl','supported_population.jsonl'):
  b=(pool/name).read_bytes();assets[name]=sha(b);data[name]=[json.loads(x)for x in b.splitlines()if x]
 selected=data['selected.jsonl'];population=data['supported_population.jsonl'];by_id={r['id']:r for r in population};require(len(by_id)==len(population),'population_duplicate_original')
 for index,row in enumerate(selected,1):
  require(row.get('seq')==index,'selected_request_sequence_not_contiguous');require(row['id']in by_id,'selected_not_in_supported_population')
  require(all(row.get(k)==by_id[row['id']].get(k)for k in ('source',*FIELDS,'compiler_unit')),'selected_population_snapshot_mismatch:'+row['id'])
 with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True,timeout=30)as db:
  db.execute('pragma query_only=ON');db.execute('begin');a=check_rows(population,db,expected_unit);b=check_rows(selected,db,expected_unit)
 return {'ok':True,'policy':POLICY,'selected':b,'population':a,'selected_population_exact_contract':True,'manifest_sha256':assets,'validator_sha256':sha(Path(__file__).read_bytes()),'read_only':True,'reservations_written':False,'dispatches_written':False}

def same_source_snapshots(a,b):
 """Process observations may change; source and exact baseline bytes may not."""
 def stable(value):
  if 'selected'in value:return {k:stable(value[k])for k in ('selected','population')}|{'manifest_sha256':value['manifest_sha256']}
  return {k:value[k]for k in ('rows','ids_sha256','snapshot_sha256','complete_canonical_source_objects_exact','complete_existing_output_record_hashes_exact','baseline_code_and_image_snapshots_exact')}
 return stable(a)==stable(b)
