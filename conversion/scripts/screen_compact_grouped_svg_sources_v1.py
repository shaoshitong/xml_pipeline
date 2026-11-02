"""Source-only expansion for compact labels and genuinely grouped drawings.

Retains the previous target selection. This additional rule uses distinct
visible-by-static-attributes labels and non-path primitives, never QA outcomes.
It makes no claim of scientific merit or successful native conversion.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,datetime,hashlib,json,os,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
P=R/'release/compiler_iterations/source_pools/svg_actual_shadow_unseen100_20261102_v4'
C=R/'release/compiler_iterations/source_pools/svg_complex_background_rotation_cached_unseen_20261102_v9'
SEED='compact-grouped-source-observation-v1-20261102'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def rows(p):
    with p.open()as stream:return[json.loads(l)for l in stream if l.strip()]
def select(f):
    if f['stylesheet_visibility_requires_render']:return []
    n=f['distinct_labels'];chars=f['label_characters'];g=f['source_label_groups'];shapes=f['source_shape_units'];panels=f['panel_label_clues']
    rules=[]
    if n>=24 and chars>=80 and g>=4 and shapes>=40:rules.append('compact_distinct_labels_with_multiple_source_groups_and_primitives')
    if panels>=3 and n>=18 and chars>=80 and g>=3 and shapes>=40:rules.append('compact_labeled_multi_panel_source_layout')
    return rules
def controls():
    from priority_svg_dense_source_screen_v2 import features
    good=('<svg>'+''.join('<g>'+''.join('<rect/><text>x_'+str(6*g+i)+'</text>'for i in range(6))+'</g>'for g in range(8))+'</svg>').encode()
    tests=dict(compact_grouped_labels_selected=bool(select(features(good))))
    for name,doc in [('path_fragment_spam','<svg>'+('<path d="M0 0L1 1"/>'*1000)+'</svg>'),('repeated_labels','<svg>'+('<g><rect/><text>x</text><text>x</text></g>'*100)+'</svg>'),('hidden_drawing','<svg><g display="none">'+good.decode()+'</g></svg>'),('definitions_only','<svg><defs>'+good.decode()+'</defs></svg>')]:tests[name+'_not_promoted']=not select(features(doc.encode()))
    assert all(tests.values()),tests;return tests
def inspect(item):
    request,row,locator=item
    try:
        from priority_svg_dense_source_screen_v2 import features
        p=(R/locator).resolve(strict=True);assert p.is_relative_to(R);data=p.read_bytes();assert sha(data)==request['source']['code_sha256']==row['source_code_sha256_observed']
        f=features(data);rules=select(f)
        return dict(id=request['id'],source=request['source']['source'],source_code_sha256=request['source']['code_sha256'],source_image_sha256=request['source']['image_sha256'],source_code=locator,features=f,rules=rules,selected=bool(rules),prior_status=row['status'],source_hash_verified=True,code_bytes_read=len(data),candidate_or_QA_or_model_calls=0)
    except Exception as error:return dict(id=request['id'],selected=False,error=type(error).__name__+':'+str(error),candidate_or_QA_or_model_calls=0)
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();root=a.work.resolve();assert root.is_relative_to(R/'clean/priority_svg_compact_source_screen_v1');root.mkdir(parents=True,exist_ok=False)
    test=controls();full=rows(P/'supported_population.jsonl');previous={r['id']for r in rows(C/'all_complex_raw_supported_population.jsonl')};index=R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources/index.jsonl';by={r['id']:r for r in rows(index)};tasks=[];deferred=collections.Counter()
    with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        for request in full:
            if request['id']in previous:continue
            row=by.get(request['id'])
            if not row:deferred['outside_primary_priority_index']+=1;continue
            if row.get('source_hash_matches_manifest')is not True or row.get('read_status')!='read_code_only' or row.get('provenance',{}).get('structurally_complete')is False:deferred['source_hash_or_completeness_unresolved']+=1;continue
            # Cheap original-source metadata prefilter, not a scientific-value
            # decision. Recompute the final rule from exact source bytes below.
            f=row.get('features',{})
            if f.get('distinct_owner_labels',0)<18 or f.get('label_characters',0)<80 or f.get('collapsed_drawing_objects',0)<40:deferred['below_compact_prefilter']+=1;continue
            hit=db.execute('select input_manifest from jobs where id=?',(request['id'],)).fetchone();assert hit
            manifest=json.loads(hit[0]);tasks.append((request,row,manifest['source_code']))
    policy=dict(schema='compact_grouped_source_selection_v1',seed=SEED,source_only=True,additional_selection_preserves_all_prior_targets=True,requirements=dict(grouped=dict(distinct_labels=24,label_characters=80,source_label_groups=4,non_path_shape_units=40),multi_panel=dict(panel_clues=3,distinct_labels=18,label_characters=80,source_label_groups=3,non_path_shape_units=40)),logical_nodes_not_inferred_from_path_or_glyph_counts=True,scientific_value_and_conversion_not_asserted=True,quality_thresholds_changed=False,source_input_population=asset(P/'supported_population.jsonl'),prior_targets=asset(C/'all_complex_raw_supported_population.jsonl'),priority_index=asset(index),producer=asset(Path(__file__)),feature_extractor=asset(S/'priority_svg_dense_source_screen_v2.py'),controls=test)
    (root/'policy.json').write_bytes(raw(policy));(root/'owner.json').write_bytes(raw(dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19])));started=time.monotonic();selected=[];results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool,(root/'screened.jsonl').open('w')as stream:
        for result in pool.map(inspect,tasks):
            results.append(result);stream.write(json.dumps(result,sort_keys=True)+'\n')
            if result['selected']:selected.append(result)
            if len(results)%32==0:
                stream.flush();(root/'progress.json').write_bytes(raw(dict(completed=len(results),total=len(tasks),selected=len(selected),source_bytes_read=sum(r.get('code_bytes_read',0)for r in results),elapsed_seconds=time.monotonic()-started)))
    selected.sort(key=lambda r:r['id']);(root/'selected.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in selected));sample=sorted(selected,key=lambda r:sha((SEED+r['id']).encode()))[:8];(root/'source_sample.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in sample))
    out=dict(root=str(root),finished=True,full_static_supported=10104,prior_complex_targets=len(previous),inspected=len(results),additional_source_candidates=len(selected),errors=sum('error'in r for r in results),deferred=dict(deferred),by_source=dict(collections.Counter(r['source']for r in selected)),elapsed_seconds=time.monotonic()-started,files={n:asset(root/n)for n in ['policy.json','screened.jsonl','selected.jsonl','source_sample.jsonl']},normal_calls=0,QA_calls=0,model_calls=0,goal_complete=False)
    (root/'summary.json').write_bytes(raw(out))
    for path in root.iterdir():path.chmod(0o444)
    print(json.dumps(out))
if __name__=='__main__':main()
