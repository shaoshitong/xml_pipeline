from pathlib import Path
import json,sqlite3,collections
R=Path('/backup/shaoshitong/img2code_20261029');H=R/'release/round2_heldout_v1/unseen_protocol_20261101_v2';C=R/'release/compiler_validation_v1/cluster_audit_20261101_v1'
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
dev=rows(C/'compiler_validation_development_ids.jsonl');dids={r['id'] for r in dev};old=rows(H/'manifest.jsonl');db=sqlite3.connect('file:'+str(R/'release/round2_fixed_v1/repair_pass_20261101_0627/status.sqlite')+'?mode=ro',uri=True);counts=collections.defaultdict(collections.Counter)
for r in old:
 x=db.execute('select attempts,status from samples where id=?',(r['id'],)).fetchone();counts[r['source']['format']][str(x)]+=1
history=json.loads((R/'conversion/compiler_validation_historical_inventory_example_ids_v1.json').read_text());missing=[r for r in history['historical_inventory_example_ids'] if r['id'] not in dids]
for p in [R/'conversion/compiler_native_languages_v1_development/development_ids.jsonl',R/'conversion/compiler_native_languages_v1_development/additional_seen_development_ids.jsonl']:
 if p.exists():
  for r in rows(p):
   if r['id'] not in dids:missing.append({'id':r['id'],'historical_artifact':str(p),'reason':'not_in_development6581'})
print(json.dumps({'old480_current_round2_attempts_status':{k:dict(v) for k,v in counts.items()},'historical_explicit_case_ids_outside_dev6581':missing,'history_provider_counts':history['provider_counts'],'no_target_outcomes_read':True,'no_registry_or_source_writes':True}))
