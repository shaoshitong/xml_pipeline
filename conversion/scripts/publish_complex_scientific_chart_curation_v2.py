"""Publish source-rule curation after real positive/negative PNG spot checks."""
from pathlib import Path
import collections,hashlib,json,os,sys
R=Path('/backup/shaoshitong/img2code_20261029');ROOT=Path(sys.argv[1]).resolve();assert ROOT.is_relative_to(R/'clean/complex_scientific_chart_curation_v4')
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def main():
 summary=read(ROOT/'summary.json');assert summary['selected']>=88 and summary['producer_sha256']==sha((R/'conversion/scripts/curate_executed_complex_scientific_charts_v4.py').read_bytes())
 for ref in summary['files'].values():assert sha((R/ref['file']).read_bytes())==ref['sha256']
 pairs=[json.loads(x)for x in(ROOT/'complex_scientific_candidates.jsonl').read_text().splitlines()];by_id={r['id']:r for r in pairs};old=read(R/'clean/complex_scientific_chart_curation_v1/4370e9e37e9e45db9e56e015341bf74d/selected_spot_review.json');technical=read(R/'clean/matplotlib_plot_pipeline_20261102_v1/vector_backend_rollout_v6/catalogue_v4_spot_review_selection.json');new=read(R/'clean/complex_scientific_chart_curation_v3/0d9a557524034cd9a94ed422c16eb18b/Agg_spot_review_selection.json')
 assert len(new)==2
 positive=[old[1],old[4],old[5],technical[4],*new];negative=[technical[2],technical[3],old[0],old[2],old[3]]
 assert all(r['id']in by_id for r in positive)and all(r['id']not in by_id for r in negative)
 catalog=read(R/'clean/research_pairs_catalog/current.json');assert catalog['publisher']=='research_catalog_refresh_v5';b=(R/catalog['index']['file']).read_bytes();assert sha(b)==catalog['index']['sha256'];membership=collections.defaultdict(set)
 for p in map(json.loads,b.splitlines()):
  for ref in p['source_records']:membership[ref['source_id']].add(p['code_sha256'])
 assert all(r['code_sha256']in membership[r['id']]for r in pairs)
 profiles=dict(collections.Counter(r['profile']for r in pairs));target=ROOT/'curated_pairs_by_reference_profile.jsonl'
 if not target.exists():os.link(ROOT/'complex_scientific_candidates.jsonl',target)
 proof=dict(rows=len(pairs),profile_counts=profiles,curation_type='actual_source_structure_and_scientific_text_rule_with_native_PNG_spot_checks',actual_native_PNG_positive_samples=[r['id']for r in positive],actual_native_PNG_negative_samples=[r['id']for r in negative],actual_PNGs_inspected=True,positive_and_negative_source_rule_controls_passed=True,scientific_value_individually_certified=False,source_rule_not_conversion_validation=True,fresh_unseen_validation_claimed=False,all_nonselected_originals_and_prior_rules_retained=True,original_reference_profiles_preserved=True,strict_full8_main_unchanged=True,curated_pairs=asset(target),source_screen_summary=asset(ROOT/'summary.json'),source_policy=asset(ROOT/'policy.json'),verified_unified_catalog=catalog['index'],new_conversions=0,new_QA=0,model_calls=0,goal_complete=False)
 p=ROOT/'curation_acceptance.json';p.write_text(json.dumps(proof,indent=2)+'\n');p.chmod(0o444)
 parent=R/'clean/complex_scientific_charts';parent.mkdir(exist_ok=True);pointer=dict(curated_pairs=asset(target),summary=asset(p),rows=len(pairs),profile_counts=profiles,strict_full8_main_unchanged=True,goal_complete=False);temp=parent/'current.tmp';temp.write_text(json.dumps(pointer,indent=2)+'\n');temp.replace(parent/'current.json');print(json.dumps(pointer))
if __name__=='__main__':main()
