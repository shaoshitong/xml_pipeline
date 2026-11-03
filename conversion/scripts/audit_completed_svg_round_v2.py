"""Verify terminal fixed-batch execution and account for each qualified value review."""
from pathlib import Path
import argparse,collections,datetime,hashlib,json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def read(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def main():
 import fixed_batch_pipeline_v1 as base
 p=argparse.ArgumentParser();p.add_argument('--program',choices=['svg_complex_resolved_geometry_cached_unseen_20261102_v11','svg_complex_source_whitespace_cached_unseen_20261103_v12']);p.add_argument('--disjoint-run',choices=['svg_source_whitespace_disjoint_20261103_v1_mass','svg_source_whitespace_disjoint_20261103_v2_mass']);a=p.parse_args();assert bool(a.program)!=bool(a.disjoint_run);B=R/'release/compiler_iterations';P=B/'disjoint_batches'/a.disjoint_run if a.disjoint_run else B/'programs'/a.program;run=B/'runs'/(a.disjoint_run or a.program+'_mass')
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:
  meta=base.metadata(d);samples=d.execute('select id,status,attempts,result from samples order by seq').fetchall()
 counts=collections.Counter(r[1]for r in samples);assert meta['finished']is True and set(counts)<={'qualified','abandoned'};assert all(r[2]==1 for r in samples);assert len({r[0]for r in samples})==len(samples)
 assert sha((run/'targets.jsonl').read_bytes())==meta['input_sha256'];outcomes=[json.loads(r[3])for r in samples];assert all(r.get('case_cleanup_complete')is True and r.get('infrastructure_failure')is not True for r in outcomes)
 final=read(run/'final_asset_audit.json');assert final['late_asset_failures']==0 and final['qualified_payloads_verified']==counts['qualified'];state=read(P/'state.json');assert state['stage']==('disjoint_mass_finished_parent_catchup_retained'if a.disjoint_run else'round_complete_next_repair_required');summary=read(P/'summary.json');assert(summary.get('finished')is True and summary['targets']==len(samples))if a.disjoint_run else summary['mass']==str(run)
 C=R/'clean/complexity_curation_20261102T054553Z_v1';pointer=read(C/'current.json');ref=pointer['views']['paired_priority_complex'];b=(R/ref['file']).read_bytes();assert sha(b)==ref['sha256'];main_ids={r['id']for r in map(json.loads,b.splitlines())}
 with sqlite3.connect((C/'value_review_registry_v1/status.sqlite').as_uri()+'?mode=ro',uri=True)as d:registry={(r[0],r[1],r[2]):dict(status=r[3],review_root=r[4])for r in d.execute('select id,code_sha256,image_sha256,status,review_root from reviews')}
 coverage=[];failures=collections.Counter()
 for row in outcomes:
  if row['status']!='qualified':
   detail=row.get('detail');reasons=[str(x.get('reason'))for x in detail]if isinstance(detail,list)else[str(detail or row.get('reason'))];failures.update(reasons);continue
  m=row['manifest'];entry=registry.get((row['id'],m['code_sha256'],m['image_sha256']));status='source_id_already_in_curated_main'if row['id']in main_ids else'held_after_actual_PNG_review'if entry and entry['status']=='held'else'unaccounted';assert status!='unaccounted',row['id'];coverage.append(dict(id=row['id'],code_sha256=m['code_sha256'],image_sha256=m['image_sha256'],status=status,review=entry))
 root=R/'clean/completed_svg_round_audits_v2'/uuid.uuid4().hex;root.mkdir(parents=True);report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),program=a.program,disjoint_run=a.disjoint_run,run=str(run),counts=dict(counts),targets=len(samples),all_dispatch_attempts_exactly_one=True,all_case_cleanup_complete=True,infrastructure_errors=0,qualified_asset_final_audit=asset(run/'final_asset_audit.json'),qualified_value_review_status=dict(collections.Counter(r['status']for r in coverage)),qualified_value_review_coverage=coverage,failure_details=dict(failures),source_main=ref,program_summary=asset(P/'summary.json'),next_repair=asset(P/'next_repair.json')if(P/'next_repair.json').exists()else None,execution_state=state,producer=asset(Path(__file__)),new_normal_calls=0,new_QA_calls=0,goal_complete=False)
 out=root/'audit.json';out.write_text(json.dumps(report,indent=2)+'\n');out.chmod(0o444);print(json.dumps(dict(root=str(root),audit=asset(out),counts=dict(counts),qualified_value_review_status=report['qualified_value_review_status'],top_failure_details=failures.most_common(12),infrastructure_errors=0,goal_complete=False)))
if __name__=='__main__':main()
