"""Publish a requirement-by-requirement census without inferring completion."""
from pathlib import Path
import collections,datetime,hashlib,json,uuid,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/complexity_curation_20261102T054553Z_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def read(p):return json.loads(p.read_bytes())
def rows(p):return[json.loads(x)for x in p.read_bytes().splitlines()if x]
def program_status(name):
 p=R/'release/compiler_iterations/programs'/name;s=read(p/'state.json');o=read(p/'owner.json');q=Path('/proc',str(o['pid']),'stat');f=q.read_text().rsplit(') ',1)[1].split()if q.exists()else None
 out=dict(run=name,stage=s.get('stage'),owner=dict(pid=o['pid'],start_ticks=o['start_ticks'],live=bool(f and f[0]!='Z'and int(f[19])==o['start_ticks'])),infrastructure_stop=read(p/'infrastructure_stop.json')if(p/'infrastructure_stop.json').exists()else None)
 for phase in ['B','C','mass']:
  q=R/'release/compiler_iterations/runs'/(name+'_'+phase)/'status.sqlite'
  if q.exists():
   with sqlite3.connect(q.as_uri()+'?mode=ro',uri=True)as d:out[phase]=dict(counts=dict(d.execute('select status,count(*)from samples group by status')),infrastructure_errors=sum(json.loads(r[0]).get('infrastructure_failure')is True for r in d.execute('select result from samples where result is not null')))
 if(p/'release_gate.json').exists():
  g=read(p/'release_gate.json');out['release_gate']=dict(units=g['units'],infrastructure_errors=g['infrastructure_errors'],controls_passed=g['controls_passed'],reference=asset(p/'release_gate.json'))
 q=p/'foreign_pending_observation.json'
 if q.exists():out['verified_foreign_pending_originals']=len(read(q)['pending_ids'])
 return out

def disjoint_status(name='svg_source_whitespace_disjoint_20261103_v1_mass'):
 b=R/'release/compiler_iterations/disjoint_batches'/name;run=R/'release/compiler_iterations/runs'/name;launch=read(b/'launch.json');plan=read(b/'plan.json');q=Path('/proc',str(launch['pid']),'stat');fields=q.read_text().rsplit(') ',1)[1].split()if q.exists()else None
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:
  counts=dict(d.execute('select status,count(*)from samples group by status'));results=[json.loads(r[0])for r in d.execute('select result from samples where result is not null')]
 assert sum(counts.values())==launch['targets']==plan['targets']
 return dict(run=name,state=read(b/'state.json'),counts=counts,targets=launch['targets'],infrastructure_errors=sum(r.get('infrastructure_failure')is True for r in results),owner=dict(pid=launch['pid'],birth=launch['birth_ticks'],live=bool(fields and fields[0]!='Z'and int(fields[19])==int(launch['birth_ticks']))),summary=read(b/'summary.json')if(b/'summary.json').exists()else None,failure=read(b/'failure.json')if(b/'failure.json').exists()else None,launch=asset(b/'launch.json'),approved_plan=asset(b/'plan.json'),parent_full_catchup_unchanged=launch['parent_full_catchup_unchanged'])

