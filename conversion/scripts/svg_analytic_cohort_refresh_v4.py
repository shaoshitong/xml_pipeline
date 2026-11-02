"""Fresh metadata exclusions over sealed full-source transitive components.

No source XML, PNG, rendering, model call or canonical job write is performed.
The reservation owner supplies current canonicalized keys under its write lock.
"""
import datetime,json
from pathlib import Path
import compiler_validation_identity_alias_v1 as aliases
import compiler_validation_sealed_cohort_v1 as sealed
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
def readrows(path):return[json.loads(line)for line in Path(path).read_bytes().splitlines()if line]
def knowledge_snapshot(pool,configuration):
 import svg_analytic_iteration_pool_v5 as sourcepool
 import svg_analytic_source_contract_v4 as contract
 import compiler_source_core_attempts_v3 as history
 from compiler_mermaid_alpha_qualifications_v2 import ledger_manifests
 from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot as overlap_snapshot
 pool=Path(pool);manifest=readrows(pool/'supported_population.jsonl');ids={r['id']for r in manifest};development=[r for p in sourcepool.development_inputs()for r in sourcepool.rows(p)]+sourcepool.supplementary_development_rows()+readrows(pool/'seen_source_IDs_snapshot.jsonl')
 events=history.collect(configuration,root=R,catalog=contract.CATALOG);history.validate(events,configuration,root=R)
 development.extend(dict(id=row['id'])for row in events);known=set();pairs=[]
 for row in development:
  if row.get('id'):known.add(row['id']);pairs.append(('id',row['id']))
  for field,kind in [('source_code_sha256','code'),('code_sha256','code'),('source_image_sha256','image'),('image_sha256','image')]:
   if row.get(field):pairs.append((kind,row[field]))
  pairs.extend(('hard_cluster',key)for key in(row.get('cluster_keys')or()))
 # Qualifications and verified live overlap remove only their target request.
 # Independent-family contamination comes from actual seen/development IDs.
 qualified={r['id']for r in readrows(pool/'preserved_qualified.jsonl')}
 qualified.update(r['id']for r in ledger_manifests(root=R,identifiers=ids));qualified.update(r['id']for r in sourcepool.control_qualified(ids))
 overlap=overlap_snapshot();active=set(overlap['active'])
 snapshot=dict(schema='SVG_analytic_sealed_SOURCE_metadata_freshness_v1',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_only_metadata=True,known_source_ids=sorted(known),exclusion_keys=[list(k)for k in sorted(aliases.normalize_keys(pairs))],same_core_normal_events=events,qualified_ids=sorted(qualified&ids),verified_live_ids=sorted(active&ids),qualified_and_active_deferred_per_target_only=True,source_XML_or_PNG_read=False,canonical_writes=0,model_calls=0)
 return snapshot

def choose(seal,requests,snapshot,current_registry_keys,*,seed,limit=100):
 if seal.get('full_scope_records')!=131904 or seal.get('target_records')!=26754:raise ValueError('SVG_sealed_source_scope_or_global_bridge_coverage_changed')
 blocked={tuple(k)for k in snapshot['exclusion_keys']}|set(current_registry_keys);target_deferred=set(snapshot['qualified_ids'])|set(snapshot['verified_live_ids'])
 available=[r for r in requests if r['id']not in target_deferred]
 result=sealed.select(seal['components'],available,blocked,seed=seed,limit=limit)
 result.update(sealed_full_scope_records=seal['full_scope_records'],sealed_target_records=seal['target_records'],current_known_source_ids=len(snapshot['known_source_ids']),current_same_core_normal_events=len(snapshot['same_core_normal_events']),qualified_targets_removed=len(set(snapshot['qualified_ids'])),verified_live_targets_removed=len(set(snapshot['verified_live_ids'])),cross_kind_aliases_normalized=True,source_bytes_reopened=False)
 return result
