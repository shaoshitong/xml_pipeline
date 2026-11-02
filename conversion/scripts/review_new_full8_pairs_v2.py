"""Keep conversion QA and scientific-value selection as explicit evidence."""
from pathlib import Path
import collections,datetime,hashlib,json,os,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
C=R/'clean/complexity_curation_20261102T054553Z_v1'
from priority_svg_dense_source_screen_v2 import features,select
from priority_source_complexity_filter_v1 import native,classify


def sha(data):return hashlib.sha256(data).hexdigest()
def raw(value):return(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def asset(path):return dict(file=str(path.relative_to(R)),sha256=sha(path.read_bytes()),bytes=path.stat().st_size)


def main():
    run=R/'release/compiler_iterations/runs/svg_complex_actual_shadow_unseen100_20261102_v6_C'
    with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        results=[json.loads(row[0])for row in db.execute("select result from samples where status='qualified'")]
    for result in results:result['new_core']=True
    ids={row['id']for row in results};index={};scope=collections.Counter();target_ids=set()
    for line in(C/'priority_sources/index.jsonl').open():
        row=json.loads(line)
        if row['source_format']=='svg':
            scope[row['status']]+=1
            if row['status']=='complex_candidate':target_ids.add(row['id'])
        if row['id']in ids:index[row['id']]=row
    dense_path=R/'clean/priority_svg_dense_source_screen_v2/new_complex_candidates.jsonl'
    for line in dense_path.open():target_ids.add(json.loads(line)['id'])
    visual={
      '2e27fda9f64c46b92c73fa7936e7d727b2b56b93419da42d5d0e8ab0ba222f2e':('hold_label_occlusion','Actual native PNG: left layer labels are partly covered by layer boxes in the entity-linking architecture; hold until source-completeness review.'),
      'fba9044f5e3936d99b8d96c36ea8badbb761b2a89fd956f8fe3208d6cb2e8b3c':('hold_label_occlusion','Actual native PNG: learning annotations overlap the upper source branch boxes; hold for source-completeness review.'),
      '7755f4bf41d00c231b1300069f3979345643c6c1425686b8ce1f4d5429dd56e6':('simple_repetitive_network','Actual native PNG: generic three-layer fully-connected MLP with repeated nodes and few distinct research labels; connectivity alone does not establish content complexity.'),
      '0dc3f8bb2a134a79aba055dc8cc6686f7d097b187bd08267a5bdc4f8d8bd633e':('value_review_pending','Actual native PNG: two vector-chunk embedding/ansatz/measurement panels. Source-use conversion repair is verified; strict complex-set selection remains pending.')}
    rows=[]
    for result in results:
        pair=result['manifest']
        for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
            path=(R/pair[field]).resolve(strict=True);assert path.is_relative_to((R/'clean').resolve());assert sha(path.read_bytes())==pair[digest]
        record=json.loads((R/pair['metadata_file']).read_text());qa_path=Path(result['quality_report']);qa_path=qa_path if qa_path.is_absolute()else R/qa_path;report=json.loads(qa_path.read_text())
        if result.get('new_core'):
            import compiler_svg_general_guard_v8 as compiler
            import svg_analytic_iteration_controls_v4 as quality
        else:
            import compiler_svg_general_guard_v4 as compiler
            import svg_analytic_iteration_controls_v3 as quality
        quality.full_quality(report,record,compiler.configuration(),asset(qa_path.parent/'native_render.json'))
        blob=(R/pair['original_source_code']).read_bytes();dense=features(blob);native_features=native((R/pair['code_file']).read_text());status,native_rules=classify(native_features,'drawio',{})
        source_status=index.get(pair['id'],{}).get('status');decision,note=visual.get(pair['id'],('simple_source_deprioritized'if source_status=='simple_deprioritized'else'value_review_pending','No direct visual approval recorded; preserved outside the strict complex main.'))
        rows.append(dict(id=pair['id'],pair=pair,full_eight_quality_reverified=True,quality_report=asset(qa_path),source_screen_status=source_status,dense_source_features=dense,dense_source_rules=select(dense),native_structure=native_features,native_complexity_status=status,native_rules=native_rules,visual_value_status=decision,visual_note=note,approved_for_strict_main=False))
    output=C/'value_reviews'/('new_full8_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));output.mkdir(parents=True)
    (output/'reviewed_pairs.jsonl').write_bytes(b''.join((json.dumps(row,sort_keys=True)+'\n').encode()for row in rows))
    summary=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),full8_pairs=len(rows),strict_main_additions=0,value_states=dict(collections.Counter(r['visual_value_status']for r in rows)),priority_source_index_svg_states=dict(scope),frozen_complex_or_dense_source_targets=len(target_ids),qualified_pair_ids_in_frozen_source_targets=sum(r['id']in target_ids for r in rows),not_all_full8_pairs_are_complex=True,new_normal_conversions=0,new_QA_calls=0,new_model_calls=0,main_pointer_changed=False,producer=asset(Path(__file__)),pairs=asset(output/'reviewed_pairs.jsonl'))
    (output/'summary.json').write_bytes(raw(summary))
    for path in output.iterdir():path.chmod(0o444)
    temporary=C/('latest_value_review.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw(dict(summary=asset(output/'summary.json'),pairs=asset(output/'reviewed_pairs.jsonl'))));os.replace(temporary,C/'latest_value_review.json')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
