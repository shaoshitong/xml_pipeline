"""Curate existing author-native research diagrams without changing QA grades.

Use original editable graph topology, labels and groups. No image/path/glyph
fragment count can stand in for connected logical nodes. This is source
selection, not a new conversion or an independent unseen validation.
"""
from pathlib import Path
import collections,datetime,hashlib,json,re,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def main():
    from priority_source_complexity_filter_v1 import native,classify
    pointer=R/'clean/research_pairs_catalog/current.json';catalog=json.loads(pointer.read_text());index=R/catalog['index']['file'];data=index.read_bytes();assert sha(data)==catalog['index']['sha256'];rows=[json.loads(l)for l in data.splitlines()]
    rows=[r for r in rows if 'arxiv_author_native_source_replay'in r['quality_views']];root=R/'clean/complex_arxiv_native_source_curation_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    policy=dict(original_author_native_XML_graph_only=True,source_metric_module=asset(S/'priority_source_complexity_filter_v1.py'),logical_nodes_are_actual_connected_native_vertices=True,drawn_path_or_glyph_fragments_not_logical_nodes=True,source_page_count_must_equal_one=True,quality_profiles_preserved=True,arxiv_source_replay_does_not_imply_original_PDF_fidelity=True,scientific_value_individually_certified=False,all_nonselected_originals_retained=True,new_conversions=0,new_QA=0,new_models=0)
    (root/'policy.json').write_text(json.dumps(policy,indent=2));audit=[];selected=[];counts=collections.Counter()
    for row in rows:
        result=dict(id=row['id'],code_sha256=row['code_sha256'],image_sha256=row['image_sha256'],quality_views=row['quality_views'],source_records=row['source_records'])
        try:
            p=(R/row['code_file']).resolve(strict=True);assert p.is_relative_to(R/'clean');b=p.read_bytes();assert sha(b)==row['code_sha256'];f=native(b.decode('utf-8-sig'));status,reasons=classify(f,'drawio',{})
            if f['native_pages']!=1:status='structure_review';reasons=['multi_page_source_requires_explicit_selected_page_proof']
            if status=='complex_candidate':
                # The existing general classifier has image-composite rules.
                # This particular deliverable requires a complex native graph.
                n=f['source_backed_logical_nodes'];e=f['connected_edges'];c=f['label_characters'];g=f['native_connected_groups']
                graph=(n>=20 and e>=15 and c>=200 and not f['directed_chain_only'])or(n>=30 and c>=200)or(n>=12 and e>=12 and g>=2 and c>=250)
                if not graph:status='structure_review';reasons=['rich_native_graph_required_for_complex_arxiv_framework_view']
            result.update(status=status,reasons=reasons,features=f)
            if status=='complex_candidate':selected.append(row)
        except Exception as e:result.update(status='source_structure_error',reason=type(e).__name__+':'+str(e))
        counts[result['status']]+=1;audit.append(result)
    for name,values in [('source_audit.jsonl',audit),('complex_native_graph_candidates.jsonl',selected)]:
        (root/name).write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in values))
    proof=dict(root=str(root),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),input_pairs=len(rows),selected=len(selected),counts=dict(counts),selected_original_PDF_visual=sum('arxiv_registered_original_PDF_visual_v2'in r['quality_views']for r in selected),source_catalogue_index=catalog['index'],producer=asset(Path(__file__)),source_rule_only=True,scientific_value_individually_certified=False,strict_full8_main_changed=False,actual_native_PNG_spot_review_pending=True,new_conversions=0,new_QA=0,model_calls=0,goal_complete=False,files={p.name:asset(p)for p in root.iterdir()})
    (root/'summary.json').write_text(json.dumps(proof,indent=2))
    for p in root.iterdir():p.chmod(0o444)
    print(json.dumps(proof))
if __name__=='__main__':main()
