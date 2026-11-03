"""Publish native graph/composite curation with explicit fidelity grades."""
from pathlib import Path
import collections,hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/complex_arxiv_native_source_curation_v2/54a34d8a731f4252b7e69d1332d85796';OLD=R/'clean/complex_arxiv_native_source_curation_v1/dc240e85ea4a460a9d3b83e8897b52ab'
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def rows(p):return[json.loads(l)for l in p.read_text().splitlines()if l]
def main():
    summary=json.loads((P/'summary.json').read_text());assert summary['selected']==263
    for ref in summary['files'].values():assert sha((R/ref['file']).read_bytes())==ref['sha256']
    candidates=rows(P/'complex_native_research_candidates.jsonl');by={r['id']:r for r in candidates};prior=rows(OLD/'complex_native_graph_candidates.jsonl');assert len(prior)==99 and {r['id']for r in prior}<=by.keys()
    old_spots=json.loads((OLD/'actual_PNG_spot_selection.json').read_text());new_spots=rows(P/'reviewed_pairs.jsonl');assert len(old_spots)==10 and len(new_spots)==4
    for r in old_spots+new_spots:
        pair=r['pair'];assert sha((R/pair['code_file']).read_bytes())==pair['code_sha256'];assert sha((R/pair['image_file']).read_bytes())==pair['image_sha256']
    held_id='b53184a947a1975d83682b2295b7f85945eeffc672549f680260d5afb748fc65';assert held_id in by and any(r['pair']['id']==held_id for r in new_spots)
    held=dict(id=held_id,status='held_source_visual_review',reason='Actual native PNG has an unexplained large rectangular cover inside the circular figure. Preserve source-replay qualification but hold from curated research delivery pending original/source layout review.',actual_native_PNG_inspected=True)
    selected=[r for r in candidates if r['id']!=held_id]
    manifests={};checked=0
    for pair in selected:
        references=[r for r in pair['source_records']if r['input_id'].startswith('arxiv_author_native')];assert references
        for ref in references:
            if ref['manifest']not in manifests:manifests[ref['manifest']]=rows(R/ref['manifest'])
            original=manifests[ref['manifest']][ref['line']-1]
            assert original['id']==ref['source_id']and original['code_sha256']==pair['code_sha256']
            assert original.get('whole_figure_wrapper')is False and original.get('standalone_image_assets_complete')is True
            checked+=1
    target=P/'curated_pairs_by_reference_profile.jsonl';assert not target.exists();target.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in selected));target.chmod(0o444)
    proof=dict(rows=len(selected),curation_views=dict(collections.Counter(r['curation_view']for r in selected)),original_PDF_visual_rows=sum('arxiv_registered_original_PDF_visual_v2'in r['quality_views']for r in selected),source_replay_only_rows=sum('arxiv_registered_original_PDF_visual_v2'not in r['quality_views']for r in selected),source_structure_rule_with_actual_PNG_spot_checks=True,actual_native_PNG_spots=[dict(id=r['pair']['id'],paper=r['paper'],current_rule_selected=r['pair']['id']in by,held_from_delivery=r['pair']['id']==held_id)for r in old_spots+new_spots],actual_PNGs_inspected=True,prior_graph_only_selection_gap_corrected=True,existing_99_graphs_retained=True,whole_figure_wrapper_and_asset_closure_upstream_records_checked=checked,held=[held],curated_pairs=asset(target),source_summary=asset(P/'summary.json'),source_policy=asset(P/'policy.json'),producer=asset(Path(__file__)),scientific_value_individually_certified=False,original_PDF_and_source_replay_grades_not_interchangeable=True,standalone_font_portability_not_claimed=True,strict_full8_main_unchanged=True,new_conversions=0,new_QA=0,new_model_calls=0,goal_complete=False)
    f=P/'curation_acceptance.json';f.write_text(json.dumps(proof,indent=2));f.chmod(0o444)
    parent=R/'clean/complex_arxiv_native';parent.mkdir(exist_ok=True);pointer=dict(rows=len(selected),curated_pairs=asset(target),acceptance=asset(f),curation_views=proof['curation_views'],original_PDF_visual_rows=proof['original_PDF_visual_rows'],source_replay_only_rows=proof['source_replay_only_rows'],strict_full8_main_unchanged=True,goal_complete=False);tmp=parent/'current.tmp';tmp.write_text(json.dumps(pointer,indent=2));tmp.replace(parent/'current.json');print(json.dumps(pointer))
if __name__=='__main__':main()
