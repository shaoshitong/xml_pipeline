"""Read-only cohort/development/registry metadata inventory; no target outcomes."""
from pathlib import Path
import sqlite3,json,collections,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');H=R/'release/round2_heldout_v1/unseen_protocol_20261101_v2';C=R/'release/compiler_validation_v1/cluster_audit_20261101_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
order=R/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl';universe=rows(order);uid={r['id']:r for r in universe};fmtcounts=collections.Counter(r['format'] for r in universe)
dev=rows(C/'compiler_validation_development_ids.jsonl');dids={r['id'] for r in dev};dcodes={r['code_sha256'] for r in dev};dimages={r['image_sha256'] for r in dev}
registry=R/'release/compiler_v1/validation_registry.sqlite';db=sqlite3.connect('file:'+str(registry)+'?mode=ro',uri=True,timeout=30);keys=set(db.execute('select kind,value from reservation_keys').fetchall());reservedids={v for k,v in keys if k=='id'};registry_meta=[]
for row in db.execute('select reservation_id,run_prefix,state,record from reservations').fetchall():
 r=json.loads(row[3]);registry_meta.append({k:r.get(k) for k in ('reservation_id','run_prefix','state','consumed','created_at','audit','source_ids','selected_manifest_sha256','protocol_sha256','phase_runs')})
db.close()
formats={}
for fmt,total in sorted(fmtcounts.items()):
 ur=[r for r in universe if r['format']==fmt];dr=[r for r in dev if r['format']==fmt]
 excluded=[r for r in ur if r['id'] in dids or r['source_code_sha256'] in dcodes or r['source_image_sha256'] in dimages or ('id',r['id']) in keys or ('code',r['source_code_sha256']) in keys or ('image',r['source_image_sha256']) in keys]
 formats[fmt]={'population':total,'dev_ids':len(dr),'dev_providers':dict(collections.Counter(r['provider'] for r in dr)),'dev_source_unknown':sum(r['cluster_parse_status']=='unknown' for r in dr),'registry_reserved_ids':sum(r['id'] in reservedids for r in ur),'excluded_exact_id_code_image_current_development_or_registry':len(excluded),'exact_identity_eligible_upper_bound':total-len(excluded)}
old=rows(H/'manifest.jsonl');audit=rows(C/'compiler_validation_cluster_candidates.jsonl');auditmap={r['id']:r for r in audit};pool=rows(H/'oversample.jsonl');cohort={}
for fmt in sorted({r['source']['format'] for r in old}):
 rs=[r for r in old if r['source']['format']==fmt];ar=[auditmap[r['id']] for r in rs];legal=[];collisions=collections.Counter()
 for r in rs:
  identity=[('id',r['id']),('code',r['source']['code_sha256']),('image',r['source']['image_sha256'])];a=auditmap[r['id']];identity+=[('audit_cluster',a['audit_cluster'])]+[('hard_cluster',v) for v in a.get('cluster_keys',[])]
  found=[k for k,v in identity if (k,v) in keys]
  if found:collisions.update(found)
  else:legal.append(r['id'])
 cohort[fmt]={'old480_count':len(rs),'registry_unreserved_by_id_and_current_known_hard_keys':len(legal),'registry_key_collisions':dict(collisions),'old_program_skeleton_audit_dispositions':dict(collections.Counter(r['audit_disposition'] for r in ar)),'old_operational_eligible_count':sum(r['audit_disposition']=='eligible_unconsumed_audited_cluster' for r in ar),'old_pool_oversample':sum(r['source']['format']==fmt for r in pool),'native_old_predicate_supported_and_old_audit_eligible':sum(bool(r.get('supported_by_predeclared_predicate')) and r['audit_disposition']=='eligible_unconsumed_audited_cluster' for r in ar),'conclusive_unseen_group_of30_ready':False}
localexamples={};inventory=R/'conversion/code_format_inventory.json'
# No raw source/target records are read. Provider inventory is supplied separately
# from existing local control metadata; original examples are not needed here.
summary={'kind':'read-only remaining-format unseen metadata inventory','universe':{'input_order':str(order),'bytes':order.stat().st_size,'sha256':sha(order.read_bytes()),'records':len(universe),'keys':sorted(universe[0])},'formats':formats,'development_roster':{'path':str(C/'compiler_validation_development_ids.jsonl'),'sha256':sha((C/'compiler_validation_development_ids.jsonl').read_bytes()),'count':len(dev)},'registry':{'path':str(registry),'reservation_records':registry_meta,'reserved_original_ids':len(reservedids),'reserved_key_counts':dict(collections.Counter(k for k,v in keys)),'keys_readonly_snapshot':True,'state_is_reservation_not_consumption_truth':True},'old480_cohort':{'path':str(H/'manifest.jsonl'),'sha256':sha((H/'manifest.jsonl').read_bytes()),'formats':cohort},'old_native_predeclared_unit_counts':json.loads((C/'compiler_validation_summary.json').read_text()).get('release_unit_statistics'),'new_source_or_image_read':False,'new_conversion_or_QA':False,'registry_written':False,'canonical_jobs_queries':0,'generator_independence_proven':False}
print(json.dumps(summary,ensure_ascii=False))
