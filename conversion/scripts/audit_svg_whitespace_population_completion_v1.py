"""Close the complete frozen SVG population and compare exact-source outcomes."""
from pathlib import Path
import collections,datetime,hashlib,json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S));B=R/'release/compiler_iterations';NAME='svg_complex_source_whitespace_cached_unseen_20261103_v12';P=B/'programs'/NAME
def read(p):return json.loads(p.read_text())
def rows(p):return[json.loads(x)for x in p.read_text().splitlines()]
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def source_pair(r):return(r['source_code_sha256'],r['source_image_sha256'])
def terminal(run):
 import fixed_batch_pipeline_v1 as base
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:
  meta=base.metadata(d);rs=d.execute('select id,status,attempts,result from samples order by seq').fetchall()
 assert meta['finished']is True and all(x[1]in ['qualified','abandoned']and x[2]==1 for x in rs)
 assert sha((run/'targets.jsonl').read_bytes())==meta['input_sha256'];values=[json.loads(x[3])for x in rs];assert all(x.get('case_cleanup_complete')is True and x.get('infrastructure_failure')is not True for x in values)
 final=read(run/'final_asset_audit.json');assert final['late_asset_failures']==0 and final['qualified_payloads_verified']==sum(x['status']=='qualified'for x in values)
 return values,dict(targets=len(values),counts=dict(collections.Counter(x['status']for x in values)),all_attempts_exactly_one=True,all_cleanup_complete=True,final_asset_audit=asset(run/'final_asset_audit.json'))