def main():
 catalog=read(R/'clean/research_pairs_catalog/current.json')
 for key in ['index','summary','validation']:assert sha((R/catalog[key]['file']).read_bytes())==catalog[key]['sha256']
 pointer=read(C/'current.json');ref=pointer['views']['paired_priority_complex'];assert sha((R/ref['file']).read_bytes())==ref['sha256'];main=rows(R/ref['file']);main_counts=dict(collections.Counter(r['source']for r in main));assert len(main)==ref['rows']
 priority=C/'priority_sources';receipt=read(priority/'completion_receipt.json');assert sha((priority/'summary.json').read_bytes())==receipt['files']['summary.json']['sha256'];source_summary=read(priority/'summary.json')
 sci=R/'clean/priority_scidiagram_source_preflight_v1/38f4921046864d83aef91ce40f9d4f0f/summary.json';s=read(sci);assert s['finished']and s['completed']==46
 dwt=R/'clean/priority_dwt_native_complete_export_20261102_v1/dwt_native_source_failure_disposition_v1.json';d=read(dwt)
 tikz=R/'clean/priority_datikz_source_readiness_v1/c9f7944137cc43559b6062f203469aea/source_readiness.jsonl';t=rows(tikz);assert len(t)==39 and all(r['source_bytes_hash_verified']for r in t)
 chart=R/'clean/matplotlib_plot_pipeline_20261102_v1/vector_backend_rollout_v6';cs=read(chart/'summary.json');assert cs['finished']and cs['qualified_pairs']==1875
 chart_counts=collections.defaultdict(collections.Counter)
 for profile,ref in cs['profiles'].items():
  p=Path(ref['file']);assert sha(p.read_bytes())==ref['sha256']
  for row in rows(p):chart_counts[row['source']][profile]+=1
 programs={name:program_status(name)for name in ['svg_complex_resolved_geometry_cached_unseen_20261102_v11','svg_complex_source_whitespace_cached_unseen_20261103_v12']}
 current_pool=R/'release/compiler_iterations/source_pools/svg_complex_source_whitespace_cached_unseen_20261103_v12/summary.json';pool=read(current_pool)
 sources={
  'SciDiagramRevision':dict(source='yashengsun--SciDiagramRevision',complex_targets=46,strict_main_pairs=main_counts.get('yashengsun--SciDiagramRevision',0),source_preflight=s['counts'],evidence=asset(sci),remaining='Original-reference/font mismatch and unsupported SVG source effects/panels; no qualification claimed.'),
  'RAP':dict(source='VincentHancoder--RAP',complex_source_candidates=source_summary['by_source']['VincentHancoder--RAP']['complex_candidate'],strict_main_pairs=main_counts.get('VincentHancoder--RAP',0),reference_profile='Released/reconstructed HTML templates; supplied original poster bitmaps are auxiliary.',remaining='Remaining source candidates and indeterminate layouts stay in the original source queue.'),
  'DwT_drawio':dict(source='miracle10--DwT_drawio',complex_targets=d['scope_rows'],strict_main_pairs=main_counts.get('miracle10--DwT_drawio',0),source_provenance=d['provenance_counts'],visual_disposition=d['visual_disposition_counts'],evidence=asset(dwt),remaining='Provider-unverified reconstructed XML; three measured original-reference mismatches, other items undetermined.'),
  'VFIG':dict(source='QijiaHe--VFIG-Data',strict_main_pairs=main_counts.get('QijiaHe--VFIG-Data',0),retained_complex_source_targets=pool['counters']['all_complex_raw_supported'],source_admitted=pool['counters']['supported_remaining_population'],source_pool=asset(current_pool),programs=programs,remaining='Current fixed v11 batch continues; validated v24 waits for birth-verified foreign pending work, then processes the complete applicable population. All source errors and unsupported originals remain retained.'),
  'DaTikZ':dict(source_aliases=['nllg--DaTikZ-V4','nllg--datikz','nllg--datikz-v3'],complex_targets=39,baseline_original_sources_compiled=sum(r['baseline_original_source_compiled']for r in t),readiness=dict(collections.Counter(r['readiness_status']for r in t)),strict_main_pairs=sum(v for k,v in main_counts.items()if k.lower().startswith('nllg--datikz')),evidence=asset(tikz),remaining='Node/text-only terminal ownership and exact closed-Bezier marker handling now emit an editable candidate. It remains unqualified: original-PDF/source-SVG SSIM 0.88937 is below the unchanged 0.90 gate.'),
 }
 for label,key in [('ChartMimic','ChartMimic--ChartMimic'),('Chart2Code','CSU-JPG--Chart2Code')]:sources[label]=dict(source=key,complex_source_candidates=source_summary['by_source'][key]['complex_candidate'],latest_vector_rollout_by_reference_profile=dict(chart_counts[key]),strict_full8_main_pairs=main_counts.get(key,0),remaining='Preserve declared reference profiles; actual source-panel/scientific-context curation is separate from technical conversion acceptance.')
 requests=[dict(number=1,status='in_progress',evidence='seven_sources',reason='All named sources are accounted for; several have unresolved reference/provenance/native-conversion failures.'),dict(number=2,status='screened_with_remaining_structure_review',source_index_rows=receipt['index_unique_rows'],original_complex_candidates=receipt['status_counts']['complex_candidate'],original_structure_review=receipt['status_counts']['structure_review'],source_screen_receipt=asset(priority/'completion_receipt.json')),dict(number=3,status='in_progress',reason='Resolved geometry and source whitespace repairs passed independent controls and fixed unseen B/C gates. The whole-population programs remain active; see source-bound program snapshots.'),dict(number=4,status='fixed_programs_installed_and_running',reason='Failures retained, once-only dispatch and automatic validation-to-bulk gate; this is not proof that current batch has finished.'),dict(number=5,status='delivered_current_immutable_snapshots',catalog_pointer=asset(R/'clean/research_pairs_catalog/current.json'),strict_main=ref),dict(number=6,status='arxiv_recovery_and_reference_audits_in_progress',evidence_views={k:v for k,v in catalog['unique_pairs_by_evidence_view'].items()if k.startswith('arxiv')},original_PDF_and_source_replay_profiles_are_not_equivalent=True),dict(number=7,status='improved_with_remaining_runtime_costs',reason='Verified-manifest/stat reuse avoids rescanning unchanged old image payloads; source/native/QA costs remain measured by their fixed programs.')]
 curated=read(R/'clean/complex_scientific_charts/current.json');assert sha((R/curated['curated_pairs']['file']).read_bytes())==curated['curated_pairs']['sha256'];curated_rows=rows(R/curated['curated_pairs']['file']);curated_counts=collections.Counter(r['source']for r in curated_rows)
 for label in ['ChartMimic','Chart2Code']:sources[label]['actual_source_complexity_curated_pairs']=curated_counts[sources[label]['source']]
 root=R/'clean/complex_research_delivery_audit_v6'/uuid.uuid4().hex;root.mkdir(parents=True)
 delivery=read(R/'clean/curated_complex_research_delivery/current.json');assert sha((R/delivery['pairs']['file']).read_bytes())==delivery['pairs']['sha256'];arxiv_curated=read(R/'clean/complex_arxiv_native/current.json');assert sha((R/arxiv_curated['curated_pairs']['file']).read_bytes())==arxiv_curated['curated_pairs']['sha256']
 baseline_screen=C/'published_v1/summary.json';baseline=read(baseline_screen);assert baseline['frozen_recorded_qualified_rows_screened']==15118
 disjoint=disjoint_status();disjoint_masses={b.name:disjoint_status(b.name)for b in sorted((R/'release/compiler_iterations/disjoint_batches').glob('svg_source_whitespace_disjoint_20261103_v*_mass'))if(b/'launch.json').exists()}
 report=dict(existing_qualified_complexity_screen=dict(recorded_qualified_rows=baseline['frozen_recorded_qualified_rows_screened'],baseline_publication=asset(baseline_screen),exact_frozen_input_sha256=baseline['frozen_qualified_sha256'],existing_qualifications_modified=baseline['existing_indices_and_qualifications_modified']),approved_disjoint_mass=disjoint,all_approved_disjoint_masses=disjoint_masses,curated_research_delivery=delivery,complex_arxiv_curation=arxiv_curated,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),strict_main_rows=len(main),strict_main_by_source=main_counts,unified_catalog=catalog,seven_sources=sources,complex_scientific_chart_curation=curated,requirements=requests,producer=asset(Path(__file__)),source_candidates_are_not_qualified_pairs=True,reference_profiles_are_not_interchangeable=True,goal_complete=False,new_conversions=0,new_QA=0,model_calls=0)
 p=root/'audit.json';p.write_text(json.dumps(report,indent=2)+'\n');p.chmod(0o444);current=root.parent/'current.json';temp=current.with_suffix('.tmp');temp.write_text(json.dumps(dict(audit=asset(p),goal_complete=False),indent=2)+'\n');temp.replace(current);print(json.dumps(dict(root=str(root),audit=asset(p),strict_main_by_source=main_counts,latest_chart_by_source={k:dict(v)for k,v in chart_counts.items()},curated_delivery=delivery,programs=programs,approved_disjoint_mass=disjoint,all_approved_disjoint_masses=disjoint_masses,existing_qualified_rows_screened=baseline['frozen_recorded_qualified_rows_screened'],goal_complete=False)))
if __name__=='__main__':main()