def main():
 assert read(P/'state.json')['stage']=='round_complete_next_repair_required';summary=read(P/'summary.json');gate=read(P/'release_gate.json');assert gate['controls_passed']and gate['infrastructure_errors']==0 and all(x['passed']for x in gate['units'].values())
 population=rows(P/'supported_population.jsonl');by_id={r['id']:r for r in population};assert len(by_id)==len(population)==1149
 runs=[NAME+'_C','svg_source_whitespace_disjoint_20261103_v1_mass','svg_source_whitespace_disjoint_20261103_v2_mass']
 if summary.get('mass'):runs.append(Path(summary['mass']).name)
 outcomes={};phases={}
 for name in runs:
  values,proof=terminal(B/'runs'/name);phases[name]=proof
  for r in values:
   assert r['id']in by_id and r['id']not in outcomes;original=by_id[r['id']]['source'];assert source_pair(r)==(original['code_sha256'],original['image_sha256']);outcomes[r['id']]=dict(r,observed_run=name)
 baseline,baseline_proof=terminal(B/'runs'/(NAME+'_B'));assert len(baseline)==phases[NAME+'_C']['targets']==43
 unit=next(iter(gate['units'].values()));assert unit['B_qualified']==sum(r['status']=='qualified'for r in baseline)and unit['C_qualified']==phases[NAME+'_C']['counts'].get('qualified',0)
 preserved={r['id']:r['manifest']for r in rows(P/'mass_preserved_qualified_controls.jsonl')};history=rows(P/'mass_once_core_history.jsonl');prior={r['id']:r for r in history};assert len(prior)==len(history)
 coverage=[]
 for identifier,request in by_id.items():
  if identifier in outcomes:r=outcomes[identifier];category='terminal_current_round';detail=dict(run=r['observed_run'],status=r['status'])
  elif identifier in preserved:
   r=preserved[identifier];assert source_pair(r)==(request['source']['code_sha256'],request['source']['image_sha256']);category='preserved_qualified_artifact';detail=dict(metadata_file=r['metadata_file'],metadata_sha256=r['metadata_sha256'])
  elif identifier in prior:category='preserved_same_core_prior_attempt';detail=dict(evidence_kind=prior[identifier]['evidence_kind'],normal_reexecution_allowed=prior[identifier]['normal_reexecution_allowed']);assert detail['normal_reexecution_allowed']is False
  else:raise AssertionError('unaccounted_applicable_original:'+identifier)
  coverage.append(dict(id=identifier,category=category,**detail))
 overlap=read(P/'mass_live_overlap_snapshot.json');assert not(set(overlap['active'])&set(by_id))
 C=R/'clean/complexity_curation_20261102T054553Z_v1';pointer=read(C/'current.json');ref=pointer['views']['paired_priority_complex'];body=(R/ref['file']).read_bytes();assert sha(body)==ref['sha256'];main_ids={r['id']for r in map(json.loads,body.splitlines())}
 with sqlite3.connect((C/'value_review_registry_v1/status.sqlite').as_uri()+'?mode=ro',uri=True)as d:registry={(x[0],x[1],x[2]):x[3]for x in d.execute('select id,code_sha256,image_sha256,status from reviews')}
 value_counts=collections.Counter();failures=collections.Counter()
 for r in outcomes.values():
  if r['status']=='qualified':
   m=r['manifest'];status='source_id_in_curated_main'if r['id']in main_ids else'held_after_actual_PNG_review'if registry.get((r['id'],m['code_sha256'],m['image_sha256']))=='held'else'unreviewed';assert status!='unreviewed',r['id'];value_counts[status]+=1
  else:
   detail=r.get('detail');failures.update([str(x.get('reason'))for x in detail]if isinstance(detail,list)else[str(detail or r.get('reason'))])
 old={}
 for phase in ['C','mass']:
  values,_=terminal(B/'runs'/('svg_complex_resolved_geometry_cached_unseen_20261102_v11_'+phase))
  for r in values:
   key=source_pair(r)
   if key not in old or r['status']=='qualified':old[key]=r
 matched=[];rescued=[]
 for r in outcomes.values():
  key=source_pair(r)
  if key not in old:continue
  previous=old[key];row=dict(id=r['id'],old_id=previous['id'],source_code_sha256=key[0],source_image_sha256=key[1],old_status=previous['status'],new_status=r['status'],old_reason=previous.get('reason'),old_detail=previous.get('detail'),new_run=r['observed_run']);matched.append(row)
  if previous['status']!='qualified'and r['status']=='qualified':rescued.append(row)
 root=R/'clean/whole_svg_whitespace_completion_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
 for name,values in [('population_coverage.jsonl',coverage),('matched_previous_source_outcomes.jsonl',matched),('previous_failures_now_qualified.jsonl',rescued),('current_terminal_outcomes.jsonl',list(outcomes.values()))]:
  (root/name).write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in values))
 report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),applicable_population=len(population),population_classification=dict(collections.Counter(r['category']for r in coverage)),unaccounted_applicable_originals=0,phases=phases,validation_baseline=baseline_proof,validation_gate=asset(P/'release_gate.json'),all_phase_originals_disjoint=True,source_id_and_both_original_hashes_preserved=True,normal_reexecution_of_prior_events=False,current_round_qualified=sum(r['status']=='qualified'for r in outcomes.values()),current_round_qualified_value_status=dict(value_counts),current_failure_details=dict(failures),same_source_pair_comparisons=len(matched),previous_failures_now_qualified=len(rescued),comparison_scope='Exact original source-code and original-reference image SHA256; historical qualifications are preserved rather than reexecuted. Different populations are not treated as paired trials.',complete_supported_population_only=True,unsupported_source_grammar_and_other_format_queues_retained=True,source_main=ref,files={p.name:asset(p)for p in root.iterdir()},producer=asset(Path(__file__)),new_normal_calls=0,new_QA_calls=0,new_model_calls=0,whole_goal_completion_claimed=False)
 out=root/'summary.json';out.write_text(json.dumps(report,indent=2)+'\n')
 for p in root.iterdir():p.chmod(0o444)
 print(json.dumps(dict(root=str(root),summary=asset(out),applicable_population=len(population),population_classification=report['population_classification'],current_round_qualified=report['current_round_qualified'],qualified_value_status=dict(value_counts),previous_failures_now_qualified=len(rescued),same_source_pair_comparisons=len(matched),unaccounted_applicable_originals=0,goal_complete=False)))
if __name__=='__main__':main()
